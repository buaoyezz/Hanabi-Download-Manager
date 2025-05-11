import logging
import json
import traceback
from typing import Dict, Any, Optional, Callable
import threading
import time

from PySide6.QtCore import Qt, QObject, Signal, Slot

# 定义服务器类型标记
USE_WEBSOCKET = False
SERVER_TYPE = "TCP"  # 强制使用TCP服务器

# 提前导入TCP服务器，确保它总是可用作为后备选项
try:
    from connect.tcp_server import get_server_instance as get_tcp_server
    logging.info("已导入TCP服务器作为后备选项")
except (ImportError, ModuleNotFoundError) as e:
    logging.error(f"导入TCP服务器失败: {e}")
    logging.error(traceback.format_exc())
    raise

# WebSocket相关导入放在这里，但不使用
try:
    import websockets.legacy
    logging.info("检测到websockets.legacy模块可用，但已配置为不使用")
    
    # 不再设置USE_WEBSOCKET为True
    # USE_WEBSOCKET = True
    # SERVER_TYPE = "WebSocket"
    
    try:
        from connect.websocket_server import get_server_instance as get_ws_server
        logging.info("WebSocket服务器可用，但当前配置为使用TCP")
    except (ImportError, ModuleNotFoundError) as e:
        logging.warning(f"导入WebSocket服务器实现失败: {e}")
except Exception as e:
    logging.warning(f"WebSocket服务器检测过程中出错: {e}")
    # 这里不需改变值，因为默认已经是False和TCP

from core.download_core.download_kernel_reformed import DownloadEngine

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
        self._request_queue = []  # 保存请求队列，确保不丢失请求
        self._request_queue_lock = threading.Lock()  # 请求队列锁
        self._is_processing = False  # 是否正在处理请求队列
        self._request_count = 0  # 请求计数
        
        # 尝试初始化服务器
        self.initialize_server()
        
        # 连接信号
        if self._download_handler:
            self.downloadRequestReceived.connect(self._download_handler)
    
    def initialize_server(self):
        """初始化服务器，使用TCP"""
        try:
            # 直接使用TCP服务器，不尝试WebSocket
            self.server = get_tcp_server(port=20971)
            self.logger.info("使用TCP服务器连接器")
        except Exception as e:
            self.logger.error(f"服务器初始化失败: {e}")
            self.logger.error(traceback.format_exc())
            # 再次尝试TCP服务器
            try:
                self.server = get_tcp_server(port=20971)
                self.logger.info("重新尝试TCP服务器成功")
            except Exception as final_error:
                self.logger.error(f"TCP服务器初始化失败: {final_error}")
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
                # 尝试启动服务器
                self.server.start()
                
                # 获取实际使用的端口（可能已被自动切换）
                actual_port = getattr(self.server, 'port', 20971)
                self.logger.info(f"TCP服务器已启动，端口: {actual_port}")
                
                # 处理之前积压的请求
                self.process_queued_requests()
            except Exception as e:
                self.logger.error(f"启动服务器失败: {e}")
                self.logger.error(traceback.format_exc())
                
                # 如果启动失败，再次尝试
                self.logger.info("尝试重新启动TCP服务器...")
                try:
                    self.server = get_tcp_server(port=20971)
                    self.server.set_download_handler(self.handle_download_request)
                    self.server.start()
                    self.logger.info("成功重启TCP服务器")
                    
                    # 再次尝试处理队列
                    self.process_queued_requests()
                except Exception as retry_error:
                    self.logger.error(f"重启TCP服务器也失败了: {retry_error}")
                    self.logger.error(traceback.format_exc())
        else:
            self.logger.error("没有可用的服务器，无法启动")
            # 再次尝试初始化服务器
            try:
                # 直接初始化TCP服务器
                self.server = get_tcp_server(port=20971)
                
                # 设置下载处理程序
                if self.server:
                    self.server.set_download_handler(self.handle_download_request)
                    self.server.start()
                    self.logger.info("重试初始化服务器成功")
                    
                    # 再次尝试处理队列
                    self.process_queued_requests()
            except Exception as retry_error:
                self.logger.error(f"重试初始化服务器失败: {retry_error}")
                self.logger.error(traceback.format_exc())
    
    def process_queued_requests(self):
        """处理积压的下载请求"""
        # 只允许一个线程处理队列
        with self._request_queue_lock:
            if self._is_processing or not self._request_queue:
                return
            self._is_processing = True
        
        try:
            # 复制队列并清空原队列
            with self._request_queue_lock:
                queue_copy = self._request_queue.copy()
                self._request_queue.clear()
            
            self.logger.info(f"开始处理积压请求队列，共 {len(queue_copy)} 个请求")
            
            # 处理队列中的每个请求
            for request in queue_copy:
                request_id = request.get("requestId", "未知ID")
                self.logger.info(f"从队列处理积压请求 [ID: {request_id}]: {request.get('url', '未知URL')}")
                try:
                    # 直接发送信号到主线程处理
                    self.downloadRequestReceived.emit(request)
                    self.logger.info(f"请求 [ID: {request_id}] 已发送到下载处理程序")
                except Exception as e:
                    self.logger.error(f"处理队列请求 [ID: {request_id}] 失败: {e}")
                    self.logger.error(traceback.format_exc())
            
            self.logger.info(f"队列处理完成，已处理 {len(queue_copy)} 个请求")
        finally:
            # 处理完成，重置处理标志
            with self._request_queue_lock:
                self._is_processing = False
                
                # 检查是否有新请求入队
                if self._request_queue:
                    # 如果有新请求，再次调用处理
                    new_count = len(self._request_queue)
                    self.logger.info(f"处理过程中有 {new_count} 个新请求入队，准备处理")
                    # 使用延迟调用避免递归过深
                    import threading
                    threading.Timer(0.1, self.process_queued_requests).start()
    
    def is_running(self):
        """检查连接器是否正在运行"""
        try:
            if hasattr(self, '_running'):
                return self._running
            
            if hasattr(self, 'server') and self.server:
                # 检查服务器状态
                if hasattr(self.server, 'running'):
                    return self.server.running
                elif hasattr(self.server, 'is_alive'):
                    # 检查is_alive是方法还是属性
                    if callable(self.server.is_alive):
                        return self.server.is_alive()
                    else:
                        return self.server.is_alive
                elif hasattr(self.server, 'is_running'):
                    # 检查is_running是方法还是属性
                    if callable(self.server.is_running):
                        return self.server.is_running()
                    else:
                        return self.server.is_running
            
            # 如果有_websocket_server_thread属性，检查线程状态
            if hasattr(self, '_websocket_server_thread'):
                thread = self._websocket_server_thread
                if thread and thread.is_alive():
                    return True
            
            return False
        except Exception as e:
            logging.error(f"检查连接器运行状态出错: {e}")
            return False
    
    def has_active_connections(self):
        """检查是否有活跃的浏览器连接"""
        if not self.is_running():
            return False
            
        if hasattr(self.server, 'has_clients') and callable(self.server.has_clients):
            return self.server.has_clients()
            
        # 如果服务器没有直接提供检测方法，尝试检查客户端列表
        if hasattr(self.server, 'clients') and isinstance(self.server.clients, list):
            return len(self.server.clients) > 0
        elif hasattr(self.server, 'clients') and isinstance(self.server.clients, dict):
            return len(self.server.clients) > 0
            
        # 保守默认，如果无法确定，返回False
        return False
    
    def stop(self):
        """停止服务器"""
        if self.server:
            try:
                self.server.stop()
                self.logger.info("TCP服务器已停止")
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
        # 为请求添加唯一ID
        if "requestId" not in data:
            data["requestId"] = f"req_{int(time.time() * 1000)}_{self._request_count}"
            self._request_count += 1
            
        self.logger.info(f"收到下载请求 [ID: {data['requestId']}]: {data.get('url', '未知URL')}")
        
        # 将请求添加到队列
        with self._request_queue_lock:
            self._request_queue.append(data)
            queue_len = len(self._request_queue)
        
        self.logger.info(f"请求已加入队列 [ID: {data['requestId']}], 当前队列长度: {queue_len}")
        
        # 尝试处理队列，使用非阻塞方式
        import threading
        threading.Thread(target=self.process_queued_requests, daemon=True).start()
    
    @staticmethod
    def create_download_task(download_data: Dict[str, Any]) -> DownloadEngine:
        """根据下载数据创建下载任务"""
        url = download_data.get('url')
        filename = download_data.get('filename')
        referrer = download_data.get('referrer')
        
        # 从请求中提取HTTP头信息
        headers = download_data.get('headers', {})
        
        # 如果有referrer参数，添加到headers中
        if referrer:
            headers['Referer'] = referrer
        
        # 确保有User-Agent
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
        
        # 设置接受所有内容类型
        if 'Accept' not in headers:
            headers['Accept'] = '*/*'
        
        # 创建下载引擎
        download_engine = DownloadEngine(
            url=url,
            headers=headers,
            max_concurrent=8,  # 可以从配置中读取
            save_path=None,    # 使用默认保存路径，也可以从请求中获取
            file_name=filename,
            smart_threading=True
        )
        
        return download_engine