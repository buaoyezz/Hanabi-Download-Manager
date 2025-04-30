# coding:utf-8
import sys
import os
import re
import configparser
from pathlib import Path
from re import compile

from PySide6.QtCore import QRect, QStandardPaths


version = "1.0.1"

class ProxyValidator:
    PATTERN = compile(r'^(socks5|http|https):\/\/'
                      r'((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                      r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):'
                      r'(6553[0-5]|655[0-2][0-9]|65[0-4][0-9]{2}|[1-5]?[0-9]{1,4})$')

    @staticmethod
    def validate(value: str) -> bool:
        return bool(ProxyValidator.PATTERN.match(value)) or value == "Auto" or value == "Off"

    @staticmethod
    def correct(value) -> str:
        return value if ProxyValidator.validate(value) else "Auto"


class GeometrySerializer:
    @staticmethod
    def serialize(value: QRect) -> str:
        if value == "Default":
            return value
        return f"{value.x()},{value.y()},{value.width()},{value.height()}"

    @staticmethod
    def deserialize(value: str) -> QRect:
        if value == "Default":
            return value
        x, y, w, h = map(int, value.split(","))
        return QRect(x, y, w, h)


class Config:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
        
        # 默认配置
        self.defaults = {
            "Download": {
                "MaxReassignSize": "8",
                "DownloadFolder": QStandardPaths.writableLocation(QStandardPaths.DownloadLocation),
                "HistoryDownloadFolder": "",
                "PreBlockNum": "8",
                "MaxTaskNum": "3",
                "SpeedLimitation": "0",
                "AutoSpeedUp": "True",
                "SSLVerify": "True",
                "ProxyServer": "Auto",
                "SkipSavePathPrompt": "False"
            },
            "Browser": {
                "EnableBrowserExtension": "False"
            },
            "Personalization": {
                "BackgroundEffect": "Mica" if sys.platform == "win32" else "None",
                "ThemeMode": "System",
                "DpiScale": "0"
            },
            "Software": {
                "CheckUpdateAtStartUp": "True",
                "AutoRun": "False",
                "ClipboardListener": "True",
                "Geometry": "Default"
            }
        }
        
        # 加载默认配置
        self.load_config()
        
        # 全局变量
        self.appPath = "./"
        self.globalSpeed = 0
        
    def load_config(self):
        # 加载默认配置
        for section, options in self.defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for option, value in options.items():
                if not self.config.has_option(section, option):
                    self.config.set(section, option, value)
        
        # 从文件加载配置
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section, option, default=None):
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def getint(self, section, option, default=0):
        try:
            return self.config.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def getboolean(self, section, option, default=False):
        try:
            return self.config.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))
        self.save_config()
    
    # 属性和方法，模拟原来的配置项
    @property
    def maxReassignSize(self):
        return self.getint("Download", "MaxReassignSize", 8)
    
    @maxReassignSize.setter
    def maxReassignSize(self, value):
        self.set("Download", "MaxReassignSize", max(1, min(100, value)))
    
    @property
    def downloadFolder(self):
        return self.get("Download", "DownloadFolder", QStandardPaths.writableLocation(QStandardPaths.DownloadLocation))
    
    @downloadFolder.setter
    def downloadFolder(self, value):
        if os.path.isdir(value):
            self.set("Download", "DownloadFolder", value)
    
    @property
    def historyDownloadFolder(self):
        folders = self.get("Download", "HistoryDownloadFolder", "")
        return folders.split("|") if folders else []
    
    @historyDownloadFolder.setter
    def historyDownloadFolder(self, value):
        if isinstance(value, list):
            self.set("Download", "HistoryDownloadFolder", "|".join(value))
    
    @property
    def preBlockNum(self):
        return self.getint("Download", "PreBlockNum", 8)
    
    @preBlockNum.setter
    def preBlockNum(self, value):
        self.set("Download", "PreBlockNum", max(1, min(256, value)))
    
    @property
    def maxTaskNum(self):
        return self.getint("Download", "MaxTaskNum", 3)
    
    @maxTaskNum.setter
    def maxTaskNum(self, value):
        self.set("Download", "MaxTaskNum", max(1, min(10, value)))
    
    @property
    def speedLimitation(self):
        return self.getint("Download", "SpeedLimitation", 0)
    
    @speedLimitation.setter
    def speedLimitation(self, value):
        self.set("Download", "SpeedLimitation", max(0, min(104857600, value)))
    
    @property
    def autoSpeedUp(self):
        return self.getboolean("Download", "AutoSpeedUp", True)
    
    @autoSpeedUp.setter
    def autoSpeedUp(self, value):
        self.set("Download", "AutoSpeedUp", "True" if value else "False")
    
    @property
    def SSLVerify(self):
        return self.getboolean("Download", "SSLVerify", True)
    
    @SSLVerify.setter
    def SSLVerify(self, value):
        self.set("Download", "SSLVerify", "True" if value else "False")
    
    @property
    def proxyServer(self):
        value = self.get("Download", "ProxyServer", "Auto")
        return ProxyValidator.correct(value)
    
    @proxyServer.setter
    def proxyServer(self, value):
        self.set("Download", "ProxyServer", ProxyValidator.correct(value))
    
    @property
    def enableBrowserExtension(self):
        return self.getboolean("Browser", "EnableBrowserExtension", False)
    
    @enableBrowserExtension.setter
    def enableBrowserExtension(self, value):
        self.set("Browser", "EnableBrowserExtension", "True" if value else "False")
    
    @property
    def backgroundEffect(self):
        if sys.platform == "win32":
            return self.get("Personalization", "BackgroundEffect", "Mica")
        return "None"
    
    @backgroundEffect.setter
    def backgroundEffect(self, value):
        if sys.platform == "win32" and value in ["Acrylic", "Mica", "MicaBlur", "MicaAlt", "Aero", "None"]:
            self.set("Personalization", "BackgroundEffect", value)
    
    @property
    def customThemeMode(self):
        return self.get("Personalization", "ThemeMode", "System")
    
    @customThemeMode.setter
    def customThemeMode(self, value):
        if value in ["Light", "Dark", "System"]:
            self.set("Personalization", "ThemeMode", value)
    
    @property
    def dpiScale(self):
        return self.getint("Personalization", "DpiScale", 0)
    
    @dpiScale.setter
    def dpiScale(self, value):
        self.set("Personalization", "DpiScale", max(0, min(5, value)))
    
    @property
    def checkUpdateAtStartUp(self):
        return self.getboolean("Software", "CheckUpdateAtStartUp", True)
    
    @checkUpdateAtStartUp.setter
    def checkUpdateAtStartUp(self, value):
        self.set("Software", "CheckUpdateAtStartUp", "True" if value else "False")
    
    @property
    def autoRun(self):
        return self.getboolean("Software", "AutoRun", False)
    
    @autoRun.setter
    def autoRun(self, value):
        self.set("Software", "AutoRun", "True" if value else "False")
    
    @property
    def enableClipboardListener(self):
        return self.getboolean("Software", "ClipboardListener", True)
    
    @enableClipboardListener.setter
    def enableClipboardListener(self, value):
        self.set("Software", "ClipboardListener", "True" if value else "False")
    
    @property
    def skipSavePathPrompt(self):
        return self.getboolean("Download", "SkipSavePathPrompt", False)
    
    @skipSavePathPrompt.setter
    def skipSavePathPrompt(self, value):
        self.set("Download", "SkipSavePathPrompt", "True" if value else "False")
    
    @property
    def geometry(self):
        value = self.get("Software", "Geometry", "Default")
        if value != "Default":
            return GeometrySerializer.deserialize(value)
        return value
    
    @geometry.setter
    def geometry(self, value):
        if value == "Default":
            self.set("Software", "Geometry", value)
        elif isinstance(value, QRect):
            self.set("Software", "Geometry", GeometrySerializer.serialize(value))
    
    def resetGlobalSpeed(self):
        self.globalSpeed = 0
        
    # 添加下载管理器需要的方法
    def get_save_path_for_category(self, category):
        """获取指定分类的保存路径"""
        # 首先尝试从配置文件获取特定分类的路径
        category_path = self.get(f"CategoryPaths", category, None)
        if category_path:
            return category_path
            
        # 如果没有找到，返回默认下载文件夹
        base_path = self.downloadFolder
        category_folder = os.path.join(base_path, category)
        
        # 确保目录存在
        os.makedirs(category_folder, exist_ok=True)
        return category_folder
        
    def set_save_path_for_category(self, category, path):
        """设置指定分类的保存路径"""
        if not self.config.has_section("CategoryPaths"):
            self.config.add_section("CategoryPaths")
        self.set("CategoryPaths", category, path)
        
    def get_categories(self):
        """获取所有下载分类"""
        # 默认分类
        default_categories = ["程序", "视频", "音乐", "文档", "压缩包", "其他"]
        
        # 尝试从配置中加载自定义分类
        custom_categories = self.get("Download", "Categories", None)
        if custom_categories:
            return custom_categories.split("|")
        return default_categories
        
    def guess_category(self, filename):
        """根据文件名猜测分类"""
        ext = os.path.splitext(filename)[1].lower()
        
        # 扩展名到分类的映射
        ext_map = {
            # 程序类
            ".exe": "程序", ".msi": "程序", ".app": "程序", ".dmg": "程序", ".apk": "程序",
            # 视频类
            ".mp4": "视频", ".avi": "视频", ".mkv": "视频", ".mov": "视频", ".flv": "视频", 
            ".wmv": "视频", ".m4v": "视频", ".rmvb": "视频",
            # 音乐类
            ".mp3": "音乐", ".wav": "音乐", ".flac": "音乐", ".aac": "音乐", ".ogg": "音乐",
            ".m4a": "音乐", ".wma": "音乐",
            # 文档类
            ".doc": "文档", ".docx": "文档", ".pdf": "文档", ".txt": "文档", ".ppt": "文档",
            ".pptx": "文档", ".xls": "文档", ".xlsx": "文档", ".csv": "文档", ".md": "文档",
            # 压缩包类
            ".zip": "压缩包", ".rar": "压缩包", ".7z": "压缩包", ".tar": "压缩包", 
            ".gz": "压缩包", ".bz2": "压缩包",
        }
        
        return ext_map.get(ext, "其他")
        
    def get_last_browse_path(self):
        """获取上次浏览的路径"""
        last_path = self.get("Download", "LastBrowsePath", None)
        if last_path and os.path.exists(last_path):
            return last_path
        return self.downloadFolder
        
    def set_last_browse_path(self, path):
        """设置上次浏览的路径"""
        if os.path.exists(path):
            self.set("Download", "LastBrowsePath", path)


DEFAULT_HEADERS = {
    "accept-encoding": "deflate, br, gzip",
    "accept-language": "zh-CN,zh;q=0.9",
    "cookie": "down_ip=1",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.64",
    "software": f"HanabiDownloadManager/{version}",
    "UA_HanabiDownloadManager": f"HanabiDownloadManager/{version} (Release x64) By ZZBUAOYE & REQUESTED BY HDM"
}


ATTACHMENT_TYPES = {
    "3gp", "7z", "aac", "ace", "aif", "arj", "asf", "avi", "bin", "bz2", "dmg", "exe", "gz", "gzip", 
    "img", "iso", "lzh", "m4a", "m4v", "mkv", "mov", "mp3", "mp4", "mpa", "mpe", "mpeg", "mpg", "msi", 
    "msu", "ogg", "ogv", "pdf", "plj", "pps", "ppt", "qt", "ra", "rar", "rm", "rmvb", "sea", "sit", 
    "sitx", "tar", "tif", "tiff", "wav", "wma", "wmv", "z", "zip", "esd", "wim", "msp", "apk", "apks", 
    "apkm", "cab"
}

cfg = Config()

class DownloadConfig:
    def __init__(self):
        # 下载设置
        self.maxThreads = 8
        self.SSLVerify = True
        self.speedLimitation = 0  # 字节/秒，0表示不限速
        self.maxReassignSize = 10  # MB，重分配分段的最小大小
        self.proxyServer = "Auto"
        
        # 路径设置
        self.downloadPath = str(Path.home() / "Downloads")
        
        # 用户代理
        self.userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # 加载用户配置
        self._load_user_config()
    
    def _load_user_config(self):
        try:
            # 在这里可以添加从配置文件加载用户设置的代码
            # 例如从JSON或INI文件加载配置
            pass
        except Exception as e:
            print(f"加载用户配置失败: {e}")

# 创建全局配置实例
cfg = DownloadConfig()
