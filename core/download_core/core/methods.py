import ctypes
import importlib
import inspect
import os
import re
import subprocess
import sys
import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import socket
import time
import functools
from datetime import datetime, timedelta, timezone
from email.utils import decode_rfc2231
from functools import wraps, lru_cache
from pathlib import Path
from time import sleep, localtime, time_ns
from urllib.parse import unquote, parse_qs, urlparse
from concurrent.futures import ThreadPoolExecutor
import requests
from typing import Tuple, Optional, Dict, Any, Union

# 使用标准库替换第三方库
# import httpx -> 使用urllib.request
# from loguru import logger -> 使用标准logging
# from qfluentwidgets import MessageBox -> 使用简单的控制台输出或自定义实现

from core.download_core.core.config import cfg, DEFAULT_HEADERS
from core.download_core.core.signal_manager import SignalManager

# 配置标准库logging - 使用缓冲写入提高性能
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.expanduser('~'), '.hanabidownloadmanager', 'logs', "hanabi_downloader.log"), encoding='utf-8')
    ]
)

# 确保日志目录存在
log_dir = os.path.join(os.path.expanduser('~'), '.hanabidownloadmanager', 'logs')
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger("HanabiDownloader")

# 全局线程池 - 避免重复创建
_thread_pool = ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4 or 4))
plugins = []
_proxy_cache = {}  # 代理缓存
_fs_support_cache = {}  # 文件系统支持缓存

# 改进文件名处理的正则表达式 - 预编译提高性能
FILENAME_RFC_REGEX = re.compile(r'filename\*\s*=\s*([^;]+)', re.IGNORECASE)
FILENAME_REGEX = re.compile(r'filename\s*=\s*["\']?([^"\';]+)["\']?', re.IGNORECASE)

# 文件类型缓存
SPARSE_SUPPORTED_FS = {
    'windows': {'exFAT', 'NTFS', 'ReFS'},
    'linux': {'ext4', 'xfs', 'btrfs', 'zfs'},
    'macos': {'apfs', 'hfs'}
}

# Windows平台Constants
FSCTL_SET_SPARSE = 0x000900C4  # 常量定义，避免依赖win32con

# def isWin11():
#     return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000

def loadPlugins(mainWindow, directory="plugins"):
 
    if not os.path.exists(directory):
        logger.warning(f"插件目录不存在: {directory}")
        return
    
    plugin_files = [
        os.path.join(directory, f) for f in os.listdir(directory)
        if f.endswith((".py", ".pyd", ".so"))
    ]
    
    def _load_plugin(file_path):
        try:
            module_name = os.path.basename(file_path).split(".")[0]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_classes = [
                obj for name, obj in inspect.getmembers(module)
                if inspect.isclass(obj) and hasattr(obj, 'load') and name != 'PluginBase'
            ]
            
            loaded_plugins = []
            for plugin_class in plugin_classes:
                try:
                    plugin_instance = plugin_class(mainWindow)
                    plugin_instance.load()
                    loaded_plugins.append(plugin_instance)
                    logger.info(f"加载插件: {getattr(plugin_instance, 'name', module_name)}")
                except Exception as e:
                    logger.error(f"加载插件类 {plugin_class.__name__} 失败: {e}")
            
            return loaded_plugins
        except Exception as e:
            logger.error(f"导入插件文件 {file_path} 失败: {e}")
            return []
    
    # 使用线程池并行加载插件
    results = list(_thread_pool.map(_load_plugin, plugin_files))
    for plugin_list in results:
        plugins.extend(plugin_list)


@lru_cache(maxsize=8)
def getSystemProxy():
    # 检查环境变量 - 对所有平台都适用
    for env_var in ('http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY'):
        if env_var in os.environ:
            return os.environ[env_var]
    
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
            )
            
            # 读取代理状态
            proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
            if proxy_enable:
                proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
                return "http://" + proxy_server
        except Exception as e:
            logger.error(f"获取Windows代理设置失败: {e}")
    
    return None


def getProxy() -> Optional[str]:
    return os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')


def getReadableSize(size_bytes: int) -> str:
    # 转换格式
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def retry(retries: int = 3, delay: float = 0.1, backoff: float = 2.0, handleFunction: callable = None):
    retries = max(0, retries)
    delay = max(0.01, delay)  # 最小10ms避免CPU占用过高
    backoff = max(1.0, backoff)  # 至少是1.0不减少
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == retries:
                        logger.error(f'错误: {repr(e)}! "{func.__name__}()" 执行失败，已重试{retries}次.')
                        try:
                            if handleFunction:
                                handleFunction(e)
                        finally:
                            break
                    else:
                        logger.warning(
                            f'错误: {repr(e)}! "{func.__name__}()"执行失败，将在{current_delay:.2f}秒后第[{attempt+1}/{retries}]次重试...'
                        )
                        sleep(current_delay)
                        current_delay *= backoff  # 指数退避
            
            if last_exception:
                raise last_exception  # 重新抛出最后一个异常
            
        return wrapper
    
    return decorator


def openFile(file_path):
    file_path = str(file_path)
    try:
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":  # macOS
            subprocess.run(["open", file_path], check=False)
        else:  # Linux
            subprocess.run(["xdg-open", file_path], check=False)
    except Exception as e:
        logger.error(f"打开文件失败: {file_path}, 错误: {e}")


@lru_cache(maxsize=16)
def getLocalTimeFromGithubApiTime(gmtTimeStr: str):
    gmtTime = datetime.fromisoformat(gmtTimeStr.replace("Z", "+00:00"))
    localTimeOffsetSec = localtime().tm_gmtoff
    localTz = timezone(timedelta(seconds=localTimeOffsetSec))
    localTime = gmtTime.astimezone(localTz)
    return localTime.replace(tzinfo=None)


def _extract_filename_from_headers(head):
    headerValue = head.get("content-disposition", "")
    
    # 尝试RFC 5987格式
    if 'filename*' in headerValue:
        match = FILENAME_RFC_REGEX.search(headerValue)
        if match:
            filename = match.group(1)
            return decode_rfc2231(filename)[2]
    
    # 尝试普通filename格式
    if 'filename' in headerValue:
        match = FILENAME_REGEX.search(headerValue)
        if match:
            return match.group(1)
    
    return None


def getLinkInfo(url: str, headers: Dict[str, str], 
                filename: Optional[str] = None) -> Tuple[str, str, int]:
    """
    Args:
        url: 下载链接
        headers: HTTP请求头
        filename: 可选的自定义文件名，如果未提供则从URL或响应头中获取
    
    Returns:
        Tuple[str, str, int]: (URL, 文件名, 文件大小)
    """
    try:
        # 发送HEAD请求获取文件信息
        response = requests.head(url, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        # 获取最终URL（考虑重定向）
        final_url = response.url
        
        # 获取文件大小
        content_length = response.headers.get('Content-Length')
        file_size = int(content_length) if content_length else -1
        
        # 获取文件名
        if not filename:
            # 尝试从Content-Disposition头获取
            content_disposition = response.headers.get('Content-Disposition')
            if content_disposition and 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')
            else:
                # 从URL路径获取
                path = urlparse(final_url).path
                filename = unquote(os.path.basename(path))
                
            # 如果文件名为空，使用默认名称
            if not filename:
                filename = "downloaded_file"
                
        return final_url, filename, file_size
        
    except Exception as e:
        logging.error(f"获取链接信息失败: {repr(e)}")
        return url, filename or "downloaded_file", -1


def bringWindowToTop(window):
    if not window:
        return
        
    # 使用安全的属性访问方式
    for method_name in ("show", "activateWindow", "raise_"):
        method = getattr(window, method_name, None)
        if callable(method):
            method()
    
    # 处理最小化窗口
    if hasattr(window, "isMinimized") and callable(window.isMinimized) and window.isMinimized():
        if hasattr(window, "showNormal") and callable(window.showNormal):
            window.showNormal()


def addDownloadTask(url: str, fileName: str = None, filePath: str = None,
                    headers: dict = None, status: str = "working", preBlockNum: int = None, 
                    notCreateHistoryFile: bool = False, fileSize: int = -1):
    # 使用解包简化默认值处理
    task_data = {
        "url": url,
        "fileName": fileName,
        "filePath": filePath or cfg.downloadFolder,
        "headers": headers or DEFAULT_HEADERS,
        "status": status,
        "preBlockNum": preBlockNum or cfg.preBlockNum,
        "notCreateHistoryFile": notCreateHistoryFile,
        "fileSize": str(fileSize)
    }
    
    # 直接解包字典作为参数
    SignalManager.addTaskSignal.emit(**task_data)


def showMessageBox(title: str, content: str, showYesButton=False, yesSlot=None):
    # ANSI颜色代码
    BOLD = '\033[1m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    
    print(f"\n{BOLD}{CYAN}[{title}]{RESET}\n{content}")
    
    if showYesButton:
        response = input(f"{YELLOW}按Y确认，任意键取消:{RESET} ").strip().lower()
        if response == 'y' and yesSlot is not None:
            yesSlot()
    else:
        input(f"{GREEN}按Enter键继续...{RESET}")


@lru_cache(maxsize=32)
def isSparseSupported(filePath: str) -> bool:
    # 转换为字符串以确保可哈希用于缓存
    filePath = str(filePath)
    
    # 从缓存获取结果
    drive_key = os.path.splitdrive(filePath)[0] or filePath
    if drive_key in _fs_support_cache:
        return _fs_support_cache[drive_key]
    
    try:
        result = False
        if sys.platform == "win32":
            # Windows实现
            root_path = os.path.splitdrive(filePath)[0] + '\\'
            
            # 获取文件系统类型
            file_system_buffer = ctypes.create_unicode_buffer(1024)
            volume_name_buffer = ctypes.create_unicode_buffer(1024)
            success = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root_path),
                volume_name_buffer, 
                ctypes.sizeof(volume_name_buffer),
                None, None, None,
                file_system_buffer, 
                ctypes.sizeof(file_system_buffer)
            )
            
            if success:
                result = file_system_buffer.value in SPARSE_SUPPORTED_FS['windows']
        
        elif sys.platform == "linux":
            # Linux实现
            try:
                # 尝试获取文件系统类型
                import os.path
                st = os.statvfs(filePath)
                if hasattr(st, 'f_basetype'):
                    fs_type = st.f_basetype
                else:
                    # 使用命令行工具获取
                    fs_info = subprocess.check_output(
                        ["df", "--output=fstype", filePath],
                        stderr=subprocess.DEVNULL,
                        universal_newlines=True
                    ).strip().split("\n")
                    fs_type = fs_info[-1] if len(fs_info) > 1 else ""
                
                result = fs_type in SPARSE_SUPPORTED_FS['linux']
            except:
                result = False
        
        elif sys.platform == "darwin":
            # macOS实现
            try:
                # 使用diskutil获取文件系统类型
                device_info = subprocess.check_output(
                    ["df", "-P", filePath],
                    stderr=subprocess.DEVNULL,
                    universal_newlines=True
                ).strip().split("\n")
                
                if len(device_info) > 1:
                    device = device_info[1].split()[0]
                    fs_info = subprocess.check_output(
                        ["diskutil", "info", device],
                        stderr=subprocess.DEVNULL,
                        universal_newlines=True
                    )
                    
                    for line in fs_info.split("\n"):
                        if "Type" in line and ":" in line:
                            fs_type = line.split(":")[-1].strip().lower()
                            result = fs_type in SPARSE_SUPPORTED_FS['macos']
                            break
            except:
                result = False
        
        # 缓存结果
        _fs_support_cache[drive_key] = result
        return result
    
    except Exception as e:
        logger.warning(f"文件系统检测失败: {repr(e)}")
        return False


def createSparseFile(file_path: Union[str, Path], size: Optional[int] = None):
    """
    Args:
        file_path: 文件路径
        size: 文件大小（字节），如果为None则不预分配
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path
    
    # 确保文件存在
    if not path.exists():
        path.touch()
    
    if size is None:
        return
        
    if sys.platform == "win32":
        # Windows 平台使用 DeviceIoControl
        try:
            import win32file
            
            handle = win32file.CreateFile(
                str(path),
                win32file.GENERIC_WRITE,
                win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            
            win32file.SetFilePointer(handle, size, 0)
            win32file.SetEndOfFile(handle)
            
            # 设置为稀疏文件 - 使用全局定义的常量值
            try:
                win32file.DeviceIoControl(
                    handle, 
                    FSCTL_SET_SPARSE, 
                    None, 
                    0, 
                    None
                )
            except Exception as e:
                # 如果DeviceIoControl失败，尝试使用fsutil命令行工具
                try:
                    subprocess.run(
                        ["fsutil", "sparse", "setflag", str(path)],
                        check=True,
                        capture_output=True
                    )
                except Exception as subp_e:
                    logging.warning(f"设置稀疏文件标志失败: {subp_e}")
            
            win32file.CloseHandle(handle)
            
        except ImportError:
            # 如果win32file模块不可用，则使用普通方法
            with open(path, "wb") as f:
                f.truncate(size)
                
    else:  # Linux/macOS
        try:
            with open(path, "wb") as f:
                f.truncate(size)
        except Exception as e:
            logging.error(f"创建稀疏文件失败: {repr(e)}")


# 清理函数 - 在程序退出时调用
def cleanup():
    # 关闭线程池
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
    
    # 清空缓存
    _proxy_cache.clear()
    _fs_support_cache.clear()
    
    # 解除缓存装饰器
    getSystemProxy.cache_clear()
    getLocalTimeFromGithubApiTime.cache_clear()
    isSparseSupported.cache_clear()


# 注册清理函数
import atexit
atexit.register(cleanup)
