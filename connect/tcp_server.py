import asyncio
import json
import logging
import threading
import traceback
import re
import base64
import hashlib
import socket
from typing import Dict, List, Optional, Callable

class BasicTCPServer:
    """简单的TCP服务器，用于在WebSocket服务器不可用时作为备选"""
    
    def __init__(self, host: str = "localhost", port: int = 20971):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self.server_thread = None
        self.is_running = False
        self._download_handler: Optional[Callable] = None
        
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
        self.clients.add(client_id)
        
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
                
                # 发送版本信息 (WebSocket格式)
                version_info = {
                    "type": "version",
                    "ClientVersion": "1.0.5",
                    "LatestExtensionVersion": "1.0.1"
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
                        "ClientVersion": "1.0.5",
                        "LatestExtensionVersion": "1.0.1"
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
            
            if client_id in self.clients:
                self.clients.remove(client_id)
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

# 单例模式，全局访问点
_server_instance = None

def get_server_instance(host="localhost", port=20971) -> BasicTCPServer:
    """获取TCP服务器单例"""
    global _server_instance
    if _server_instance is None:
        _server_instance = BasicTCPServer(host, port)
    return _server_instance 