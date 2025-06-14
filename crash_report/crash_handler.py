#!/usr/bin/env python
"""
花火下载管理器崩溃处理程序

为主应用程序提供崩溃处理功能，捕获未处理的异常并显示崩溃报告。
"""

import sys
import os
import traceback
import logging
import threading
import tempfile
import json
from datetime import datetime

# 删除不兼容的导入
# from PySide6.QtWidgets import QApplication
# from PySide6.QtCore import QCoreApplication, Qt
# from .crash_dialog import CrashDialog

# 对话框UI需要延迟导入
_DIALOG_IMPORTED = False

# 全局变量
_original_hook = sys.excepthook
_crash_handlers = []
_app_instance = None
_crash_dialog = None
_settings = {
    "app_name": "花火下载管理器",
    "github_url": "https://github.com/buaoyezz/Hanabi-Download-Manager/issues",
    "silent_mode": False,
    "log_file": None
}

# 自定义异常类
class CrashHandlerError(Exception):
    """崩溃处理器相关异常"""
    pass

def _lazy_import_dialog():
    """延迟导入对话框模块"""
    global _DIALOG_IMPORTED
    
    if not _DIALOG_IMPORTED:
        try:
            # 尝试从同目录导入
            from . import crash_dialog
            _DIALOG_IMPORTED = True
            return crash_dialog
        except ImportError:
            try:
                # 直接导入
                import crash_dialog
                _DIALOG_IMPORTED = True
                return crash_dialog
            except ImportError as e:
                logging.error(f"无法导入崩溃对话框模块: {e}")
                return None
    return None

def _get_crash_info(exc_type, exc_value, exc_traceback):
    """收集崩溃信息
    
    Args:
        exc_type: 异常类型
        exc_value: 异常值
        exc_traceback: 异常回溯
        
    Returns:
        dict: 崩溃信息字典
    """
    # 格式化异常信息
    exception_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # 创建基本崩溃信息
    crash_info = {
        "app_name": _settings["app_name"],
        "timestamp": datetime.now().timestamp(),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": sys.version,
        "platform": sys.platform,
        "exception_type": exc_type.__name__,
        "exception_message": str(exc_value),
        "traceback": exception_str
    }
    
    # 尝试读取日志文件最后几行
    if _settings["log_file"] and os.path.exists(_settings["log_file"]):
        try:
            with open(_settings["log_file"], "r", encoding="utf-8", errors="replace") as f:
                # 读取最后20行日志
                lines = f.readlines()[-20:]
                crash_info["log_tail"] = "".join(lines)
        except Exception as e:
            crash_info["log_tail_error"] = f"读取日志失败: {e}"
    
    return crash_info

def _save_crash_dump(crash_info):
    """保存崩溃信息到临时文件
    
    Args:
        crash_info: 崩溃信息字典
        
    Returns:
        str: 临时文件路径，失败则返回None
    """
    try:
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="hanabi_crash_")
        os.close(fd)
        
        # 写入崩溃信息
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(crash_info, f, ensure_ascii=False, indent=2)
            
        return temp_path
    except Exception as e:
        logging.error(f"保存崩溃信息失败: {e}")
        return None

def _show_crash_dialog(crash_info):
    """显示崩溃对话框
    
    Args:
        crash_info: 崩溃信息字典
    """
    global _crash_dialog, _app_instance
    
    # 首先尝试使用PySide6对话框
    try:
        # 尝试从同目录导入
        from .crash_dialog import show_crash_dialog as show_qt_dialog
        
        # 构建原因和详情
        reason = f"{crash_info['exception_type']}: {crash_info['exception_message']}"
        details = crash_info["traceback"]
        if "log_tail" in crash_info:
            details += "\n\n日志文件最后内容:\n" + crash_info["log_tail"]
        
        # 保存崩溃信息到文件
        dump_path = _save_crash_dump(crash_info)
        if dump_path:
            details += f"\n\n崩溃信息已保存到: {dump_path}"
        
        # 显示PySide6对话框
        show_qt_dialog(
            reason=reason, 
            details=details, 
            github_url=_settings["github_url"]
        )
        return
    except ImportError:
        # Qt导入失败，尝试使用Tkinter备选方案
        logging.info("Qt UI导入失败，尝试使用Tkinter备选方案")
    except Exception as e:
        # 其他错误，记录日志并尝试Tkinter
        logging.error(f"Qt崩溃对话框失败: {e}")
    
    # 如果Qt方式失败，尝试Tkinter备选方案
    try:
        # 导入Tkinter对话框模块
        from .tkinter_dialog import show_crash_dialog as show_tk_dialog
        
        # 构建原因和详情
        reason = f"{crash_info['exception_type']}: {crash_info['exception_message']}"
        details = crash_info["traceback"]
        if "log_tail" in crash_info:
            details += "\n\n日志文件最后内容:\n" + crash_info["log_tail"]
        
        # 设置图标路径
        try:
            from .tkinter_dialog import set_app_icon
            # 尝试查找图标
            icon_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "logo.png"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "logo.png")
            ]
            for path in icon_paths:
                if os.path.exists(path):
                    set_app_icon(path)
                    break
        except Exception:
            pass
        
        # 显示Tkinter对话框
        show_tk_dialog(
            reason=reason, 
            details=details, 
            github_url=_settings["github_url"]
        )
        return
    except Exception as e:
        # 如果Tkinter也失败，回退到控制台输出
        logging.error(f"Tkinter崩溃对话框失败: {e}")
    
    # 所有图形界面方案都失败，使用控制台输出
    print("崩溃信息：", crash_info["exception_message"], file=sys.stderr)
    print(crash_info["traceback"], file=sys.stderr)

def _crash_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理钩子
    
    Args:
        exc_type: 异常类型
        exc_value: 异常值
        exc_traceback: 异常回溯
    """
    # 跳过键盘中断等特殊异常
    if issubclass(exc_type, KeyboardInterrupt):
        _original_hook(exc_type, exc_value, exc_traceback)
        return
    
    # 收集崩溃信息
    crash_info = _get_crash_info(exc_type, exc_value, exc_traceback)
    
    # 记录到日志
    logging.error(f"未处理的异常: {crash_info['exception_type']}: {crash_info['exception_message']}")
    logging.error(crash_info["traceback"])
    
    # 调用自定义处理程序
    for handler in _crash_handlers:
        try:
            handler(crash_info)
        except Exception as e:
            logging.error(f"调用自定义崩溃处理程序失败: {e}")
    
    # 如果不是静默模式，显示崩溃对话框
    if not _settings["silent_mode"]:
        # 在主线程中显示对话框
        if threading.current_thread() is threading.main_thread():
            _show_crash_dialog(crash_info)
        else:
            # 如果在子线程中崩溃，记录到日志但不显示对话框
            logging.error("子线程崩溃，无法显示对话框")
    
    # 调用原始的异常处理钩子
    _original_hook(exc_type, exc_value, exc_traceback)

def add_crash_handler(handler):
    """添加自定义崩溃处理函数
    
    Args:
        handler: 接收崩溃信息字典的函数
    """
    if callable(handler) and handler not in _crash_handlers:
        _crash_handlers.append(handler)

def configure(app_name=None, github_url=None, silent_mode=None, log_file=None):
    """配置崩溃处理器
    
    Args:
        app_name: 应用程序名称
        github_url: GitHub Issues URL
        silent_mode: 是否为静默模式
        log_file: 日志文件路径
    """
    if app_name is not None:
        _settings["app_name"] = app_name
    
    if github_url is not None:
        _settings["github_url"] = github_url
    
    if silent_mode is not None:
        _settings["silent_mode"] = bool(silent_mode)
    
    if log_file is not None:
        _settings["log_file"] = log_file

def install(app=None, silent_mode=False):
    """安装全局异常处理钩子
    
    Args:
        app: PySide6 QApplication实例(可选)
        silent_mode: 是否为静默模式
        
    Returns:
        bool: 安装是否成功
    """
    global _app_instance, _original_hook
    
    # 保存应用程序实例
    if app is not None:
        _app_instance = app
    
    # 设置静默模式
    _settings["silent_mode"] = silent_mode
    
    # 安装全局异常处理钩子
    try:
        _original_hook = sys.excepthook
        sys.excepthook = _crash_handler
        
        # 同时处理未捕获的线程异常
        threading.excepthook = lambda args: _crash_handler(args.exc_type, args.exc_value, args.exc_traceback)
        
        logging.debug("已安装崩溃处理钩子")
        return True
    except Exception as e:
        logging.error(f"安装崩溃处理钩子失败: {e}")
        return False

def uninstall():
    """卸载全局异常处理钩子
    
    Returns:
        bool: 卸载是否成功
    """
    global _original_hook
    
    try:
        if _original_hook:
            sys.excepthook = _original_hook
            logging.debug("已卸载崩溃处理钩子")
        return True
    except Exception as e:
        logging.error(f"卸载崩溃处理钩子失败: {e}")
        return False

# 测试函数
def test_crash():
    """触发一个测试崩溃"""
    raise RuntimeError("这是一个测试崩溃")

class CrashHandler:
    """崩溃处理程序
    
    使用全局异常钩子检测未捕获异常，显示崩溃报告对话框
    """
    
    _instance = None
    _lock = threading.Lock()
    _is_installed = False
    _original_hook = None
    _silent_mode = False
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化崩溃处理程序"""
        if CrashHandler._instance is not None:
            raise RuntimeError("CrashHandler是单例类，请使用get_instance()获取实例")
        
        self._original_hook = sys.excepthook
        self._restart_app = True
        self._main_app = None
    
    def install(self, app=None, silent_mode=False):
        """安装全局异常钩子
        
        Args:
            app: QApplication实例，用于重启程序
            silent_mode: 是否为静默模式，静默模式下只记录日志不显示界面
            
        Returns:
            bool: 安装结果
        """
        if CrashHandler._is_installed:
            return False
            
        # 保存应用实例和静默模式设置
        self._main_app = app
        CrashHandler._silent_mode = silent_mode
        
        # 安装异常钩子
        sys.excepthook = self._exception_hook
        
        # 安装线程异常钩子
        threading.excepthook = self._thread_exception_hook
        
        CrashHandler._is_installed = True
        return True
    
    def uninstall(self):
        """卸载全局异常钩子"""
        if not CrashHandler._is_installed:
            return False
            
        # 恢复原始钩子
        if self._original_hook is not None:
            sys.excepthook = self._original_hook
            
        CrashHandler._is_installed = False
        return True
    
    def _exception_hook(self, exc_type, exc_value, exc_traceback):
        """全局异常钩子函数
        
        捕获未处理异常，显示崩溃报告对话框
        """
        # 提取异常信息
        exception_info = self._get_exception_info(exc_type, exc_value, exc_traceback)
        
        # 记录异常到日志
        self._log_exception(exception_info)
        
        # 如果在静默模式下，只记录日志不显示界面
        if CrashHandler._silent_mode:
            # 调用原始异常处理
            if self._original_hook is not None:
                self._original_hook(exc_type, exc_value, exc_traceback)
            return
        
        # 在主线程中显示崩溃对话框
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QCoreApplication
            
            if QApplication.instance() is not None:
                # 在GUI环境中运行
                QCoreApplication.processEvents()
                self._show_crash_dialog(exception_info)
            else:
                # 在非GUI环境中打印异常
                print("程序发生严重错误：", file=sys.stderr)
                traceback.print_exception(exc_type, exc_value, exc_traceback)
        except ImportError:
            # 如果无法导入Qt，则简单打印异常
            print("程序发生严重错误：", file=sys.stderr)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
    
    def _thread_exception_hook(self, args):
        """线程异常钩子函数
        
        捕获线程中的未处理异常
        """
        # 提取异常信息
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        
        exception_info = self._get_exception_info(exc_type, exc_value, exc_traceback)
        
        # 记录异常到日志
        thread_name = args.thread.name
        self._log_exception(exception_info, thread_name)
        
        # 如果在静默模式下，只记录日志不显示界面
        if CrashHandler._silent_mode:
            return
        
        # 如果界面存在，则在主线程中显示崩溃对话框
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QCoreApplication
            
            if QApplication.instance() is not None:
                # 使用invokeMethod在主线程中显示对话框
                QCoreApplication.processEvents()
                
                # 创建一个函数来处理异常显示
                def show_thread_crash():
                    self._show_crash_dialog(exception_info, thread_name)
                
                # 在主线程中调用
                QApplication.instance().callLater(10, show_thread_crash)
        except ImportError:
            # 如果无法导入Qt，则简单记录异常
            print(f"线程 '{thread_name}' 发生未捕获异常:", file=sys.stderr)
            print(f"{exception_info['type']}: {exception_info['value']}", file=sys.stderr)
            print(exception_info['traceback'], file=sys.stderr)
    
    def _get_exception_info(self, exc_type, exc_value, exc_traceback):
        """获取异常信息
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
            exc_traceback: 异常跟踪信息
            
        Returns:
            dict: 包含异常信息的字典
        """
        exception_info = {
            'type': exc_type.__name__ if exc_type else "Unknown",
            'value': str(exc_value) if exc_value else "Unknown",
            'traceback': ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)) if exc_traceback else "No traceback available"
        }
        return exception_info
    
    def _log_exception(self, exception_info, thread_name=None):
        """记录异常信息到日志
        
        Args:
            exception_info: 异常信息字典
            thread_name: 线程名称
        """
        try:
            # 尝试使用应用程序的日志系统
            from core.log.log_manager import log
            if thread_name:
                log.critical(f"线程 '{thread_name}' 发生未捕获异常: {exception_info['type']}: {exception_info['value']}")
            else:
                log.critical(f"程序发生未捕获异常: {exception_info['type']}: {exception_info['value']}")
            log.critical(exception_info['traceback'])
        except ImportError:
            # 如果无法导入日志系统，使用简单的控制台输出
            if thread_name:
                print(f"线程 '{thread_name}' 发生未捕获异常:", file=sys.stderr)
            else:
                print("程序发生未捕获异常:", file=sys.stderr)
            print(f"{exception_info['type']}: {exception_info['value']}", file=sys.stderr)
            print(exception_info['traceback'], file=sys.stderr)
    
    def _show_crash_dialog(self, exception_info, thread_name=None):
        """显示崩溃报告对话框
        
        Args:
            exception_info: 异常信息字典
            thread_name: 线程名称
        """
        # 使用新的崩溃对话框API
        try:
            # 从同包导入崩溃对话框模块
            from .crash_dialog import show_crash_dialog
            
            # 构建原因和详情
            reason = f"{exception_info['type']}: {exception_info['value']}"
            details = exception_info['traceback']
            
            # 如果有线程信息，添加到详情中
            if thread_name:
                details = f"线程 '{thread_name}' 中的异常:\n\n" + details
            
            # 显示崩溃对话框
            show_crash_dialog(reason=reason, details=details)
        except ImportError as e:
            # 如果导入失败，打印错误
            print(f"无法显示崩溃对话框: {e}", file=sys.stderr)
            print(f"崩溃信息: {exception_info['type']}: {exception_info['value']}", file=sys.stderr)
            print(exception_info['traceback'], file=sys.stderr)
    
    def _restart_application(self):
        """重启应用程序"""
        # 检查是否有可重启的应用程序
        if not self._main_app:
            return
        
        # 使用新的函数重启应用程序
        try:
            from .crash_dialog import _restart_application
            _restart_application()
        except ImportError:
            # 如果无法导入重启函数，尝试自己实现
            try:
                # 获取程序路径和启动参数
                app_path = sys.executable
                args = sys.argv[:]
                
                # 确保不进入静默模式重启
                if '--silent' in args:
                    args.remove('--silent')
                    
                # 要在新进程中启动程序，在父进程退出后
                import subprocess
                
                # 在Windows上，使用startupinfo隐藏控制台窗口
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0  # SW_HIDE
                    
                # 启动新进程
                subprocess.Popen([app_path] + args[1:], startupinfo=startupinfo)
                
                # 结束当前进程
                sys.exit(0)
            except Exception as e:
                print(f"重启应用程序失败: {e}", file=sys.stderr) 