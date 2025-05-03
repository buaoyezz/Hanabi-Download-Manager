import os
import json
import time
from datetime import datetime
import threading

class HistoryManager:
    """下载历史记录管理器，负责保存和读取下载历史"""
    
    def __init__(self, history_file=None):
        """
        初始化历史记录管理器
        
        Args:
            history_file: 历史记录文件路径，如果为None则使用默认路径
        """
        # 如果未指定历史记录文件，则使用默认路径
        if not history_file:
            # 获取用户主目录
            home_dir = os.path.expanduser("~")
            # 创建应用配置目录
            app_dir = os.path.join(home_dir, ".hanabi_download_manager")
            if not os.path.exists(app_dir):
                os.makedirs(app_dir, exist_ok=True)
            
            # 设置历史记录文件路径
            self.history_file = os.path.join(app_dir, "download_history.json")
        else:
            self.history_file = history_file
        
        # 保存的最大历史记录数量
        self.max_history_items = 100
        
        # 创建锁以确保线程安全
        self.lock = threading.Lock()
        
        # 加载历史记录
        self.history_records = self._load_history()
    
    def _load_history(self):
        """从文件加载历史记录"""
        try:
            # 尝试打开并读取历史记录文件
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 确保返回的是列表
                    if isinstance(data, list):
                        return data
                    return []
        except Exception as e:
            print(f"加载历史记录失败: {e}")
        
        # 如果文件不存在或加载失败，返回空列表
        return []
    
    def _save_history(self):
        """将历史记录保存到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            # 写入历史记录文件
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_records, f, ensure_ascii=False, indent=2)
            
            print(f"已保存{len(self.history_records)}条历史记录到{self.history_file}")
            return True
        except Exception as e:
            print(f"保存历史记录失败: {e}")
            return False
    
    def add_record(self, download_info):
        """
        添加一条下载记录
        
        Args:
            download_info: 包含下载信息的字典，应该包含以下字段:
                          filename: 文件名
                          url: 下载URL
                          save_path: 保存路径
                          file_size: 文件大小
                          status: 状态（'completed'或'error'）
                          
        Returns:
            bool: 是否成功添加
        """
        with self.lock:
            # 创建记录
            record = {
                "filename": download_info.get("filename", "未知文件"),
                "url": download_info.get("url", ""),
                "save_path": download_info.get("save_path", ""),
                "file_size": download_info.get("file_size", 0),
                "download_time": download_info.get("download_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "status": download_info.get("status", "completed"),
            }
            
            # 如果是错误状态，添加错误信息
            if record["status"] == "error" and "error_message" in download_info:
                record["error_message"] = download_info["error_message"]
            
            # 检查是否已有相同文件的记录
            for i, existing_record in enumerate(self.history_records):
                if (existing_record.get("filename") == record["filename"] and 
                    existing_record.get("save_path") == record["save_path"]):
                    # 更新现有记录
                    self.history_records[i] = record
                    print(f"更新历史记录: {record['filename']}")
                    self._save_history()
                    return True
            
            # 添加新记录到列表开头（最新的记录在前面）
            self.history_records.insert(0, record)
            
            # 限制历史记录数量
            if len(self.history_records) > self.max_history_items:
                self.history_records = self.history_records[:self.max_history_items]
            
            # 保存到文件
            print(f"添加历史记录: {record['filename']}")
            return self._save_history()
    
    def get_all_records(self, force_reload=True):
        """获取所有历史记录，可选择强制重新从文件加载
        
        Args:
            force_reload: 是否强制从文件重新加载，默认为True
            
        Returns:
            list: 历史记录列表的副本
        """
        with self.lock:
            # 如果设置了强制重新加载，则从文件中重新读取
            if force_reload:
                self.history_records = self._load_history()
                print(f"已重新加载历史记录，共{len(self.history_records)}条")
                
            # 返回历史记录的副本，避免外部修改
            return self.history_records.copy()
    
    def get_recent_records(self, limit=10):
        """获取最近的n条历史记录"""
        with self.lock:
            return self.history_records[:limit]
    
    def clear_history(self):
        """清空历史记录"""
        with self.lock:
            self.history_records.clear()
            return self._save_history()
    
    def remove_record(self, filename, save_path):
        """删除指定的历史记录"""
        with self.lock:
            # 查找要删除的记录
            for i, record in enumerate(self.history_records):
                if (record.get("filename") == filename and 
                    record.get("save_path") == save_path):
                    # 删除记录
                    self.history_records.pop(i)
                    print(f"删除历史记录: {filename}")
                    return self._save_history()
            
            # 未找到记录
            print(f"未找到历史记录: {filename}")
            return False 