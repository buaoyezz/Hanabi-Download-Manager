import asyncio
import json
import logging
import threading
import traceback
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
    
    async def handle_client(self, reader, writer):
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        self.logger.info(f"客户端已连接: {addr}")
        client_id = id(writer)
        self.clients.add(client_id)
        
        try:
            # 发送版本信息
            version_info = {
                "type": "version",
                "ClientVersion": "1.0.0",
                "LatestExtensionVersion": "1.0.0"
            }
            writer.write((json.dumps(version_info) + '\n').encode('utf-8'))
            await writer.drain()
            
            # 读取客户端消息
            while True:
                try:
                    data = await reader.readline()
                    if not data:
                        break
                    
                    message = data.decode('utf-8').strip()
                    try:
                        data = json.loads(message)
                        self.logger.info(f"收到消息: {data}")
                        
                        if data.get("type") == "heartbeat":
                            # 响应心跳消息
                            response = {
                                "type": "heartbeat",
                                "timestamp": data.get("timestamp")
                            }
                            writer.write((json.dumps(response) + '\n').encode('utf-8'))
                            await writer.drain()
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
                            writer.write((json.dumps(response) + '\n').encode('utf-8'))
                            await writer.drain()
                        
                    except json.JSONDecodeError:
                        self.logger.error(f"无效的JSON消息: {message}")
                    except Exception as e:
                        self.logger.error(f"处理消息时出错: {e}")
                        self.logger.error(traceback.format_exc())
                
                except Exception as e:
                    self.logger.error(f"读取客户端消息时出错: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"处理客户端连接时出错: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            
            self.clients.remove(client_id)
            self.logger.info(f"客户端已断开连接: {addr}")
    
    async def start_server(self):
        """启动服务器"""
        try:
            self.logger.info(f"正在启动TCP服务器在 {self.host}:{self.port}")
            self.server = await asyncio.start_server(
                self.handle_client, self.host, self.port
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
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_server())
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