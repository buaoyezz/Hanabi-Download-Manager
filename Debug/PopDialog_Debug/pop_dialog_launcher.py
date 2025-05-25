import sys
import os
# 设置环境变量以过滤Qt的字体警告日志
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont, QIcon
from PySide6.QtCore import QObject, Signal, Slot, QTimer, Qt
from client.ui.extension_interface.pop_dialog import DownloadPopDialog
from connect.fallback_connector import FallbackConnector
from core.font.font_manager import FontManager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("popup_downloader.log"),
        logging.StreamHandler()
    ]
)

# 下载请求处理器
class PopupDownloadHandler(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_dialogs = []  # 保存活跃的弹窗
        
        # 初始化连接器
        self.connector = None
        self._init_connector()
        
        # 启动健康检查
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._check_connector_health)
        self.health_timer.start(5000)  # 每5秒检查一次
        
    def _init_connector(self):
        """初始化连接器"""
        try:
            logging.info("初始化浏览器连接器")
            self.connector = FallbackConnector()
            self.connector.downloadRequestReceived.connect(self.handle_download_request)
            self.connector.start()
            logging.info("浏览器连接器初始化成功")
        except Exception as e:
            logging.error(f"初始化连接器失败: {e}")
            
    def _check_connector_health(self):
        """检查连接器健康状态"""
        if not self.connector or not self.connector.is_running():
            logging.warning("连接器未运行，尝试重新初始化")
            self._init_connector()
    
    @Slot(dict)
    def handle_download_request(self, download_data):
        """处理下载请求"""
        try:
            logging.info(f"收到下载请求: {download_data.get('url', '')}")
            
            # 创建弹窗并显示，指定不自动开始下载
            dialog = DownloadPopDialog.create_and_show(download_data, auto_start=False)
            
            # 连接信号
            dialog.downloadCompleted.connect(self._on_download_completed)
            
            # 保存弹窗引用
            self.active_dialogs.append(dialog)
            
            # 当弹窗关闭时移除引用
            dialog.destroyed.connect(lambda obj=dialog: self._remove_dialog(obj))
            
            # 确保窗口在最前面
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            
            return True
        except Exception as e:
            logging.error(f"处理下载请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _on_download_completed(self, task_data):
        """下载完成处理"""
        logging.info(f"下载完成: {task_data.get('file_name', '未知文件')}")
        
    def _remove_dialog(self, dialog):
        """从活跃列表中移除弹窗"""
        if dialog in self.active_dialogs:
            self.active_dialogs.remove(dialog)
            
    def show_empty_dialog(self):
        """显示一个空的下载弹窗（用于手动添加下载）"""
        dialog = DownloadPopDialog()
        dialog.show()
        
        # 激活窗口
        dialog.raise_()
        dialog.activateWindow()
        
        # 保存弹窗引用
        self.active_dialogs.append(dialog)
        
        # 连接下载请求信号
        dialog.downloadRequested.connect(self._handle_manual_download)
        
        # 当弹窗关闭时移除引用
        dialog.destroyed.connect(lambda obj=dialog: self._remove_dialog(obj))
        
    def _handle_manual_download(self, task_data):
        """处理手动添加的下载"""
        # 创建下载弹窗
        dialog = DownloadPopDialog.create_and_show(task_data, auto_start=True)
        
        # 连接信号
        dialog.downloadCompleted.connect(self._on_download_completed)
        
        # 保存弹窗引用
        self.active_dialogs.append(dialog)
        
        # 当弹窗关闭时移除引用
        dialog.destroyed.connect(lambda obj=dialog: self._remove_dialog(obj))

# 主函数
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序属性，防止显示主窗口
    # PySide6中没有AA_DisableWindowContextHelpButton属性
    # 使用其他方式保持窗口在前
    
    # 初始化字体管理器
    font_manager = FontManager()
    font_manager.apply_font(app)
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "logo.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    
    # 创建下载处理器
    handler = PopupDownloadHandler()
    
    # 显示一个空的下载弹窗
    handler.show_empty_dialog()
    
    sys.exit(app.exec()) 