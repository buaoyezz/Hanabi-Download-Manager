#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
import time

class FileOrganizer:
    """File organizer that automatically sorts downloaded files into corresponding folders based on file type"""
    
    # File type mapping table
    FILE_TYPE_MAP = {
        # Programs
        ".exe": "Programs", ".msi": "Programs", ".app": "Programs", ".dmg": "Programs", ".apk": "Programs",
        # Videos
        ".mp4": "Videos", ".avi": "Videos", ".mkv": "Videos", ".mov": "Videos", ".flv": "Videos", 
        ".wmv": "Videos", ".m4v": "Videos", ".rmvb": "Videos", ".webm": "Videos",
        # Music
        ".mp3": "Music", ".wav": "Music", ".flac": "Music", ".aac": "Music", ".ogg": "Music",
        ".m4a": "Music", ".wma": "Music",
        # Documents
        ".doc": "Documents", ".docx": "Documents", ".pdf": "Documents", ".txt": "Documents", ".ppt": "Documents",
        ".pptx": "Documents", ".xls": "Documents", ".xlsx": "Documents", ".csv": "Documents", ".md": "Documents",
        # Archives
        ".zip": "Archives", ".rar": "Archives", ".7z": "Archives", ".tar": "Archives", 
        ".gz": "Archives", ".bz2": "Archives",
        # Images
        ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images", ".bmp": "Images",
        ".webp": "Images", ".svg": "Images", ".ico": "Images", ".tif": "Images", ".tiff": "Images",
        # Code
        ".py": "Code", ".java": "Code", ".js": "Code", ".html": "Code", ".css": "Code",
        ".cpp": "Code", ".c": "Code", ".h": "Code", ".php": "Code", ".go": "Code",
        ".ts": "Code", ".json": "Code", ".xml": "Code", ".yaml": "Code", ".yml": "Code",
    }
    
    # Default category folders
    DEFAULT_CATEGORIES = ["Programs", "Videos", "Music", "Documents", "Archives", "Images", "Code", "Others"]
    
    def __init__(self, base_path: str = None):
        """Initialize file organizer
        
        Args:
            base_path: Base path, defaults to None, meaning use system downloads folder
        """
        self.base_path = base_path or str(Path.home() / "Downloads")
        self.category_paths = {}
        
        # Initialize logger
        self.logger = logging.getLogger("FileOrganizer")
        
    def set_base_path(self, path: str) -> None:
        """Set base path
        
        Args:
            path: New base path
        """
        if path and os.path.exists(path) and os.path.isdir(path):
            self.base_path = path
            self.logger.info(f"Base path set: {path}")
        else:
            self.logger.warning(f"Invalid base path: {path}")
    
    def set_category_path(self, category: str, path: str) -> None:
        """Set save path for specific category
        
        Args:
            category: Category name
            path: Save path
        """
        if path and os.path.exists(path) and os.path.isdir(path):
            self.category_paths[category] = path
            self.logger.info(f"Path set for category '{category}': {path}")
        else:
            self.logger.warning(f"Invalid category path: {path}")
    
    def get_file_category(self, filename: str) -> str:
        """Get file category based on filename
        
        Args:
            filename: Filename
            
        Returns:
            str: File category
        """
        ext = os.path.splitext(filename)[1].lower()
        return self.FILE_TYPE_MAP.get(ext, "Others")
    
    def get_category_path(self, category: str) -> str:
        """Get save path for category
        
        Args:
            category: Category name
            
        Returns:
            str: Category save path
        """
        # If custom path exists, use custom path
        if category in self.category_paths:
            return self.category_paths[category]
        
        # Otherwise use category folder under base path
        return os.path.join(self.base_path, category)
    
    def ensure_category_folders(self) -> None:
        """Ensure all category folders exist"""
        for category in self.DEFAULT_CATEGORIES:
            category_path = self.get_category_path(category)
            os.makedirs(category_path, exist_ok=True)
            self.logger.debug(f"Ensuring category folder exists: {category_path}")
    
    def organize_file(self, file_path: str, move: bool = True) -> Optional[str]:
        """Organize single file into corresponding category folder
        
        Args:
            file_path: File path
            move: Whether to move file, True for move, False for copy
            
        Returns:
            Optional[str]: New file path after organization, None if failed
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                self.logger.warning(f"File does not exist or is not a file: {file_path}")
                return None
            
            # Get filename and category
            filename = os.path.basename(file_path)
            category = self.get_file_category(filename)
            
            # Ensure category folder exists
            category_path = self.get_category_path(category)
            os.makedirs(category_path, exist_ok=True)
            
            # Target file path
            target_path = os.path.join(category_path, filename)
            
            # If target file exists, add timestamp
            if os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                new_filename = f"{name}_{timestamp}{ext}"
                target_path = os.path.join(category_path, new_filename)
            
            # Move or copy file
            if move:
                shutil.move(file_path, target_path)
                self.logger.info(f"File moved: {file_path} -> {target_path}")
            else:
                shutil.copy2(file_path, target_path)
                self.logger.info(f"File copied: {file_path} -> {target_path}")
            
            return target_path
            
        except Exception as e:
            self.logger.error(f"Failed to organize file: {file_path}, error: {str(e)}")
            return None
    
    def organize_folder(self, folder_path: str = None, move: bool = True) -> Dict[str, List[str]]:
        """Organize all files in folder
        
        Args:
            folder_path: Folder path to organize, defaults to base path
            move: Whether to move files, True for move, False for copy
            
        Returns:
            Dict[str, List[str]]: Files organized by category
        """
        folder_path = folder_path or self.base_path
        result = {category: [] for category in self.DEFAULT_CATEGORIES}
        
        try:
            # Ensure folder exists
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                self.logger.warning(f"Folder does not exist or is not a folder: {folder_path}")
                return result
            
            # Ensure category folders exist
            self.ensure_category_folders()
            
            # Iterate through all files in folder
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                
                # Only process files, not folders
                if os.path.isfile(file_path):
                    # Get file category
                    category = self.get_file_category(filename)
                    
                    # Skip if file is already in corresponding category folder
                    if folder_path == self.get_category_path(category):
                        continue
                    
                    # Organize file
                    new_path = self.organize_file(file_path, move)
                    
                    # Record result
                    if new_path:
                        result[category].append(new_path)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to organize folder: {folder_path}, error: {str(e)}")
            return result
    
    def organize_download(self, file_path: str, move: bool = True) -> Optional[str]:
        """Organize downloaded file, called after download completes
        
        Args:
            file_path: Downloaded file path
            move: Whether to move file, True for move, False for copy
            
        Returns:
            Optional[str]: New file path after organization, None if failed
        """
        try:
            # Ensure file exists
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                self.logger.warning(f"Downloaded file does not exist or is not a file: {file_path}")
                return None
            
            # Organize file
            return self.organize_file(file_path, move)
            
        except Exception as e:
            self.logger.error(f"整理下载文件失败: {file_path}, 错误: {str(e)}")
            return None

# 单例模式
_instance = None

def get_file_organizer() -> FileOrganizer:
    """获取文件整理器单例实例"""
    global _instance
    if _instance is None:
        _instance = FileOrganizer()
    return _instance

# 测试代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建文件整理器
    organizer = get_file_organizer()
    
    # 设置基础路径
    import tempfile
    test_dir = tempfile.mkdtemp()
    organizer.set_base_path(test_dir)
    
    # 创建测试文件
    test_files = {
        "test.mp4": "视频",
        "test.pdf": "文档",
        "test.mp3": "音乐",
        "test.exe": "程序",
        "test.zip": "压缩包",
        "test.unknown": "其他"
    }
    
    for filename, category in test_files.items():
        file_path = os.path.join(test_dir, filename)
        with open(file_path, "w") as f:
            f.write("test content")
        
        # 测试整理单个文件
        new_path = organizer.organize_file(file_path)
        
        # 验证结果
        expected_path = os.path.join(test_dir, category, filename)
        assert os.path.exists(expected_path), f"文件未正确整理: {filename} -> {category}"
        
    print("测试通过，所有文件都已正确整理！")
    
    # 清理测试目录
    shutil.rmtree(test_dir) 