import logging
import json
import traceback
from typing import Dict, Any, Optional, Callable

from PySide6.QtCore import Qt, QObject, Signal, Slot

# 定义服务器类型标记
USE_WEBSOCKET = True
SERVER_TYPE = "WebSocket"

# 尝试导入WebSocket服务器，如果失败再导入TCP服务器
try:
    # 先尝试导入websockets.legacy模块，确保它存在
    try:
        import websockets.legacy
        logging.info("成功导入websockets.legacy模块")
    except (ImportError, ModuleNotFoundError) as e:
        logging.warning(f"导入websockets.legacy模块失败: {e}")
        USE_WEBSOCKET = False
        SERVER_TYPE = "TCP"
        raise ImportError("websockets.legacy模块不可用")
        
    from connect.websocket_server import get_server_instance as get_ws_server
    logging.info("成功导入WebSocket服务器")
except (ImportError, ModuleNotFoundError) as e:
    logging.warning(f"导入WebSocket服务器失败: {e}")
    USE_WEBSOCKET = False
    SERVER_TYPE = "TCP"
    try:
        from connect.tcp_server import get_server_instance as get_tcp_server
        logging.info("已回退到TCP服务器")
    except (ImportError, ModuleNotFoundError) as e:
        logging.error(f"导入TCP服务器也失败了: {e}")
        logging.error(traceback.format_exc())
        raise

from core.download_core.download_kernel import TransferManager

class FallbackConnector(QObject):
    """
    连接器适配器，能够在WebSocket服务器不可用时切换到TCP服务器
    """
    downloadRequestReceived = Signal(dict)
    
    def __init__(self, download_handler: Optional[Callable] = None):
        super().__init__()
        
        self.logger = logging.getLogger('FallbackConnector')
        self.server = None
        self._download_handler = download_handler
        
        # 尝试初始化服务器
        self.initialize_server()
        
        # 连接信号
        if self._download_handler:
            self.downloadRequestReceived.connect(self._download_handler)
    
    def initialize_server(self):
        """初始化服务器，尝试WebSocket，如失败则使用TCP"""
        try:
            if USE_WEBSOCKET:
                self.logger.info("尝试初始化WebSocket服务器...")
                try:
                    # 再次检查websockets.legacy模块是否可用
                    try:
                        import websockets.legacy
                    except (ImportError, ModuleNotFoundError):
                        self.logger.warning("运行时检测到websockets.legacy模块不可用，强制使用TCP服务器")
                        raise ImportError("websockets.legacy模块不可用")
                        
                    self.server = get_ws_server(port=20971)
                    self.logger.info("使用WebSocket服务器连接器")
                except Exception as ws_error:
                    self.logger.error(f"初始化WebSocket服务器失败: {ws_error}")
                    self.logger.error(traceback.format_exc())
                    # WebSocket失败，尝试TCP
                    try:
                        from connect.tcp_server import get_server_instance as get_tcp_server
                        self.server = get_tcp_server(port=20971)
                        self.logger.info("已回退到TCP服务器")
                    except Exception as tcp_error:
                        self.logger.error(f"初始化TCP服务器也失败了: {tcp_error}")
                        self.logger.error(traceback.format_exc())
            else:
                # 直接使用TCP服务器
                self.server = get_tcp_server(port=20971)
                self.logger.info("使用TCP服务器连接器")
        except Exception as e:
            self.logger.error(f"服务器初始化失败: {e}")
            self.logger.error(traceback.format_exc())
            # 最后尝试一次TCP服务器
            try:
                from connect.tcp_server import get_server_instance as get_tcp_server
                self.server = get_tcp_server(port=20971)
                self.logger.info("最终回退到TCP服务器成功")
            except Exception as final_error:
                self.logger.error(f"最终回退到TCP服务器也失败了: {final_error}")
                self.logger.error(traceback.format_exc())
        
        # 设置下载处理程序
        if self.server:
            self.server.set_download_handler(self.handle_download_request)
        else:
            self.logger.error("没有可用的服务器，无法设置下载处理程序")
    
    def start(self):
        """启动服务器"""
        if self.server:
            try:
                self.server.start()
                server_type = "WebSocket" if USE_WEBSOCKET else "TCP"
                self.logger.info(f"{server_type}服务器已启动，端口: 20971")
            except Exception as e:
                self.logger.error(f"启动服务器失败: {e}")
                self.logger.error(traceback.format_exc())
                
                # 如果是WebSocket服务器启动失败，尝试回退到TCP服务器
                if USE_WEBSOCKET:
                    self.logger.info("尝试回退到TCP服务器...")
                    try:
                        from connect.tcp_server import get_server_instance as get_tcp_server
                        self.server = get_tcp_server(port=20971)
                        self.server.set_download_handler(self.handle_download_request)
                        self.server.start()
                        self.logger.info("成功回退到TCP服务器")
                    except Exception as tcp_error:
                        self.logger.error(f"回退到TCP服务器也失败了: {tcp_error}")
                        self.logger.error(traceback.format_exc())
        else:
            self.logger.error("没有可用的服务器，无法启动")
            # 再次尝试初始化TCP服务器
            try:
                from connect.tcp_server import get_server_instance as get_tcp_server
                self.server = get_tcp_server(port=20971)
                self.server.set_download_handler(self.handle_download_request)
                self.server.start()
                self.logger.info("重试初始化TCP服务器成功")
            except Exception as retry_error:
                self.logger.error(f"重试初始化TCP服务器失败: {retry_error}")
                self.logger.error(traceback.format_exc())
    
    def stop(self):
        """停止服务器"""
        if self.server:
            try:
                self.server.stop()
                server_type = "WebSocket" if USE_WEBSOCKET else "TCP"
                self.logger.info(f"{server_type}服务器已停止")
            except Exception as e:
                self.logger.error(f"停止服务器出错: {e}")
                self.logger.error(traceback.format_exc())
    
    def set_download_handler(self, handler: Callable):
        """设置下载处理程序"""
        self._download_handler = handler
        
        # 重新连接信号到新的处理程序
        if handler is not None:
            try:
                self.downloadRequestReceived.disconnect()  # 先断开旧的连接
            except:
                pass  # 如果没有连接，忽略错误
            self.downloadRequestReceived.connect(self._download_handler)
            
        # 更新服务器的处理程序
        if self.server:
            self.server.set_download_handler(self.handle_download_request)
        else:
            self.logger.error("没有可用的服务器，无法设置下载处理程序")
    
    def handle_download_request(self, data: Dict[str, Any]):
        """处理下载请求"""
        self.logger.info(f"收到下载请求: {data}")
        # 发出信号，将请求数据传递到主线程
        self.downloadRequestReceived.emit(data)
    
    @staticmethod
    def create_download_task(download_data: Dict[str, Any]) -> TransferManager:
        """根据下载数据创建下载任务"""
        url = download_data.get('url')
        filename = download_data.get('filename')
        referrer = download_data.get('referrer')
        
        # 从请求中提取HTTP头信息
        headers = download_data.get('headers', {})
        
        # 创建下载管理器
        transfer_manager = TransferManager(
            url=url,
            headers=headers,
            maxThreads=8,  # 可以从配置中读取
            savePath=None,  # 使用默认保存路径，也可以从请求中获取
            filename=filename,
            dynamicThreads=True,
            referrer=referrer
        )
        
        return transfer_manager 