from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLineEdit, QTableWidget, 
                              QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
                              QSplitter, QFrame, QLabel, QSizePolicy, QStackedWidget, QScrollArea, QDialog,QApplication)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QPropertyAnimation, QEasingCurve, QPoint, QTimer, QCoreApplication
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPainterPath, QBrush, QMouseEvent, QFontDatabase
from PySide6.QtWidgets import QSystemTrayIcon

from client.ui.components.progressBar import ProgressBar
from client.ui.title_styles.titleStyles import TitleBar
from connect.fallback_connector import FallbackConnector
from core.font.font_manager import FontManager
from client.ui.client_interface.about_window import AboutWindow
from client.ui.client_interface.settings.settings_page import SettingsPage
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.download_log_dialog import DownloadLogDialog
from client.ui.components.update_log_dialog import UpdateLogDialog
from core.update.update_log_manager import UpdateLogManager
from client.ui.pages_manager import PagesManager, CategoryButton
from client.ui.client_interface.task_window import TaskWindow, RoundedTaskFrame
from client.ui.client_interface.history_window import HistoryWindow

import os
import sys
import threading
import types
import datetime
import time

# 字体管理器已经在font_manager.py中集成，支持Fluent图标系统
# 提供以下功能:
# 1. 自动加载字体和图标
# 2. 统一应用字体到组件
# 3. 创建图标标签
# 4. 获取可用图标列表

class RoundedWidget(QWidget):
    def __init__(self, parent=None, radius=10, bg_color="#2C2C2C", corners="all"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.corners = corners  # 可以是 "all", "left", "right", "top", "bottom", "top-left", "bottom-left" 
        self.setAttribute(Qt.WA_TranslucentBackground)  # 确保背景透明
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        
        # 根据不同的角落设置不同的圆角
        if self.corners == "all":
            path.addRoundedRect(rect, self.radius, self.radius)
        elif self.corners == "left":
            # 左侧两个角落圆角，右侧直角
            path = QPainterPath()
            path.moveTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left() + self.radius, rect.bottom())
            path.arcTo(rect.left(), rect.bottom() - 2 * self.radius, 
                      2 * self.radius, 2 * self.radius, 270, 90)
            path.lineTo(rect.left(), rect.top() + self.radius)
            path.arcTo(rect.left(), rect.top(), 
                      2 * self.radius, 2 * self.radius, 180, 90)
            path.lineTo(rect.right(), rect.top())
        elif self.corners == "bottom-left":
            # 只有左下角是圆角
            path = QPainterPath()
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left() + self.radius, rect.bottom())
            path.arcTo(rect.left(), rect.bottom() - 2 * self.radius, 
                      2 * self.radius, 2 * self.radius, 270, 90)
            path.lineTo(rect.left(), rect.top())
        else:
            # 默认全圆角
            path.addRoundedRect(rect, self.radius, self.radius)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)
        
class DownloadManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化更新日志管理器
        self.update_log_manager = UpdateLogManager()
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 应用字体到全局应用程序实例
        self.apply_global_font()
        
        # 初始化配置管理器
        from client.ui.client_interface.settings.config import config
        self.config_manager = config
        
        # 设置窗口基本属性
        self.setWindowTitle("Hanabi Download Manager")
        self.resize(1050, 650)
        
        # 设置应用图标
        self.icon_path = self.get_resource_path("resources/logo.png")
        
        # 确保图标存在
        if os.path.exists(self.icon_path):
            self.app_icon = QIcon(self.icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            print(f"警告: 图标文件不存在: {self.icon_path}")
            self.app_icon = None
        
        # 属性
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置应用深色主题 - 注意这里不要设置主窗口背景色，由paintEvent处理
        self.setStyleSheet("""
            QWidget {
                color: #FFFFFF;
            }
            QTableWidget::item {
                color: #FFFFFF;
            }
        """)
        
        # 初始化下载任务列表
        self.download_tasks = []
        
        # 设置中心部件 - 中心部件需要透明背景
        self.central_widget = QWidget()
        self.central_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(self.central_widget)
        
        # 创建布局
        self.setup_ui()
        
        # 启动时检查一次更新日志
        self.check_update_logs()
        
        # 初始化浏览器下载监听器
        self.init_browser_download_listener()
    
    def init_browser_download_listener(self):
        """初始化浏览器下载监听器"""
        try:
            # 创建FallbackConnector并设置下载处理函数
            self.connector = FallbackConnector()
            self.connector.downloadRequestReceived.connect(self.add_download_from_extension)
            
            # 启动连接器，监听浏览器扩展的连接
            self.connector.start()
            print("已启动浏览器下载监听器")
            
            # 设置定时器定期刷新WebSocket连接，确保长期稳定性
            self.ws_refresh_timer = QTimer(self)
            self.ws_refresh_timer.timeout.connect(self.refresh_websocket_connection)
            self.ws_refresh_timer.start(30000)  # 30秒刷新一次
            print("已设置WebSocket连接定时刷新器")
        except Exception as e:
            print(f"启动浏览器下载监听器失败: {e}")
            import traceback
            traceback.print_exc()
    
    def paintEvent(self, event):
        # 使用高质量抗锯齿
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        # 创建圆角路径
        path = QPainterPath()
        rect = self.rect()
        
        # 增大圆角半径
        cornerRadius = 30
        path.addRoundedRect(rect, cornerRadius, cornerRadius)
        
        # 设置无边框和背景色
        painter.setPen(Qt.NoPen)  # 确保不画任何边框
        painter.setBrush(QColor("#1E1E1E"))
        
        # 使用路径裁剪和绘制
        painter.setClipPath(path)
        painter.drawPath(path)  # 使用drawPath替代drawRect，确保完全按照路径绘制
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.title_bar.underMouse():
                super().mousePressEvent(event)
                
    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(12, 0, 12, 12)  # 左右下添加边距，顶部为0让标题栏紧贴窗口
        main_layout.setSpacing(0)  # 去掉间距完全消除白线
        
        # 自定义标题栏
        self.title_bar = TitleBar(self)
        self.title_bar.setAttribute(Qt.WA_TranslucentBackground)  # 确保标题栏背景透明
        # 连接托盘信号
        self.title_bar.minimizeToTray.connect(self.on_minimize_to_tray)
        main_layout.addWidget(self.title_bar)
        
        # 内容区布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)  # 去掉顶部间距
        content_layout.setSpacing(12)  # 增加侧边栏和内容区之间的间距
        
        # 创建左侧导航栏 - 使用普通Widget而非RoundedWidget，移除圆角效果
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("background-color: #1E1E1E;")  # 保持背景色一致
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 25)
        sidebar_layout.setSpacing(20)
        
        # 品牌和应用信息区域
        brand_container = QWidget()
        brand_container.setStyleSheet("background-color: transparent;")
        brand_layout = QVBoxLayout(brand_container)
        brand_layout.setContentsMargins(10, 0, 10, 0)
        brand_layout.setSpacing(8)
        
        # 应用名称
        app_title = QLabel()
        app_title.setText("<span style='font-size: 28px;'>Hanabi</span><br><span style='font-size: 14px;'>Download Manager</span>")
        app_title.setStyleSheet("color: #B39DDB; font-weight: bold; background-color: transparent;")
        app_title.setTextFormat(Qt.RichText)
        self.font_manager.apply_font(app_title)
        brand_layout.addWidget(app_title)
        
        # 应用口号
        slogan_label = QLabel("Dev By ZZBuAoYe")
        slogan_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.font_manager.apply_font(slogan_label)
        brand_layout.addWidget(slogan_label)
        
        # 下方装饰线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333; margin-top: 8px;")
        separator.setFixedHeight(1)
        brand_layout.addWidget(separator)
        
        sidebar_layout.addWidget(brand_container)
        
        # 右侧内容区域
        self.content_area = RoundedWidget(radius=20, bg_color="#1E1E1E", corners="all")
                
        # 创建设置页面和关于页面
        self.settings_page = SettingsPage(self.config_manager, self)
        # 连接设置页面消息信号
        self.settings_page.settingsMessage.connect(self.handle_settings_message)
        
        # 关于页面
        self.about_page = AboutWindow()
        
        # 使用PagesManager进行页面管理并传入主窗口引用
        self.pages_manager = PagesManager(self.sidebar, self.content_area, self)
        
        # 注册所有常用页面
        pages = self.pages_manager.register_common_pages()
        
        # 获取下载页面的引用
        self.download_page = pages["downloads"]
        self.download_content = self.download_page.content_widget
        self.download_page_layout = self.download_page.content_layout
        
        # 获取已完成页面的引用
        self.finished_page = pages["history"]
        
        # 连接历史页面信号
        if self.finished_page and hasattr(self.finished_page, 'content_widget'):
            history_window = self.finished_page.content_widget
            if isinstance(history_window, HistoryWindow):
                # 连接历史项点击信号
                history_window.history_item_clicked.connect(self.redownload_from_history)
                
                # 连接历史窗口刷新按钮信号
                if hasattr(history_window, 'refresh_btn'):
                    print("连接历史窗口刷新按钮")
                    # 使用lambda以避免直接调用
                    history_window.refresh_btn.clicked.connect(lambda: history_window.load_history())
        
        # 创建卡片式布局 - 在TaskWindow初始化前先创建布局
        self.setup_card_layout()
        
        # 创建任务窗口实例并确保其可见性
        self.task_window = TaskWindow(self.font_manager, self)
        # 移除隐藏属性以确保TaskWindow可见
        self.task_window.setVisible(True)
        self.task_window.setAttribute(Qt.WA_DontShowOnScreen, False)
        
        # 连接任务信号
        self.task_window.taskPaused.connect(self.pause_download_task)
        self.task_window.taskResumed.connect(self.resume_download_task)
        self.task_window.taskCancelled.connect(self.cancel_download_task)
        
        # 连接文件操作信号
        self.connect_file_operations()
        
        # 添加下载任务窗口到下载页面 - 使用单独的卡片包装
        task_card = RoundedTaskFrame()
        task_card.setMinimumHeight(300)  # 确保任务卡片有足够高度
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(5, 5, 5, 5) # 减小内边距避免过多空白
        task_layout.addWidget(self.task_window, 1) # 设置stretch为1使其可扩展填充空间
        
        # 添加到下载页面布局
        self.download_page_layout.addWidget(task_card, 1) # 设置stretch为1使其占据更多空间
        
        # 保留空间占位区域
        spacer_widget = QWidget()
        spacer_widget.setFixedHeight(100)  # 设置适当的高度以匹配之前的过滤器区域
        spacer_widget.setStyleSheet("background-color: transparent;")
        sidebar_layout.addWidget(spacer_widget)
        
        # 添加左侧导航栏到内容布局
        content_layout.addWidget(self.sidebar)
        
        # 添加内容区到内容布局
        content_layout.addWidget(self.content_area, 1)
        
        # 添加内容布局到主布局
        main_layout.addLayout(content_layout, 1)
        
        # 加载配置
        self.save_path = self.config_manager.get_save_path()
    
    def setup_card_layout(self):
        # 顶部URL输入和按钮区域
        top_card = RoundedWidget(radius=15)
        top_card.setMinimumHeight(150)  # 确保卡片有足够的高度
        top_card_layout = QVBoxLayout(top_card)
        top_card_layout.setContentsMargins(20, 20, 20, 20)
        top_card_layout.setSpacing(15)
        
        # URL输入框标题 - 居中
        url_title = QLabel("添加下载")
        url_title.setAlignment(Qt.AlignCenter)
        url_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(url_title)
        top_card_layout.addWidget(url_title)
        
        # URL输入框和按钮
        url_input_layout = QHBoxLayout()
        url_input_layout.setSpacing(10)
        
        # URL输入框
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入下载链接...")
        self.url_input.setMinimumHeight(45)
        self.font_manager.apply_font(self.url_input)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 15px;
            }
            QLineEdit:focus {
                border: 1px solid #B39DDB;
            }
        """)
        url_input_layout.addWidget(self.url_input, 5)  # 保持输入框占较大比例
        
        # 开始下载按钮
        download_button_style = """
            QPushButton {
                background-color: #1FB15F;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 5px 15px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #17A452;
            }
            QPushButton:pressed {
                background-color: #149048;
            }
        """
        
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setMinimumWidth(100)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setSizePolicy(size_policy)
        self.download_btn.setStyleSheet(download_button_style)
        
        # 创建水平布局用于图标和文本
        download_btn_layout = QHBoxLayout(self.download_btn)
        download_btn_layout.setContentsMargins(10, 0, 10, 0)
        download_btn_layout.setSpacing(8)
        
        # 添加图标 - 使用新的create_icon_label方法
        icon_label = self.font_manager.create_icon_label(
            self.download_btn, 
            "ic_fluent_arrow_download_24_regular", 
            size=14,
            color="#FFFFFF"
        )
        download_btn_layout.addWidget(icon_label)
        
        # 添加文本
        text_label = QLabel("开始下载")
        text_label.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
        self.font_manager.apply_font(text_label)
        download_btn_layout.addWidget(text_label)
        
        # 连接点击事件
        self.download_btn.clicked.connect(self.start_download)
        url_input_layout.addWidget(self.download_btn, 1)  # 保持按钮占较小比例
        
        # 选择保存路径按钮
        self.path_btn = QPushButton()
        self.path_btn.setMinimumHeight(45)
        self.path_btn.setMinimumWidth(150)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.path_btn.setSizePolicy(size_policy)
        self.path_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """)
        
        # 使用布局方式设置图标和文本
        path_btn_layout = QHBoxLayout(self.path_btn)
        path_btn_layout.setContentsMargins(10, 0, 10, 0)
        path_btn_layout.setSpacing(5)
        
        # 创建图标标签 - 使用新的create_icon_label方法
        folder_icon = self.font_manager.create_icon_label(
            self.path_btn,
            "ic_fluent_folder_24_regular",
            size=14,
            color="#FFFFFF"
        )
        path_btn_layout.addWidget(folder_icon)
        
        # 创建文本标签
        path_text = QLabel("保存位置")
        path_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_text.setMinimumWidth(70)
        path_text.setAlignment(Qt.AlignCenter)
        path_btn_layout.addWidget(path_text)
        
        self.path_btn.clicked.connect(self.select_save_path)
        url_input_layout.addWidget(self.path_btn, 2) # 稍微调整比例
        
        top_card_layout.addLayout(url_input_layout)
        
        # 显示当前保存路径
        self.save_path_label = QLabel(f"当前保存位置: {os.path.expanduser('~/Downloads')}")
        self.save_path_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.save_path_label.setAlignment(Qt.AlignCenter)
        top_card_layout.addWidget(self.save_path_label)
        
        # 当前保存路径
        self.save_path = os.path.expanduser("~/Downloads")
        
        # 添加顶部区域到内容布局
        self.download_page_layout.addWidget(top_card)
    
    def select_save_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.save_path = folder_path
            # 更新路径显示标签
            self.save_path_label.setText(f"当前保存位置: {self.save_path}")
            # 更新配置
            self.config_manager.set_save_path(folder_path)
            QMessageBox.information(self, "保存位置", f"已选择保存位置: {self.save_path}")
    
    def start_download(self):
        """开始下载"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入下载URL")
            return
        
        # 开始下载任务
        save_path = self.save_path
        if not save_path or not os.path.isdir(save_path):
            save_path = None  # 使用默认路径
            
        # 创建任务窗口中的项并获取行号
        task_data = {
            "url": url,
            "file_name": "准备下载...",
            "total_size": "获取中...",
            "progress": 0,
            "status": "初始化中",
            "speed": "0 B/s",
            "save_path": save_path if save_path else os.path.join(os.path.expanduser("~"), "Downloads"),
            "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        row = self.task_window.add_task(task_data)
        
        if row >= 0:
            download_data = {
                "url": url,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                }
        }
        
            # 创建下载任务
            connector = FallbackConnector()
            transfer_manager = connector.create_download_task(download_data)
            
            if save_path:
                transfer_manager.save_path = save_path
        
        # 连接信号
            transfer_manager.initialized.connect(lambda supports_multi: self.update_file_size(row, transfer_manager.file_size))
            transfer_manager.block_progress_updated.connect(lambda progress_data: self.update_progress(row, progress_data))
            transfer_manager.speed_updated.connect(lambda speed: self.update_speed(row, speed))
            transfer_manager.download_completed.connect(lambda: self.download_completed(row))
            transfer_manager.error_occurred.connect(lambda error: self.download_error(row, error))
        
            # 保存任务
            self.download_tasks.append({
                "row": row,
                "thread": transfer_manager,
                "manager": transfer_manager,  # 使用manager关键字存储，确保和update_file_size等方法兼容
                "url": url,
                "save_path": save_path,
                "status": "下载中"
            })
            
        # 启动下载
            transfer_manager.start()
            
            # 将进入任务窗口
            self.switch_page(0)
            
            # 清空URL输入框
            self.url_input.clear()
        else:
            QMessageBox.warning(self, "错误", "无法创建下载任务")
    
    def update_file_size(self, row, size):
        # 更新任务窗口中的文件大小
        for task in self.download_tasks:
            if task['row'] == row:
                # 更新文件名
                self.task_window.update_file_info(row, filename=task['manager'].file_name, size=size)
                break
    
    def update_progress(self, row, progress_data):
        # 查找对应任务获取文件大小
        file_size = 0
        download_manager = None
        for task in self.download_tasks:
            if task['row'] == row:
                file_size = task['manager'].file_size
                download_manager = task['manager']
                break
        
        # 如果没有进度数据但有下载管理器，可能需要从管理器获取进度数据
        if (not progress_data or len(progress_data) == 0) and download_manager:
            try:
                # 兼容新旧下载引擎
                if hasattr(download_manager, 'blocks'):
                    # 新版下载引擎使用blocks属性
                    progress_data = []
                    for block in download_manager.blocks:
                        progress_data.append({
                            'start_position': block.start_position,
                            'current_position': block.current_position,
                            'end_position': block.end_position
                        })
                elif hasattr(download_manager, 'segments'):
                    # 旧版下载引擎使用segments属性
                    progress_data = []
                    for segment in download_manager.segments:
                        progress_data.append({
                            'startPos': segment.startPos,
                            'progress': segment.progress,
                            'endPos': segment.endPos
                        })
            except Exception as e:
                print(f"[WARNING] 从下载管理器获取进度数据失败: {e}")
                
        # 打印进度数据用于调试
        print(f"[DEBUG] 更新进度: 行={row}, 文件大小={file_size}, 进度数据={progress_data[:2] if progress_data else None}")
                
        # 更新任务窗口中的进度条
        self.task_window.update_progress(row, progress_data, file_size)
        
        # 计算总进度百分比
        total_progress = 0
        total_downloaded = 0
        total_size = 0
        
        try:
            if progress_data:
                if isinstance(progress_data[0], dict):
                    for block in progress_data:
                        # 兼容新旧字段名
                        start_pos = block.get('start_position', block.get('start_pos', block.get('startPos', 0)))
                        end_pos = block.get('end_position', block.get('end_pos', block.get('endPos', 0)))
                        current = block.get('current_position', block.get('progress', start_pos))
                        
                        # 确保值有效
                        start_pos = max(0, start_pos)
                        end_pos = max(start_pos, end_pos)
                        current = max(start_pos, min(end_pos, current))
                        
                        # 计算当前块的下载量和总大小
                        block_downloaded = current - start_pos
                        block_size = end_pos - start_pos + 1
                        
                        # 累加已下载和总大小
                        total_downloaded += block_downloaded
                        total_size += block_size
                elif isinstance(progress_data[0], (list, tuple)) and len(progress_data[0]) >= 3:
                    for segment in progress_data:
                        start_pos = segment[0]
                        current = segment[1]
                        end_pos = segment[2]
                        
                        # 确保值有效
                        start_pos = max(0, start_pos)
                        end_pos = max(start_pos, end_pos)
                        current = max(start_pos, min(end_pos, current))
                        
                        # 计算已下载和总大小
                        segment_downloaded = current - start_pos
                        segment_size = end_pos - start_pos + 1
                        
                        # 累加已下载和总大小
                        total_downloaded += segment_downloaded
                        total_size += segment_size
                        
                # 计算总进度百分比
                if total_size > 0:
                    total_progress = (total_downloaded / total_size) * 100
                    
                    # 如果接近完成但未完全完成，限制为99%
                    if total_progress >= 99.5 and total_downloaded < total_size:
                        total_progress = 99
                    else:
                        total_progress = int(total_progress)
                        
                    # 如果计算出的总进度为100%，标记为完成
                    if total_progress == 100 and self._is_download_complete(progress_data):
                        for task in self.download_tasks:
                            if task['row'] == row and task['status'] == 'running':
                                task['status'] = 'completed'
                                self.task_window.update_status(row, "下载完成", True)
                                print(f"[INFO] 任务 {row} 已完成")
                                
                                # 获取保存路径并发送文件下载完成信号
                                save_path = None
                                if hasattr(task['manager'], 'save_path') and hasattr(task['manager'], 'file_name'):
                                    save_path = os.path.join(task['manager'].save_path, task['manager'].file_name)
                                    # 触发下载完成事件
                                    self.file_downloaded.emit(save_path)
                                break
        except Exception as e:
            import traceback
            print(f"[ERROR] 计算进度百分比错误: {e}")
            traceback.print_exc()
    
    def _is_download_complete(self, progress_data):
        """检查下载是否已完成"""
        if not progress_data:
            return False
            
        try:
            # 检查是否所有分段都已下载完成
            for segment in progress_data:
                if isinstance(segment, dict):
                    # 兼容新旧字段名
                    start_pos = segment.get('start_position', segment.get('start_pos', segment.get('startPos', 0)))
                    end_pos = segment.get('end_position', segment.get('end_pos', segment.get('endPos', 0)))
                    current = segment.get('current_position', segment.get('progress', start_pos))
                    
                    # 确保值有效
                    start_pos = max(0, start_pos)
                    end_pos = max(start_pos, end_pos)
                    current = max(start_pos, min(end_pos, current))
                    
                    # 如果当前位置未达到结束位置，则未完成
                    if current < end_pos:
                        # 特殊情况：如果只差1个字节，也认为完成（解决某些服务器1字节问题）
                        if end_pos - current <= 1:
                            continue
                        return False
                        
                elif isinstance(segment, (list, tuple)) and len(segment) >= 3:
                    start_pos = segment[0]
                    current = segment[1]
                    end_pos = segment[2]
                    
                    # 确保值有效
                    start_pos = max(0, start_pos)
                    end_pos = max(start_pos, end_pos)
                    current = max(start_pos, min(end_pos, current))
                    
                    # 如果当前位置未达到结束位置，则未完成
                    if current < end_pos:
                        # 特殊情况：如果只差1个字节，也认为完成（解决某些服务器1字节问题）
                        if end_pos - current <= 1:
                            continue
                        return False
            
            # 所有分段都已完成
            return True
        except Exception as e:
            print(f"[ERROR] 检查下载完成状态出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_speed(self, row, speed_bytes):
        # 更新任务窗口中的下载速度
        self.task_window.update_speed(row, speed_bytes)
    
    def download_completed(self, row):
        """下载完成后更新状态并添加到历史记录"""
        print(f"\n========== 下载完成处理开始 ==========")
        print(f"行号: {row}")
        
        # 更新任务窗口中的状态为已完成
        try:
            print(f"更新任务状态为已完成...")
            if not hasattr(self, 'task_window') or self.task_window is None:
                print(f"错误: task_window不存在或为None")
            else:
                print(f"调用update_status, row={row}")
                self.task_window.update_status(row, "下载完成", True)
                print(f"状态更新成功")
        except Exception as e:
            print(f"更新任务状态失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 标记任务为已完成
        task_found = False
        for task in self.download_tasks:
            if task['row'] == row:
                task_found = True
                print(f"找到对应任务: {row}")
                
                try:
                    task['status'] = 'completed'
                    print(f"任务状态已更新为completed")
                
                    # 获取任务信息
                    download_manager = task.get('manager')
                    if download_manager:
                        print(f"下载管理器存在: {type(download_manager)}")
                        try:
                            # 创建历史记录项
                            save_path = self.save_path if hasattr(self, 'save_path') and self.save_path else os.path.expanduser("~/Downloads")
                            print(f"保存路径: {save_path}")
                            
                            if not hasattr(download_manager, 'file_name'):
                                print(f"警告: 下载管理器没有file_name属性")
                            else:
                                print(f"文件名: {download_manager.file_name}")
                                
                            if not hasattr(download_manager, 'url'):
                                print(f"警告: 下载管理器没有url属性")
                            else:
                                print(f"URL: {download_manager.url}")
                                
                            if not hasattr(download_manager, 'file_size'):
                                print(f"警告: 下载管理器没有file_size属性")
                            else:
                                print(f"文件大小: {download_manager.file_size}")
                            
                            history_item = {
                                'filename': download_manager.file_name if hasattr(download_manager, 'file_name') else "未知文件",
                                'url': download_manager.url if hasattr(download_manager, 'url') else "",
                                'save_path': os.path.join(save_path, download_manager.file_name if hasattr(download_manager, 'file_name') else "未知文件"),
                                'file_size': download_manager.file_size if hasattr(download_manager, 'file_size') else 0,
                                'download_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'status': 'completed'
                            }
                            
                            print(f"历史记录项创建成功: {history_item}")
                            
                            # 添加到历史记录管理器
                            try:
                                print(f"正在导入HistoryManager...")
                                from core.history.history_manager import HistoryManager
                                print(f"HistoryManager导入成功，初始化...")
                                
                                history_manager = HistoryManager()
                                print(f"HistoryManager初始化成功: {type(history_manager)}")
                                
                                print(f"正在添加历史记录...")
                                success = history_manager.add_record(history_item)
                                print(f"历史记录添加结果: {'成功' if success else '失败'}")
                                
                                # 如果历史页面已创建，刷新历史记录
                                if hasattr(self, 'finished_page') and self.finished_page:
                                    print(f"历史页面存在，准备刷新...")
                                    if hasattr(self.finished_page, 'content_widget') and hasattr(self.finished_page.content_widget, 'load_history'):
                                        print("调用load_history()刷新历史记录...")
                                        self.finished_page.content_widget.load_history()
                                        print("历史记录刷新完成")
                                    else:
                                        print("无法刷新历史记录：content_widget不存在或没有load_history方法")
                                else:
                                    print("历史页面不存在，跳过刷新")
                            except Exception as e:
                                print(f"[ERROR] 保存历史记录失败: {e}")
                                import traceback
                                traceback.print_exc()
                        except Exception as e:
                            print(f"创建历史记录项失败: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"警告: 下载管理器不存在或为None")
                except Exception as e:
                    print(f"处理任务完成状态失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                break
        
        if not task_found:
            print(f"未找到row={row}的任务")
            
        print(f"========== 下载完成处理结束 ==========\n")
    
    def download_error(self, row, error):
        # 更新任务窗口中的状态为错误
        error_message = str(error)
        print(f"[ERROR] 下载错误: {error_message}")
        
        # 使用更新过的update_status方法，传递error_info参数
        self.task_window.update_status(row, "下载失败", False, error_message)
        
        # 显示更详细的错误信息
        if "Permission denied" in error_message:
            self.task_window.set_task_failed(row, "没有写入权限，请检查目标文件夹权限")
        
        # 更新任务状态
        for task in self.download_tasks:
            if task['row'] == row:
                task['status'] = 'error'
                break
    
    def pause_download_task(self, row):
        for task in self.download_tasks:
            if task['row'] == row and task['status'] == 'running':
                task['manager'].stop()
                task['status'] = 'paused'
                self.task_window.update_status(row, "已暂停")
    
    def resume_download_task(self, row):
        """继续下载任务"""
        for task in self.download_tasks:
            if task["row"] == row and task["status"] in ["暂停", "错误"]:
                # 需要重新创建下载任务，FallbackConnector中的下载器不支持恢复
                url = task["url"]
                save_path = task["save_path"]
                
                download_data = {
                    "url": url,
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                    }
                }
                
                # 创建下载任务
                connector = FallbackConnector()
                transfer_manager = connector.create_download_task(download_data)
                
                if save_path:
                    transfer_manager.save_path = save_path
                
                # 连接信号
                transfer_manager.initialized.connect(lambda supports_multi: self.update_file_size(row, transfer_manager.file_size))
                transfer_manager.block_progress_updated.connect(lambda progress_data: self.update_progress(row, progress_data))
                transfer_manager.speed_updated.connect(lambda speed: self.update_speed(row, speed))
                transfer_manager.download_completed.connect(lambda: self.download_completed(row))
                transfer_manager.error_occurred.connect(lambda error: self.download_error(row, error))
                
                # 更新任务状态
                task["thread"] = transfer_manager
                task["status"] = "下载中"
                
                # 启动下载
                transfer_manager.start()
                
                # 更新UI
                self.task_window.set_task_status(row, "下载中")
                break
    
    def cancel_download_task(self, row):
        for task in self.download_tasks:
            if task['row'] == row:
                task['manager'].stop()
                task['status'] = 'canceled'
                self.task_window.update_status(row, "已取消")
    
    def show_download_log(self, download_info):
        # 创建并显示日志对话框
        log_dialog = DownloadLogDialog(self, download_info)
        log_dialog.exec()
        
    def add_download_from_extension(self, download_data):
        """从浏览器扩展添加下载"""
        # 记录详细的请求信息
        import threading
        current_thread_id = threading.current_thread().ident
        print(f"\n========== 浏览器下载请求开始处理 ==========")
        print(f"当前线程ID: {current_thread_id}, 主线程: {'是' if QThread.currentThread() == QCoreApplication.instance().thread() else '否'}")
        print(f"收到浏览器下载请求: {download_data}")
        request_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"请求时间: {request_time}")
        
        # 尝试刷新WebSocket服务器
        try:
            if hasattr(self, 'connector'):
                print("刷新WebSocket服务器状态...")
                # 确保服务器仍在运行
                self.connector.start()
                print("WebSocket服务器状态已刷新")
            else:
                print("警告: connector属性不存在")
        except Exception as e:
            print(f"刷新WebSocket服务器失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 创建任务数据
        url = download_data.get("url", "")
        if not url:
            print("缺少URL，无法创建下载任务")
            return False
        
        # 确保在主GUI线程中执行任务添加操作
        def add_task_in_main_thread():
            thread_id = threading.current_thread().ident
            print(f"主线程任务添加开始, 线程ID: {thread_id}, 主线程: {'是' if QThread.currentThread() == QCoreApplication.instance().thread() else '否'}")
            
            # 记录当前下载任务数量    
            print(f"当前下载任务数量: {len(self.download_tasks)}")
            
            # 检查TaskWindow实例
            if not hasattr(self, 'task_window'):
                print("严重错误: self.task_window不存在!")
                return False
                
            if self.task_window is None:
                print("严重错误: self.task_window为None!")
                return False
                
            print(f"task_window类型: {type(self.task_window)}")
            print(f"task_window可见性: {self.task_window.isVisible()}")
            print(f"task_window父组件: {self.task_window.parent()}")
            
            if hasattr(self.task_window, 'task_items'):
                print(f"task_window.task_items类型: {type(self.task_window.task_items)}")
                print(f"task_window.task_items长度: {len(self.task_window.task_items)}")
            else:
                print("警告: task_window没有task_items属性")
                
            # 检查任务容器
            if hasattr(self.task_window, 'tasks_container'):
                print(f"tasks_container存在: 是")
                print(f"tasks_container可见性: {self.task_window.tasks_container.isVisible()}")
            else:
                print("警告: task_window没有tasks_container属性")
                
            if hasattr(self.task_window, 'tasks_container_layout'):
                print(f"tasks_container_layout存在: 是")
                print(f"tasks_container_layout项目数: {self.task_window.tasks_container_layout.count()}")
            else:
                print("警告: task_window没有tasks_container_layout属性")
            
            # 根据TaskWindow.add_download_task的要求简化调用参数
            filename = download_data.get("filename", "准备下载...")
            print(f"准备添加任务：{filename}")
            
            # 确保任务窗口已初始化且可见
            if not hasattr(self, 'task_window') or not self.task_window:
                print("错误：任务窗口未初始化")
                return False
            
            # 直接调用add_download_task方法
            print("调用task_window.add_download_task方法...")
            try:
                row = self.task_window.add_download_task(filename, "获取中...")
                print(f"task_window.add_download_task返回值: {row}")
            except Exception as e:
                print(f"调用add_download_task失败: {e}")
                import traceback
                traceback.print_exc()
                return False
                
            print(f"任务添加结果: row={row}")
            
            if row >= 0:
                # 创建下载任务
                print("创建下载管理器...")
                try:
                    # 每次创建新的连接器实例，避免重用可能存在问题的连接
                    connector = FallbackConnector()
                    transfer_manager = connector.create_download_task(download_data)
                    print(f"下载管理器创建成功: {type(transfer_manager)}")
                except Exception as e:
                    print(f"创建下载管理器失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                
                # 设置保存路径
                if hasattr(self, 'save_path') and self.save_path:
                    transfer_manager.save_path = self.save_path
                    print(f"设置保存路径: {self.save_path}")
            
                # 连接信号
                print("连接信号...")
                try:
                    transfer_manager.initialized.connect(lambda supports_multi: self.update_file_size(row, transfer_manager.file_size))
                    transfer_manager.block_progress_updated.connect(lambda progress_data: self.update_progress(row, progress_data))
                    transfer_manager.speed_updated.connect(lambda speed: self.update_speed(row, speed))
                    transfer_manager.download_completed.connect(lambda: self.download_completed(row))
                    transfer_manager.error_occurred.connect(lambda error: self.download_error(row, error))
                    print("信号连接成功")
                except Exception as e:
                    print(f"连接信号失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            
                # 保存任务
                print("保存任务到下载列表...")
                try:
                    self.download_tasks.append({
                        "row": row,
                        "thread": transfer_manager,
                        "manager": transfer_manager,
                        "url": url,
                        "save_path": transfer_manager.save_path,
                        "status": "下载中",
                        "request_id": f"req_{int(time.time() * 1000)}"
                    })
                    print(f"保存任务成功, 当前任务数: {len(self.download_tasks)}")
                except Exception as e:
                    print(f"保存任务失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            
                # 启动下载
                print("启动下载...")
                try:
                    transfer_manager.start()
                    print("下载启动成功")
                except Exception as e:
                    print(f"启动下载失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                
                # 切换到任务页面
                print("切换到下载页面...")
                try:
                    self.switch_page(0)
                    print("页面切换成功")
                except Exception as e:
                    print(f"切换页面失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                # 如果窗口最小化，则显示通知
                if self.isMinimized() or not self.isVisible():
                    print("窗口最小化，显示通知...")
                    if hasattr(self, 'tray_icon') and self.tray_icon:
                        try:
                            self.tray_icon.showMessage(
                                "新下载任务",
                                f"已从浏览器添加任务: {filename}",
                                QSystemTrayIcon.Information,
                                5000
                            )
                        except Exception as e:
                            print(f"显示托盘通知失败: {e}")
                
                # 处理完成后主动刷新WebSocket连接，确保后续请求能正常接收
                try:
                    print("再次刷新WebSocket连接...")
                    # 重新创建一个连接器以确保WebSocket服务器处于活跃状态
                    new_connector = FallbackConnector()
                    new_connector.downloadRequestReceived.connect(self.add_download_from_extension)
                    new_connector.start()
                    # 保留引用以防止被垃圾回收
                    self.connector = new_connector
                    print("WebSocket连接已刷新，准备接收下一个请求")
                except Exception as e:
                    print(f"刷新WebSocket连接失败: {e}")
                    import traceback
                    traceback.print_exc()
                
                print(f"浏览器下载请求处理完成: {url}")
                print(f"主线程任务添加结束, 线程ID: {thread_id}")
                print("========== 浏览器下载请求处理结束 ==========\n")
                return True
            else:
                print("无法创建下载任务，任务窗口返回错误行号")
                print("========== 浏览器下载请求处理失败 ==========\n")
                return False
        
        # 使用单次计时器确保在主线程中执行
        try:
            print(f"调度任务到主线程...")
            QTimer.singleShot(0, add_task_in_main_thread)
            print(f"调度成功，等待主线程执行")
        except Exception as e:
            print(f"调度到主线程失败: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        return True
        
    def refresh_websocket_connection(self):
        """定期刷新WebSocket连接，确保连接保持活跃"""
        try:
            if hasattr(self, 'connector'):
                print("定时刷新WebSocket连接...")
                self.connector.start()
                print("WebSocket连接已刷新")
            else:
                print("警告: WebSocket连接器不存在，重新创建")
                self.init_browser_download_listener()
        except Exception as e:
            print(f"刷新WebSocket连接失败: {e}")
            try:
                print("尝试重新创建WebSocket连接器...")
                self.init_browser_download_listener()
            except Exception as e2:
                print(f"重新创建WebSocket连接器也失败: {e2}")
                import traceback
                traceback.print_exc()
    
    def switch_page(self, index):
        # 将索引转换为页面ID
        page_id = None
        if index == 0:
            page_id = "downloads"
        elif index == 1:
            page_id = "finished"
        elif index == 2:
            page_id = "settings"
        elif index == 3:
            page_id = "about"
        
        # 切换到指定页面
        if page_id:
            self.pages_manager.switch_page(page_id)
    
    def open_settings(self):
        self.pages_manager.switch_page("settings")

    def handle_settings_message(self, success, message):
        # 不再显示消息框，因为设置页面已经显示了一个
        # 只在控制台打印消息，用于调试
        print(f"设置{'成功' if success else '失败'}: {message}")
        
        # 也可以更新状态栏或通知管理器显示消息
        if hasattr(self, 'notify_manager'):
            level = "info" if success else "warning"
            self.notify_manager.show_message("设置", message, level=level)
        
    def closeEvent(self, event):
        # 在这里添加关闭事件的处理逻辑
        super().closeEvent(event)
        
    def check_update_logs(self):
        latest = self.update_log_manager.get_latest_version_log()
        if latest:
            version, log_data = latest
            dialog = UpdateLogDialog(
                version=version,
                content=log_data["content"],
                update_time=log_data["update_time"],
                parent=self
            )
            if dialog.exec() == QDialog.Accepted:
                self.update_log_manager.mark_as_read(version)
                # 清理旧的更新日志
                self.update_log_manager.clean_old_logs()
        
    def connect_file_operations(self):
        """连接文件操作功能"""
        def open_file_method(self, row):
            """打开下载的文件"""
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件路径
                        filename = task.get('manager').file_name
                        if not filename:
                            continue
                        
                        filepath = os.path.join(self.save_path, filename)
                        if not os.path.exists(filepath):
                            QMessageBox.warning(self, "错误", f"文件不存在: {filepath}")
                            return
                        
                        # 使用系统默认程序打开文件
                        import subprocess
                        import sys
                        
                        if sys.platform == 'win32':
                            os.startfile(filepath)
                        elif sys.platform == 'darwin':  # macOS
                            subprocess.call(['open', filepath])
                        else:  # Linux
                            subprocess.call(['xdg-open', filepath])
                            
                        print(f"打开文件: {filepath}")
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法打开文件: {str(e)}")
                    break
        
        def delete_file_method(self, row):
            """删除下载的文件"""
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件路径
                        filename = task.get('manager').file_name
                        if not filename:
                            continue
                        
                        filepath = os.path.join(self.save_path, filename)
                        if not os.path.exists(filepath):
                            QMessageBox.warning(self, "错误", f"文件不存在: {filepath}")
                            return
                        
                        # 确认删除
                        confirm = QMessageBox.question(self, "确认删除", 
                                                     f"确定要删除文件 {filename} 吗？",
                                                     QMessageBox.Yes | QMessageBox.No)
                        if confirm == QMessageBox.Yes:
                            os.remove(filepath)
                            QMessageBox.information(self, "成功", f"文件已删除: {filename}")
                            print(f"删除文件: {filepath}")
                            
                            # 也可以从任务列表中移除该任务
                            # self.download_tasks.remove(task)
                            # self.task_window.download_table.removeRow(row)
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法删除文件: {str(e)}")
                    break
        
        def open_folder_method(self, row):
            """打开文件所在文件夹"""
            import sys
            import subprocess
            
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件夹路径和文件名
                        folder_path = self.save_path
                        filename = task['manager'].file_name
                        
                        if not os.path.exists(folder_path):
                            QMessageBox.warning(self, "错误", f"文件夹不存在: {folder_path}")
                            return
                        
                        # 构建完整文件路径
                        file_path = os.path.join(folder_path, filename)
                        file_path = os.path.normpath(file_path)  # 规范化路径
                        
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            # 如果文件不存在，只打开文件夹
                            QMessageBox.warning(self, "提示", f"文件不存在，将只打开文件夹")
                            # 直接打开文件夹
                            if sys.platform == 'win32':
                                os.startfile(folder_path)
                            elif sys.platform == 'darwin':  # macOS
                                subprocess.call(['open', folder_path])
                            else:  # Linux
                                subprocess.call(['xdg-open', folder_path])
                            return
                        
                        # 打开文件夹并选中文件
                        if sys.platform == 'win32':
                            # Windows下使用explorer /select命令选中文件
                            # 确保路径使用反斜杠并用双引号包裹
                            normalized_path = file_path.replace('/', '\\')
                            cmd = f'explorer /select,"{normalized_path}"'
                            print(f"执行命令: {cmd}")
                            subprocess.run(cmd, shell=True)
                        elif sys.platform == 'darwin':  # macOS
                            # macOS下使用open -R命令选中文件
                            subprocess.call(['open', '-R', file_path])
                        else:  # Linux
                            # Linux下不同的文件管理器有不同的方法，这里尝试几种常见的
                            try:
                                # 尝试使用xdg-open打开文件夹
                                subprocess.call(['xdg-open', os.path.dirname(file_path)])
                            except:
                                # 如果失败，尝试dbus方法或其他方法
                                if os.path.exists('/usr/bin/nautilus'):
                                    subprocess.call(['nautilus', file_path])
                                else:
                                    subprocess.call(['xdg-open', os.path.dirname(file_path)])
                        
                        print(f"打开文件夹并选中文件: {file_path}")
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法打开文件夹: {str(e)}")
                        import traceback
                        traceback.print_exc()
                    break
        
        # 动态绑定方法到任务窗口
        self.task_window.open_file = types.MethodType(open_file_method, self)
        self.task_window.delete_file = types.MethodType(delete_file_method, self)
        self.task_window.open_folder = types.MethodType(open_folder_method, self)
        
    def on_minimize_to_tray(self):
        """处理最小化到托盘的逻辑"""
        # 检查是否有活跃的下载任务
        active_downloads = False
        for task in self.download_tasks:
            if task['status'] == 'running':
                active_downloads = True
                break
                
        # 显示通知
        tray_icon = self.title_bar.tray_icon
        if tray_icon.isSystemTrayAvailable() and tray_icon.supportsMessages():
            # 获取图标实例
            notification_icon = self.app_icon
            
            if active_downloads:
                tray_icon.showMessage(
                    "Hanabi Download Manager",
                    "应用程序将在后台继续下载，双击托盘图标可以恢复窗口。",
                    QSystemTrayIcon.Information,
                    3000  # 显示3秒
                )
            else:
                tray_icon.showMessage(
                    "Hanabi Download Manager",
                    "应用程序已最小化到系统托盘，双击托盘图标可以恢复窗口。",
                    QSystemTrayIcon.Information,
                    3000  # 显示3秒
                )
                
        # 记录状态
        self.is_minimized_to_tray = True
        
        # 检查是否有活跃下载任务，只有存在活跃任务时才保存状态
        if active_downloads:
            self.save_application_state()
    
    def save_application_state(self):
        """保存应用状态"""
        try:
            # 保存活跃下载任务状态等
            active_tasks = []
            for task in self.download_tasks:
                if task['status'] in ['running', 'paused']:
                    active_tasks.append({
                        'url': task['manager'].url,
                        'filename': task['manager'].file_name,
                        'status': task['status'],
                        'progress': task['manager'].current_progress
                    })
            
            # 如果有需要，可以将状态写入临时文件
            # import tempfile
            # import json
            # with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            #     json.dump(active_tasks, f)
            #     self.state_file = f.name
            
            print(f"[DEBUG] 已保存{len(active_tasks)}个活跃任务的状态")
        except Exception as e:
            print(f"[ERROR] 保存应用状态失败: {str(e)}")
        
    @staticmethod
    def get_resource_path(relative_path):
        """获取资源文件的绝对路径，适用于开发环境和打包环境"""
        import os
        import sys
        
        # 统一处理路径分隔符
        relative_path = relative_path.replace('/', os.sep)
        
        if getattr(sys, 'frozen', False):
            # 如果是打包环境
            base_path = os.path.dirname(sys.executable)
            # 获取应用安装目录 (HanabiDownloadManager)
            app_dir = os.path.basename(base_path)
            if app_dir != "HanabiDownloadManager":
                # 检查是否在上级目录
                parent_dir = os.path.dirname(base_path)
                if os.path.basename(parent_dir) == "HanabiDownloadManager":
                    base_path = parent_dir
                    
            # 直接构建资源路径
            resource_path = os.path.join(base_path, "resources", os.path.basename(relative_path))
            
            # 调试信息
            print(f"应用基础路径: {base_path}")
            print(f"尝试加载资源: {resource_path}")
            
            if os.path.exists(resource_path):
                return resource_path
                
            # 向上一级查找
            parent_resource_path = os.path.join(os.path.dirname(base_path), "resources", os.path.basename(relative_path))
            if os.path.exists(parent_resource_path):
                return parent_resource_path
                
            # 在当前目录查找
            direct_resource = os.path.join(base_path, os.path.basename(relative_path))
            if os.path.exists(direct_resource):
                return direct_resource
                
            # 搜索logo.png
            if os.path.basename(relative_path) == "logo.png":
                print("正在搜索logo.png文件...")
                for root, dirs, files in os.walk(base_path, topdown=True):
                    if "logo.png" in files:
                        logo_path = os.path.join(root, "logo.png")
                        print(f"找到logo文件: {logo_path}")
                        return logo_path
            
            # 查看基础目录内容
            print(f"目录 {base_path} 内容:")
            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path):
                        print(f"- 目录: {item}")
                        # 检查resources目录
                        if item == "resources":
                            resources_dir = item_path
                            print(f"  Resources目录内容:")
                            for res_item in os.listdir(resources_dir):
                                print(f"  - {res_item}")
                    else:
                        print(f"- 文件: {item}")
            except Exception as e:
                print(f"列出目录内容出错: {str(e)}")
                
            # 返回硬编码的正确路径
            hardcoded_path = "E:\\HanabiDownloadManager\\resources\\" + os.path.basename(relative_path)
            if os.path.exists(hardcoded_path):
                print(f"使用硬编码路径: {hardcoded_path}")
                return hardcoded_path
                
            return resource_path
        else:
            # 如果是开发环境
            # 先尝试在当前工作目录下查找
            current_dir = os.getcwd()
            resource_path = os.path.join(current_dir, relative_path)
            if os.path.exists(resource_path):
                return resource_path
                
            # 尝试在项目根目录下查找
            base_path = os.path.dirname(os.path.abspath(__file__))
            # 转到项目根目录，注意现在是在client/ui/client_interface下
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(base_path))))
            resource_path = os.path.join(project_root, relative_path)
            if os.path.exists(resource_path):
                return resource_path
                
            # 直接尝试查找资源文件名（不包含路径）
            if "resources" in relative_path:
                resource_name = os.path.basename(relative_path)
                direct_resource_path = os.path.join(project_root, "resources", resource_name)
                if os.path.exists(direct_resource_path):
                    return direct_resource_path
            
            # 打印调试信息
            print(f"尝试查找资源路径: {resource_path}")
            print(f"当前工作目录: {current_dir}")
            print(f"项目根目录: {project_root}")
            
            # 最后尝试在项目根目录下的resources文件夹中查找
            final_path = os.path.join(project_root, "resources", os.path.basename(relative_path))
            if os.path.exists(final_path):
                return final_path
                
            return resource_path
        
    def apply_global_font(self):
        """应用字体到全局应用程序"""
        try:
            # 获取应用程序实例
            app = QApplication.instance()
            if app:
                # 应用字体到应用程序
                self.font_manager.apply_font(app)
                
                # 设置正常和加粗字体
                app.setFont(self.font_manager.create_optimized_font(is_bold=False, size=12))
                
                # 打印字体族信息
                if hasattr(self.font_manager, 'loaded_families') and self.font_manager.loaded_families:
                    print(f"已加载字体族: {', '.join(self.font_manager.loaded_families[:3])}...")
        except Exception as e:
            print(f"应用全局字体出错: {e}")
        
    def get_available_icons(self):
        """获取可用的Fluent图标列表示例"""
        try:
            # 获取所有Fluent图标
            fluent_icons = self.font_manager.get_fluent_icons()
            # 获取下载相关图标
            download_icons = self.font_manager.get_available_icons("ic_fluent_arrow_download_")
            # 返回前10个图标用于示例
            return fluent_icons[:10] if fluent_icons else []
        except Exception as e:
            print(f"获取图标出错: {e}")
            return []
        
    def print_available_icons(self, category=None):
        """打印可用的Fluent图标列表，方便查找图标名称
        
        参数:
            category: 可选的图标类别前缀，例如'arrow', 'folder'等
        """
        try:
            if category:
                # 获取特定类别的图标
                icons = self.font_manager.get_available_icons(f"ic_fluent_{category}")
                print(f"\n===== {category} 类别的图标 =====")
            else:
                # 获取所有Fluent图标
                icons = self.font_manager.get_fluent_icons()
                print("\n===== 所有可用Fluent图标 =====")
            
            # 按字母顺序排序
            icons.sort()
            
            # 分组打印，每行5个
            for i in range(0, len(icons), 5):
                group = icons[i:i+5]
                print(" | ".join(group))
            
            print(f"共找到 {len(icons)} 个图标\n")
            return icons
        except Exception as e:
            print(f"获取图标出错: {e}")
            return []
        
    def redownload_from_history(self, history_record):
        """从历史记录中重新下载文件"""
        # 获取URL和文件名
        url = history_record.get('url')
        if not url:
            QMessageBox.warning(self, "错误", "无法重新下载，缺少下载URL")
            return
            
        # 切换到下载页面
        self.pages_manager.switch_page("downloads")
        
        # 设置URL输入框
        if hasattr(self, 'url_input'):
            self.url_input.setText(url)
            
            # 自动启动下载
            QTimer.singleShot(100, self.start_download)
            
            # 显示信息
            QMessageBox.information(self, "重新下载", f"已开始重新下载：{history_record.get('filename')}")
        else:
            QMessageBox.warning(self, "错误", "无法访问下载界面")
            return
        