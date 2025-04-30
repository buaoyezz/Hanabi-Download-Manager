import asyncio
import json
import logging
import threading
import traceback
from typing import Dict, List, Optional, Callable

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
        self.logger = logging.getLogger('WebSocketServer')
    
    def set_download_handler(self, handler: Callable):
        self._download_handler = handler
    
    # 最简化的连接处理函数
    async def handler(self, websocket):
        try:
            self.clients.add(websocket)
            self.logger.info(f"客户端已连接")
            
            # 发送版本信息
            version_info = {
                "type": "version",
                "ClientVersion": "1.0.1",
                "LatestExtensionVersion": "1.0.1"
            }
            await websocket.send(json.dumps(version_info))
            
            # 处理消息
            async for message in websocket:
                try:
                    data = json.loads(message)
                    self.logger.info(f"收到消息: {data}")
                    
                    if data.get("type") == "heartbeat":
                        # 响应心跳消息
                        response = {
                            "type": "heartbeat",
                            "timestamp": data.get("timestamp")
                        }
                        await websocket.send(json.dumps(response))
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
                        await websocket.send(json.dumps(response))
                    
                except json.JSONDecodeError:
                    self.logger.error(f"无效的JSON消息: {message}")
                except Exception as e:
                    self.logger.error(f"处理消息时出错: {e}")
                    self.logger.error(traceback.format_exc())
        
        except Exception as e:
            self.logger.error(f"处理连接时出错: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.clients.remove(websocket)
            self.logger.info(f"客户端已断开连接")
    
    # 服务器运行函数
    def run_server(self):
        async def inner_run():
            try:
                # 使用最基本的API创建服务器
                self.logger.info(f"正在尝试启动WebSocket服务器在 {self.host}:{self.port}")
                
                # 使用websockets的基本API创建服务器
                server_instance = await websockets.serve(self.handler, self.host, self.port)
                self.server = server_instance
                self.is_running = True
                self.logger.info(f"WebSocket服务器已启动，监听于 {self.host}:{self.port}")
                
                # 保持服务器运行
                await asyncio.Future()
            except Exception as e:
                self.logger.error(f"启动WebSocket服务器出错: {e}")
                self.logger.error(traceback.format_exc())
                raise
        
        try:
            # 创建新的事件循环并运行服务器
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(inner_run())
        except Exception as e:
            self.logger.error(f"启动WebSocket服务器线程出错: {e}")
            self.logger.error(traceback.format_exc())
            raise
        finally:
            try:
                if loop and loop.is_running():
                    loop.close()
            except:
                pass
    
    # 启动服务器
    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            self.logger.warning("WebSocket服务器已经在运行")
            return
        
        # 使用守护线程运行WebSocket服务器
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        self.logger.info("WebSocket服务器线程已启动")
    
    # 停止服务器
    def stop(self):
        try:
            if self.server:
                self.server.close()
            self.is_running = False
            self.logger.info("WebSocket服务器已标记为停止")
        except Exception as e:
            self.logger.error(f"停止WebSocket服务器出错: {e}")

# 单例模式，全局访问点
_server_instance = None

def get_server_instance(host="localhost", port=20971) -> WebSocketServer:
    global _server_instance
    if _server_instance is None:
        _server_instance = WebSocketServer(host, port)
    return _server_instance 