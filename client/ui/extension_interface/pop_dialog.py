from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLabel, QProgressBar, QFrame, QFileDialog, QLineEdit,
                                QGraphicsDropShadowEffect, QSpacerItem, QSizePolicy, QCheckBox,
                                QScrollArea, QApplication)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen, QFont, QIcon

import os
import time
import logging
import threading
import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from core.download_core.download_kernel_reformed import DownloadEngine
from connect.fallback_connector import FallbackConnector
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle

class ShadowFrame(QFrame):
    """带阴影效果的圆角边框"""
    def __init__(self, parent=None, radius=12, bg_color="#252526"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        
        # 设置阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
        
        # 透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        # 绘制圆角矩形
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建路径
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self.radius, self.radius)
        
        # 填充背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)

class DownloadPopDialog(QDialog):
    """下载弹窗对话框"""
    
    # 定义信号
    downloadRequested = Signal(dict)   # 请求下载
    downloadCancelled = Signal(str)    # 取消下载
    downloadPaused = Signal(str)       # 暂停下载
    downloadResumed = Signal(str)      # 恢复下载
    fileOpened = Signal(str)           # 打开文件
    folderOpened = Signal(str)         # 打开文件夹
    downloadCompleted = Signal(dict)   # 下载完成信号
    
    # 辅助方法：安全检查UI控件是否已被销毁
    @staticmethod
    def _is_destroyed(widget):
        """检查Qt控件是否已被销毁
        
        参数:
            widget: Qt控件对象
            
        返回:
            bool: 如果控件已被销毁则返回True，否则返回False
        """
        try:
            # 对于Qt对象，我们可以尝试访问其属性来检查是否已销毁
            # 此处使用对象的metaObject或objectName等属性进行测试
            # 如果已销毁，将引发RuntimeError
            if widget is None:
                return True
                
            # 尝试访问Qt对象属性
            if hasattr(widget, 'objectName'):
                widget.objectName()
                return False
            elif hasattr(widget, 'isVisible'):
                widget.isVisible()
                return False
            else:
                # 如果无法确定，假设未销毁
                return False
        except (RuntimeError, AttributeError, Exception):
            # 如果访问属性时出错，则认为对象已销毁
            return True
    
    @staticmethod
    def create_and_show(download_data=None, parent=None, auto_start=False):
        """创建并显示下载弹窗
        
        参数:
            download_data (dict): 下载数据，如果为None则显示添加下载界面
            parent: 父窗口
            auto_start (bool): 是否自动开始下载，默认为False
            
        返回:
            DownloadPopDialog: 创建的弹窗对象
        """
        dialog = DownloadPopDialog(parent)
        
        if download_data:
            # 预处理下载数据
            task_data = dialog._process_download_data(download_data)
            
            if auto_start:
                # 显示下载中界面并开始下载
                dialog._create_downloading_ui(task_data)
                dialog._start_download(task_data)
            else:
                # 显示添加下载界面，但填入URL和文件名
                dialog._create_add_download_ui()
                
                # 填入URL
                if "url" in task_data and dialog.url_input:
                    dialog.url_input.setText(task_data.get("url", ""))
                    
                # 填入文件名
                if "file_name" in task_data and dialog.filename_input:
                    dialog.filename_input.setText(task_data.get("file_name", ""))
                    
                # 填入保存路径
                if "save_path" in task_data and dialog.save_path_input:
                    dialog.save_path_input.setText(task_data.get("save_path", ""))
                    
                # 多线程选项
                if "multi_thread" in task_data and dialog.multi_thread_checkbox:
                    dialog.multi_thread_checkbox.setChecked(task_data.get("multi_thread", True))
                    
                # 保存任务数据，以便下载按钮使用
                dialog.pending_task_data = task_data
        
        dialog.show()
        return dialog
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 设置无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 窗口大小 - 根据不同状态动态设置
        # 注意：不再设置固定的最小尺寸，而是在各个创建UI的方法中设置具体尺寸
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 初始化UI
        self._setup_ui()
        
        # 任务ID和状态
        self.task_id = ""
        self.current_state = "add"  # add, downloading, completed
        
        # 下载引擎
        self.download_engine = None
        
        # 线程锁
        self.thread_lock = threading.Lock()
        
        # 鼠标拖动相关
        self.dragging = False
        self.drag_position = QPoint()
        
        # 定时关闭 - 5秒后自动关闭完成弹窗
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close)
        
        # 进度更新定时器
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_download_info)
        
        # 分段信息区域是否显示
        self.show_segments = True
        
        # 是否自动关闭完成页面
        self.auto_close_completed = False
        
        # 待处理的任务数据
        self.pending_task_data = None
        
        # 安装事件过滤器以确保窗口可以正常关闭
        self.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """事件过滤器，确保窗口可以正常响应事件"""
        # 处理任何可能导致窗口卡住的事件
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止下载引擎
        with self.thread_lock:
            if hasattr(self, 'download_engine') and self.download_engine and hasattr(self.download_engine, 'is_running') and self.download_engine.is_running:
                try:
                    self.download_engine.stop()
                    # 等待线程安全停止
                    if hasattr(self.download_engine, 'wait'):
                        self.download_engine.wait(300)  # 等待最多300ms
                except Exception as e:
                    logging.error(f"停止下载引擎失败: {e}")
                
        # 停止定时器
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        if hasattr(self, 'auto_close_timer') and self.auto_close_timer.isActive():
            self.auto_close_timer.stop()
        
        # 断开所有信号连接
        try:
            if hasattr(self, 'download_engine') and self.download_engine:
                self.download_engine.initialized.disconnect()
                self.download_engine.block_progress_updated.disconnect()
                self.download_engine.speed_updated.disconnect()
                self.download_engine.download_completed.disconnect()
                self.download_engine.error_occurred.disconnect()
                self.download_engine.file_name_changed.disconnect()
        except Exception:
            pass  # 忽略断开连接时的错误
        
        # 接受关闭事件
        event.accept()
        
        # 使用计时器延迟删除，确保所有待处理事件已处理
        QTimer.singleShot(100, self.deleteLater)
    
    def _setup_ui(self):
        """初始化UI"""
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 创建内容框架
        self.frame = ShadowFrame(self, radius=15, bg_color="#252526")
        self.main_layout.addWidget(self.frame)
        
        # 框架布局
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(15, 15, 15, 15)  # 缩小边距
        self.frame_layout.setSpacing(10)  # 减小间距
        
        # 顶部区域 - 标题栏
        self._create_title_bar()
        
        # 内容区域 - 根据状态动态创建
        self.content_widget = QFrame()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 5, 0, 5)  # 缩小边距
        self.content_layout.setSpacing(10)  # 减小间距
        self.frame_layout.addWidget(self.content_widget)
        
        # 底部区域 - 按钮
        self.button_widget = QFrame()
        self.button_layout = QHBoxLayout(self.button_widget)
        self.button_layout.setContentsMargins(0, 5, 0, 0)  # 缩小边距
        self.button_layout.setSpacing(10)  # 减小间距
        self.frame_layout.addWidget(self.button_widget)
        
        # 默认显示添加下载UI
        self._create_add_download_ui()
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QFrame()
        title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)
        title_layout.setSpacing(10)
        
        # 标题图标
        self.title_icon = QLabel()
        self.title_icon.setFixedSize(24, 24)
        # 使用字体图标替代图片
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(self.title_icon, "ic_fluent_arrow_download_24_regular", size=22)
            self.title_icon.setStyleSheet("color: #B39DDB;")
        else:
            self.title_icon.setStyleSheet("background-image: url(assets/icons/icon_download_purple.png); background-position: center; background-repeat: no-repeat;")
        title_layout.addWidget(self.title_icon)
        
        # 标题文本
        self.title_label = QLabel("添加下载")
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.title_label)
        title_layout.addWidget(self.title_label, 1)
        
        # 关闭按钮
        self.close_button = QPushButton()
        self.close_button.setFixedSize(30, 30)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(self.close_button, "ic_fluent_dismiss_24_regular", size=16)
            self.close_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                    color: #AAAAAA;
                    border-radius: 15px;
                }
                QPushButton:hover {
                    background-color: #3E3E42;
                    color: #FFFFFF;
                }
            """)
        else:
            self.close_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                    background-image: url(assets/icons/icon_close.png);
                    background-position: center;
                    background-repeat: no-repeat;
                }
                QPushButton:hover {
                    background-color: #3E3E42;
                    border-radius: 15px;
                }
            """)
        self.close_button.clicked.connect(self.close)
        title_layout.addWidget(self.close_button)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        
        # 添加到布局
        title_container = QVBoxLayout()
        title_container.setContentsMargins(0, 0, 0, 0)
        title_container.setSpacing(5)
        title_container.addWidget(title_bar)
        title_container.addWidget(separator)
        
        self.frame_layout.addLayout(title_container)
    
    def _create_add_download_ui(self):
        """创建添加下载UI"""
        # 清空内容区域
        self._clear_content()
        
        # 设置标题
        self.title_label.setText("添加下载")
        
        # 创建一个总容器
        main_container = QFrame()
        main_container.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # URL输入区域
        url_layout = QHBoxLayout()
        url_layout.setSpacing(5)
        
        url_label = QLabel("下载链接")
        url_label.setFixedWidth(60)
        url_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(url_label)
        url_layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入下载链接...")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.url_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.url_input)
        url_layout.addWidget(self.url_input)
        
        main_layout.addLayout(url_layout)
        
        # 文件名区域
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(5)
        
        filename_label = QLabel("文件名")
        filename_label.setFixedWidth(60)
        filename_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(filename_label)
        filename_layout.addWidget(filename_label)
        
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("自动获取文件名...")
        self.filename_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.filename_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.filename_input)
        filename_layout.addWidget(self.filename_input)
        
        main_layout.addLayout(filename_layout)
        
        # 保存路径区域
        save_path_layout = QHBoxLayout()
        save_path_layout.setSpacing(5)
        
        save_path_label = QLabel("保存位置")
        save_path_label.setFixedWidth(60)
        save_path_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(save_path_label)
        save_path_layout.addWidget(save_path_label)
        
        self.save_path_input = QLineEdit()
        self.save_path_input.setText(os.path.join(os.path.expanduser("~"), "Downloads"))
        self.save_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.save_path_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.save_path_input)
        save_path_layout.addWidget(self.save_path_input)
        
        self.browse_button = QPushButton("浏览")
        self.browse_button.setFixedSize(60, 28)
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.browse_button.clicked.connect(self._on_browse)
        save_path_layout.addWidget(self.browse_button)
        
        main_layout.addLayout(save_path_layout)
        
        # 多线程选项
        self.multi_thread_checkbox = QCheckBox("使用多线程下载")
        self.multi_thread_checkbox.setChecked(True)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.multi_thread_checkbox)
        
        self.multi_thread_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 2px;
                border: 1px solid #555555;
                background: #333333;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #8A7CEC;
            }
            QCheckBox::indicator:checked {
                background: #8A7CEC;
                border: 1px solid #8A7CEC;
            }
        """)
        main_layout.addWidget(self.multi_thread_checkbox)
        
        # 添加到主内容区域
        self.content_layout.addWidget(main_container)
        
        # 底部按钮
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        
        button_layout.addStretch(1)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(80, 32)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 13px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel_download)
        button_layout.addWidget(self.cancel_button)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedSize(80, 32)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #8A7CEC;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #9E8FEF;
            }
            QPushButton:pressed {
                background-color: #7A6CD8;
            }
        """)
        self.download_button.clicked.connect(self._on_download)
        button_layout.addWidget(self.download_button)
        
        self.content_layout.addWidget(button_container)
        
        # 设置当前状态
        self.current_state = "add"
        
        # 为URL输入框添加内容变化处理
        self.url_input.textChanged.connect(self._on_url_changed)
        
        # 设置添加下载页面的窗口大小
        QTimer.singleShot(0, lambda: self.setMinimumSize(643, 318))
    
    def _create_downloading_ui(self, task_data):
        """创建下载中UI"""
        # 清空内容区域 - 确保先前的UI完全清除
        self._clear_content()
        
        # 设置标题
        self.title_label.setText("正在下载")
        
        # 文件名和图标区域
        file_info_frame = QFrame()
        file_info_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        file_info_layout = QHBoxLayout(file_info_frame)
        file_info_layout.setContentsMargins(15, 12, 15, 12)
        file_info_layout.setSpacing(15)
        
        # 文件图标
        file_icon = QLabel()
        file_icon.setFixedSize(36, 36)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(file_icon, "ic_fluent_document_24_regular", size=24)
            file_icon.setStyleSheet("color: #B39DDB; background-color: transparent;")
        else:
            file_icon.setStyleSheet("background-image: url(assets/icons/icon_file.png); background-position: center; background-repeat: no-repeat;")
        file_info_layout.addWidget(file_icon)
        
        # 文件信息区域
        file_text_layout = QVBoxLayout()
        file_text_layout.setSpacing(4)
        
        # 文件名
        self.filename_label = QLabel(task_data.get("file_name", "未知文件"))
        self.filename_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.filename_label)
        self.filename_label.setWordWrap(True)
        self.filename_label.setMaximumWidth(380)  # 限制最大宽度，防止窗口过宽
        file_text_layout.addWidget(self.filename_label)
        
        # 文件大小和状态
        size_status_layout = QHBoxLayout()
        size_status_layout.setSpacing(15)
        
        # 文件大小
        self.size_label = QLabel("大小: 获取中...")
        self.size_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.size_label)
        size_status_layout.addWidget(self.size_label)
        
        # 下载状态
        self.status_label = QLabel("初始化中...")
        self.status_label.setStyleSheet("color: #8A7CEC; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.status_label)
        size_status_layout.addWidget(self.status_label)
        
        size_status_layout.addStretch(1)
        file_text_layout.addLayout(size_status_layout)
        
        file_info_layout.addLayout(file_text_layout, 1)
        self.content_layout.addWidget(file_info_frame)
        
        # 进度信息区域
        progress_frame = QFrame()
        progress_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(15, 15, 15, 15)
        progress_layout.setSpacing(15)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3A3A3A;
                border: none;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8A7CEC, stop:1 #B39DDB);
                border-radius: 5px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # 下载详情布局
        details_layout = QHBoxLayout()
        details_layout.setSpacing(20)
        
        # 速度信息
        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(6)
        
        # 速度图标
        speed_icon = QLabel()
        speed_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(speed_icon, "ic_fluent_arrow_trending_24_regular", size=14)
            speed_icon.setStyleSheet("color: #B0B0B0;")
        else:
            speed_icon.setStyleSheet("background-image: url(assets/icons/icon_speed.png); background-position: center; background-repeat: no-repeat;")
        speed_layout.addWidget(speed_icon)
        
        # 速度文本
        self.speed_label = QLabel("0 B/s")
        self.speed_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.speed_label)
        speed_layout.addWidget(self.speed_label)
        
        details_layout.addLayout(speed_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("background-color: #505050;")
        separator.setFixedWidth(1)
        details_layout.addWidget(separator)
        
        # 剩余时间信息
        time_layout = QHBoxLayout()
        time_layout.setSpacing(6)
        
        # 时间图标
        time_icon = QLabel()
        time_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(time_icon, "ic_fluent_clock_24_regular", size=14)
            time_icon.setStyleSheet("color: #B0B0B0;")
        else:
            time_icon.setStyleSheet("background-image: url(assets/icons/icon_time.png); background-position: center; background-repeat: no-repeat;")
        time_layout.addWidget(time_icon)
        
        # 时间文本
        self.time_label = QLabel("计算中...")
        self.time_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.time_label)
        time_layout.addWidget(self.time_label)
        
        details_layout.addLayout(time_layout)
        details_layout.addStretch(1)
        
        progress_layout.addLayout(details_layout)
        self.content_layout.addWidget(progress_frame)
        
        # 分段信息按钮容器
        segment_header_frame = QFrame()
        segment_header_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        segment_header_layout = QHBoxLayout(segment_header_frame)
        segment_header_layout.setContentsMargins(15, 10, 15, 10)
        segment_header_layout.setSpacing(10)
        
        # 分段信息图标
        segments_icon = QLabel()
        segments_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(segments_icon, "ic_fluent_data_histogram_24_regular", size=14)
            segments_icon.setStyleSheet("color: #B39DDB;")
        else:
            segments_icon.setStyleSheet("background-image: url(assets/icons/icon_segments.png); background-position: center; background-repeat: no-repeat;")
        segment_header_layout.addWidget(segments_icon)
        
        # 分段信息标题
        segments_title = QLabel("分段下载信息")
        segments_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(segments_title)
        segment_header_layout.addWidget(segments_title)
        
        segment_header_layout.addStretch(1)
        
        # 切换按钮
        self.toggle_segments_button = QPushButton()
        self.toggle_segments_button.setFixedSize(24, 24)
        if hasattr(self, 'font_manager') and hasattr(self, 'toggle_segments_button'):
            if self.show_segments:
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_up_24_regular", size=16)
            else:
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_down_24_regular", size=16)
        else:
            self.toggle_segments_button.setText("分段信息 ▽" if self.show_segments else "分段信息 ▷")
        self.toggle_segments_button.clicked.connect(self._toggle_segments_display)
        segment_header_layout.addWidget(self.toggle_segments_button)
        
        self.content_layout.addWidget(segment_header_frame)
        
        # 分段信息区域
        self.segments_frame = QFrame()
        self.segments_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        self.segments_layout = QVBoxLayout(self.segments_frame)
        self.segments_layout.setContentsMargins(15, 15, 15, 15)
        self.segments_layout.setSpacing(10)
        
        # 分段信息表头
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #323232; border-radius: 6px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(15)
        
        # 序号
        index_header = QLabel("#")
        index_header.setFixedWidth(30)
        index_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(index_header)
        header_layout.addWidget(index_header)
        
        # 状态
        status_header = QLabel("状态")
        status_header.setFixedWidth(100)
        status_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(status_header)
        header_layout.addWidget(status_header)
        
        # 已下载
        downloaded_header = QLabel("已下载")
        downloaded_header.setFixedWidth(100)
        downloaded_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(downloaded_header)
        header_layout.addWidget(downloaded_header)
        
        # 总大小
        total_header = QLabel("总大小")
        total_header.setFixedWidth(100)
        total_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(total_header)
        header_layout.addWidget(total_header)
        
        self.segments_layout.addWidget(header_frame)
        
        # 分段信息内容区域 - 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 应用滚动条样式
        ScrollStyle.apply_to_widget(scroll_area, "dark")
        
        self.segments_scroll_area = QFrame()
        self.segments_scroll_layout = QVBoxLayout(self.segments_scroll_area)
        self.segments_scroll_layout.setContentsMargins(0, 3, 0, 3)  # 减小边距
        self.segments_scroll_layout.setSpacing(3)  # 减少间距
        
        scroll_area.setWidget(self.segments_scroll_area)
        scroll_area.setMinimumHeight(80)  # 减小最小高度
        scroll_area.setMaximumHeight(120)  # 减小最大高度
        self.segments_layout.addWidget(scroll_area)
        
        self.content_layout.addWidget(self.segments_frame)
        self.segments_frame.setVisible(self.show_segments)
        
        # 添加空白空间
        self.content_layout.addStretch(1)
        
        # 底部按钮
        self.button_layout.addStretch(1)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(100, 40)
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_dismiss_24_regular")
            self.cancel_button.setIcon(icon)
            self.cancel_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            self.cancel_button.setText("  取消")
            self.font_manager.apply_font(self.cancel_button)
        
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel_download)
        self.button_layout.addWidget(self.cancel_button)
        
        self.download_button = QPushButton("")
        self.download_button.setFixedSize(100, 40)
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_pause_24_regular")  # 默认显示暂停图标
            self.download_button.setIcon(icon)
            self.download_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            self.download_button.setText("  暂停")
            self.font_manager.apply_font(self.download_button)
        
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #8A7CEC;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #9E8FEF;
            }
            QPushButton:pressed {
                background-color: #7A6CD8;
            }
        """)
        self.download_button.clicked.connect(self._on_pause_resume)
        self.button_layout.addWidget(self.download_button)
        
        # 设置当前状态
        self.current_state = "downloading"
        self.is_paused = False
        
        # 保存任务ID
        self.task_id = task_data.get("task_id", "")
        
        # 初始化段列表
        self.segment_rows = []
        
        # 设置窗口大小
        QTimer.singleShot(0, lambda: self.setMinimumSize(633, 474))
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _extract_filename_from_url(self, url):
        """从URL提取文件名"""
        try:
            # 解析URL
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # 从路径中获取文件名
            if path:
                filename = os.path.basename(path)
                # 处理查询参数
                if '?' in filename:
                    filename = filename.split('?')[0]
                # URL解码
                try:
                    filename = unquote(filename)
                except:
                    pass
                return filename
        except:
            pass
            
        return ""
    
    def _get_readable_size(self, size_bytes):
        """获取可读的文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
    
    def _get_readable_speed(self, speed_bytes):
        """获取可读的下载速度"""
        if speed_bytes < 1024:
            return f"{speed_bytes} B/s"
        elif speed_bytes < 1024 * 1024:
            return f"{speed_bytes/1024:.1f} KB/s"
        elif speed_bytes < 1024 * 1024 * 1024:
            return f"{speed_bytes/(1024*1024):.2f} MB/s"
        else:
            return f"{speed_bytes/(1024*1024*1024):.2f} GB/s"
    
    def _get_readable_time(self, seconds):
        """获取可读的时间格式"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}分{seconds:.0f}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}时{minutes:.0f}分"
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 用于窗口拖动"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 用于窗口拖动"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
    
    def _process_download_data(self, download_data):
        """处理下载数据，添加必要的信息
        
        参数:
            download_data (dict): 原始下载数据
            
        返回:
            dict: 处理后的任务数据
        """
        # 拷贝数据，避免修改原始对象
        task_data = dict(download_data)
        
        # 确保有ID
        if "task_id" not in task_data:
            task_data["task_id"] = f"popup_{int(time.time() * 1000)}"
        
        # 确保有requestId
        if "requestId" not in task_data:
            task_data["requestId"] = f"popup_{int(time.time() * 1000)}"
        
        # 确保有保存路径
        if "save_path" not in task_data:
            task_data["save_path"] = os.path.expanduser("~/Downloads")
            # 创建目录
            os.makedirs(task_data["save_path"], exist_ok=True)
        
        # 确保有标头
        if "headers" not in task_data:
            task_data["headers"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
            }
        
        # 处理文件名
        url = task_data.get("url", "")
        if not url:
            logging.error("下载数据缺少URL")
            return None
            
        if "file_name" not in task_data or not task_data["file_name"]:
            filename = self._extract_filename_from_url(url)
            task_data["file_name"] = filename
        
        # 添加开始时间
        task_data["start_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加多线程标志
        if "multi_thread" not in task_data:
            task_data["multi_thread"] = True
        
        return task_data
    
    def _start_download(self, task_data):
        """开始下载任务
        
        参数:
            task_data (dict): 下载任务数据
        """
        try:
            # 获取必要参数
            url = task_data.get("url", "")
            headers = task_data.get("headers", {})
            save_path = task_data.get("save_path", os.path.expanduser("~/Downloads"))
            file_name = task_data.get("file_name", "")
            multi_thread = task_data.get("multi_thread", True)
            max_concurrent = 8 if multi_thread else 1
            
            # 创建下载引擎
            with self.thread_lock:
                self.download_engine = DownloadEngine(
                    url=url,
                    headers=headers,
                    max_concurrent=max_concurrent,
                    save_path=save_path,
                    file_name=file_name,
                    smart_threading=multi_thread
                )
                
                # 连接信号
                self.download_engine.initialized.connect(self._on_download_initialized)
                self.download_engine.block_progress_updated.connect(self._on_progress_updated)
                self.download_engine.speed_updated.connect(self._on_speed_updated)
                self.download_engine.download_completed.connect(self._on_download_completed)
                self.download_engine.error_occurred.connect(self._on_download_error)
                self.download_engine.file_name_changed.connect(self._on_filename_changed)
                
                # 启动下载
                self.download_engine.start()
                
                # 启动进度更新定时器
                self.progress_timer.start(500)  # 每500毫秒更新一次
                
                # 保存任务ID
                self.task_id = task_data.get("task_id", "")
                
                # 更新UI状态
                self.status_label.setText("初始化中...")
                
                logging.info(f"弹窗已启动下载任务: {url}")
                
        except Exception as e:
            logging.error(f"启动下载任务失败: {e}")
            self._on_download_error(str(e))
    
    def _on_download_initialized(self, multi_thread_support):
        """下载初始化完成回调
        
        参数:
            multi_thread_support (bool): 是否支持多线程下载
        """
        with self.thread_lock:
            if not self.download_engine:
                return
                
            # 更新UI
            self.status_label.setText("下载中...")
            
            # 更新文件大小
            if hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                size_str = self._get_readable_size(self.download_engine.file_size)
                self.size_label.setText(f"大小: {size_str}")
    
    def _on_progress_updated(self, progress_data):
        """进度更新回调
        
        参数:
            progress_data (list): 进度数据
        """
        try:
            # 计算总进度百分比
            total_downloaded = 0
            total_size = 0
            
            # 添加更详细的字段兼容处理
            processed_blocks = []
            
            for block in progress_data:
                if isinstance(block, dict):
                    # 支持多种字段名格式
                    start_pos = block.get('start_pos', block.get('start_position', block.get('startPos', 0)))
                    end_pos = block.get('end_pos', block.get('end_position', block.get('endPos', 0)))
                    current = block.get('progress', block.get('current_pos', block.get('current_position', block.get('currentPos', start_pos))))
                    status = block.get('status', "下载中")
                elif isinstance(block, (list, tuple)) and len(block) >= 3:
                    start_pos, current, end_pos = block[:3]
                    status = "下载中" if current < end_pos else "已完成"
                else:
                    continue
                
                # 确保值合法并转为整数
                try:
                    start_pos = max(0, int(start_pos))
                    end_pos = max(start_pos, int(end_pos)) 
                    current = max(start_pos, min(end_pos, int(current)))
                except (ValueError, TypeError):
                    # 如果转换失败，使用默认值
                    start_pos, current, end_pos = 0, 0, 0
                
                # 计算已下载量
                block_downloaded = current - start_pos
                block_size = end_pos - start_pos + 1
                
                # 累计总量
                total_downloaded += block_downloaded
                total_size += block_size
                
                # 创建统一格式的块信息
                processed_block = {
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'progress': current,
                    'status': status,
                    'downloaded': block_downloaded,
                    'size': block_size
                }
                processed_blocks.append(processed_block)
            
            # 计算百分比
            if total_size > 0:
                progress = (total_downloaded / total_size) * 100
                # 如果进度超过99.9%，视为完成
                if progress > 99.9:
                    progress = 100
                
                # 更新进度条
                self.update_progress(progress)
            
            # 使用处理后的块信息更新分段信息
            if processed_blocks:
                self._update_segments_info(processed_blocks)
            
        except Exception as e:
            logging.error(f"处理进度更新失败: {e}")
    
    def _on_speed_updated(self, speed_bytes):
        """速度更新回调
        
        参数:
            speed_bytes (int): 下载速度(字节/秒)
        """
        # 更新UI
        speed_str = self._get_readable_speed(speed_bytes)
        self.speed_label.setText(f"速度: {speed_str}")
        
        # 估算剩余时间
        if hasattr(self, 'download_engine') and self.download_engine:
            try:
                if speed_bytes > 0 and hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                    # 计算已下载量
                    downloaded = self.download_engine.current_progress
                    remaining = self.download_engine.file_size - downloaded
                    
                    # 计算剩余时间
                    if remaining > 0:
                        seconds_left = remaining / speed_bytes
                        time_str = self._get_readable_time(seconds_left)
                        self.time_label.setText(time_str)
            except Exception as e:
                logging.error(f"计算剩余时间失败: {e}")
    
    def _on_download_completed(self, status=None):
        """下载完成回调"""
        logging.info("下载任务完成")
        
        # 停止定时器
        self.progress_timer.stop()
        
        # 如果已经关闭了窗口，不处理
        if not self.isVisible():
            return
        
        # 准备完成数据 - 从下载引擎获取信息
        file_name = ""
        file_size = 0
        save_path = ""
        
        with self.thread_lock:
            if self.download_engine:
                file_name = self.download_engine.file_name
                file_size = self.download_engine.file_size
                save_path = self.download_engine.save_path
                
                # 如果文件大小未知或为0，尝试从实际文件获取
                if file_size <= 0:
                    try:
                        file_path = Path(save_path) / file_name
                        if file_path.exists():
                            file_size = file_path.stat().st_size
                            logging.info(f"从实际文件获取大小: {file_size} 字节")
                    except Exception as e:
                        logging.error(f"获取实际文件大小失败: {e}")
        
        # 创建完成数据
        task_data = {
            "task_id": self.task_id,
            "file_name": file_name,
            "file_size": file_size,
            "save_path": save_path,
            "status": "已完成"
        }
        
        # 如果提供了status参数，使用其中的值覆盖
        if status and isinstance(status, dict):
            if "file_name" in status and status["file_name"]:
                task_data["file_name"] = status["file_name"]
            if "file_size" in status and status["file_size"]:
                task_data["file_size"] = status["file_size"]
            if "save_path" in status and status["save_path"]:
                task_data["save_path"] = status["save_path"]
            if "status" in status:
                task_data["status"] = status["status"]
        
        # 记录之前的窗口状态
        old_state = self.current_state
        
        # 彻底清除当前UI
        self._clear_content()
        
        # 使用QTimer延迟创建完成界面，确保前一个界面被完全清除
        QTimer.singleShot(50, lambda: self._create_completed_ui_delayed(task_data))
        
        # 发送下载完成信号
        self.downloadCompleted.emit(task_data)
        
    def _create_completed_ui_delayed(self, task_data):
        """延迟创建完成界面，确保UI刷新"""
        # 更新UI - 显示下载完成界面
        self._create_completed_ui(task_data)
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _on_download_error(self, error_msg):
        """下载错误回调
        
        参数:
            error_msg (str): 错误信息
        """
        logging.error(f"下载失败: {error_msg}")
        
        # 停止定时器
        self.progress_timer.stop()
        
        # 更新状态
        if hasattr(self, 'status_label'):
            self.status_label.setText("下载失败")
            self.status_label.setStyleSheet("color: #E53935; font-size: 12px;")
        
        # 更新按钮状态
        if hasattr(self, 'download_button'):
            self.download_button.setEnabled(False)
    
    def _on_filename_changed(self, new_filename):
        """文件名变更回调
        
        参数:
            new_filename (str): 新文件名
        """
        # 更新UI
        if hasattr(self, 'filename_label'):
            self.filename_label.setText(new_filename)
    
    def _update_download_info(self):
        """更新下载信息"""
        if self.current_state != "downloading":
            return
        
        with self.thread_lock:
            if not self.download_engine or not hasattr(self.download_engine, 'is_running'):
                return
            
            try:
                # 文件大小未知但已完成下载的情况
                file_size_unknown = hasattr(self.download_engine, 'file_size') and self.download_engine.file_size <= 0
                
                # 如果文件大小未知，尝试从实际文件获取
                if file_size_unknown:
                    try:
                        file_path = Path(self.download_engine.save_path) / self.download_engine.file_name
                        if file_path.exists():
                            actual_size = file_path.stat().st_size
                            # 检查文件是否已下载完毕（无活动块且文件大小已稳定）
                            all_inactive = True
                            for block in self.download_engine.blocks:
                                if hasattr(block, 'active') and block.active:
                                    all_inactive = False
                                    break
                                    
                            if all_inactive and actual_size > 0:
                                # 更新下载引擎中的文件大小
                                self.download_engine.file_size = actual_size
                                logging.info(f"从实际文件更新大小: {actual_size} 字节")
                    except Exception as e:
                        logging.debug(f"获取实际文件大小失败: {e}")
                
                # 更新进度
                progress = 0
                if hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                    progress = min(100, (self.download_engine.current_progress / self.download_engine.file_size) * 100)
                    self.progress_bar.setValue(int(progress))
                    
                    # 更新状态文本
                    self.status_label.setText(f"{progress:.1f}%")
                else:
                    # 文件大小未知，显示下载中状态
                    self.status_label.setText("下载中...")
                    
                    # 对于未知大小的文件，显示不确定进度
                    if hasattr(self.download_engine, 'current_progress'):
                        downloaded = self.download_engine.current_progress
                        if downloaded > 0:
                            downloaded_str = self._get_readable_size(downloaded)
                            self.size_label.setText(f"已下载: {downloaded_str}")
                
                # 更新速度
                if hasattr(self.download_engine, 'avg_speed'):
                    speed = self.download_engine.avg_speed
                    speed_str = self._get_readable_speed(speed)
                    self.speed_label.setText(speed_str)
                    
                    # 更新剩余时间 - 根据下载速度计算
                    if speed > 0 and hasattr(self.download_engine, 'file_size') and hasattr(self.download_engine, 'current_progress'):
                        if self.download_engine.file_size > 0:
                            remaining_bytes = self.download_engine.file_size - self.download_engine.current_progress
                            if remaining_bytes > 0:
                                remaining_time = remaining_bytes / speed
                                time_str = self._get_readable_time(remaining_time)
                                self.time_label.setText(time_str)
                            else:
                                self.time_label.setText("即将完成")
                        else:
                            self.time_label.setText("计算中...")
                
                # 更新文件大小信息
                if hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                    total_size_str = self._get_readable_size(self.download_engine.file_size)
                    downloaded_size_str = self._get_readable_size(self.download_engine.current_progress)
                    self.size_label.setText(f"大小: {downloaded_size_str} / {total_size_str}")
                
                # 处理下载块信息 - 从blocks属性获取信息
                if hasattr(self.download_engine, 'blocks') and self.download_engine.blocks:
                    # 创建块信息列表
                    blocks_info = []
                    all_blocks_completed = True
                    any_block_active = False
                    
                    for i, block in enumerate(self.download_engine.blocks):
                        if isinstance(block, object) and hasattr(block, 'start_position'):
                            # 计算块统计数据
                            start_pos = block.start_position
                            current_pos = block.current_position
                            end_pos = block.end_position
                            downloaded = current_pos - start_pos
                            total_size = end_pos - start_pos + 1
                            status = getattr(block, 'status', "下载中")
                            
                            # 检查块是否活跃
                            if hasattr(block, 'active') and block.active:
                                any_block_active = True
                                
                            # 检查是否所有块都已完成
                            if current_pos < end_pos:
                                all_blocks_completed = False
                            
                            # 创建块信息字典
                            block_info = {
                                "index": i,
                                "status": status,
                                "downloaded": downloaded,
                                "size": total_size,
                                "start_pos": start_pos,
                                "progress": current_pos,
                                "end_pos": end_pos,
                                "speed": getattr(block, 'download_speed', 0),
                                "active": getattr(block, 'active', False)
                            }
                            blocks_info.append(block_info)
                    
                    # 检查是否下载已完成（所有块已完成且无活动块）
                    if all_blocks_completed and not any_block_active and not self.download_engine.is_paused:
                        # 触发下载完成信号
                        logging.info("检测到所有块已完成且无活动块，触发下载完成")
                        self.progress_timer.stop()
                        
                        # 设置为100%显示
                        self.progress_bar.setValue(100)
                        self.status_label.setText("100%")
                        
                        # 可能的文件大小更新
                        if file_size_unknown:
                            try:
                                file_path = Path(self.download_engine.save_path) / self.download_engine.file_name
                                if file_path.exists():
                                    self.download_engine.file_size = file_path.stat().st_size
                                    total_size_str = self._get_readable_size(self.download_engine.file_size)
                                    downloaded_size_str = self._get_readable_size(self.download_engine.current_progress)
                                    self.size_label.setText(f"大小: {downloaded_size_str} / {total_size_str}")
                            except Exception:
                                pass
                        
                        # 调用下载完成方法
                        QTimer.singleShot(100, self._on_download_completed)
                    
                    # 如果是初始化阶段，创建分段信息UI
                    if hasattr(self, 'segment_rows') and not self.segment_rows and blocks_info:
                        self._update_segments_info(blocks_info)
                    # 否则更新现有分段信息
                    elif hasattr(self, 'segment_rows') and self.segment_rows and blocks_info:
                        for i, block_info in enumerate(blocks_info):
                            if i < len(self.segment_rows):
                                self._update_segment_row(
                                    i, 
                                    status=block_info.get("status"),
                                    start_pos=block_info.get("start_pos"),
                                    progress=block_info.get("progress"),
                                    end_pos=block_info.get("end_pos")
                                )
                
                # 如果下载已完成或已暂停，停止定时器
                if not self.download_engine.is_running or self.download_engine.is_paused:
                    self.progress_timer.stop()
                
            except Exception as e:
                logging.error(f"更新下载信息失败: {e}")
                import traceback
                traceback.print_exc()
    
    def _on_cancel_download(self):
        """取消下载"""
        with self.thread_lock:
            if hasattr(self, 'download_engine') and self.download_engine:
                try:
                    self.download_engine.stop()
                except Exception as e:
                    logging.error(f"停止下载引擎失败: {e}")
                
            if self.task_id:
                try:
                    self.downloadCancelled.emit(self.task_id)
                except Exception as e:
                    logging.error(f"发送取消下载信号失败: {e}")
        
        # 关闭窗口
        self.close()
    
    def _toggle_segments_display(self):
        """切换分段信息显示状态"""
        self.show_segments = not self.show_segments
        self.segments_frame.setVisible(self.show_segments)
        
        # 更新按钮图标
        if hasattr(self, 'font_manager') and hasattr(self, 'toggle_segments_button'):
            if self.show_segments:
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_up_24_regular", size=16)
            else:
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_down_24_regular", size=16)
        else:
            self.toggle_segments_button.setText("分段信息 ▽" if self.show_segments else "分段信息 ▷")
        
        # 调整窗口大小
        if self.isVisible():
            self.adjustSize()
    
    def _update_segment_row(self, index, status=None, downloaded=None, total=None, start_pos=None, progress=None, end_pos=None):
        """更新分段下载信息行
        
        参数:
            index (int): 行索引
            status (str): 状态文本
            downloaded (int): 已下载字节数
            total (int): 总字节数
            start_pos (int): 起始位置
            progress (int): 当前进度位置
            end_pos (int): 结束位置
        """
        # 检查索引是否有效
        if not hasattr(self, 'segment_rows') or index < 0 or index >= len(self.segment_rows):
            return
            
        row = self.segment_rows[index]
        
        # 更新状态
        if status is not None and 'status' in row:
            # 根据状态设置颜色
            status_color = "#B39DDB"  # 默认紫色
            
            if "完成" in status or "成功" in status:
                status_color = "#4CAF50"  # 完成 - 绿色
            elif "错误" in status or "失败" in status:
                status_color = "#F44336"  # 错误 - 红色
            elif "暂停" in status:
                status_color = "#FF9800"  # 暂停 - 橙色
            elif "等待" in status:
                status_color = "#FFC107"  # 等待 - 黄色
            elif "下载中" in status or "连接中" in status:
                status_color = "#2196F3"  # 活跃 - 蓝色
                
            # 设置文本和颜色
            row['status'].setText(status)
            row['status'].setStyleSheet(f"color: {status_color}; font-size: 13px;")
        
        # 更新已下载大小 - 优先使用直接提供的downloaded参数
        if downloaded is not None and 'downloaded' in row:
            downloaded_str = self._get_readable_size(downloaded)
            row['downloaded'].setText(downloaded_str)
        # 如果提供了start_pos和progress，计算downloaded
        elif start_pos is not None and progress is not None and 'downloaded' in row:
            downloaded = progress - start_pos if progress > start_pos else 0
            downloaded_str = self._get_readable_size(downloaded)
            row['downloaded'].setText(downloaded_str)
        
        # 更新总大小 - 优先使用直接提供的total参数
        if total is not None and 'total' in row:
            total_str = self._get_readable_size(total)
            row['total'].setText(total_str)
        # 如果提供了start_pos和end_pos，计算total
        elif start_pos is not None and end_pos is not None and 'total' in row:
            total_size = end_pos - start_pos + 1 if end_pos >= start_pos else 0
            total_str = self._get_readable_size(total_size)
            row['total'].setText(total_str)
    
    def _update_segments_info(self, blocks_info):
        """更新分段下载信息
        
        参数:
            blocks_info (list): 下载块信息列表
        """
        if not hasattr(self, 'segments_scroll_layout'):
            return
        
        # 清空现有段信息
        for i in reversed(range(self.segments_scroll_layout.count())):
            widget = self.segments_scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 清空段行引用
        self.segment_rows = []
        
        # 如果没有块信息，显示提示
        if not blocks_info:
            empty_label = QLabel("没有分段信息")
            empty_label.setStyleSheet("color: #B0B0B0; font-size: 13px; background-color: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(empty_label)
            self.segments_scroll_layout.addWidget(empty_label)
            return
        
        # 添加每个段的信息
        for i, block in enumerate(blocks_info):
            segment_frame = QFrame()
            segment_frame.setStyleSheet("background-color: #323232; border-radius: 5px;")  # 减小圆角
            segment_layout = QHBoxLayout(segment_frame)
            segment_layout.setContentsMargins(8, 6, 8, 6)  # 减小内边距
            segment_layout.setSpacing(10)  # 减少间距
            
            # 序号
            index_label = QLabel(f"{i+1}")
            index_label.setFixedWidth(25)  # 减少宽度
            index_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(index_label)
            segment_layout.addWidget(index_label)
            
            # 状态 - 使用不同颜色表示不同状态
            status_text = block.get("status", "未知")
            status_color = "#B39DDB"  # 默认紫色
            
            if "完成" in status_text or "成功" in status_text:
                status_color = "#4CAF50"  # 完成 - 绿色
            elif "错误" in status_text or "失败" in status_text:
                status_color = "#F44336"  # 错误 - 红色
            elif "暂停" in status_text:
                status_color = "#FF9800"  # 暂停 - 橙色
            elif "等待" in status_text:
                status_color = "#FFC107"  # 等待 - 黄色
            elif "下载中" in status_text or "连接中" in status_text:
                status_color = "#2196F3"  # 活跃 - 蓝色
            
            status_label = QLabel(status_text)
            status_label.setFixedWidth(90)  # 减少宽度
            status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")  # 减小字体
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(status_label)
            segment_layout.addWidget(status_label)
            
            # 已下载 - 从processed_blocks计算
            downloaded = block.get("downloaded", 0)
            if downloaded == 0:
                # 尝试从进度和起始位置计算
                start_pos = block.get("start_pos", 0)
                progress = block.get("progress", start_pos)
                downloaded = progress - start_pos if progress > start_pos else 0
            
            downloaded_str = self._get_readable_size(downloaded)
            downloaded_label = QLabel(downloaded_str)
            downloaded_label.setFixedWidth(90)  # 减少宽度
            downloaded_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(downloaded_label)
            segment_layout.addWidget(downloaded_label)
            
            # 总大小 - 从processed_blocks计算
            total_size = block.get("size", 0)
            if total_size == 0:
                # 尝试从起始位置和结束位置计算
                start_pos = block.get("start_pos", 0) 
                end_pos = block.get("end_pos", 0)
                total_size = end_pos - start_pos + 1 if end_pos >= start_pos else 0
            
            total_str = self._get_readable_size(total_size)
            total_label = QLabel(total_str)
            total_label.setFixedWidth(90)  # 减少宽度
            total_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(total_label)
            segment_layout.addWidget(total_label)
            
            self.segments_scroll_layout.addWidget(segment_frame)
            
            # 保存行引用，用于更新
            self.segment_rows.append({
                "frame": segment_frame,
                "status": status_label,
                "downloaded": downloaded_label,
                "total": total_label
            })
        
        # 更新后调整大小，但是避免窗口变得过大
        if self.isVisible() and self.current_state == "downloading":
            # 确保窗口大小适合当前内容
            self.setMinimumSize(633, 474)
    
    def _clear_content(self):
        """清空内容区域"""
        # 停止所有可能运行的定时器
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        if hasattr(self, 'auto_close_timer') and self.auto_close_timer.isActive():
            self.auto_close_timer.stop()
            
        # 清理内容布局
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                
        # 清理按钮布局
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                
        # 确保内存中的引用也被清除
        if hasattr(self, 'filename_label'):
            self.filename_label = None
        if hasattr(self, 'size_label'):
            self.size_label = None
        if hasattr(self, 'status_label'):
            self.status_label = None
        if hasattr(self, 'speed_label'):
            self.speed_label = None
        if hasattr(self, 'time_label'):
            self.time_label = None
        if hasattr(self, 'progress_bar'):
            self.progress_bar = None
        if hasattr(self, 'segments_frame'):
            self.segments_frame = None
        if hasattr(self, 'segment_rows'):
            self.segment_rows = []
        if hasattr(self, 'segments_scroll_area'):
            self.segments_scroll_area = None
        if hasattr(self, 'toggle_segments_button'):
            self.toggle_segments_button = None
        if hasattr(self, 'url_input'):
            self.url_input = None
        if hasattr(self, 'filename_input'):
            self.filename_input = None
        if hasattr(self, 'save_path_input'):
            self.save_path_input = None
        if hasattr(self, 'multi_thread_checkbox'):
            self.multi_thread_checkbox = None
        if hasattr(self, 'cancel_button'):
            self.cancel_button = None
        if hasattr(self, 'download_button'):
            self.download_button = None
            
        # 强制清理
        self.content_widget.update()
        self.button_widget.update()
        
        # 强制重新处理事件和重绘
        QApplication.processEvents()
            
        # 重置UI状态
        self.update()
    
    def _clear_layout(self, layout):
        """清空布局中的所有部件"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                layout.removeItem(item) # 从布局中移除子布局
    
    def _on_browse(self):
        """浏览保存位置"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path_input.text())
        if folder_path:
            self.save_path_input.setText(folder_path)
            
    def _on_download(self):
        """开始下载按钮点击处理"""
        # 在下载按钮被点击时，先获取并保存所有需要的数据
        try:
            # 构建任务数据
            task_data = {}
            
            # 如果有待处理的任务数据，优先使用它
            if self.pending_task_data and isinstance(self.pending_task_data, dict):
                task_data = dict(self.pending_task_data)  # 创建副本避免修改原始数据
                
                # 更新用户可能修改的字段，使用安全方式访问UI控件
                try:
                    if hasattr(self, 'url_input') and self.url_input and not self._is_destroyed(self.url_input):
                        task_data["url"] = self.url_input.text().strip()
                except (RuntimeError, AttributeError, Exception) as e:
                    # 控件可能已被删除，保留原值
                    logging.debug(f"访问url_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'filename_input') and self.filename_input and not self._is_destroyed(self.filename_input):
                        task_data["file_name"] = self.filename_input.text().strip()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问filename_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'save_path_input') and self.save_path_input and not self._is_destroyed(self.save_path_input):
                        task_data["save_path"] = self.save_path_input.text()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问save_path_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'multi_thread_checkbox') and self.multi_thread_checkbox and not self._is_destroyed(self.multi_thread_checkbox):
                        task_data["multi_thread"] = self.multi_thread_checkbox.isChecked()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问multi_thread_checkbox时出错: {e}")
            else:
                # 如果没有待处理数据，从UI控件获取数据
                try:
                    url = ""
                    if hasattr(self, 'url_input') and self.url_input and not self._is_destroyed(self.url_input):
                        url = self.url_input.text().strip()
                    if not url:
                        logging.warning("下载失败: URL为空")
                        return
                        
                    # 获取文件名
                    filename = ""
                    if hasattr(self, 'filename_input') and self.filename_input and not self._is_destroyed(self.filename_input):
                        filename = self.filename_input.text().strip()
                    
                    # 如果没有输入文件名，尝试从URL中提取
                    if not filename:
                        filename = self._extract_filename_from_url(url)
                    
                    # 保存路径
                    save_path = ""
                    if hasattr(self, 'save_path_input') and self.save_path_input and not self._is_destroyed(self.save_path_input):
                        save_path = self.save_path_input.text()
                    
                    # 多线程选项
                    multi_thread = True
                    if hasattr(self, 'multi_thread_checkbox') and self.multi_thread_checkbox and not self._is_destroyed(self.multi_thread_checkbox):
                        multi_thread = self.multi_thread_checkbox.isChecked()
                    
                    # 创建下载任务数据
                    task_data = {
                        "url": url,
                        "file_name": filename,
                        "save_path": save_path,
                        "multi_thread": multi_thread,
                        "source": "browser_extension",
                        "request_id": f"popup_{int(time.time() * 1000)}"
                    }
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.error(f"从UI获取下载信息时出错: {e}")
                    return
            
            # 验证URL
            url = task_data.get("url", "")
            if not url:
                logging.error("下载失败: URL为空")
                return
                
            # 添加保存以供发送
            task_data_copy = dict(task_data)
                
            # 先保存副本，防止信号触发后窗口关闭导致访问已删除对象
            try:
                # 发送下载请求信号
                if hasattr(self, 'downloadRequested'):
                    self.downloadRequested.emit(task_data_copy)
                    
                # 不立即关闭窗口，我们应该在这里切换到下载中界面
                # 先彻底清除当前UI
                self._clear_content()
                
                # 用延时确保前一界面完全清除
                QTimer.singleShot(100, lambda: self._switch_to_downloading_ui(task_data_copy))
                
                # 使用延时器而不是直接调用close()，防止线程在UI更新前被销毁
                # 确保在主线程中保持足够长的时间
                QApplication.processEvents()
                
            except Exception as e:
                logging.error(f"发送下载请求时出错: {e}")
        except Exception as e:
            logging.error(f"处理下载请求时出错: {e}")
    
    def _switch_to_downloading_ui(self, task_data):
        """切换到下载中界面并开始下载"""
        try:
            # 检查对话框是否仍然有效
            if not self.isVisible() or not self.isActiveWindow():
                logging.warning("窗口已不可见或非活跃，取消UI切换")
                return
                
            # 继续显示下载界面并开始下载
            self._create_downloading_ui(task_data)
            
            # 强制更新UI以确保界面已完全更新
            self.repaint()
            QApplication.processEvents()
            
            # 在UI更新后开始下载
            QTimer.singleShot(50, lambda: self._start_download_delayed(task_data))
            
        except Exception as e:
            logging.error(f"切换到下载中界面失败: {e}")
            
    def _start_download_delayed(self, task_data):
        """延迟启动下载，确保UI已经更新"""
        try:
            # 检查对话框是否仍然有效
            if not self.isVisible():
                logging.warning("窗口已不可见，取消下载启动")
                return
                
            # 开始下载
            self._start_download(task_data)
            
            # 强制更新UI
            self.repaint()
            QApplication.processEvents()
            
        except Exception as e:
            logging.error(f"延迟启动下载失败: {e}")
    
    def _on_pause_resume(self):
        """暂停/继续按钮点击处理"""
        if self.is_paused:
            # 恢复下载
            self.download_button.setText("暂停")
            self.download_button.setStyleSheet("""
                QPushButton {
                    background-color: #8A7CEC;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 4px 12px;
                    font-size: 14px;
                    font-weight: bold;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #9E8FEF;
                }
                QPushButton:pressed {
                    background-color: #7A6CD8;
                }
            """)
            self.download_button.clicked.connect(self._on_pause_resume)
            self.is_paused = False
            self.download_engine.resume()
        else:
            # 暂停下载
            self.download_button.setText("继续")
            self.download_button.setStyleSheet("""
                QPushButton {
                    background-color: #8A7CEC;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 4px 12px;
                    font-size: 14px;
                    font-weight: bold;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #9E8FEF;
                }
                QPushButton:pressed {
                    background-color: #7A6CD8;
                }
            """)
            self.download_button.clicked.connect(self._on_pause_resume)
            self.is_paused = True
            self.download_engine.pause()
    
    def _on_url_changed(self, url):
        """URL输入变化处理"""
        if not url:
            return
            
        # 尝试从URL提取文件名
        if not self.filename_input.text():
            filename = self._extract_filename_from_url(url)
            if filename:
                self.filename_input.setText(filename)
                
    def update_progress(self, progress_percent, speed_bytes=0, time_left="计算中..."):
        """更新下载进度"""
        if self.current_state != "downloading":
            return
            
        # 更新进度条
        self.progress_bar.setValue(int(progress_percent))
        
        # 更新状态文本
        self.status_label.setText(f"{progress_percent:.1f}%")
        
        # 更新速度
        speed_str = self._get_readable_speed(speed_bytes)
        self.speed_label.setText(f"速度: {speed_str}")
        
        # 更新剩余时间
        self.time_label.setText(f"剩余时间: {time_left}")

    def _create_completed_ui(self, task_data):
        """创建下载完成UI
        
        参数:
            task_data (dict): 任务数据
        """
        # 确保先前的UI完全清除
        self._clear_content()
        
        # 停止进度更新定时器
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
            
        # 设置标题
        self.title_label.setText("下载完成")
        
        # 文件信息区域
        file_info_frame = QFrame()
        file_info_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 10px;")
        file_info_layout = QHBoxLayout(file_info_frame)
        file_info_layout.setContentsMargins(15, 15, 15, 15)
        file_info_layout.setSpacing(15)
        
        # 图标
        file_icon = QLabel()
        file_icon.setFixedSize(36, 36)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(file_icon, "ic_fluent_checkmark_circle_24_regular", size=28)
            file_icon.setStyleSheet("color: #4CAF50; background-color: transparent;")
        file_info_layout.addWidget(file_icon)
        
        # 文件信息布局
        file_text_layout = QVBoxLayout()
        file_text_layout.setSpacing(5)
        
        # 文件名
        filename = task_data.get("file_name", "未知文件")
        filename_label = QLabel(filename)
        filename_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        filename_label.setWordWrap(True)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(filename_label)
        file_text_layout.addWidget(filename_label)
        
        # 文件大小
        file_size = task_data.get("file_size", 0)
        if file_size <= 0:
            # 如果文件大小仍未知，尝试再次从文件获取
            try:
                save_path = task_data.get("save_path", "")
                if save_path and filename:
                    file_path = Path(save_path) / filename
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        logging.info(f"完成UI - 从实际文件获取大小: {file_size} 字节")
            except Exception as e:
                logging.error(f"完成UI - 获取实际文件大小失败: {e}")
                
        size_str = self._get_readable_size(file_size) if file_size > 0 else "未知大小"
        size_label = QLabel(f"大小: {size_str}")
        size_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(size_label)
        file_text_layout.addWidget(size_label)
        
        # 保存路径
        save_path = task_data.get("save_path", "")
        path_layout = QHBoxLayout()
        path_layout.setSpacing(5)
        
        path_icon = QLabel()
        path_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(path_icon, "ic_fluent_folder_24_regular", size=14)
            path_icon.setStyleSheet("color: #B0B0B0;")
        path_layout.addWidget(path_icon)
        
        path_label = QLabel(save_path)
        path_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(path_label)
        # 对于过长的路径，显示省略号
        path_label.setWordWrap(False)
        path_label.setMaximumWidth(300)
        path_layout.addWidget(path_label, 1)
        
        file_text_layout.addLayout(path_layout)
        file_info_layout.addLayout(file_text_layout, 1)
        
        self.content_layout.addWidget(file_info_frame)
        
        # 消息区域
        message_frame = QFrame()
        message_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 10px;")
        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(15, 15, 15, 15)
        
        message_label = QLabel("文件已成功下载，您可以打开文件或查看文件所在文件夹。")
        message_label.setStyleSheet("color: #FFFFFF; font-size: 14px;")
        message_label.setWordWrap(True)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(message_label)
        message_layout.addWidget(message_label)
        
        # 添加自动关闭选项
        self.auto_close_checkbox = QCheckBox("5秒后自动关闭")
        self.auto_close_checkbox.setChecked(self.auto_close_completed)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.auto_close_checkbox)
        
        self.auto_close_checkbox.setStyleSheet("""
            QCheckBox {
                color: #B0B0B0;
                font-size: 13px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 2px;
                border: 1px solid #555555;
                background: #333333;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #8A7CEC;
            }
            QCheckBox::indicator:checked {
                background: #8A7CEC;
                border: 1px solid #8A7CEC;
            }
        """)
        self.auto_close_checkbox.stateChanged.connect(self._on_auto_close_changed)
        message_layout.addWidget(self.auto_close_checkbox)
        
        self.content_layout.addWidget(message_frame)
        
        # 添加空白空间
        self.content_layout.addStretch(1)
        
        # 底部按钮
        self.button_layout.addStretch(1)
        
        # 打开文件夹按钮
        open_folder_button = QPushButton("")
        open_folder_button.setFixedSize(120, 40)
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_folder_open_24_regular")
            open_folder_button.setIcon(icon)
            open_folder_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            open_folder_button.setText("  打开文件夹")
            self.font_manager.apply_font(open_folder_button)
        
        open_folder_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 15px;
                font-size: 14px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        open_folder_button.clicked.connect(lambda: self._on_open_folder(task_data.get("save_path", "")))
        self.button_layout.addWidget(open_folder_button)
        
        # 关闭按钮
        close_button = QPushButton("")
        close_button.setFixedSize(120, 40)
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_checkmark_24_regular")
            close_button.setIcon(icon)
            close_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            close_button.setText("  完成")
            self.font_manager.apply_font(close_button)
        
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #8A7CEC;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 5px 15px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #9E8FEF;
            }
            QPushButton:pressed {
                background-color: #7A6CD8;
            }
        """)
        close_button.clicked.connect(self.close)
        self.button_layout.addWidget(close_button)
        
        # 设置当前状态
        self.current_state = "completed"
        
        # 开始自动关闭定时器 - 只有在勾选自动关闭时才启动
        if self.auto_close_completed:
            self.auto_close_timer.start(5000)
        
        # 设置下载完成页面的窗口大小
        QTimer.singleShot(0, lambda: self.setMinimumSize(457, 350))
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _on_open_folder(self, folder_path):
        """打开文件夹
        
        参数:
            folder_path (str): 文件夹路径
        """
        if not folder_path:
            return
            
        # 发送信号
        self.folderOpened.emit(folder_path)
        
        # 尝试使用系统默认方式打开文件夹
        try:
            import subprocess
            import os
            import platform
            
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", folder_path])
            else:  # Linux
                subprocess.call(["xdg-open", folder_path])
                
        except Exception as e:
            logging.error(f"打开文件夹失败: {e}")
    
    def _on_auto_close_changed(self, state):
        """自动关闭选项改变处理"""
        self.auto_close_completed = (state == Qt.Checked)
        
        # 更新定时器状态
        if self.auto_close_completed:
            self.auto_close_timer.start(5000)
        else:
            self.auto_close_timer.stop()
