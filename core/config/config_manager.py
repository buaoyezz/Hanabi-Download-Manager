import os
import json
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.config = {
            "download": {
                "max_threads": 8,
                "chunk_size": 1024 * 1024,  # 1MB
                "default_speed_limit": 0,    # 0 = no limit, value in bytes/s
                "retry_count": 3,
                "timeout": 30,
                "user_agent": "HanabiDownloader/1.0"
            },
            "paths": {
                "download_dir": str(Path.home() / "Downloads"),
                "temp_dir": str(Path.home() / "Downloads" / ".temp")
            },
            "ui": {
                "theme": "light",
                "language": "en"
            }
        }
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    self._merge_config(loaded_config)
        except Exception as e:
            print(f"Error loading config: {e}")
            
    def _merge_config(self, loaded_config):
        for category, values in loaded_config.items():
            if category in self.config:
                if isinstance(self.config[category], dict) and isinstance(values, dict):
                    self.config[category].update(values)
                else:
                    self.config[category] = values
            else:
                self.config[category] = values
    
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, category, key=None):
        if key is None:
            return self.config.get(category, {})
        return self.config.get(category, {}).get(key)
    
    def set(self, category, key, value):
        if category not in self.config:
            self.config[category] = {}
        self.config[category][key] = value
        
    def update(self, category, values):
        if category not in self.config:
            self.config[category] = {}
        if isinstance(values, dict):
            self.config[category].update(values)
    
# Create singleton instance
config = ConfigManager() 