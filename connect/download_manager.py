import logging
import json
from typing import Dict, Any, Optional, Callable

from PySide6.QtCore import Qt, QObject, Signal, Slot
from connect.websocket_server import get_server_instance
from core.download_core.download_kernel import TransferManager

class DownloadConnector(QObject):
    downloadRequestReceived = Signal(dict)
    
    def __init__(self, download_handler: Optional[Callable] = None):
        super().__init__()
        
        self.logger = logging.getLogger('DownloadConnector')
        # 使用端口20971
        self.server = get_server_instance(port=20971)
        self.server.set_download_handler(self.handle_download_request)
        self._download_handler = download_handler
        
        # 如果提供了下载处理程序，将信号连接到它
        if self._download_handler:
            self.downloadRequestReceived.connect(self._download_handler)
        
    def start(self):
        self.server.start()
        self.logger.info("下载连接器已启动，WebSocket服务器端口: 20971")
        
    def stop(self):
        self.server.stop()
        self.logger.info("下载连接器已停止")
        
    def set_download_handler(self, handler: Callable):
        self._download_handler = handler
        # 重新连接信号到新的处理程序
        self.downloadRequestReceived.connect(self._download_handler)
        
    def handle_download_request(self, data: Dict[str, Any]):
        self.logger.info(f"收到下载请求: {data}")
        # 发出信号，将请求数据传递到主线程
        self.downloadRequestReceived.emit(data)
        
    @staticmethod
    def create_download_task(download_data: Dict[str, Any]) -> TransferManager:
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