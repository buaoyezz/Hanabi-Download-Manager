import asyncio
import json
import logging
import threading
import traceback
import re
import base64
import hashlib
import socket
import sys
import os
import time
from typing import Dict, List, Optional, Callable

# 添加父目录到sys.path以导入客户端模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# 导入版本管理器
try:
    from client.version.version_manager import VersionManager
    version_manager = VersionManager.get_instance()
except ImportError:
    # 创建一个简单的版本管理类作为备用
    class VersionManagerFallback:
        def get_client_version(self):
            return "1.0.7"  # 默认版本
        def get_extension_version(self):
            return "1.0.3"  # 默认扩展版本
    version_manager = VersionManagerFallback()
    logging.warning("无法导入版本管理器，使用默认版本")

class BasicTCPServer:
    """简单的TCP服务器，用于在WebSocket服务器不可用时作为备选"""
    
    def __init__(self, host: str = "localhost", port: int = 20971):
        self.host = host
        self.port = port
        self.clients = {}  # 修改为字典，存储writer对象
        self.server = None
        self.server_thread = None
        self.is_running = False
        self._download_handler: Optional[Callable] = None
        self._clients_lock = threading.Lock()  # 添加锁以保护clients字典
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('TCPServer')
    
    def set_download_handler(self, handler: Callable):
        self._download_handler = handler
    
    def has_clients(self):
        """检查是否有客户端连接"""
        with self._clients_lock:
            return len(self.clients) > 0
    
    def _is_websocket_handshake(self, data: bytes) -> tuple:
        """判断是否是WebSocket握手请求"""
        try:
            text = data.decode('utf-8')
            if "GET" in text and "HTTP" in text and "Upgrade: websocket" in text:
                # 提取Sec-WebSocket-Key
                key_match = re.search(r'Sec-WebSocket-Key: (.*)\r\n', text)
                if key_match:
                    return True, key_match.group(1)
                return True, None
            return False, None
        except:
            return False, None
    
    def _generate_websocket_accept(self, key: str) -> str:
        """生成WebSocket握手响应的Accept值"""
        GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        sha1 = hashlib.sha1((key + GUID).encode()).digest()
        return base64.b64encode(sha1).decode()
    
    def _create_websocket_response(self, key: str) -> bytes:
        """创建WebSocket握手响应"""
        accept = self._generate_websocket_accept(key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        return response.encode()
    
    def _decode_websocket_frame(self, data: bytes) -> Optional[str]:
        """解码WebSocket帧"""
        try:
            if len(data) < 6:
                return None
            
            # 检查是否是文本帧
            if (data[0] & 0x0f) != 0x01:  # 0x01表示文本帧
                return None
            
            # 检查是否有掩码
            masked = (data[1] & 0x80) != 0
            if not masked:
                return None
            
            # 获取payload长度
            payload_len = data[1] & 0x7F
            offset = 2
            
            if payload_len == 126:
                payload_len = (data[2] << 8) | data[3]
                offset = 4
            elif payload_len == 127:
                # 不处理超长消息
                return None
            
            # 获取掩码键
            mask = data[offset:offset+4]
            offset += 4
            
            # 应用掩码解码数据
            payload = bytearray()
            for i in range(payload_len):
                if offset + i < len(data):
                    payload.append(data[offset + i] ^ mask[i % 4])
            
            return payload.decode('utf-8')
        except Exception as e:
            self.logger.error(f"解码WebSocket帧出错: {e}")
            return None
    
    def _encode_websocket_frame(self, message: str) -> bytes:
        """编码WebSocket帧"""
        data = message.encode('utf-8')
        length = len(data)
        
        # 创建帧头
        if length <= 125:
            frame = bytearray([0x81, length])  # 0x81表示文本帧
        elif length <= 65535:
            frame = bytearray([0x81, 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            # 支持更大的消息
            frame = bytearray([0x81, 127])
            for i in range(8):
                frame.append((length >> ((7-i)*8)) & 0xFF)
        
        # 添加payload
        frame.extend(data)
        return bytes(frame)
    
    async def _safe_write(self, writer, data):
        """安全地写入数据到客户端，处理可能的连接错误"""
        try:
            writer.write(data)
            await writer.drain()
            return True
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            self.logger.debug(f"连接已重置或关闭: {e}")
            return False
        except Exception as e:
            self.logger.error(f"发送数据时出错: {e}")
            return False
    
    async def handle_client(self, reader, writer):
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        self.logger.info(f"客户端已连接: {addr}")
        client_id = id(writer)
        
        # 使用锁保护添加客户端操作
        with self._clients_lock:
            self.clients[client_id] = {
                "writer": writer, 
                "addr": addr,
                "is_websocket": False,  # 默认为非WebSocket连接
                "last_activity": time.time()  # 记录最后活动时间
            }
        
        # 用于跟踪连接类型
        is_websocket = False
        
        try:
            # 先读取第一个消息，检查是否是WebSocket握手
            try:
                first_data = await reader.read(1024)
                if not first_data:
                    return
            except (ConnectionResetError, ConnectionAbortedError) as e:
                self.logger.debug(f"读取初始数据时客户端断开: {e}")
                return
            
            is_ws_handshake, ws_key = self._is_websocket_handshake(first_data)
            
            if is_ws_handshake and ws_key:
                self.logger.info("检测到WebSocket握手请求，发送握手响应")
                # 发送WebSocket握手响应
                handshake_response = self._create_websocket_response(ws_key)
                if not await self._safe_write(writer, handshake_response):
                    return
                is_websocket = True
                
                # 更新客户端的WebSocket状态
                with self._clients_lock:
                    if client_id in self.clients:
                        self.clients[client_id]["is_websocket"] = True
                
                # 发送版本信息 (WebSocket格式)
                version_info = {
                    "type": "version",
                    "ClientVersion": version_manager.get_client_version(),
                    "LatestExtensionVersion": version_manager.get_extension_version()
                }
                ws_message = self._encode_websocket_frame(json.dumps(version_info))
                if not await self._safe_write(writer, ws_message):
                    return
            else:
                # 按普通TCP处理
                self.logger.info("按普通TCP连接处理")
                
                # 检查是否能解析JSON
                try:
                    message = first_data.decode('utf-8').strip()
                    data = json.loads(message)
                    # 是有效的JSON消息，处理它
                    await self._process_json_message(data, writer)
                except json.JSONDecodeError:
                    # 不是有效的JSON，发送版本信息
                    version_info = {
                        "type": "version",
                        "ClientVersion": version_manager.get_client_version(),
                        "LatestExtensionVersion": version_manager.get_extension_version()
                    }
                    if not await self._safe_write(writer, (json.dumps(version_info) + '\n').encode('utf-8')):
                        return
                except Exception as e:
                    self.logger.error(f"处理首次消息时出错: {e}")
            
            # 持续读取后续消息
            buffer = bytearray()
            while True:
                try:
                    data = await reader.read(4096)
                    if not data:
                        break
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    self.logger.debug(f"读取消息时客户端断开: {e}")
                    break
                except Exception as e:
                    self.logger.error(f"读取消息时发生错误: {e}")
                    break
                
                if is_websocket:
                    # WebSocket处理逻辑
                    buffer.extend(data)
                    
                    # 尝试解码帧
                    message = self._decode_websocket_frame(buffer)
                    if message:
                        buffer.clear()  # 清空缓冲区
                        try:
                            # 解析JSON
                            data = json.loads(message)
                            self.logger.info(f"收到WebSocket消息: {data}")
                            
                            # 处理消息
                            if data.get("type") == "heartbeat":
                                # 响应心跳消息
                                response = {
                                    "type": "heartbeat",
                                    "timestamp": data.get("timestamp")
                                }
                                ws_response = self._encode_websocket_frame(json.dumps(response))
                                if not await self._safe_write(writer, ws_response):
                                    break
                            elif data.get("type") == "download" or (data.get("url") and "type" not in data):
                                # 处理下载请求
                                if "type" not in data:
                                    data["type"] = "download"
                                
                                if self._download_handler:
                                    self._download_handler(data)
                                    response = {
                                        "type": "download_response",
                                        "status": "success",
                                        "message": "下载任务已添加"
                                    }
                                else:
                                    response = {
                                        "type": "download_response",
                                        "status": "error",
                                        "message": "下载处理程序未设置"
                                    }
                                ws_response = self._encode_websocket_frame(json.dumps(response))
                                if not await self._safe_write(writer, ws_response):
                                    break
                        except json.JSONDecodeError:
                            self.logger.error(f"无效的WebSocket JSON消息: {message}")
                        except Exception as e:
                            self.logger.error(f"处理WebSocket消息时出错: {e}")
                            self.logger.debug(traceback.format_exc())
                else:
                    # 普通TCP处理逻辑
                    try:
                        message = data.decode('utf-8').strip()
                        for line in message.splitlines():
                            if not line.strip():
                                continue
                            
                            try:
                                data = json.loads(line)
                                if not await self._process_json_message(data, writer):
                                    return
                            except json.JSONDecodeError:
                                self.logger.debug(f"无效的JSON消息: {line}")
                            except Exception as e:
                                self.logger.error(f"处理TCP消息时出错: {e}")
                                self.logger.debug(traceback.format_exc())
                    except UnicodeDecodeError:
                        self.logger.debug("接收到非UTF-8数据，忽略")
                
        except Exception as e:
            self.logger.error(f"处理客户端连接时出错: {e}")
            self.logger.debug(traceback.format_exc())
        finally:
            try:
                # 安全关闭连接
                try:
                    writer.close()
                    try:
                        # 使用超时来防止无限等待
                        await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
                    except asyncio.TimeoutError:
                        self.logger.debug("等待连接关闭超时")
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    # 忽略连接已重置的错误
                    pass
                except Exception as e:
                    self.logger.debug(f"关闭连接时出错: {e}")
            except Exception as e:
                self.logger.debug(f"处理客户端关闭时出错: {e}")
            
            # 使用锁保护删除客户端操作
            with self._clients_lock:
                if client_id in self.clients:
                    self.clients.pop(client_id, None)
            self.logger.info(f"客户端已断开连接: {addr}")
    
    async def _process_json_message(self, data, writer):
        """处理JSON消息，返回是否成功"""
        self.logger.info(f"收到消息: {data}")
        
        if data.get("type") == "heartbeat":
            # 响应心跳消息
            response = {
                "type": "heartbeat",
                "timestamp": data.get("timestamp")
            }
            return await self._safe_write(writer, (json.dumps(response) + '\n').encode('utf-8'))
        elif data.get("type") == "download" or (data.get("url") and "type" not in data):
            # 处理下载请求
            if "type" not in data:
                data["type"] = "download"
            
            if self._download_handler:
                self._download_handler(data)
                response = {
                    "type": "download_response",
                    "status": "success",
                    "message": "下载任务已添加"
                }
            else:
                response = {
                    "type": "download_response",
                    "status": "error",
                    "message": "下载处理程序未设置"
                }
            return await self._safe_write(writer, (json.dumps(response) + '\n').encode('utf-8'))
        return True
    
    async def start_server(self):
        """启动服务器"""
        try:
            self.logger.info(f"正在启动TCP服务器在 {self.host}:{self.port}")
            self.server = await asyncio.start_server(
                self.handle_client, self.host, self.port,
                # 设置socket选项以确保连接正确关闭
                reuse_address=True,
                start_serving=True
            )
            self.is_running = True
            self.logger.info(f"TCP服务器已启动，监听于 {self.host}:{self.port}")
            
            async with self.server:
                await self.server.serve_forever()
                
        except Exception as e:
            self.logger.error(f"启动TCP服务器出错: {e}")
            self.logger.error(traceback.format_exc())
            self.is_running = False
    
    def run_server(self):
        """在线程中运行服务器"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 添加信号处理，优雅关闭
            try:
                loop.run_until_complete(self.start_server())
            except KeyboardInterrupt:
                self.logger.info("服务器接收到关闭信号")
            finally:
                loop.close()
        except Exception as e:
            self.logger.error(f"运行TCP服务器线程出错: {e}")
            self.logger.error(traceback.format_exc())
    
    def start(self):
        """启动服务器线程"""
        if self.server_thread and self.server_thread.is_alive():
            self.logger.warning("TCP服务器已经在运行")
            return
        
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        self.logger.info("TCP服务器线程已启动")
    
    def stop(self):
        """停止服务器"""
        try:
            if self.server:
                self.server.close()
            self.is_running = False
            self.logger.info("TCP服务器已标记为停止")
        except Exception as e:
            self.logger.error(f"停止TCP服务器出错: {e}")

    async def _safe_broadcast(self, message, exclude_client_id=None):
        """安全地广播消息到所有客户端"""
        with self._clients_lock:
            clients_copy = dict(self.clients)  # 创建客户端字典的副本，避免在迭代过程中修改

        # 记录开始广播
        self.logger.debug(f"开始广播消息到 {len(clients_copy)} 个客户端")
        
        # 使用副本进行迭代
        for client_id, client_info in clients_copy.items():
            # 如果指定了排除的客户端ID，则跳过该客户端
            if exclude_client_id and client_id == exclude_client_id:
                continue
            
            writer = client_info.get("writer")
            is_websocket = client_info.get("is_websocket", False)
            
            if writer:
                try:
                    # 根据连接类型选择发送格式
                    if is_websocket:
                        # WebSocket格式
                        ws_message = self._encode_websocket_frame(message)
                        await self._safe_write(writer, ws_message)
                    else:
                        # 普通TCP格式
                        await self._safe_write(writer, (message + '\n').encode('utf-8'))
                    
                    # 更新最后活动时间
                    with self._clients_lock:
                        if client_id in self.clients:
                            self.clients[client_id]["last_activity"] = time.time()
                            
                except Exception as e:
                    self.logger.error(f"广播到客户端 {client_id} 时出错: {e}")
                    # 可能需要移除失效的客户端连接
                    with self._clients_lock:
                        if client_id in self.clients:
                            self.clients.pop(client_id, None)
                            self.logger.info(f"已从客户端列表中移除失效客户端 {client_id}")
        
        # 记录广播完成
        self.logger.debug("广播消息完成")

    def broadcast_message(self, message):
        """向所有连接的客户端广播消息"""
        if not self.is_running:
            self.logger.info("服务器未运行，无法广播消息，但会记录此消息")
            # 记录消息但不返回，以防未来有客户端连接
        
        # 即使没有客户端也安全处理
        with self._clients_lock:
            if len(self.clients) == 0:
                self.logger.debug("当前没有连接的客户端，消息已记录但不会发送")
                # 不再直接返回，继续尝试创建任务
        
        # 创建异步任务
        async def _do_broadcast():
            await self._safe_broadcast(message)
        
        # 获取当前事件循环，或创建新的
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环已经运行，使用事件循环的create_task
                asyncio.create_task(_do_broadcast())
            else:
                # 如果循环没有运行，使用run_until_complete
                loop.run_until_complete(_do_broadcast())
        except RuntimeError:
            # 如果无法获取当前循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_do_broadcast())
        except Exception as e:
            self.logger.error(f"广播消息时出错: {e}")
            self.logger.error(traceback.format_exc())

# 单例模式，全局访问点
_server_instance = None

def get_server_instance(host="localhost", port=20971) -> BasicTCPServer:
    """获取TCP服务器单例"""
    global _server_instance
    if _server_instance is None:
        _server_instance = BasicTCPServer(host, port)
    return _server_instance 