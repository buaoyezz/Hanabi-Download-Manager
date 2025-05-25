import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import time
import threading
from typing import Optional
import colorama
from colorama import Fore, Style

class ColoredFormatter(logging.Formatter):
    
    COLORS = {
        'DEBUG': '',  # 软件内不使用颜色
        'INFO': '',
        'WARNING': '',
        'ERROR': '',
        'CRITICAL': '',
    }
    
    def __init__(self, fmt: str, datefmt: Optional[str] = None, use_colors: bool = True):
        # 修改格式化字符串，使用固定宽度
        fmt = ('[%(asctime)s] │ %(levelname)-8s │ %(pathname)-25s:%(lineno)-4d │ %(message)s')
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors
        if use_colors:
            colorama.init()
            self.COLORS = {
                'DEBUG': Fore.CYAN,
                'INFO': Fore.GREEN,
                'WARNING': Fore.YELLOW,
                'ERROR': Fore.RED,
                'CRITICAL': Fore.RED + Style.BRIGHT,
            }
    
    def format(self, record: logging.LogRecord) -> str:
        # 保存原始的属性
        original_levelname = record.levelname
        original_pathname = record.pathname
        
        # 获取实际的调用文件信息
        if hasattr(record, 'pathname'):
            import inspect
            frame = inspect.currentframe()
            caller_frame = None
            
            while frame:
                module_name = frame.f_globals.get('__name__', '')
                if (not module_name.startswith('logging') and 
                    not module_name.startswith('core.log')):
                    caller_frame = frame
                    break
                frame = frame.f_back
            
            if caller_frame:
                filename = os.path.basename(caller_frame.f_code.co_filename)
                # 确保文件名不超过25个字符，如果超过则截断
                if len(filename) > 25:
                    filename = filename[:22] + "..."
                record.pathname = filename
                record.lineno = caller_frame.f_lineno
        
        # 根据是否使用颜色来格式化
        if self.use_colors:
            if record.levelname in self.COLORS:
                record.levelname = (f"{self.COLORS[record.levelname]}"
                                  f"{record.levelname}"
                                  f"{Style.RESET_ALL}")
            record.pathname = f"{Fore.BLUE}{record.pathname}{Style.RESET_ALL}"
        
        # 格式化消息
        result = super().format(record)
        
        # 恢复原始属性
        record.levelname = original_levelname
        record.pathname = original_pathname
        
        return result

class LogManager:
    _instance = None
    _initialized = False
    _active_filters = set()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LogManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LogManager._initialized:
            return
            
        LogManager._initialized = True
        
        # 创建日志目录
        self.log_dir = os.path.join(os.path.expanduser('~'), '.hanabidownloadmanager', 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建日志文件名
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.log_file = os.path.join(self.log_dir, f'hanabidownloadmanager_{current_time}.log')
        
        # 创建主日志记录器
        self.logger = logging.getLogger('HanabiDownloadManager')
        self.logger.setLevel(logging.DEBUG)
        
        # 清除可能存在的处理器
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # 创建两种格式化器
        console_formatter = ColoredFormatter(
            '[%(asctime)s] │ %(levelname)s │ %(pathname)s:%(lineno)s │ %(message)s',  
            datefmt='%H:%M:%S',
            use_colors=True  # 控制台使用颜色
        )
        
        file_formatter = ColoredFormatter(
            '[%(asctime)s] │ %(levelname)s │ %(pathname)s:%(lineno)s │ %(message)s',  
            datefmt='%H:%M:%S',
            use_colors=False  # 文件不使用颜色
        )
        
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 修改过滤器实现
        class LevelFilter(logging.Filter):
            def __init__(self, log_manager):
                super().__init__()
                self.log_manager = log_manager

            def filter(self, record):
                # 检查是否应该显示此记录
                if not self.log_manager._active_filters:
                    return True  # 没有过滤器时显示所有日志
                
                return record.levelname in self.log_manager._active_filters

        # 为每个处理器添加过滤器
        self.level_filter = LevelFilter(self)
        for handler in self.logger.handlers:
            handler.addFilter(self.level_filter)
        
        # 添加观察者支持
        self.observers = []
        
        # 启动信息
        self.info("="*50)
        self.info("日志系统初始化完成")
        self.info(f"日志文件路径: {self.log_file}")
        self.info("="*50)
        
        # 启动日志清理
        self._setup_log_cleanup()
    
    def debug(self, message: str) -> None:
        self.logger.debug(message)
        self._notify_observers('DEBUG', message)
    
    def info(self, message: str) -> None:
        self.logger.info(message)
        self._notify_observers('INFO', message)
    
    def warning(self, message: str) -> None:
        self.logger.warning(message)
        self._notify_observers('WARNING', message)
    
    def error(self, message: str) -> None:
        self.logger.error(message)
        self._notify_observers('ERROR', message)
    
    def critical(self, message: str) -> None:
        self.logger.critical(message)
        self._notify_observers('CRITICAL', message)
    
    def exception(self, message: str) -> None:
        self.logger.exception(message)
        self._notify_observers('ERROR', f"{message} (Exception)\n{sys.exc_info()[1]}")
    
    # 观察者模式支持
    def add_observer(self, observer):
        """添加日志观察者
        
        Args:
            observer: 观察者对象，必须实现on_log方法
        """
        if observer not in self.observers and hasattr(observer, 'on_log'):
            self.observers.append(observer)
            # 直接使用logger打印，避免循环调用
            self.logger.debug(f"添加日志观察者: {observer}")
            return True
        return False
    
    def remove_observer(self, observer):
        """移除日志观察者
        
        Args:
            observer: 要移除的观察者对象
        """
        if observer in self.observers:
            self.observers.remove(observer)
            return True
        return False
    
    def _notify_observers(self, level, message):
        """通知所有观察者
        
        Args:
            level: 日志级别
            message: 日志消息
        """
        # 获取调用者信息
        import inspect
        frame = inspect.currentframe().f_back
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = frame.f_lineno
        
        # 当前时间戳
        timestamp = time.time()
        
        # 通知每个观察者
        for observer in self.observers[:]:  # 使用副本避免迭代时修改
            try:
                observer.on_log(level, timestamp, filename, message)
            except Exception as e:
                # 避免在通知过程中的异常影响其他观察者
                print(f"通知观察者时出错: {e}")
    
    def get_logger(self) -> logging.Logger:
        return self.logger
    
    def set_level_filter(self, level: str) -> None:
        """设置日志等级过滤器
        
        Args:
            level: 日志等级 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'ALL')
        """
        # 清除之前的过滤器
        self._active_filters.clear()
        
        # 如果不是 ALL，则设置新的过滤级别
        if level != 'ALL':
            self._active_filters.add(level)
            
        # 强制更新处理器的过滤器
        for handler in self.logger.handlers:
            handler.removeFilter(self.level_filter)
            handler.addFilter(self.level_filter)
    
    def _setup_log_cleanup(self):
        """设置日志清理定时器"""
        # 立即清理一次旧日志
        self.cleanup_old_logs()
        
        # 创建定时器线程，每天清理一次
        cleanup_thread = threading.Thread(target=self._log_cleanup_scheduler, daemon=True)
        cleanup_thread.start()
        self.info("日志自动清理功能已启动")
    
    def _log_cleanup_scheduler(self):
        """日志清理定时调度器"""
        while True:
            # 计算下一次清理时间（每天凌晨3点）
            now = datetime.now()
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            
            # 计算等待时间
            wait_seconds = (next_run - now).total_seconds()
            
            # 等待到下一次清理时间
            time.sleep(wait_seconds)
            
            # 执行清理
            try:
                self.cleanup_old_logs()
            except Exception as e:
                self.error(f"日志清理失败: {e}")
    
    def cleanup_old_logs(self, max_age_days=7, max_files=30):
        """清理旧的日志文件
        
        Args:
            max_age_days: 保留日志的最大天数，默认7天
            max_files: 保留日志的最大文件数，默认30个
        """
        try:
            self.info(f"开始清理旧日志文件，保留{max_age_days}天内的日志，最多保留{max_files}个文件")
            
            # 确保日志目录存在
            if not os.path.exists(self.log_dir):
                self.warning(f"日志目录不存在: {self.log_dir}")
                return
            
            # 获取所有日志文件
            log_files = []
            for filename in os.listdir(self.log_dir):
                if filename.startswith('hanabidownloadmanager_') and filename.endswith('.log'):
                    file_path = os.path.join(self.log_dir, filename)
                    if os.path.isfile(file_path):
                        # 获取文件创建时间
                        file_time = os.path.getctime(file_path)
                        log_files.append((file_path, file_time))
            
            # 按时间排序，最新的在前
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # 计算截止日期
            cutoff_date = time.time() - (max_age_days * 24 * 60 * 60)
            
            # 保留当前使用的日志文件
            current_log = os.path.abspath(self.log_file)
            
            # 要删除的文件
            files_to_delete = []
            
            # 检查每个文件
            for i, (file_path, file_time) in enumerate(log_files):
                file_path_abs = os.path.abspath(file_path)
                
                # 跳过当前正在使用的日志文件
                if file_path_abs == current_log:
                    continue
                
                # 如果超过了最大文件数或者超过了最大天数
                if i >= max_files or file_time < cutoff_date:
                    files_to_delete.append(file_path)
            
            # 删除文件
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    self.debug(f"已删除旧日志文件: {file_path}")
                except Exception as e:
                    self.error(f"删除日志文件失败 {file_path}: {e}")
            
            # 记录清理结果
            if files_to_delete:
                self.info(f"日志清理完成，共删除了{len(files_to_delete)}个旧日志文件")
            else:
                self.info("日志清理完成，没有需要删除的旧日志文件")
                
        except Exception as e:
            self.error(f"清理旧日志文件时出错: {e}")

# 全局访问点
log = LogManager()


"""
使用方法：

from core.log.log_manager import log

# 测试不同级别的日志
log.debug("这是一条调试信息")
log.info("这是一条普通信息")
log.warning("这是一条警告信息")
log.error("这是一条错误信息")
log.critical("这是一条严重错误信息")

try:
    1/0
except Exception as e:
    log.exception("发生了一个异常")

"""