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
from core.autoboot.silent_mode import is_silent_mode, SILENT_ARG
from core.autoboot.auto_boot import add_to_startup, remove_from_startup
# 导入崩溃处理程序
from crash_report import install_crash_handler, configure_crash_handler

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
    parser.add_argument('--silent', action='store_true',
                        help='静默启动模式，启动时最小化到系统托盘')
    parser.add_argument('--no_crash_report', action='store_true',
                        help='禁用崩溃报告')
    parser.add_argument('--autostart', action='store_true',
                        help='添加到Windows启动项')
    parser.add_argument('--no-autostart', action='store_true',
                        help='从Windows启动项移除')
    
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
                log.info(f"AS_Kernel: 已为下载请求 [ID: {request_id}] 选择下载核心 [Kernel: {task_data.get('kernel', 'Unknown')}]")
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
            # 检查对话框对象是否已被删除
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            if dialog and hasattr(DownloadPopDialog, '_is_destroyed'):
                if not DownloadPopDialog._is_destroyed(dialog):
                    log.debug(f"弹窗对象 [ID: {request_id}] 仍然有效")
                else:
                    log.debug(f"弹窗对象 [ID: {request_id}] 已被删除")
            
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
            import traceback
            log.debug(traceback.format_exc())

if __name__ == "__main__":
    # 解析命令行参数
    args = parse_arguments()
    
    # 处理版本信息参数
    if args.version:
        print(f"Hanabi Download Manager v{version_manager.get_client_version()}")
        print(f"浏览器扩展版本: v{version_manager.get_extension_version()}")
        sys.exit(0)
    
    # 处理自启动参数
    if args.autostart:
        from core.autoboot.auto_boot import add_to_startup
        success = add_to_startup(True)  # 默认使用静默模式
        print(f"添加到启动项{'成功' if success else '失败'}")
        sys.exit(0 if success else 1)
        
    if getattr(args, 'no_autostart', False):  # 使用getattr避免属性不存在的错误
        from core.autoboot.auto_boot import remove_from_startup
        success = remove_from_startup()
        print(f"从启动项移除{'成功' if success else '失败'}")
        sys.exit(0 if success else 1)
    
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    
    # Disable button focus
    app.setStyleSheet("""
        QPushButton:focus {
            outline: none;
            border: none;
        }
        QToolButton:focus {
            outline: none;
            border: none;
        }
    """)
    # 记录禁用按钮焦点效果
    log.info("已禁用按钮焦点效果")
    
    # 检查是否处于静默模式
    silent_mode = is_silent_mode()  # 不传递参数，让函数自己从sys.argv获取
    
    # 安装崩溃处理程序 - 除非显式禁用
    if not args.no_crash_report:
        # 确保崩溃处理程序在日志初始化后启动
        try:
            # 先导入必要的模块
            from crash_report import install_crash_handler, configure_crash_handler
            
            # 设置崩溃处理程序配置
            configure_crash_handler(
                app_name="花火下载管理器",
                github_url="https://github.com/buaoyezz/Hanabi-Download-Manager/issues",
                silent_mode=silent_mode,
                # 指定日志文件路径，确保崩溃报告能包含日志内容
                log_file=log.get_log_file_path()
            )
            
            # 安装崩溃处理钩子
            installed = install_crash_handler(app, silent_mode)
            if installed:
                log.info("已安装崩溃报告程序")
                
                # 根据需要设置自定义崩溃处理函数
                def custom_crash_handler(crash_info):
                    """自定义崩溃处理函数，在崩溃时执行额外操作"""
                    try:
                        log.critical(f"程序崩溃: {crash_info['exception_type']}: {crash_info['exception_message']}")
                        
                        # 尝试保存系统状态信息
                        if hasattr(window, 'save_current_state') and callable(window.save_current_state):
                            log.info("尝试保存当前程序状态...")
                            window.save_current_state()
                    except Exception:
                        pass  # 安全处理自定义处理器异常
                    
                # 添加自定义处理器
                from crash_report import add_crash_handler
                add_crash_handler(custom_crash_handler)
            else:
                log.warning("无法安装崩溃报告程序")
        except ImportError as e:
            log.error(f"导入崩溃处理模块失败: {e}")
        except Exception as e:
            log.error(f"安装崩溃处理程序失败: {e}")
            import traceback
            log.debug(traceback.format_exc())
    
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
    log.info(f"Hanabi Download Manager v{version_manager.get_client_version()}")
    log.info(f"浏览器扩展版本: v{version_manager.get_extension_version()}")
    
    # 启动HTTP状态服务器
    try:
        from connect.http_status_server import get_status_server
        status_server = get_status_server()
        status_server.start()
        log.info("HTTP状态服务器已启动")
    except Exception as e:
        log.error(f"启动HTTP状态服务器失败: {e}")
    
    # 创建主窗口
    window = DownloadManagerWindow()
    
    # 添加直接连接到浏览器扩展的方法
    def force_connect_to_extension():
        """强制连接到浏览器扩展，直接创建连接并发送信号"""
        try:
            # 尝试直接创建TCP客户端连接到浏览器扩展
            import socket
            import json
            import time
            
            # 创建TCP连接
            client = None
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(3)  # 设置3秒超时
                
                # 连接到扩展监听的端口 (Chrome扩展监听20971端口)
                client.connect(("localhost", 20971))
                
                # 构建alive消息
                alive_message = {
                    "type": "alive",
                    "timestamp": int(time.time() * 1000),
                    "ClientVersion": version_manager.get_client_version(),
                    "message": "HDM客户端已连接",
                    "status": "online"
                }
                
                # 发送消息
                message_data = json.dumps(alive_message) + "\n"
                client.sendall(message_data.encode("utf-8"))
                log.info("已直接发送alive信号到浏览器扩展端口")
                
                # 等待响应
                try:
                    response = client.recv(1024).decode("utf-8")
                    log.info(f"收到扩展响应: {response}")
                    return True
                except (socket.timeout, ConnectionResetError) as e:
                    log.warning(f"等待扩展响应时出错: {e}")
                    return False
            except (ConnectionRefusedError, socket.timeout, ConnectionResetError) as e:
                log.warning(f"直接连接扩展失败: {e}")
                return False
            finally:
                # 确保socket在任何情况下都能正确关闭
                if client:
                    try:
                        client.shutdown(socket.SHUT_RDWR)
                    except (OSError, socket.error, ConnectionResetError) as e:
                        # 忽略关闭时的错误
                        pass
                    finally:
                        try:
                            client.close()
                        except (OSError, socket.error):
                            pass
        except Exception as e:
            log.error(f"强制连接到扩展时出错: {e}")
        
        # 尝试通过已有连接器发送信号
        try:
            if hasattr(window, 'browser_connector') and window.browser_connector:
                window.browser_connector._send_alive_signal_now()
                log.info("通过连接器发送了alive信号")
                return True
        except Exception as e:
            log.error(f"通过连接器发送信号失败: {e}")
        
        return False
    
    # 保存方法到窗口对象
    window.force_connect_to_extension = force_connect_to_extension
    
    # 添加检查连接状态的方法
    def check_extension_connection():
        """检查浏览器扩展连接状态，返回是否已连接"""
        try:
            # 尝试通过HTTP状态服务器检查扩展连接状态
            import requests
            try:
                # 使用更短的超时时间避免长时间等待
                response = requests.get("http://localhost:20972/status", timeout=0.5)
                if response.status_code == 200:
                    data = response.json()
                    # 如果状态服务器正常，还需进一步检查扩展是否连接
                    # 尝试向扩展发送测试请求
                    import socket
                    test_socket = None
                    try:
                        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        test_socket.settimeout(1)  # 快速测试，1秒超时
                        test_socket.connect(("localhost", 20971))
                        # 能够连接表示扩展处于正常状态
                        return True
                    except (ConnectionRefusedError, socket.timeout, ConnectionResetError) as e:
                        # 连接失败，表示扩展未连接
                        log.debug(f"扩展连接测试失败: {e}")
                        return False
                    finally:
                        # 确保socket在任何情况下都能正确关闭
                        if test_socket:
                            try:
                                test_socket.shutdown(socket.SHUT_RDWR)
                            except (OSError, socket.error, ConnectionResetError) as e:
                                # 忽略关闭时的错误
                                pass
                            finally:
                                try:
                                    test_socket.close()
                                except (OSError, socket.error):
                                    pass
            except requests.RequestException as e:
                # HTTP请求失败，认为连接不可用
                log.debug(f"HTTP状态检查失败: {e}")
                # 尝试直接socket连接作为备用检测方式
                import socket
                test_socket = None
                try:
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(0.5)  # 使用更短的超时时间
                    test_socket.connect(("localhost", 20971))
                    # 能够连接表示扩展处于正常状态
                    log.debug("HTTP检查失败但直接socket连接成功")
                    return True
                except (ConnectionRefusedError, socket.timeout, ConnectionResetError) as e:
                    # 连接失败，表示扩展未连接
                    log.debug(f"备用socket连接检测也失败: {e}")
                    return False
                finally:
                    # 确保socket在任何情况下都能正确关闭
                    if test_socket:
                        try:
                            test_socket.shutdown(socket.SHUT_RDWR)
                        except (OSError, socket.error, ConnectionResetError) as e:
                            # 忽略关闭时的错误
                            pass
                        finally:
                            try:
                                test_socket.close()
                            except (OSError, socket.error):
                                pass
        except Exception as e:
            log.debug(f"检查扩展连接状态时出错: {e}")
        
        # 默认假设连接丢失
        return False
    
    # 保存方法到窗口对象
    window.check_extension_connection = check_extension_connection
    
    # 启动后立即尝试强制连接
    QTimer.singleShot(2000, force_connect_to_extension)
    
    # 创建一个定时器，定期检查浏览器扩展连接状态，只在丢失连接时发送alive信号
    browser_connection_timer = QTimer()
    browser_connection_timer.setInterval(15000)  # 每15秒检查一次
    
    def check_browser_connection():
        """检查浏览器连接状态，只在连接丢失时发送alive信号"""
        try:
            # 首先检查连接状态
            is_connected = window.check_extension_connection()
            
            if not is_connected:
                # 只在连接丢失时才发送alive信号
                log.info("Connect Status: Offline, Sending alive signal")
                result = window.force_connect_to_extension()
                if result:
                    log.info("Alive信号发送成功，等待下次检查确认连接状态")
                else:
                    log.warning("Alive信号发送失败，将在下次检查时重试")
            else:
                log.debug("Connect Status: Online, No need to send alive signal")
        except Exception as e:
            log.error(f"检查连接状态时出错: {e}")
            # 出错时默认发送alive信号，确保连接恢复
            try:
                window.force_connect_to_extension()
            except Exception as e2:
                log.error(f"尝试恢复连接时出错: {e2}")
    
    # 连接定时器信号
    browser_connection_timer.timeout.connect(check_browser_connection)
    # 启动定时器
    browser_connection_timer.start()
    
    # 保存定时器到窗口，避免被垃圾回收
    window.browser_connection_timer = browser_connection_timer
    
    # 如果窗口有"立即连接"按钮，添加点击事件处理
    if hasattr(window, 'ui') and hasattr(window.ui, 'reconnectButton'):
        def on_reconnect_button_clicked():
            """处理立即连接按钮点击"""
            log.info("用户点击了立即连接按钮")
            
            # 先检查当前连接状态
            is_connected = window.check_extension_connection()
            
            if is_connected:
                log.info("扩展已连接，无需重新连接")
                # 显示提示
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(window, "连接状态", "浏览器扩展已连接，无需重新连接")
                except Exception as e:
                    log.error(f"显示连接状态提示时出错: {e}")
            else:
                log.info("扩展未连接，尝试强制连接")
                # 使用强制连接方法
                success = window.force_connect_to_extension()
                
                if success:
                    log.info("已成功发送连接信号到浏览器扩展")
                    # 显示连接成功提示
                    try:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.information(window, "连接状态", "已成功连接到浏览器扩展")
                    except Exception as e:
                        log.error(f"显示连接成功提示时出错: {e}")
                else:
                    log.warning("未能成功连接到浏览器扩展")
                    # 显示连接失败提示
                    try:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(window, "连接状态", "未能连接到浏览器扩展，请确保浏览器已启动")
                    except Exception as e:
                        log.error(f"显示连接失败提示时出错: {e}")
                    
                    # 再次尝试使用连接器发送信号
                    if hasattr(window, 'browser_connector') and window.browser_connector:
                        try:
                            window.browser_connector._send_alive_signal_now()
                            log.info("已通过连接器重试发送alive信号")
                        except Exception as e:
                            log.error(f"重试发送alive信号时出错: {e}")
        
        # 连接按钮点击信号
        window.ui.reconnectButton.clicked.connect(on_reconnect_button_clicked)
        log.info("已连接立即连接按钮点击事件")
    
    # 检查是否应该启动时最小化到托盘
    from client.ui.client_interface.settings.config import ConfigManager
    config = ConfigManager()
    
    # 检查是否指定了静默启动参数 - 优先级最高
    silent_mode = is_silent_mode()
    
    # 从配置中获取启动设置 - 仅当没有静默模式参数时才检查
    start_minimized = False
    if not silent_mode:
        # 只有当命令行没有指定--silent参数时，才检查配置
        start_minimized = config.get_setting("window", "start_minimized", False)
    else:
        # 命令行指定了--silent参数，强制设为True
        start_minimized = True
        log.info("检测到静默启动参数，应用将在启动时最小化到托盘")
    
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
            
            # 启动后立即发送alive信号，确保浏览器扩展能够立即检测到连接
            QTimer.singleShot(1000, lambda: connector._send_alive_signal_now())
            
            # 再设置一个延迟，确保信号能被接收
            QTimer.singleShot(3000, lambda: connector._send_alive_signal_now())
            
            # 将连接器保存到全局变量，避免被垃圾回收
            window.browser_connector = connector
        except Exception as e:
            log.error(f"启动浏览器下载连接器失败: {e}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: window.init_browser_download_listener())
    
    if start_minimized:
        log.info("应用将在启动时最小化到托盘")
        # 修改启动逻辑，避免窗口闪烁
        # 1. 不先显示窗口，直接设置窗口为隐藏状态
        window.hide()
        # 2. 确保托盘图标可见
        if hasattr(window.title_bar, 'tray_icon'):
            window.title_bar.tray_icon.show()
        # 3. 触发托盘最小化逻辑，确保系统托盘功能正常
        QTimer.singleShot(100, lambda: window.title_bar.minimize_to_tray())
    else:
        # 正常显示窗口
        window.show()
    
    sys.exit(app.exec())
