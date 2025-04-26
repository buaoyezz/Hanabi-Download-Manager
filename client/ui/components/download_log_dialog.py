from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                              QPushButton, QLabel, QWidget, QSplitter)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QTextFormat
from core.font.font_manager import FontManager
import time
import json

class DownloadLogDialog(QDialog):
    def __init__(self, parent=None, download_info=None):
        super().__init__(parent)
        
        # 设置窗口基本属性
        self.setWindowTitle("下载详细日志")
        self.resize(900, 600)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 设置下载信息
        self.download_info = download_info or {}
        
        # 创建UI
        self.setup_ui()
        
        # 填充日志信息
        self.update_log_info()
        
    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        
        # 上部分 - 基本下载信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # 下载基本信息标签
        info_title = QLabel("下载基本信息")
        info_title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.font_manager.apply_font(info_title)
        info_layout.addWidget(info_title)
        
        # 文本编辑器用于显示基本信息
        self.info_editor = QTextEdit()
        self.info_editor.setReadOnly(True)
        self.info_editor.setMinimumHeight(150)
        self.info_editor.setFont(QFont("Consolas", 10))
        self.info_editor.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
            }
        """)
        info_layout.addWidget(self.info_editor)
        
        # 下部分 - 分段下载信息
        segments_widget = QWidget()
        segments_layout = QVBoxLayout(segments_widget)
        segments_layout.setContentsMargins(0, 0, 0, 0)
        
        # 分段信息标签
        segments_title = QLabel("分段下载信息")
        segments_title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.font_manager.apply_font(segments_title)
        segments_layout.addWidget(segments_title)
        
        # 文本编辑器用于显示分段信息
        self.segments_editor = QTextEdit()
        self.segments_editor.setReadOnly(True)
        self.segments_editor.setFont(QFont("Consolas", 10))
        self.segments_editor.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
            }
        """)
        segments_layout.addWidget(self.segments_editor)
        
        # 添加两个部分到分割器
        splitter.addWidget(info_widget)
        splitter.addWidget(segments_widget)
        splitter.setSizes([200, 400])  # 设置初始大小比例
        
        # 将分割器添加到主布局
        main_layout.addWidget(splitter, 1)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        self.font_manager.apply_font(self.refresh_btn)
        self.refresh_btn.clicked.connect(self.update_log_info)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #B39DDB;
                color: #121212;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
        """)
        self.font_manager.apply_font(self.close_btn)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
        
    def set_download_info(self, download_info):
        """设置下载信息"""
        self.download_info = download_info
        self.update_log_info()
    
    def update_log_info(self):
        """更新日志信息显示"""
        if not self.download_info:
            return
            
        # 清空编辑器
        self.info_editor.clear()
        self.segments_editor.clear()
        
        # 获取下载管理器
        manager = self.download_info.get('manager')
        if not manager:
            return
            
        # 显示基本信息
        self.add_info_line("时间", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.add_info_line("下载URL", manager.url)
        self.add_info_line("文件名", manager.filename)
        self.add_info_line("保存路径", str(manager.savePath))
        self.add_info_line("文件大小", self.get_readable_size(manager.fileSize))
        self.add_info_line("线程数", str(manager.threadCount))
        self.add_info_line("动态线程", "启用" if manager.dynamicThreads else "禁用")
        self.add_info_line("支持多线程", "是" if manager.supportsMultiThreading else "否")
        self.add_info_line("下载状态", self.download_info.get('status', '未知'))
        
        # HTTP请求头信息
        self.add_info_line("HTTP请求头", "")
        headers_json = json.dumps(manager.headers, indent=2, ensure_ascii=False)
        self.info_editor.append(headers_json)
        
        # 添加空行
        self.info_editor.append("\n")
        
        # 显示分段信息
        if hasattr(manager, 'segments') and manager.segments:
            self.segments_editor.append("分段详细信息:")
            
            for i, segment in enumerate(manager.segments):
                segment_json = {
                    "分段序号": i + 1,
                    "起始位置": segment.startPos,
                    "当前进度": segment.progress,
                    "结束位置": segment.endPos,
                    "已下载": self.get_readable_size(segment.progress - segment.startPos),
                    "总大小": self.get_readable_size(segment.endPos - segment.startPos),
                    "完成率": f"{((segment.progress - segment.startPos) / (segment.endPos - segment.startPos + 1) * 100):.2f}%"
                }
                
                # 添加JSON格式的分段信息
                segment_str = json.dumps(segment_json, indent=2, ensure_ascii=False)
                format_segment = QTextCharFormat()
                
                # 根据完成情况设置不同颜色
                progress_percent = (segment.progress - segment.startPos) / (segment.endPos - segment.startPos + 1)
                if progress_percent >= 1.0:
                    format_segment.setForeground(QColor("#28A745"))  # 绿色表示完成
                elif progress_percent > 0:
                    format_segment.setForeground(QColor("#B39DDB"))  # 紫色表示进行中
                else:
                    format_segment.setForeground(QColor("#FFFFFF"))  # 白色表示未开始
                
                cursor = self.segments_editor.textCursor()
                cursor.movePosition(QTextCursor.End)
                cursor.insertText(segment_str + "\n\n", format_segment)
    
    def add_info_line(self, key, value):
        """向信息编辑器添加一行键值对"""
        cursor = self.info_editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # 添加键
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#B39DDB"))
        key_format.setFontWeight(QFont.Bold)
        cursor.insertText(f"{key}: ", key_format)
        
        # 添加值
        value_format = QTextCharFormat()
        value_format.setForeground(QColor("#FFFFFF"))
        cursor.insertText(f"{value}\n", value_format)
        
        self.info_editor.setTextCursor(cursor)
    
    @staticmethod
    def get_readable_size(size_in_bytes):
        """将字节大小转换为可读的大小格式"""
        if not isinstance(size_in_bytes, (int, float)) or size_in_bytes < 0:
            return "未知"
            
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size_in_bytes = float(size_in_bytes)
        while size_in_bytes >= 1024 and i < len(size_names) - 1:
            size_in_bytes /= 1024
            i += 1
        return f"{size_in_bytes:.2f} {size_names[i]}" 