import asyncio
import json
import logging
import threading
import traceback
import time  # 添加时间模块导入
import socket  # 添加socket模块导入
import random  # 添加随机模块导入
import sys
import os
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
            return "1.0.1"  # 默认扩展版本
    version_manager = VersionManagerFallback()
    logging.warning("无法导入版本管理器，使用默认版本")

# 尝试导入websockets包的所有必要模块
try:
    import websockets
    from websockets import server, exceptions
    logging.info("成功导入websockets模块")
except ImportError as e:
    logging.error(f"无法导入websockets模块: {e}，请确保已安装: pip install websockets")
    raise

class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 20971):
        self.host = host
        self.port = port
        self.initial_port = port  # 保存初始端口号
        self.clients = set()
        self.server = None
        self.server_thread = None
        self.is_running = False
        self._download_handler: Optional[Callable] = None
        self.connection_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.server_lock = threading.Lock()  # 服务器实例锁，防止多线程同时访问服务器
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('WebSocketServer')
    
    def set_download_handler(self, handler: Callable):
        self._download_handler = handler
        self.logger.info("已设置下载处理程序")
    
    # 最简化的连接处理函数
    async def handler(self, websocket):
        client_id = id(websocket)
        try:
            with self.connection_lock:
                self.clients.add(websocket)
            self.logger.info(f"客户端已连接 [ID: {client_id}], 当前连接数: {len(self.clients)}")
            
            # 发送版本信息
            version_info = {
                "type": "version",
                "ClientVersion": version_manager.get_client_version(),
                "LatestExtensionVersion": version_manager.get_extension_version(),
                "ServerStatus": "ready"
            }
            await websocket.send(json.dumps(version_info))
            
            # 处理消息
            async for message in websocket:
                try:
                    data = json.loads(message)
                    request_id = data.get("requestId", "unknown")
                    self.logger.info(f"收到消息 [ID: {client_id}, RequestID: {request_id}]: {data}")
                    
                    if data.get("type") == "heartbeat":
                        # 响应心跳消息
                        response = {
                            "type": "heartbeat",
                            "timestamp": data.get("timestamp"),
                            "status": "active"
                        }
                        await websocket.send(json.dumps(response))
                        self.logger.info(f"已响应心跳 [ID: {client_id}]")
                    elif data.get("type") == "download" or (data.get("url") and "type" not in data):
                        # 处理下载请求
                        if "type" not in data:
                            data["type"] = "download"
                        
                        # 添加请求ID用于跟踪
                        if "requestId" not in data:
                            data["requestId"] = f"req_{int(time.time() * 1000)}"
                        
                        self.logger.info(f"处理下载请求 [ID: {client_id}, RequestID: {data['requestId']}]")
                        
                        if self._download_handler:
                            # 在单独的线程中处理下载请求，避免阻塞WebSocket
                            def process_download_request():
                                try:
                                    self._download_handler(data)
                                    self.logger.info(f"下载请求已处理 [RequestID: {data['requestId']}]")
                                except Exception as e:
                                    self.logger.error(f"处理下载请求失败 [RequestID: {data['requestId']}]: {e}")
                                    self.logger.error(traceback.format_exc())
                            
                            threading.Thread(target=process_download_request, daemon=True).start()
                            
                            # 立即发送响应，不等待下载处理完成
                            response = {
                                "type": "download_response",
                                "requestId": data.get("requestId", "unknown"),
                                "status": "success",
                                "message": "下载任务已添加"
                            }
                        else:
                            response = {
                                "type": "download_response",
                                "requestId": data.get("requestId", "unknown"),
                                "status": "error",
                                "message": "下载处理程序未设置"
                            }
                        await websocket.send(json.dumps(response))
                        self.logger.info(f"已发送下载响应 [ID: {client_id}, RequestID: {data.get('requestId', 'unknown')}]")
                    
                except json.JSONDecodeError:
                    self.logger.error(f"无效的JSON消息 [ID: {client_id}]: {message}")
                    try:
                        error_response = {
                            "type": "error",
                            "message": "无效的JSON格式"
                        }
                        await websocket.send(json.dumps(error_response))
                    except:
                        pass
                except Exception as e:
                    self.logger.error(f"处理消息时出错 [ID: {client_id}]: {e}")
                    self.logger.error(traceback.format_exc())
                    try:
                        error_response = {
                            "type": "error",
                            "message": f"服务器错误: {str(e)}"
                        }
                        await websocket.send(json.dumps(error_response))
                    except:
                        pass
        
        except websockets.exceptions.ConnectionClosed as e:
            self.logger.info(f"客户端断开连接 [ID: {client_id}]: {e}")
        except Exception as e:
            self.logger.error(f"处理连接时出错 [ID: {client_id}]: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            with self.connection_lock:
                if websocket in self.clients:
                    self.clients.remove(websocket)
            self.logger.info(f"客户端已断开连接 [ID: {client_id}], 剩余连接数: {len(self.clients)}")
    
    def _is_port_in_use(self, port):
        """检查端口是否被占用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return False
            except socket.error:
                return True
    
    def _find_available_port(self, start_port=20971, max_attempts=10):
        """查找可用端口，从start_port开始尝试"""
        port = start_port
        attempts = 0
        
        while attempts < max_attempts:
            if not self._is_port_in_use(port):
                return port
            port += 1
            attempts += 1
        
        # 如果找不到可用端口，返回一个随机端口
        return random.randint(30000, 60000)
    
    # 服务器运行函数
    def run_server(self):
        """启动服务器，支持端口自动切换"""
        # 避免递归调用，采用循环方式重启
        retry_count = 0
        max_retries = self.max_reconnect_attempts
        current_port = self.port
        
        while retry_count <= max_retries and not self.is_running:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 在循环中启动服务器
                async def start_server():
                    nonlocal current_port
                    
                    # 检查当前端口是否可用，如果不可用则尝试切换端口
                    if self._is_port_in_use(current_port):
                        old_port = current_port
                        current_port = self._find_available_port(current_port + 1)
                        self.logger.warning(f"端口 {old_port} 已被占用，切换到新端口 {current_port}")
                        self.port = current_port
                    
                    self.logger.info(f"正在尝试启动WebSocket服务器在 {self.host}:{current_port}")
                    
                    # 配置WebSocket服务器
                    try:
                        server_instance = await websockets.serve(
                            self.handler, 
                            self.host, 
                            current_port, 
                            ping_interval=50,
                            ping_timeout=30,
                            max_size=10485760
                        )
                        
                        with self.server_lock:
                            self.server = server_instance
                            self.is_running = True
                        
                        self.reconnect_attempts = 0
                        self.logger.info(f"WebSocket服务器已启动，监听于 {self.host}:{current_port}")
                        
                        # 保持服务器运行
                        await asyncio.Future()
                    except Exception as e:
                        # 特别处理端口占用错误
                        if "address already in use" in str(e).lower() or "10048" in str(e):
                            old_port = current_port
                            current_port = self._find_available_port(current_port + 1)
                            self.logger.warning(f"启动端口 {old_port} 失败，将尝试新端口 {current_port}")
                            raise  # 重新抛出异常，进入重试循环
                        else:
                            self.logger.error(f"启动WebSocket服务器出错: {e}")
                            self.logger.error(traceback.format_exc())
                            raise
                
                # 运行服务器启动函数
                loop.run_until_complete(start_server())
                break  # 如果启动成功，跳出重试循环
                
            except Exception as e:
                self.logger.error(f"启动尝试 {retry_count + 1}/{max_retries + 1} 失败: {e}")
                retry_count += 1
                
                if retry_count <= max_retries:
                    self.logger.info(f"等待 3 秒后进行下一次尝试...")
                    time.sleep(3)  # 等待一段时间再重试
                else:
                    self.logger.error("达到最大重试次数，放弃启动服务器")
                    break
            finally:
                try:
                    if loop and loop.is_running():
                        loop.close()
                except:
                    pass
    
    # 启动服务器
    def start(self):
        with self.server_lock:
            if self.server_thread and self.server_thread.is_alive() and self.is_running:
                self.logger.info("WebSocket服务器已经在运行")
                return
            
            # 如果有旧线程但不再运行，清理它
            if self.server_thread and not self.server_thread.is_alive():
                self.logger.info("清理旧的WebSocket服务器线程")
                self.server_thread = None
            
            # 重置端口到初始值
            self.port = self.initial_port
            
            # 使用守护线程运行WebSocket服务器
            self.server_thread = threading.Thread(target=self.run_server, daemon=True)
            self.server_thread.start()
            self.logger.info("WebSocket服务器线程已启动")
    
    # 停止服务器
    def stop(self):
        with self.server_lock:
            try:
                if self.server:
                    self.server.close()
                self.is_running = False
                
                # 关闭所有客户端连接
                async def close_connections():
                    for client in list(self.clients):
                        try:
                            await client.close()
                        except:
                            pass
                    self.clients.clear()
                
                # 执行关闭连接的异步函数
                if self.clients:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(close_connections())
                    loop.close()
                
                self.logger.info("WebSocket服务器已停止")
            except Exception as e:
                self.logger.error(f"停止WebSocket服务器出错: {e}")
                self.logger.error(traceback.format_exc())

    def shutdown_gracefully(self):
        """安全地关闭服务器和所有连接"""
        try:
            # 标记服务器为非运行状态
            self.is_running = False
            
            if self.server:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def shutdown():
                    # 关闭所有客户端连接
                    if self.clients:
                        self.logger.info(f"正在关闭 {len(self.clients)} 个客户端连接")
                        close_tasks = []
                        for client in list(self.clients):
                            try:
                                close_tasks.append(client.close())
                            except:
                                pass
                        
                        if close_tasks:
                            await asyncio.gather(*close_tasks, return_exceptions=True)
                    
                    # 关闭服务器
                    if self.server:
                        self.logger.info("正在关闭WebSocket服务器")
                        self.server.close()
                        await self.server.wait_closed()
                        self.server = None
                
                try:
                    loop.run_until_complete(shutdown())
                except Exception as e:
                    self.logger.error(f"安全关闭服务器时出错: {e}")
                finally:
                    loop.close()
            
            # 等待服务器线程结束
            if self.server_thread and self.server_thread.is_alive():
                self.logger.info("等待服务器线程结束")
                self.server_thread.join(timeout=2.0)
            
            self.clients.clear()
            self.logger.info("WebSocket服务器已安全关闭")
            
            return True
        except Exception as e:
            self.logger.error(f"关闭WebSocket服务器时出错: {e}")
            self.logger.error(traceback.format_exc())
            return False


# 单例模式，全局访问点
_server_instance = None
_instance_lock = threading.Lock()

def get_server_instance(host="localhost", port=20971, force_new=False) -> WebSocketServer:
    """
    获取WebSocket服务器实例
    
    参数:
        host: 服务器主机名
        port: 服务器端口号
        force_new: 是否强制创建新实例（调试用）
    
    返回:
        WebSocketServer实例
    """
    global _server_instance
    
    # 使用锁确保线程安全的单例模式
    with _instance_lock:
        # 如果要求新实例或者实例不存在，创建一个新的
        if force_new or _server_instance is None:
            _server_instance = WebSocketServer(host, port)
        else:
            # 检查现有实例是否正在运行，如果不是，更新端口并重启
            if not _server_instance.is_running:
                # 如果现有实例的端口被占用，尝试使用新端口
                if _server_instance._is_port_in_use(port):
                    # 查找可用端口
                    new_port = _server_instance._find_available_port(port)
                    logging.info(f"更新WebSocket服务器端口: {port} -> {new_port}")
                    _server_instance.port = new_port
                    _server_instance.initial_port = new_port
                else:
                    # 如果端口未被占用，更新为提供的端口
                    if _server_instance.port != port:
                        logging.info(f"更新WebSocket服务器端口: {_server_instance.port} -> {port}")
                        _server_instance.port = port
                        _server_instance.initial_port = port
    
    return _server_instance 