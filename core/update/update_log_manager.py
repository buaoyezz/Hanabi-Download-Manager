import os
import json
from datetime import datetime
from core.log.log_manager import log

class UpdateLogManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UpdateLogManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not UpdateLogManager._initialized:
            self.log_file = os.path.join(os.path.expanduser("~"), ".hanabidownloadmanager", "update_logs.json")
            self.current_version = "0.0.1"  # 当前版本号
            self._ensure_log_file()
            UpdateLogManager._initialized = True
    
    def _ensure_log_file(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            self._save_logs({})
    
    def _load_logs(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"加载更新日志失败: {e}")
            return {}
    
    def _save_logs(self, logs):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log.error(f"保存更新日志失败: {e}")
    
    def add_update_log(self, version, content, update_time=None):
        if update_time is None:
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        logs = self._load_logs()
        logs[version] = {
            "content": content,
            "update_time": update_time,
            "is_read": False
        }
        self._save_logs(logs)
    
    def get_unread_logs(self):
        logs = self._load_logs()
        return {v: data for v, data in logs.items() 
                if not data.get("is_read", False) and v > self.current_version}
    
    def mark_as_read(self, version):
        logs = self._load_logs()
        if version in logs:
            logs[version]["is_read"] = True
            self._save_logs(logs)
    
    def get_latest_version_log(self):
        logs = self._load_logs()
        if not logs:
            return None
            
        latest_version = max(logs.keys())
        if latest_version > self.current_version:
            return latest_version, logs[latest_version]
        return None
    
    def clean_old_logs(self, keep_versions=5):
        logs = self._load_logs()
        if len(logs) <= keep_versions:
            return
            
        sorted_versions = sorted(logs.keys(), reverse=True)
        for version in sorted_versions[keep_versions:]:
            del logs[version]
        
        self._save_logs(logs) 