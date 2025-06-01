import sys
import os
import time
import argparse  # 导入参数解析模块
# 设置环境变量以过滤Qt的字体警告日志
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont, QIcon
from PySide6.QtCore import QObject, Signal, Slot, Qt, QTimer
from client.ui.client_interface.main_window import DownloadManagerWindow
# 使用FallbackConnector作为默认连接器
from connect.fallback_connector import FallbackConnector as Connector
print("使用FallbackConnector")
from core.font.font_manager import FontManager
from core.log.log_manager import log
from client.ui.extension_interface.pop_dialog import DownloadPopDialog
from client.version.version_manager import VersionManager

# 初始化版本管理器
version_manager = VersionManager.get_instance()

# 命令行参数解析函数
def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Hanabi Download Manager')
    parser.add_argument('--debug_windows', action='store_true', 
                        help='显示调试日志窗口')
    parser.add_argument('--version', action='store_true',
                        help='显示版本信息')
    
    # 添加更多可能的参数
    parser.add_argument('--no_browser_extension', action='store_true',
                        help='禁用浏览器扩展连接')
    parser.add_argument('--config', type=str, metavar='FILE',
                        help='指定配置文件路径')
    
    return parser.parse_args()

# 创建一个全局处理器，用于处理浏览器下载请求
class BrowserDownloadHandler(QObject):
    # 定义信号
    downloadRequested = Signal(dict)
    downloadCompleted = Signal(dict)  # 新增完成信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_dialogs = []  # 保存活跃的弹窗列表
        self.active_requests = {}  # 追踪活跃的下载请求
        
        # BrowserDownloadHandler 继承自 QObject，不是 QWidget
        # 所以不能使用 setAttribute 方法
        
    @Slot(dict)
    def handle_download_request(self, download_data):
        """处理浏览器下载请求"""
        try:
            # 获取请求ID，用于跟踪和避免重复处理
            request_id = download_data.get("requestId", "")
            if not request_id:
                request_id = f"ext_{int(time.time() * 1000)}"
                download_data["requestId"] = request_id
                
            log.info(f"收到浏览器下载请求 [ID: {request_id}]: {download_data.get('url', '未知URL')}")
            
            # 检查是否重复请求
            if request_id in self.active_requests:
                log.warning(f"跳过重复的下载请求 [ID: {request_id}]")
                return False
                
            # 跟踪此请求
            self.active_requests[request_id] = {
                "url": download_data.get("url", ""),
                "timestamp": time.time()
            }
            
            # 自动开始下载，不必每次都弹出确认窗口
            url = download_data.get("url", "")
            if not url:
                log.error(f"处理下载请求失败 [ID: {request_id}]: URL为空")
                self.active_requests.pop(request_id, None)
                return False
            
            # 创建任务数据
            task_data = {
                "url": url,
                "file_name": download_data.get("filename", ""),
                "save_path": os.path.expanduser("~/Downloads"), # 使用默认下载路径
                "multi_thread": True,
                "source": "browser",
                "request_id": request_id,
                "headers": download_data.get("headers", {})
            }
            
            # 添加Referer支持
            if "referrer" in download_data and "headers" in task_data:
                if "Referer" not in task_data["headers"]:
                    task_data["headers"]["Referer"] = download_data["referrer"]
            
            # 获取父窗口引用，检查其状态
            parent_window = None
            if hasattr(self, 'parent') and self.parent():
                parent_window = self.parent()
                
            # 检查主窗口最小化状态
            parent_minimized = False
            if parent_window and hasattr(parent_window, 'isMinimized'):
                try:
                    parent_minimized = parent_window.isMinimized()
                except Exception:
                    pass
            
            # 创建弹窗 - 优化后的创建方式
            # DownloadPopDialog.create_and_show 方法会根据最小化状态正确处理父窗口关系
            dialog = DownloadPopDialog.create_and_show(task_data, parent=parent_window, auto_start=False)
            
            # 确保弹窗记录了主窗口最小化的状态
            if dialog:
                # 额外确保正确记录了最小化状态
                dialog.parent_was_minimized = parent_minimized
                
                # 显式设置不要在关闭时退出应用程序 - 弹窗不应影响应用生命周期
                if hasattr(dialog, 'setAttribute') and hasattr(Qt, 'WA_QuitOnClose'):
                    dialog.setAttribute(Qt.WA_QuitOnClose, False)
                
                # 使用弱引用保存弹窗，避免循环引用
                import weakref
                self.active_dialogs.append(weakref.ref(dialog))
                
                # 连接下载完成信号 - 确保使用Qt.QueuedConnection避免阻塞
                dialog.downloadCompleted.connect(self._on_download_completed, Qt.QueuedConnection)
                
                # 当弹窗关闭时从列表中移除 - 使用QueuedConnection确保在UI线程处理
                # 使用lambda捕获当前值，避免引用变化
                dialog.destroyed.connect(
                    lambda obj=None, dlg=dialog, req_id=request_id: self._remove_dialog(dlg, req_id), 
                    Qt.QueuedConnection
                )
                
                log.info(f"已为下载请求 [ID: {request_id}] 创建下载弹窗")
                return True
            else:
                log.error(f"创建下载弹窗失败 [ID: {request_id}]")
                return False
                
        except Exception as e:
            log.error(f"处理下载请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @Slot(dict)
    def _on_download_completed(self, task_data):
        """下载完成处理 - 使用更稳定的通知处理"""
        request_id = task_data.get("request_id", "")
        log.info(f"下载完成 [ID: {request_id}]: {task_data.get('file_name', '未知文件')}")
        
        # 清理请求跟踪
        if request_id:
            self.active_requests.pop(request_id, None)
            
        try:
            # 确保通知不会堆叠在一起，使用更长的延迟
            delay = 500  # 增加延迟以确保之前的通知已经完全显示
            QTimer.singleShot(delay, lambda: self._emit_completion_signal(task_data))
        except Exception as e:
            log.error(f"设置延迟显示通知失败: {e}")
            # 直接发射信号作为备份方案
            self.downloadCompleted.emit(task_data)
    
    def _emit_completion_signal(self, task_data):
        """安全发射完成信号，确保进行正确的线程处理"""
        try:
            # 在主线程上下文中发射信号
            self.downloadCompleted.emit(task_data)
        except Exception as e:
            log.error(f"发射下载完成信号失败: {e}")
    
    def _remove_dialog(self, dialog, request_id=None):
        """从活跃列表中移除弹窗 - 优化引用管理"""
        try:
            # 清理弱引用 - 使用更安全的列表复制方法
            self.active_dialogs = [ref for ref in self.active_dialogs if ref() is not None and ref() != dialog]
                
            # 清理请求跟踪
            if request_id and request_id in self.active_requests:
                self.active_requests.pop(request_id, None)
                log.debug(f"已清理下载请求跟踪 [ID: {request_id}]")
                
            # 强制垃圾回收，确保资源被释放
            import gc
            gc.collect()
                
        except Exception as e:
            # 确保即使出错也不会影响主程序
            log.error(f"清理弹窗引用时出错: {e}")

if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()
    
    # 处理版本信息参数
    if args.version:
        print(f"花火下载管理器 v{version_manager.get_client_version()}")
        print(f"浏览器扩展版本: v{version_manager.get_extension_version()}")
        sys.exit(0)
    
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "logo.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        log.info(f"已设置应用图标: {icon_path}")
    else:
        log.warning(f"图标文件不存在: {icon_path}")
    
    # 先记录系统字体情况
    system_fonts = QFontDatabase.families()
    log.info(f"系统可用字体数量: {len(system_fonts)}")
    log.info(f"常用字体是否可用: Microsoft YaHei: {'Microsoft YaHei' in system_fonts}, "
             f"Arial: {'Arial' in system_fonts}, SimSun: {'SimSun' in system_fonts}")
    
    # 初始化字体管理器 - 这应该在所有其他字体设置之前
    # 让FontManager加载和注册外部字体
    font_manager = FontManager()
    
    # 设置应用默认等宽字体，避免使用Fixedsys
    available_monospace = ["Consolas", "Courier New", "Source Code Pro", "SimSun"]
    
    for font_name in available_monospace:
        if font_name in system_fonts:
            mono_font = QFont(font_name, 10)
            app.setFont(mono_font, "QFontDialog::FixedFont")
            log.info(f"已设置默认等宽字体: {font_name}")
            break
    
    # 现在我们让FontManager来处理应用字体设置
    # 它会使用已注册的外部字体
    font_manager.apply_font(app)
    
    # 再次检查字体注册情况
    updated_fonts = QFontDatabase.families()
    log.info(f"字体管理器加载后字体数: {len(updated_fonts)}")
    
    # 记录新增加的字体
    new_fonts = set(updated_fonts) - set(system_fonts)
    if new_fonts:
        log.info(f"新加载的字体: {', '.join(new_fonts)}")
    
    # 创建下载请求处理器
    download_handler = BrowserDownloadHandler()
    
    # 记录版本信息
    log.info(f"花火下载管理器 v{version_manager.get_client_version()}")
    log.info(f"浏览器扩展版本: v{version_manager.get_extension_version()}")
    
    # 创建主窗口
    window = DownloadManagerWindow()
    
    # 检查是否应该启动时最小化到托盘
    from client.ui.client_interface.settings.config import ConfigManager
    config = ConfigManager()
    start_minimized = config.get_setting("window", "start_minimized", False)
    
    # 如果指定了--debug_windows参数，显示日志窗口
    if args.debug_windows:
        try:
            from core.log.log_window import LogWindow
            log_window = LogWindow()
            log_window.show()
            log.info("已启用调试日志窗口")
        except Exception as e:
            log.error(f"无法启动日志窗口: {e}")
    
    # 如果指定了禁用浏览器扩展参数
    if args.no_browser_extension:
        log.info("已禁用浏览器扩展连接")
    else:
        try:
            # 创建连接器，只连接到一个处理器，避免重复处理
            connector = Connector()
            
            # 选择一个处理方式：
            # 1. 使用全局处理器 - 创建独立下载弹窗，不会拉起主窗口[推荐]
            connector.downloadRequestReceived.connect(download_handler.handle_download_request)
            
            # 2. 使用主窗口的下载窗口处理 - 会在主窗口中显示下载任务[拉起主窗口不推荐]
            # if hasattr(window, 'download_window'):
            #     connector.downloadRequestReceived.connect(window.download_window.handle_browser_download_request)
            
            connector.start()
            log.info("浏览器下载连接器已成功启动")
        except Exception as e:
            log.error(f"启动浏览器下载连接器失败: {e}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: window.init_browser_download_listener())
    
    if start_minimized:
        log.info("根据设置，应用将在启动时最小化到托盘")
        # 先显示窗口以确保正确初始化
        window.show()
        # 然后最小化到托盘
        QTimer.singleShot(500, window.on_minimize_to_tray)
    else:
        # 正常显示窗口
        window.show()
    
    sys.exit(app.exec())
