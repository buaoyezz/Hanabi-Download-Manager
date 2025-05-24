from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor

import os
import sys
import ctypes
import win32api
import win32con
import win32ui
import win32gui
from PIL import Image
import io

class FileIconGetter:
    def __init__(self):
        self.icon_provider = QFileIconProvider()
        
        # 文件类型对应的emoji字典
        self.file_emoji_map = {
            # 文档类型
            'pdf': '📄', 
            'doc': '📝', 'docx': '📝', 'txt': '📃', 'odt': '📝',
            # 图片类型
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 
            'svg': '🖼️', 'webp': '🖼️', 'bmp': '🖼️',
            # 视频类型
            'mp4': '🎬', 'mov': '🎬', 'avi': '🎬', 'mkv': '🎬', 
            'webm': '🎬', 'flv': '🎬', 'wmv': '🎬',
            # 音频类型
            'mp3': '🎵', 'wav': '🎵', 'ogg': '🎵', 'flac': '🎵', 
            'm4a': '🎵', 'aac': '🎵',
            # 压缩文件
            'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️', 'tar': '🗜️', 
            'gz': '🗜️', 'bz2': '🗜️',
            # 可执行文件
            'exe': '⚙️', 'msi': '⚙️', 'bat': '⚙️', 'sh': '⚙️',
            'apk': '📱', 'app': '📱',
            # 代码文件
            'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨', 
            'json': '📋', 'xml': '📋', 'java': '☕', 
            'cpp': '📈', 'c': '📊', 'h': '📑', 'go': '🔹',
            # 默认
            'default': '📄'
        }
        
        # 文件类型对应的颜色
        self.file_type_colors = {
            # 图片 - 紫色
            'jpg': "#B39DDB", 'jpeg': "#B39DDB", 'png': "#B39DDB", 
            'gif': "#B39DDB", 'svg': "#B39DDB", 'webp': "#B39DDB",
            # 视频 - 红色
            'mp4': "#FF7043", 'mov': "#FF7043", 'avi': "#FF7043", 
            'mkv': "#FF7043", 'webm': "#FF7043",
            # 音频 - 绿色
            'mp3': "#66BB6A", 'wav': "#66BB6A", 'ogg': "#66BB6A", 
            'flac': "#66BB6A", 'm4a': "#66BB6A",
            # 压缩包 - 黄色
            'zip': "#FFCA28", 'rar': "#FFCA28", '7z': "#FFCA28", 
            'tar': "#FFCA28", 'gz': "#FFCA28",
            # 可执行文件 - 橙色
            'exe': "#FF9800", 'msi': "#FF9800",
            # 安卓应用 - 绿色
            'apk': "#7CB342",
            # 文档 - 蓝色
            'pdf': "#42A5F5", 'doc': "#42A5F5", 'docx': "#42A5F5", 
            'txt': "#42A5F5", 'odt': "#42A5F5",
            # 代码 - 青色
            'py': "#26C6DA", 'js': "#26C6DA", 'html': "#26C6DA", 
            'css': "#26C6DA", 'json': "#26C6DA", 'xml': "#26C6DA", 
            'java': "#26C6DA", 'cpp': "#26C6DA", 'c': "#26C6DA",
            # 默认 - 浅蓝色
            'default': "#4285F4"
        }
    
    def get_windows_exe_icon(self, exe_path):
        """
        从Windows EXE文件中提取图标
        :param exe_path: EXE文件路径
        :return: QIcon对象或None
        """
        # 仅在Windows系统下运行
        if not (sys.platform.startswith('win') and os.path.exists(exe_path)):
            print("不是Windows系统或文件不存在")
            return None
            
        try:
            print(f"尝试提取Windows EXE图标: {exe_path}")
            # 使用win32api提取图标
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            
            # 检查是否成功提取到图标
            if not large or len(large) == 0:
                print("没有找到图标")
                return None
                
            # 安全地销毁small图标
            if small and len(small) > 0:
                for i in range(len(small)):
                    try:
                        if small[i] != 0:
                            win32gui.DestroyIcon(small[i])
                    except Exception as e:
                        print(f"销毁small图标失败: {e}")
            
            # 获取图标信息
            try:
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, 32, 32)
                hdc = hdc.CreateCompatibleDC()
                
                hdc.SelectObject(hbmp)
                
                # 绘制large图标
                if large[0] != 0:
                    hdc.DrawIcon((0, 0), large[0])
                    
                # 安全地销毁large图标
                for i in range(len(large)):
                    try:
                        if large[i] != 0:
                            win32gui.DestroyIcon(large[i])
                    except Exception as e:
                        print(f"销毁large图标失败: {e}")
                
                # 转换为QPixmap
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer('RGBA', (32, 32), bmpstr, 'raw', 'BGRA', 0, 1)
                
                # 释放资源
                hdc.DeleteDC()
                win32gui.ReleaseDC(0, win32gui.GetDC(0))
                
                # 转为QPixmap并创建QIcon
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                pixmap = QPixmap()
                pixmap.loadFromData(buffer.getvalue())
                
                if not pixmap.isNull():
                    print("成功提取Windows EXE图标")
                    return QIcon(pixmap)
            except Exception as e:
                print(f"处理图标数据失败: {e}")
                return None
        except Exception as e:
            print(f"提取Windows EXE图标失败: {e}")
            return None
            
        return None
    
    def get_file_icon(self, file_path=None, file_ext=None):
        """
        获取文件图标
        :param file_path: 文件路径
        :param file_ext: 文件扩展名(不带.)
        :return: QIcon对象或None
        """
        # 处理特殊情况：无扩展名
        if file_ext == "No" or file_ext == "":
            # 尝试使用通用文件图标
            try:
                generic_icon = self.icon_provider.icon(QFileIconProvider.File)
                if not generic_icon.isNull():
                    return generic_icon
            except Exception as e:
                print(f"获取通用文件图标失败: {e}")
            
            # 如果无法获取通用图标，返回None，让上层使用默认图标
            return None

        # 尝试多种方式获取系统图标
        icon = None
        
        # 特殊处理Windows下的EXE文件
        if file_path and file_ext and file_ext.lower() == 'exe' and sys.platform.startswith('win'):
            try:
                # 首先尝试提取EXE自身的图标
                exe_icon = self.get_windows_exe_icon(file_path)
                if exe_icon and not exe_icon.isNull():
                    print("成功获取EXE文件自身图标")
                    return exe_icon
            except Exception as e:
                print(f"获取EXE自身图标失败: {e}")
        
        # 方法1: 如果传入了文件路径，尝试获取系统图标
        if file_path and os.path.exists(file_path):
            try:
                print(f"尝试从实际文件获取图标: {file_path}")
                file_info = QFileInfo(file_path)
                icon = self.icon_provider.icon(file_info)
                if not icon.isNull():
                    print(f"成功从实际文件获取图标")
                    return icon
            except Exception as e:
                print(f"从实际文件获取图标失败: {e}")
        
        # 方法2: 使用临时文件路径尝试获取扩展名对应的图标
        if file_ext:
            try:
                # 对于Windows系统上的exe文件，尝试特殊处理
                if file_ext.lower() == 'exe':
                    # 尝试使用特殊类型获取可执行文件图标
                    print(f"尝试获取可执行文件图标")
                    exe_icon = self.icon_provider.icon(QFileIconProvider.File)
                    if not exe_icon.isNull():
                        print(f"成功获取可执行文件通用图标")
                        return exe_icon
                
                # 创建临时文件路径，不实际创建文件
                temp_file_path = os.path.join(os.path.expanduser("~"), f"temp_icon_test.{file_ext}")
                print(f"尝试从扩展名构建的路径获取图标: {temp_file_path}")
                
                file_info = QFileInfo(temp_file_path)
                icon = self.icon_provider.icon(file_info)
                if not icon.isNull():
                    print(f"成功从扩展名获取图标")
                    return icon
            except Exception as e:
                print(f"从扩展名获取图标失败: {e}")
                
        # 方法3: 尝试使用QFileIconProvider内置的图标类型
        try:
            if file_ext:
                file_ext = file_ext.lower()
                
                # 选择适当的内置图标类型
                icon_type = None
                if file_ext in ['exe', 'msi', 'bat']:
                    icon_type = QFileIconProvider.File  # 可执行文件
                elif file_ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
                    icon_type = QFileIconProvider.File  # 压缩文件
                elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']:
                    icon_type = QFileIconProvider.File  # 图片文件
                elif file_ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']:
                    icon_type = QFileIconProvider.File  # 音频文件
                elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                    icon_type = QFileIconProvider.File  # 视频文件
                elif file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                    icon_type = QFileIconProvider.File  # 文档文件
                else:
                    icon_type = QFileIconProvider.File  # 默认文件图标
                
                if icon_type:
                    print(f"尝试使用内置图标类型")
                    icon = self.icon_provider.icon(icon_type)
                    if not icon.isNull():
                        print(f"成功获取内置类型图标")
                        return icon
        except Exception as e:
            print(f"获取内置类型图标失败: {e}")
        
        # 无法获取系统图标，返回None，上层应该使用emoji替代
        print("无法获取系统图标，将使用替代图标")
        return None
    
    def get_file_emoji(self, filename):
        """
        获取文件对应的emoji
        :param filename: 文件名
        :return: emoji字符
        """
        if not filename:
            return self.file_emoji_map['default']
        
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip('.')
        
        # 如果没有扩展名或扩展名是"No"，使用默认图标
        if not ext or ext == "No":
            return "📄"  # 无扩展名文件使用普通文档图标
        
        return self.file_emoji_map.get(ext, self.file_emoji_map['default'])
    
    def get_file_color(self, filename):
        """
        获取文件对应的颜色
        :param filename: 文件名
        :return: 颜色值(HEX)
        """
        if not filename:
            return self.file_type_colors['default']
        
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip('.')
        
        # 如果没有扩展名或扩展名是"No"，使用特殊的灰色
        if not ext or ext == "No":
            return "#808080"  # 无扩展名文件使用灰色
        
        return self.file_type_colors.get(ext, self.file_type_colors['default'])
    
    def get_icon_label_style(self, filename):
        """
        获取图标标签的样式
        :param filename: 文件名
        :return: 样式字符串
        """
        color = self.get_file_color(filename)
        
        return f"""
            QLabel {{
                background-color: {color};
                color: white;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
                text-align: center;
            }}
        """
    
    def get_icon_placeholder(self, filename):
        """
        获取图标占位符文本
        :param filename: 文件名
        :return: 占位符文本
        """
        if not filename:
            return "?"
            
        _, ext = os.path.splitext(filename)
        ext = ext.lower().lstrip('.')
        
        # 如果没有扩展名或扩展名是"No"，显示"NO"文本
        if not ext or ext == "No":
            return "NO"
        
        # 获取emoji
        emoji = self.get_file_emoji(filename)
        
        # 如果emoji不存在或无法显示，使用扩展名首字母或特定文本代替
        if ext in ['exe', 'msi']:
            return "EXE"
        elif ext == 'apk':
            return "APK"
        elif ext in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']:
            return "IMG"
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            return "VID"
        elif ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
            return "AUD"
        elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
            return "ZIP"
        elif ext == 'pdf':
            return "PDF"
        
        # 使用文件扩展名首字母大写
        return emoji if emoji else (ext[0].upper() if ext else "NO")

    def create_pixmap_with_emoji(self, emoji, size=60, bg_color=None):
        """
        创建带有emoji的QPixmap
        :param emoji: emoji字符
        :param size: 图标大小
        :param bg_color: 背景颜色
        :return: QPixmap对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        if bg_color is None:
            bg_color = "#4285F4"  # 默认蓝色
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制圆形背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg_color))
        painter.drawEllipse(0, 0, size, size)
        
        # 绘制emoji
        font = painter.font()
        font.setPointSize(size // 2)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
        
        painter.end()
        return pixmap
