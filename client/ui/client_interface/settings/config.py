import json
import os
import logging
from pathlib import Path

class ConfigManager:
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._init_config()
        return cls._instance
    
    def _init_config(self):
        # 默认配置
        self._config = {
            "download": {
                "thread_count": 8,           # 每个任务的默认线程数
                "dynamic_threads": True,      # 是否启用动态线程
                "max_thread_count": 32,       # 最大线程数限制
                "min_segment_size": 10,       # 最小分段大小(MB)
                "save_path": str(Path.home() / "Downloads"),  # 默认保存路径
                "max_tasks": 5,               # 最大同时下载任务数
                "buffer_size": 8192,          # 缓冲区大小 (bytes)
                "chunk_size": 1024 * 1024,    # 分块大小 (1MB)
                "auto_organize": False,       # 是否自动整理下载文件
                "auto_start": True,           # 是否自动开始下载
                "max_retries": 3              # 最大重试次数
            },
            "network": {
                "proxy": {
                    "enabled": False,         # 是否启用代理
                    "type": "http",           # 代理类型: http, socks5
                    "host": "",               # 代理主机
                    "port": 1080,             # 代理端口
                    "auth": False,            # 是否启用代理认证
                    "username": "",           # 代理用户名
                    "password": ""            # 代理密码
                },
                "speed_limit": {
                    "download_enabled": False,  # 是否启用下载速度限制
                    "download_limit": 0,        # 下载速度限制 KB/s, 0 表示无限制
                    "upload_enabled": False,    # 是否启用上传速度限制
                    "upload_limit": 0           # 上传速度限制 KB/s, 0 表示无限制
                },
                "connection": {
                    "timeout": 30,              # 连接超时(秒)
                    "ssl_verify": True          # 是否验证 SSL 证书
                }
            },
            "ui": {
                "theme": "dark",              # 界面主题: dark, light
                "language": "zh_CN",          # 界面语言
                "show_notifications": True    # 是否显示通知
            },
            "startup": {
                "auto_start": False,           # 开机自启动
                "check_update": True,          # 启动时检查更新
                "restore_tasks": True          # 启动时恢复未完成的任务
            }
        }
        
        # 尝试加载现有配置文件
        self._load_config()
        
        # 打印一些关键配置以便调试
        logging.info(f"配置初始化完成，线程数: {self._config['download']['thread_count']}")
    
    def _get_config_path(self):
        config_dir = Path.home() / ".hanabidownloadmanager"
        # 确保目录存在
        config_dir.mkdir(exist_ok=True)
        return config_dir / "config.json"
    
    def _load_config(self):
        """从文件加载配置"""
        config_path = self._get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 合并加载的配置与默认配置
                    self._merge_config(loaded_config)
                
                # 打印加载后的线程设置
                logging.info(f"配置加载完成，线程数: {self._config['download']['thread_count']}")
            except Exception as e:
                logging.error(f"加载配置失败: {e}")
                print(f"加载配置失败: {e}")
    
    def _merge_config(self, loaded_config):
        def merge_dict(default_dict, loaded_dict):
          
            for key, value in loaded_dict.items():
                if key in default_dict and isinstance(default_dict[key], dict) and isinstance(value, dict):
                    merge_dict(default_dict[key], value)
                else:
                    default_dict[key] = value
        
        # 递归合并配置
        for section, values in loaded_config.items():
            if section in self._config:
                if isinstance(self._config[section], dict) and isinstance(values, dict):
                    merge_dict(self._config[section], values)
                else:
                    self._config[section] = values
            else:
                self._config[section] = values
    
    def save_config(self):
        """保存配置到文件"""
        config_path = self._get_config_path()
        try:
            # 创建父目录（如果不存在）
            config_dir = config_path.parent
            config_dir.mkdir(exist_ok=True, parents=True)
            
            # 保存配置
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            
            # 打印保存信息
            logging.info(f"配置保存成功，线程数: {self._config['download']['thread_count']}")
            return True
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            print(f"保存配置失败: {e}")
            return False
    
    def get(self, section, default=None):
        try:
            return self._config[section]
        except (KeyError, TypeError):
            return default if default is not None else {}
    
    def set(self, section, config):
        """设置整个配置段
        
        Args:
            section: 配置段名称
            config: 配置段内容（字典）
        """
        try:
            self._config[section] = config
            return True
        except Exception as e:
            logging.error(f"设置配置段失败: {section}={config}, 错误: {e}")
            return False
    
    def get_setting(self, section, key, default=None):
       
        try:
            if "." in key:
                # 支持嵌套获取，如 "proxy.enabled"
                parts = key.split(".")
                value = self._config[section]
                for part in parts:
                    value = value[part]
                return value
            else:
                return self._config[section][key]
        except (KeyError, TypeError):
            return default
    
    def set_setting(self, section, key, value):
        
        try:
            if section not in self._config:
                self._config[section] = {}
                
            if "." in key:
                # 支持嵌套设置，如 "proxy.enabled"
                parts = key.split(".")
                config_section = self._config[section]
                for part in parts[:-1]:
                    if part not in config_section:
                        config_section[part] = {}
                    config_section = config_section[part]
                config_section[parts[-1]] = value
            else:
                self._config[section][key] = value
            return True
        except (KeyError, TypeError) as e:
            logging.error(f"设置配置失败: {section}.{key}={value}, 错误: {e}")
            return False
    
    def get_download_thread_count(self):
        thread_count = self.get_setting("download", "thread_count", 8)
        logging.info(f"获取下载线程数: {thread_count}")
        return thread_count
    
    def set_download_thread_count(self, count):
        # 确保线程数在合理范围内
        max_count = self.get_setting("download", "max_thread_count", 32)
        count = max(1, min(count, max_count))  # 限制在1-max_count之间
        
        logging.info(f"设置下载线程数: {count}")
        success = self.set_setting("download", "thread_count", count)
        if success:
            self.save_config()
        return success
    
    def get_dynamic_threads(self):
        return self.get_setting("download", "dynamic_threads", True)
    
    def set_dynamic_threads(self, enabled):
        success = self.set_setting("download", "dynamic_threads", bool(enabled))
        if success:
            self.save_config()
        return success
    
    def get_save_path(self):
        return self.get_setting("download", "save_path", str(Path.home() / "Downloads"))
    
    def set_save_path(self, path):
        success = self.set_setting("download", "save_path", path)
        if success:
            self.save_config()
        return success
    
    def get_max_tasks(self):
        return self.get_setting("download", "max_tasks", 5)
    
    def set_max_tasks(self, count):
        count = max(1, min(20, count))  # 限制在1-20之间
        success = self.set_setting("download", "max_tasks", count)
        if success:
            self.save_config()
        return success
    
    def get_auto_check_update(self):
        return self.get_setting("startup", "check_update", True)
    
    def set_auto_check_update(self, enabled):
        success = self.set_setting("startup", "check_update", bool(enabled))
        if success:
            self.save_config()
        return success

# 全局访问点
config = ConfigManager()
