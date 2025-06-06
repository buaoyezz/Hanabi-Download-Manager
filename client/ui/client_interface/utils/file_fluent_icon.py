#############
# Author: ZZBuAoYe
#############
from core.font.font_manager import FontManager
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QSize
import os

class FileFluentIcon:
    
    def __init__(self):
        """初始化文件图标工具类"""
        self.font_manager = FontManager()
        self.icon_cache = {}  # 图标缓存
        # 文件类型颜色映射
        self.file_type_colors = {
            # 可执行文件
            'exe': "#FF9800",  # 橙色
            'msi': "#FF9800",
            'appx': "#FF9800",
            'msix': "#FF9800",
            
            # 压缩文件
            'zip': "#FFCA28",  # 黄色
            'rar': "#FFCA28",
            '7z': "#FFCA28",
            'tar': "#FFCA28",
            'gz': "#FFCA28",
            'bz2': "#FFCA28",
            
            # 图像文件
            'jpg': "#B39DDB",  # 紫色
            'jpeg': "#B39DDB",
            'png': "#B39DDB",
            'gif': "#B39DDB",
            'bmp': "#B39DDB",
            'svg': "#B39DDB",
            'webp': "#B39DDB",
            
            # 音频文件
            'mp3': "#66BB6A",  # 绿色
            'wav': "#66BB6A",
            'ogg': "#66BB6A",
            'flac': "#66BB6A",
            'm4a': "#66BB6A",
            'aac': "#66BB6A",
            
            # 视频文件
            'mp4': "#FF7043",  # 橙红色
            'avi': "#FF7043",
            'mov': "#FF7043",
            'mkv': "#FF7043",
            'webm': "#FF7043",
            
            # 文档文件
            'pdf': "#42A5F5",  # 蓝色
            'doc': "#42A5F5",
            'docx': "#42A5F5",
            'xls': "#42A5F5",
            'xlsx': "#42A5F5",
            'ppt': "#42A5F5",
            'pptx': "#42A5F5",
            'txt': "#42A5F5",
            
            # 代码文件
            'py': "#26C6DA",   # 青色
            'js': "#26C6DA",
            'html': "#26C6DA",
            'css': "#26C6DA",
            'cpp': "#26C6DA",
            'c': "#26C6DA",
            'java': "#26C6DA",
            
            # 默认颜色
            'default': "#78909C"  # 灰色
        }
    
    def get_icon_for_file(self, file_path=None, file_ext=None):
        """根据文件路径或扩展名获取对应的Fluent图标
        
        参数:
            file_path (str, optional): 文件路径
            file_ext (str, optional): 文件扩展名（不包含点号）
            
        返回:
            QIcon: 文件对应的图标
        """
        # 检查缓存
        if file_path and file_path in self.icon_cache:
            return self.icon_cache[file_path]
            
        # 如果没有提供扩展名，从文件路径中获取
        if not file_ext and file_path:
            file_ext_raw = os.path.splitext(file_path)[1]
            file_ext = file_ext_raw.lstrip('.') if file_ext_raw else ""
            
        if file_ext:
            file_ext = file_ext.lower()
            
        # 根据文件类型选择合适的Fluent图标
        icon_name = "ic_fluent_document_24_regular"  # 默认文档图标
        icon_color = self.file_type_colors.get(file_ext, self.file_type_colors['default'])
        
        # 根据文件类型选择图标
        if file_ext:
            if file_ext == 'exe' or file_ext == 'msi' or file_ext == 'appx' or file_ext == 'msix':
                icon_name = "ic_fluent_app_24_regular"
            elif file_ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
                icon_name = "ic_fluent_archive_24_regular"
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']:
                icon_name = "ic_fluent_image_24_regular"
            elif file_ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']:
                icon_name = "ic_fluent_music_note_2_24_regular"
            elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                icon_name = "ic_fluent_video_24_regular"
            elif file_ext in ['pdf']:
                icon_name = "ic_fluent_document_pdf_24_regular"
            elif file_ext in ['doc', 'docx']:
                icon_name = "ic_fluent_document_text_24_regular"
            elif file_ext in ['xls', 'xlsx']:
                icon_name = "ic_fluent_document_data_24_regular"
            elif file_ext in ['ppt', 'pptx']:
                icon_name = "ic_fluent_document_slideshow_24_regular"
            elif file_ext in ['py', 'js', 'html', 'css', 'cpp', 'c', 'java']:
                icon_name = "ic_fluent_code_24_regular"
            elif file_ext in ['bat', 'cmd', 'ps1', 'sh']:
                icon_name = "ic_fluent_terminal_24_regular"
                
        # 获取图标
        fluent_icon = self.font_manager.get_qicon(icon_name, icon_color)
        
        # 缓存结果
        if file_path:
            self.icon_cache[file_path] = fluent_icon
            
        return fluent_icon
    
    def get_icon_for_extension(self, file_ext):
        """直接根据文件扩展名获取对应的Fluent图标
        
        参数:
            file_ext (str): 文件扩展名（不包含点号）
            
        返回:
            QIcon: 文件对应的图标
        """
        return self.get_icon_for_file(file_ext=file_ext)
    
    def get_large_icon_for_file(self, file_path=None, file_ext=None, size=48):
        """获取大尺寸文件图标
        
        参数:
            file_path (str, optional): 文件路径
            file_ext (str, optional): 文件扩展名（不包含点号）
            size (int): 图标大小，默认48px
            
        返回:
            QIcon: 文件对应的大图标
        """
        # 如果没有提供扩展名，从文件路径中获取
        if not file_ext and file_path:
            file_ext_raw = os.path.splitext(file_path)[1]
            file_ext = file_ext_raw.lstrip('.') if file_ext_raw else ""
            
        if file_ext:
            file_ext = file_ext.lower()
            
        # 根据文件类型选择合适的Fluent图标
        icon_name = "ic_fluent_document_48_filled"  # 默认文档图标
        icon_color = self.file_type_colors.get(file_ext, self.file_type_colors['default'])
        
        # 根据文件类型选择图标
        if file_ext:
            if file_ext == 'exe' or file_ext == 'msi' or file_ext == 'appx' or file_ext == 'msix':
                icon_name = "ic_fluent_apps_24_regular"
            elif file_ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
                icon_name = "ic_fluent_folder_zip_24_regular"
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']:
                icon_name = "ic_fluent_image_48_regular"
            elif file_ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']:
                icon_name = "ic_fluent_music_note_2_24_regular"
            elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                icon_name = "ic_fluent_video_clip_24_regular"
            elif file_ext in ['pdf']:
                icon_name = "ic_fluent_document_pdf_24_regular"
            elif file_ext in ['doc', 'docx']:
                icon_name = "ic_fluent_document_catch_up_24_regular"
            elif file_ext in ['xls', 'xlsx']:
                icon_name = "ic_fluent_book_globe_24_regular"
            elif file_ext in ['ppt', 'pptx']:
                icon_name = "ic_fluent_board_24_regular"
            elif file_ext in ['py', 'js', 'html', 'css', 'cpp', 'c', 'java']:
                icon_name = "ic_fluent_code_24_regular"
            elif file_ext in ['bat', 'cmd', 'ps1', 'sh']:
                icon_name = "ic_fluent_script_24_regular"
        
        # 获取图标
        fluent_icon = self.font_manager.get_qicon(icon_name, icon_color)
        
        return fluent_icon
    