from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLineEdit, QTableWidget, 
                              QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
                              QSplitter, QFrame, QLabel, QSizePolicy, QStackedWidget, QScrollArea, QDialog,QApplication)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QPropertyAnimation, QEasingCurve, QPoint, QTimer, QCoreApplication, QMetaObject, Q_ARG, QEvent, QRect
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPainterPath, QBrush, QMouseEvent, QFontDatabase, QCursor
from PySide6.QtWidgets import QSystemTrayIcon, QGraphicsOpacityEffect, QGridLayout

from client.ui.components.progressBar import ProgressBar
from client.ui.title_styles.titleStyles import TitleBar
from connect.fallback_connector import FallbackConnector
from core.font.font_manager import FontManager
from client.ui.client_interface.about_window import AboutWindow
from client.ui.client_interface.settings.settings_container import SettingsContainer
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.download_log_dialog import DownloadLogDialog
from client.ui.components.update_log_dialog import UpdateLogDialog
from core.update.update_log_manager import UpdateLogManager
from client.ui.pages_manager import PagesManager, CategoryButton
from client.ui.client_interface.task_window import TaskWindow, RoundedTaskFrame
from client.ui.client_interface.history_window import HistoryWindow
from client.ui.client_interface.download_window import DownloadWindow
from client.ui.extension_interface.extension_window import ExtensionWindow
from client.ui.components.customNotify import NotifyManager

import os
import sys
import threading
import types
import datetime
import time
import logging
import requests
import uuid
import gc
import platform
import inspect
import weakref
from urllib.parse import urlparse, unquote

# 字体管理器已经在font_manager.py中集成，支持Fluent图标系统
# 提供以下功能:
# 1. 自动加载字体和图标
# 2. 统一应用字体到组件
# 3. 创建图标标签
# 4. 获取可用图标列表

# 添加自定义事件类
class BrowserDownloadEvent(QEvent):
    """自定义事件类，用于浏览器下载请求的线程安全处理"""
    
    # 定义自定义事件类型
    EventType = QEvent.Type(QEvent.User + 1)
    
    def __init__(self, download_data):
        super().__init__(self.EventType)
        self.download_data = download_data

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
    """下载管理器主窗口类，负责整个应用程序的界面和逻辑"""
    
    def __init__(self):
        super().__init__()
        # 初始化内部状态
        self._initialize_state()
        # 设置应用程序窗口属性
        self._setup_window_properties()
        # 创建UI组件
        self._create_ui()
        # 连接信号槽
        self._connect_signals()
        # 初始化下载组件
        self._initialize_download_system()
        # 加载配置
        self._load_configurations()
        # 检查更新
        self._check_for_updates()
    
    def _initialize_state(self):
        """初始化内部状态和变量"""
        # 任务列表
        self.download_tasks = []
        # 当前保存路径
        self.save_path = os.path.expanduser("~/Downloads")
        # 窗口状态
        self.is_minimized_to_tray = False
        # 线程锁，用于多线程操作保护
        self.thread_lock = threading.Lock()
        # 日志初始化
        self._setup_logging()
        # 字体管理器
        self.font_manager = FontManager()
        # 配置管理器
        from client.ui.client_interface.settings.config import config
        self.config_manager = config
        # 更新日志管理器
        self.update_log_manager = UpdateLogManager()
        # 天气信息初始化
        self.weather_data = {
            "city": "--",
            "temperature": "--",
            "weather": "--"
        }
        # 天气标签
        self.weather_label = None
        # 添加天气线程属性
        self.weather_thread = None
    
    def _setup_logging(self):
        """设置日志系统"""
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("hanabi_download_manager.log"),
                logging.StreamHandler()
            ]
        )
    
    def _setup_window_properties(self):
        """设置窗口基本属性"""
        # 窗口标题
        self.setWindowTitle("Hanabi Download Manager")
        # 窗口大小
        self.resize(1050, 650)
        # 设置窗口样式
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # === 重要：确保主窗口关闭时应用程序才会退出 ===
        # 这是修复最小化状态下关闭弹窗引起应用关闭的关键
        # 明确指定只有主窗口关闭时才退出应用，子窗口关闭不影响
        self.setAttribute(Qt.WA_QuitOnClose, True)
        
        # 应用全局字体
        self.apply_global_font()
        # 加载应用图标
        self._load_application_icon()
    
    def _load_application_icon(self):
        """加载应用程序图标"""
        self.icon_path = self.get_resource_path("resources/logo.png")
        if os.path.exists(self.icon_path):
            self.app_icon = QIcon(self.icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            logging.warning(f"图标文件不存在: {self.icon_path}")
            self.app_icon = None
        
    def _create_ui(self):
        """创建用户界面"""
        # 创建中心部件
        self.central_widget = QWidget()
        self.central_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(self.central_widget)
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(12, 0, 12, 12)
        self.main_layout.setSpacing(0)
        
        # 创建标题栏
        self._create_title_bar()
        
        # 创建内容区
        self._create_content_area()
    
    def _create_title_bar(self):
        """创建自定义标题栏"""
        self.title_bar = TitleBar(self)
        self.title_bar.setAttribute(Qt.WA_TranslucentBackground)
        self.title_bar.minimizeToTray.connect(self.on_minimize_to_tray)
        self.main_layout.addWidget(self.title_bar)
        
    def _create_content_area(self):
        """创建主要内容区域"""
        # 内容区布局
        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        
        # 创建侧边栏
        self._create_sidebar()
        
        # 创建主内容区
        self._create_main_content_area()
        
        # 添加到主布局
        self.main_layout.addLayout(self.content_layout, 1)
    
    def _create_sidebar(self):
        """创建左侧导航栏"""
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("background-color: #1E1E1E;")
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 25)
        sidebar_layout.setSpacing(20)
        
        # 添加品牌和应用信息
        self._create_brand_section(sidebar_layout)
        
        # 添加中间弹性空间，使下面的导航按钮可以显示在底部
        # 这里不添加具体的控件，让PagesManager在合适的位置添加按钮
        
        # 添加弹性空间，将后续导航按钮推到底部
        sidebar_layout.addStretch(1)
        
        # 添加到内容布局
        self.content_layout.addWidget(self.sidebar)
    
    def _create_brand_section(self, parent_layout):
        """创建品牌和应用信息区域"""
        brand_container = QWidget()
        brand_container.setObjectName("brand_container")  # 设置对象名，便于识别
        brand_container.setStyleSheet("background-color: transparent;")
        brand_layout = QVBoxLayout(brand_container)
        brand_layout.setContentsMargins(10, 0, 10, 0)
        brand_layout.setSpacing(8)
        
        # 应用名称水平布局
        title_layout = QHBoxLayout()
        title_layout.setSpacing(5)
        
        # 应用名称
        app_title = QLabel()
        app_title.setText("<span style='font-size: 28px;'>Hanabi</span><br><span style='font-size: 14px;'>Download Manager</span>")
        app_title.setStyleSheet("color: #B39DDB; font-weight: bold; background-color: transparent;")
        app_title.setTextFormat(Qt.RichText)
        self.font_manager.apply_font(app_title)
        title_layout.addWidget(app_title)
        
        # 添加应用名称布局
        brand_layout.addLayout(title_layout)
        
        # 应用口号
        slogan_label = QLabel("Dev By ZZBuAoYe")
        slogan_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.font_manager.apply_font(slogan_label)
        brand_layout.addWidget(slogan_label)
        
        # 天气信息作为单独的一行
        self.weather_label = QLabel()
        self.weather_label.setStyleSheet("color: #9E9E9E; background-color: transparent; padding: 4px 0;")
        self.weather_label.setTextFormat(Qt.RichText)
        self.weather_label.setCursor(Qt.PointingHandCursor)  # 设置指针光标，提示可交互
        self.font_manager.apply_font(self.weather_label)
        self._update_weather_display()  # 初始化显示
        brand_layout.addWidget(self.weather_label)
        
        # 创建天气悬浮窗
        self.weather_popup = WeatherPopup(self)
        
        # 为天气标签安装事件过滤器
        self.weather_label.installEventFilter(self)
        
        # 下方装饰线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333; margin-top: 8px;")
        separator.setFixedHeight(1)
        brand_layout.addWidget(separator)
        
        # 获取天气数据
        self._fetch_weather_data()
        
        # 设置定时器，每30分钟更新一次天气
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self._fetch_weather_data)
        self.weather_timer.start(30 * 60 * 1000)  # 30分钟 = 30 * 60 * 1000毫秒
        
        parent_layout.addWidget(brand_container)
    
    def _create_main_content_area(self):
        """创建主内容区域"""
        self.content_area = RoundedWidget(radius=20, bg_color="#1E1E1E", corners="all")
                
        # 创建页面管理器和页面
        self._setup_pages()
        
        # 添加到内容布局
        self.content_layout.addWidget(self.content_area, 1)
    
    def _setup_pages(self):
        """设置页面管理器和各个页面"""
        # 创建必要页面
        self.settings_page = SettingsContainer(self.config_manager, self)
        self.settings_page.settingsMessage.connect(self.handle_settings_message)
        
        self.about_page = AboutWindow()
        
        # 创建浏览器扩展页面
        self.extension_page = ExtensionWindow(parent=self, font_manager=self.font_manager, config_manager=self.config_manager)
        
        # 使用PagesManager管理页面
        self.pages_manager = PagesManager(self.sidebar, self.content_area, self)
        
        # 注册常用页面
        self.pages = self.pages_manager.register_common_pages()
        
        # 获取下载页面引用
        self.download_page = self.pages.get("downloads")
        if self.download_page:
            # 创建下载窗口
            self.download_window = DownloadWindow(self.font_manager, self)
            
            # 连接下载窗口信号
            self.download_window.downloadRequested.connect(self.start_download)
            self.download_window.saveFolderChanged.connect(self.on_save_folder_changed)
            
            # 添加到下载页面
            if hasattr(self.download_page, 'content_layout'):
                self.download_page.content_layout.addWidget(self.download_window, 1)
        
        # 获取历史页面引用
        self.history_page = self.pages.get("history")
        if self.history_page and hasattr(self.history_page, 'content_widget'):
            self._connect_history_page()
            
        # 添加浏览器扩展页面
        self.pages_manager.add_page(
            "extension", 
            self.extension_page, 
            "ic_fluent_apps_add_in_24_regular", 
            "浏览器扩展", 
            "top", 
            3
        )
        
        # 连接扩展页面信号
        self._connect_extension_page()
    
    def on_save_folder_changed(self, folder_path):
        """保存文件夹改变事件处理"""
        self.save_path = folder_path
        # 更新配置
        self.config_manager.set_save_path(folder_path)
        NotifyManager.info(f"默认保存路径已更改: {folder_path}")
    
    def _create_download_page(self):
        """创建下载页面内容"""
        # 此方法已不再需要，保留为空方法以兼容旧代码
        pass
    
    def _create_url_input_section(self):
        """创建URL输入和按钮区域"""
        top_card = RoundedWidget(radius=15)
        top_card.setMinimumHeight(150)
        top_card_layout = QVBoxLayout(top_card)
        top_card_layout.setContentsMargins(20, 20, 20, 20)
        top_card_layout.setSpacing(15)
        
        # URL输入框标题
        url_title = QLabel("添加下载")
        url_title.setAlignment(Qt.AlignCenter)
        url_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(url_title)
        top_card_layout.addWidget(url_title)
        
        # URL输入框和按钮区域
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
        # 添加回车键触发下载功能
        self.url_input.returnPressed.connect(self.start_download)
        url_input_layout.addWidget(self.url_input, 5)
        
        # 创建下载和路径按钮
        self._create_action_buttons(url_input_layout)
        
        top_card_layout.addLayout(url_input_layout)
        
        # 显示保存路径
        self.save_path_label = QLabel(f"当前保存位置: {self.save_path}")
        self.save_path_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.save_path_label.setAlignment(Qt.AlignCenter)
        top_card_layout.addWidget(self.save_path_label)
        
        # 添加到下载页面
        self.download_page_layout.addWidget(top_card)
    
    def _create_action_buttons(self, parent_layout):
        """创建下载和选择路径按钮"""
        # 下载按钮
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setMinimumWidth(100)
        self.download_btn.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.download_btn.setStyleSheet("""
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
        """)
        
        download_btn_layout = QHBoxLayout(self.download_btn)
        download_btn_layout.setContentsMargins(10, 0, 10, 0)
        download_btn_layout.setSpacing(8)
        
        # 添加图标
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
        parent_layout.addWidget(self.download_btn, 1)
        
        # 选择保存路径按钮
        self.path_btn = QPushButton()
        self.path_btn.setMinimumHeight(45)
        self.path_btn.setMinimumWidth(150)
        self.path_btn.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
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
        
        path_btn_layout = QHBoxLayout(self.path_btn)
        path_btn_layout.setContentsMargins(10, 0, 10, 0)
        path_btn_layout.setSpacing(5)
        
        # 创建图标
        folder_icon = self.font_manager.create_icon_label(
            self.path_btn,
            "ic_fluent_folder_24_regular",
            size=14,
            color="#FFFFFF"
        )
        path_btn_layout.addWidget(folder_icon)
        
        # 创建文本
        path_text = QLabel("保存位置")
        path_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_text.setMinimumWidth(70)
        path_text.setAlignment(Qt.AlignCenter)
        path_btn_layout.addWidget(path_text)
        
        # 连接事件
        self.path_btn.clicked.connect(self.select_save_path)
        parent_layout.addWidget(self.path_btn, 2)
    
    def _create_task_window(self):
        """创建下载任务窗口"""
        if not hasattr(self, 'task_window') or self.task_window is None:
            self.task_window = TaskWindow(self.font_manager, self)
        
        # 确保任务窗口可见
        self.task_window.setVisible(True)
        self.task_window.setAttribute(Qt.WA_DontShowOnScreen, False)
        
        # 连接任务信号
        self._connect_task_signals()
        
        # 添加到下载页面
        task_card = RoundedTaskFrame()
        task_card.setMinimumHeight(300)
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(5, 5, 5, 5)
        task_layout.addWidget(self.task_window, 1)
        
        self.download_page_layout.addWidget(task_card, 1)
    
    def _connect_task_signals(self):
        """连接任务窗口信号"""
        if hasattr(self, 'task_window') and self.task_window:
            self.task_window.taskPaused.connect(self.pause_download_task)
            self.task_window.taskResumed.connect(self.resume_download_task)
            self.task_window.taskCancelled.connect(self.cancel_download_task)
            
            # 连接文件操作信号
            self._connect_file_operations()
    
    def _connect_file_operations(self):
        """连接文件操作相关信号"""
        try:
            # 在这里添加与文件操作相关的信号连接
            if hasattr(self, 'task_window') and self.task_window and hasattr(self.task_window, 'fileOpened'):
                self.task_window.fileOpened.connect(self.open_downloaded_file)
            
            if hasattr(self, 'task_window') and self.task_window and hasattr(self.task_window, 'folderOpened'):
                self.task_window.folderOpened.connect(self.open_containing_folder)
        except Exception as e:
            logging.error(f"连接文件操作信号失败: {e}")
    
    def open_downloaded_file(self, file_path):
        """打开下载的文件"""
        try:
            import os
            import subprocess
            
            if os.path.exists(file_path):
                if sys.platform == 'win32':
                    os.startfile(file_path)
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:  # Linux
                    subprocess.call(['xdg-open', file_path])
                    
                logging.info(f"已打开文件: {file_path}")
            else:
                self.show_toast(f"文件不存在: {file_path}")
                logging.warning(f"尝试打开不存在的文件: {file_path}")
        except Exception as e:
            logging.error(f"打开文件失败: {e}")
            self.show_toast(f"无法打开文件: {str(e)}")
    
    def open_containing_folder(self, folder_path):
        """打开包含下载文件的文件夹"""
        try:
            import os
            import subprocess
            
            if os.path.exists(folder_path):
                if sys.platform == 'win32':
                    # 在Windows上打开文件夹
                    subprocess.call(['explorer', folder_path])
                elif sys.platform == 'darwin':  # macOS
                    subprocess.call(['open', folder_path])
                else:  # Linux
                    subprocess.call(['xdg-open', folder_path])
                    
                logging.info(f"已打开文件夹: {folder_path}")
            else:
                self.show_toast(f"文件夹不存在: {folder_path}")
                logging.warning(f"尝试打开不存在的文件夹: {folder_path}")
        except Exception as e:
            logging.error(f"打开文件夹失败: {e}")
            self.show_toast(f"无法打开文件夹: {str(e)}")
    
    def _connect_history_page(self):
        """连接历史页面信号"""
        history_window = self.history_page.content_widget
        if isinstance(history_window, HistoryWindow):
            # 连接历史项点击信号
            history_window.history_item_clicked.connect(self.redownload_from_history)
            
            # 连接刷新按钮
            if hasattr(history_window, 'refresh_btn'):
                history_window.refresh_btn.clicked.connect(lambda: history_window.load_history())
    
    def _connect_signals(self):
        """连接信号槽"""
        # 连接设置页面消息信号
        if hasattr(self, 'settings_page'):
            self.settings_page.settingsMessage.connect(self.handle_settings_message)
    
    def _initialize_download_system(self):
        """初始化下载系统"""
        # 延迟初始化浏览器下载监听器，确保主窗口已完全加载
        QTimer.singleShot(2000, self.init_browser_download_listener)
    
    def _load_configurations(self):
        """加载配置"""
        # 加载保存路径
        self.save_path = self.config_manager.get_save_path() or os.path.expanduser("~/Downloads")
        # 确保路径存在
        os.makedirs(self.save_path, exist_ok=True)
        # 更新UI显示
        if hasattr(self, 'save_path_label'):
            self.save_path_label.setText(f"当前保存位置: {self.save_path}")
    
    def _check_for_updates(self):
        """检查更新"""
        QTimer.singleShot(2000, self.check_update_logs)
        
    def _fetch_weather_data(self):
        """获取天气数据 - 使用线程方式避免阻塞UI"""
        try:
            # 如果有正在运行的线程，先停止它
            if self.weather_thread and self.weather_thread.isRunning():
                self.weather_thread.stop()
                self.weather_thread.wait()  # 等待线程结束
            
            # 创建新的天气获取线程
            self.weather_thread = WeatherFetchThread(self)
            
            # 连接信号
            self.weather_thread.weatherDataReceived.connect(self._on_weather_data_received)
            self.weather_thread.weatherDataFailed.connect(self._on_weather_data_failed)
            
            # 启动线程
            self.weather_thread.start()
            
            logging.debug("天气数据获取线程已启动")
            
        except Exception as e:
            logging.error(f"启动天气数据获取线程失败: {str(e)}")
    
    @Slot(dict)
    def _on_weather_data_received(self, weather_data):
        """接收到天气数据的处理函数"""
        try:
            # 更新天气数据
            self.weather_data = weather_data
            
            # 更新UI显示
            if self.weather_label:
                self._update_weather_display()
                
            # 如果悬浮窗已经创建并且可见，也更新悬浮窗
            if hasattr(self, 'weather_popup') and self.weather_popup and self.weather_popup.is_visible:
                self.weather_popup.update_weather_data(weather_data)
                
            logging.debug(f"成功获取天气数据: {weather_data['city']} {weather_data['temperature']}℃ {weather_data['weather']}")
            
        except Exception as e:
            logging.error(f"处理天气数据失败: {str(e)}")
    
    @Slot(str)
    def _on_weather_data_failed(self, error_msg):
        """天气数据获取失败的处理函数"""
        logging.warning(f"获取天气数据失败: {error_msg}")
        # 可以选择在这里更新UI，显示获取失败的状态
        # 但通常保留上次的数据更好，避免UI闪烁
    
    def _update_weather_display(self):
        """更新天气显示"""
        if self.weather_label:
            # 根据天气状况选择合适的图标
            weather_icon = self._get_weather_icon(self.weather_data.get('weather', ''))
            
            # 获取城市名称，处理过长的情况
            city = self.weather_data.get('city', '--')
            # 如果城市名称包含逗号，只取第一部分(如"Hangzhou, Zhejiang, China" -> "Hangzhou")
            if ',' in city:
                city = city.split(',')[0].strip()
            
            # 创建带图标的天气文本
            weather_text = f"<span style='font-size: 13px;'>{weather_icon}{city} {self.weather_data.get('temperature', '--')}℃</span>"
            self.weather_label.setText(weather_text)
            
            # 确保标签高度足够
            self.weather_label.setMinimumHeight(25)
        
    def paintEvent(self, event):
        """自定义绘制窗口背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        path = QPainterPath()
        rect = self.rect()
        
        # 圆角半径
        cornerRadius = 30
        path.addRoundedRect(rect, cornerRadius, cornerRadius)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1E1E1E"))
        
        painter.setClipPath(path)
        painter.drawPath(path)
    
    def mousePressEvent(self, event):
        """鼠标按下事件处理"""
        if event.button() == Qt.LeftButton:
            if not self.title_bar.underMouse():
                super().mousePressEvent(event)
                
    def show_toast(self, message, duration=2000):
        """显示轻量级提示"""
        QMessageBox.information(self, "提示", message)
    
    def handle_settings_message(self, success, message):
        """处理设置页面消息"""
        logging.info(f"设置{'成功' if success else '失败'}: {message}")
    
    def init_browser_download_listener(self):
        """初始化浏览器下载监听器"""
        try:
            logging.info("开始初始化浏览器下载监听器")
            
            # 如果已经有扩展窗口，不再初始化连接器
            if hasattr(self, 'extension_page') and self.extension_page:
                logging.info("扩展窗口已存在，使用扩展窗口处理浏览器下载")
                return
            
            # 停止现有定时器
            if hasattr(self, 'ws_refresh_timer') and self.ws_refresh_timer:
                self.ws_refresh_timer.stop()
            
            # 如果已经有连接器并且正在运行，不重新创建
            if hasattr(self, 'connector') and self.connector and self.connector.is_running():
                logging.info("连接器已存在且正在运行，跳过初始化")
                return
            
            # 销毁旧的处理器（如果存在）
            if hasattr(self, 'download_handler') and self.download_handler:
                try:
                    # 先断开信号
                    if hasattr(self.download_handler, 'downloadCompleted'):
                        try:
                            self.download_handler.downloadCompleted.disconnect()
                        except (TypeError, RuntimeError):
                            pass
                    
                    # 强制清理引用
                    import gc
                    self.download_handler = None
                    gc.collect()
                except Exception as e:
                    logging.error(f"清理旧的下载处理器失败: {e}")
                
            # 创建下载处理器
            from main import BrowserDownloadHandler
            self.download_handler = BrowserDownloadHandler(self)
            
            # 连接处理器的下载完成信号
            self.download_handler.downloadCompleted.connect(self._on_extension_download_completed, Qt.QueuedConnection)
                
            # 创建连接器
            self.connector = FallbackConnector()
            
            # 连接下载请求信号 - 使用下载处理器处理请求，而不是直接处理
            self.connector.downloadRequestReceived.connect(self.download_handler.handle_download_request, Qt.QueuedConnection)
            
            # 启动连接器
            self.connector.start()
            logging.info("浏览器下载监听器已启动并成功连接")
            
            # 设置心跳检查
            self.ws_refresh_timer = QTimer(self)
            self.ws_refresh_timer.timeout.connect(self.check_connector_health)
            self.ws_refresh_timer.start(10000)  # 10秒检查一次连接健康状况
            
        except Exception as e:
            logging.error(f"启动浏览器下载监听器失败: {e}")
            import traceback
            error_stack = traceback.format_exc()
            logging.error(error_stack)
            
            # 尝试延迟重新初始化
            QTimer.singleShot(5000, self.init_browser_download_listener)
    
    def check_connector_health(self):
        """检查连接器健康状况"""
        try:
            if not hasattr(self, 'connector') or not self.connector:
                logging.warning("连接器不存在，重新初始化")
                self.init_browser_download_listener()
                return
                
            # 检查连接器是否运行中
            if not self.connector.is_running():
                logging.warning("连接器不再运行，正在重新初始化")
                self.init_browser_download_listener()
            else:
                logging.debug("连接器健康检查: 正常运行中")
                
        except Exception as e:
            logging.error(f"检查连接器健康状况失败: {e}")
            # 失败时尝试重新初始化
            QTimer.singleShot(3000, self.init_browser_download_listener)
    
    def add_download_from_extension(self, download_data):
        """从浏览器扩展添加下载（确保线程安全）"""
        try:
            # 添加详细日志，记录请求数据
            logging.info(f"接收到浏览器扩展下载请求: {download_data}")
            
            # 验证请求数据格式
            if not isinstance(download_data, dict):
                logging.error(f"无效的下载请求数据类型: {type(download_data)}")
                return False
                
            # 检查URL
            url = download_data.get("url", "")
            if not url:
                logging.error("下载请求缺少URL")
                return False
            
            # 防止重复处理同一请求 - 使用请求ID或URL+时间戳作为唯一标识
            request_id = download_data.get("requestId", "")
            if not request_id:
                request_id = f"req_{url}_{int(time.time() * 1000)}"
                download_data["requestId"] = request_id
                
            # 初始化处理过的请求集合（如果不存在）
            if not hasattr(self, '_processed_extension_requests'):
                self._processed_extension_requests = set()
                
            # 检查请求是否已处理
            if request_id in self._processed_extension_requests:
                logging.warning(f"跳过重复的扩展下载请求 [ID: {request_id}]")
                return False
                
            # 记录此请求ID
            self._processed_extension_requests.add(request_id)
            # 添加自动清理机制，防止集合无限增长
            if len(self._processed_extension_requests) > 100:
                self._processed_extension_requests = set(list(self._processed_extension_requests)[-50:])
            
            # 确保headers字段存在
            if "headers" not in download_data:
                download_data["headers"] = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                }
            
            # 标记为浏览器扩展类型，用于区分手动添加
            download_data["type"] = "browser_extension"
            
            logging.info(f"浏览器扩展请求已验证，发送至扩展窗口处理 [ID: {download_data['requestId']}]")
            
            # 提取文件名，用于显示提示
            filename = download_data.get("filename", "")
            if not filename:
                # 从URL提取文件名
                parsed_url = urlparse(url)
                path = parsed_url.path
                if path:
                    filename = os.path.basename(path)
                    if '?' in filename:
                        filename = filename.split('?')[0]
                    try:
                        filename = unquote(filename)
                    except:
                        pass
            
            # 如果还是没有文件名，使用URL的一部分
            if not filename:
                filename = url[:30] + "..." if len(url) > 30 else url
            
            # 使用扩展窗口处理下载
            if hasattr(self, 'extension_page') and self.extension_page:
                # 切换到扩展页面
                self.pages_manager.switch_page("extension")
                # 处理下载
                QTimer.singleShot(200, lambda: self.extension_page.start_download_from_extension(download_data))
                return True
            else:
                # 创建自定义事件
                event = BrowserDownloadEvent(download_data)
                QCoreApplication.postEvent(self, event)
                return True
            
        except Exception as e:
            logging.error(f"处理浏览器扩展下载请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def select_save_path(self):
        """选择保存位置"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.save_path = folder_path
            # 确保目录存在
            os.makedirs(self.save_path, exist_ok=True)
            # 更新UI
            if hasattr(self, 'save_path_label'):
                self.save_path_label.setText(f"当前保存位置: {self.save_path}")
            # 更新配置
            self.config_manager.set_save_path(folder_path)
            # 提示用户
            NotifyManager.info(f"保存位置已更新: {folder_path}")
    
    def start_download(self, url=None):
        """手动开始下载任务"""
        # 获取URL - 可以从参数获取或从UI获取
        if url is None:
            if hasattr(self, 'download_window') and hasattr(self.download_window, 'url_input'):
                url = self.download_window.url_input.text().strip()
            elif hasattr(self, 'url_input'):
                url = self.url_input.text().strip()
            else:
                logging.error("无法获取下载URL")
                return
        
        if not url:
            self.show_toast("请输入下载URL")
            return
        
        # 确保路径有效
        if not self.save_path or not os.path.isdir(self.save_path):
            self.save_path = os.path.expanduser("~/Downloads")
            os.makedirs(self.save_path, exist_ok=True)
            logging.info(f"已设置默认保存路径: {self.save_path}")
            
            # 更新下载窗口的保存路径
            if hasattr(self, 'download_window'):
                self.download_window.set_save_path(self.save_path)
        
        # 生成请求ID
        request_id = f"manual_{int(time.time() * 1000)}"
        logging.info(f"创建手动下载任务 [ID: {request_id}]")
        
        # 创建下载请求数据，与浏览器扩展格式相同
        download_data = {
            "url": url,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
            },
            "requestId": request_id,
            "type": "manual"  # 标记为手动添加类型
        }
        
        # 使用与浏览器扩展相同的事件系统处理
        event = BrowserDownloadEvent(download_data)
        QCoreApplication.postEvent(self, event)
        
        # 记录日志
        logging.info(f"手动下载请求已提交 [ID: {request_id}, URL: {url}]")
        
        # 添加此行：延迟一段时间后重新初始化浏览器连接器
        logging.info("计划在下载任务添加后重新初始化浏览器连接器")
        QTimer.singleShot(1000, self._reinit_browser_download_listener)
    
    @Slot(dict)
    def _process_browser_download(self, download_data):
        """处理浏览器下载请求（在主线程中）"""
        try:
            # 记录请求ID和来源
            request_id = download_data.get("requestId", f"manual_{int(time.time() * 1000)}")
            download_source = download_data.get("download_source", "未知来源")
            logging.info(f"[main_window.py] 主线程处理下载请求 [ID: {request_id}] [来源: {download_source}]")
            
            # 获取URL
            url = download_data.get("url", "")
            if not url:
                logging.error(f"[main_window.py] 下载请求 [ID: {request_id}] 缺少URL")
                return
            
            # 确保路径有效
            if not self.save_path or not os.path.isdir(self.save_path):
                self.save_path = os.path.expanduser("~/Downloads")
                os.makedirs(self.save_path, exist_ok=True)
                
            # 设置保存路径
            download_data["save_path"] = self.save_path
            
            # 为了避免重复创建弹窗，检查是否已经被扩展页面处理
            if download_data.get("handled_by_extension", False):
                logging.info(f"[main_window.py] 下载请求 [ID: {request_id}] 已经被扩展页面处理，主窗口不再处理")
                return
                
            # 如果是由扩展页面发送的信号，但扩展页面已经或将要创建弹窗，则跳过
            if download_source.startswith("client/ui/extension_interface/extension_window.py"):
                logging.info(f"[main_window.py] 下载请求 [ID: {request_id}] 来自扩展页面，主窗口不再处理")
                return
            
            # 处理文件名
            filename = download_data.get("filename", "")
            if not filename:
                filename = self._extract_filename_from_url(url)
                download_data["filename"] = filename
            
            # 处理下载请求
            if hasattr(self, 'download_window') and self.download_window:
                # 添加来源标记
                download_data["download_source"] = "client/ui/client_interface/main_window.py:_process_browser_download"
                
                # 使用下载窗口处理
                success = self.download_window.handle_browser_download_request(download_data)
                if success:
                    logging.info(f"[main_window.py] 已由download_window处理下载请求 [ID: {request_id}]")
                    # 记录下载请求
                    self._count_download_request()
                    # 切换到下载页面
                    self.pages_manager.switch_page("download")
        except Exception as e:
            logging.error(f"处理浏览器下载请求失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def start_download_with_data(self, task_data, download_data):
        """使用提供的数据开始下载任务"""
        try:
            # 使用下载窗口添加任务
            if hasattr(self, 'download_window'):
                row = self.download_window.add_download_task(task_data)
            # 兼容性处理：如果没有下载窗口，尝试使用任务窗口
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    row = self.task_window.add_task(task_data)
            else:
                logging.error("任务窗口和下载窗口均未初始化")
                return False
            
            if row < 0:
                logging.error(f"添加任务返回错误: row={row}")
                return False
                
            logging.info(f"成功添加下载任务到UI, row={row}")
            
            # 创建downlaod manager
            connector = FallbackConnector()
            download_manager = connector.create_download_task(download_data)
            
            # 设置保存路径
            download_manager.save_path = task_data.get("save_path", self.save_path)
        
            # 连接信号
            download_manager.initialized.connect(lambda supports_multi: self.on_download_initialized(row, download_manager))
            download_manager.block_progress_updated.connect(lambda progress_data: self.on_progress_updated(row, progress_data))
            download_manager.speed_updated.connect(lambda speed: self.on_speed_updated(row, speed))
            download_manager.download_completed.connect(lambda: self.on_download_completed(row))
            download_manager.error_occurred.connect(lambda error: self.on_download_error(row, error))
            
            # 保存任务信息
            task_id = f"task_{int(time.time() * 1000)}_{len(self.download_tasks)}"
            self.download_tasks.append({
                "row": row,
                "task_id": task_id,
                "manager": download_manager,
                "url": task_data["url"],
                "save_path": task_data.get("save_path", self.save_path),
                "status": "下载中",
                "start_time": datetime.datetime.now(),
                "source": task_data.get("source", "unknown")
            })
            
            # 启动下载
            download_manager.start()
            
            # 切换到下载页面
            self.switch_page(0)
            
            logging.info(f"已开始下载任务: {task_data['url']}")
            return True
            
        except Exception as e:
            logging.error(f"开始下载任务失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def on_download_initialized(self, row, manager):
        """下载初始化完成回调"""
        try:
            # 更新文件信息 - 使用下载窗口或任务窗口
            if hasattr(self, 'download_window'):
                self.download_window.update_task_file_info(row, filename=manager.file_name, size=manager.file_size)
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    self.task_window.update_file_info(row, filename=manager.file_name, size=manager.file_size)
            
            # 更新任务信息
            for task in self.download_tasks:
                if task["row"] == row:
                    task["file_name"] = manager.file_name
                    task["file_size"] = manager.file_size
                    break
        
            logging.debug(f"下载初始化完成: {manager.file_name}")
        except Exception as e:
            logging.error(f"更新文件信息失败: {e}")
    
    def on_progress_updated(self, row, progress_data):
        """进度更新回调"""
        try:
            # 查找任务
            task = next((t for t in self.download_tasks if t["row"] == row), None)
            if not task:
                return
                
            # 获取下载管理器和文件大小
            manager = task.get("manager")
            file_size = getattr(manager, "file_size", 0) if manager else 0
            
            # 更新进度条 - 使用下载窗口或任务窗口
            if hasattr(self, 'download_window'):
                self.download_window.update_task_progress(row, progress_data, file_size)
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    self.task_window.update_progress(row, progress_data, file_size)
            
            # 计算总进度
            progress_percent = self._calculate_progress_percent(progress_data)
            
            # 检查下载完成
            if progress_percent >= 99.9 and task["status"] != "已完成":
                task["status"] = "已完成"
                task["end_time"] = datetime.datetime.now()
                
                if hasattr(self, 'download_window'):
                    self.download_window.update_task_status(row, "下载完成", True)
                elif hasattr(self, 'task_window') and self.task_window:
                    with self.thread_lock:
                        self.task_window.update_status(row, "下载完成", True)
                
                # 添加到历史记录
                self._add_to_history(task)
                
        except Exception as e:
            logging.error(f"更新进度出错: {e}")
    
    def _calculate_progress_percent(self, progress_data):
        """计算下载进度百分比"""
        if not progress_data:
            return 0
            
        try:
            total_downloaded = 0
            total_size = 0
            
            for block in progress_data:
                if isinstance(block, dict):
                    # 支持新旧格式
                    start_pos = block.get('start_position', block.get('startPos', 0))
                    end_pos = block.get('end_position', block.get('endPos', 0))
                    current = block.get('current_position', block.get('progress', start_pos))
                elif isinstance(block, (list, tuple)) and len(block) >= 3:
                    start_pos, current, end_pos = block[:3]
                else:
                    continue
                
                # 确保值合法
                start_pos = max(0, int(start_pos))
                end_pos = max(start_pos, int(end_pos))
                current = max(start_pos, min(end_pos, int(current)))
                
                # 计算已下载量
                block_downloaded = current - start_pos
                block_size = end_pos - start_pos + 1
                
                # 累计总量
                total_downloaded += block_downloaded
                total_size += block_size
            
            # 计算百分比
            if total_size > 0:
                progress = (total_downloaded / total_size) * 100
                # 如果进度超过99.9%，视为完成
                if progress > 99.9:
                    return 100
                return min(round(progress), 100)  # 确保不超过100%
            
            return 0
        except Exception as e:
            logging.error(f"计算进度出错: {e}")
            return 0
    
    def on_speed_updated(self, row, speed_bytes):
        """速度更新回调"""
        try:
            if hasattr(self, 'download_window'):
                self.download_window.update_task_speed(row, speed_bytes)
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    self.task_window.update_speed(row, speed_bytes)
        except Exception as e:
            logging.error(f"更新速度失败: {e}")
    
    def on_download_completed(self, row):
        """下载完成回调"""
        try:
            # 查找任务
            task = next((t for t in self.download_tasks if t["row"] == row), None)
            if not task:
                return
                
            # 如果任务已经标记为完成，不再处理
            if task.get("status") == "已完成":
                return
                
            # 标记任务为完成
            task["status"] = "已完成"
            task["end_time"] = datetime.datetime.now()
            
            # 更新UI
            if hasattr(self, 'download_window'):
                self.download_window.update_task_status(row, "下载完成", True)
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    self.task_window.update_status(row, "下载完成", True)
            
            # 添加到历史记录
            self._add_to_history(task)
            
            # 刷新历史页面
            self._refresh_history_page()
            
            # 向API发送请求，统计下载次数
            self._send_download_count()
            
            # 获取文件名用于通知
            file_name = ""
            if hasattr(task.get("manager", None), "file_name"):
                file_name = task["manager"].file_name
            else:
                file_name = task.get("file_name", "未知文件")
                
            # 显示通知
            NotifyManager.success(f"下载完成: {file_name}")
            
            logging.info(f"下载任务完成: {task.get('file_name', '')}")
            
        except Exception as e:
            logging.error(f"处理下载完成失败: {e}")
    
    def _add_to_history(self, task):
        """添加任务到历史记录"""
        try:
            # 获取下载管理器
            manager = task.get("manager")
            if not manager:
                return
                
            # 创建历史记录条目
            from core.history.history_manager import HistoryManager
            
            history_item = {
                'filename': getattr(manager, 'file_name', '未知文件'),
                'url': getattr(manager, 'url', task.get('url', '')),
                'save_path': os.path.join(task.get('save_path', ''), getattr(manager, 'file_name', '未知文件')),
                'file_size': getattr(manager, 'file_size', 0),
                'download_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'completed'
            }
            
            # 添加记录
            history_manager = HistoryManager()
            history_manager.add_record(history_item)
            
            logging.info(f"已添加到历史记录: {history_item['filename']}")
        except Exception as e:
            logging.error(f"添加历史记录失败: {e}")
    
    def _refresh_history_page(self):
        """刷新历史页面"""
        try:
            if hasattr(self, 'history_page') and self.history_page:
                history_widget = getattr(self.history_page, 'content_widget', None)
                if history_widget and hasattr(history_widget, 'load_history'):
                    # 在主线程中异步刷新
                    QTimer.singleShot(100, history_widget.load_history)
                    # 添加通知
                    QTimer.singleShot(200, lambda: NotifyManager.info("正在刷新历史记录"))
        except Exception as e:
            logging.error(f"刷新历史页面失败: {e}")
    
    def on_download_error(self, row, error):
        """下载错误回调"""
        try:
            # 错误消息
            error_message = str(error)
            logging.error(f"下载错误: {error_message}")
        
            # 更新UI状态
            if hasattr(self, 'download_window'):
                self.download_window.update_task_status(row, "下载失败", False, error_message)
            elif hasattr(self, 'task_window') and self.task_window:
                with self.thread_lock:
                    self.task_window.update_status(row, "下载失败", False, error_message)
                
                # 根据错误类型提供友好提示
                if "Permission denied" in error_message:
                    self.task_window.set_task_failed(row, "没有写入权限，请检查保存路径")
                elif "Connection" in error_message:
                    self.task_window.set_task_failed(row, "网络连接错误，请检查网络")
                elif "Timeout" in error_message:
                    self.task_window.set_task_failed(row, "连接超时，服务器无响应")
            
            # 根据错误类型提供友好提示
            if "Permission denied" in error_message:
                self.task_window.set_task_failed(row, "没有写入权限，请检查保存路径")
            elif "Connection" in error_message:
                self.task_window.set_task_failed(row, "网络连接错误，请检查网络")
            elif "Timeout" in error_message:
                self.task_window.set_task_failed(row, "连接超时，服务器无响应")
        
            # 更新任务状态
            for task in self.download_tasks:
                if task['row'] == row:
                    task['status'] = '下载失败'
                    task['error'] = error_message
                    break
        except Exception as e:
            logging.error(f"处理下载错误失败: {e}")
    
    def pause_download_task(self, row):
        """暂停下载任务"""
        try:
            for task in self.download_tasks:
                if task['row'] == row and task['status'] == '下载中':
                    # 停止下载
                    if task.get('manager'):
                        task['manager'].stop()
                    
                    # 更新状态
                    task['status'] = '已暂停'
                    
                    # 更新UI - 使用下载窗口或任务窗口
                    if hasattr(self, 'download_window'):
                        self.download_window.update_task_status(row, "已暂停")
                    elif hasattr(self, 'task_window') and self.task_window:
                        with self.thread_lock:
                            self.task_window.update_status(row, "已暂停")
                    
                    logging.info(f"已暂停任务: {row}")
                    break
        except Exception as e:
            logging.error(f"暂停下载任务失败: {e}")
    
    def resume_download_task(self, row):
        """恢复下载任务"""
        try:
            for task in self.download_tasks:
                if task["row"] == row and task["status"] in ["已暂停", "下载失败"]:
                    # 获取任务信息
                    url = task["url"]
                    save_path = task.get("save_path", self.save_path)
                
                    # 创建下载请求
                    download_data = {
                        "url": url,
                        "headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                        }
                    }
                
                    # 创建新的下载管理器
                    connector = FallbackConnector()
                    download_manager = connector.create_download_task(download_data)
                
                    # 设置保存路径
                    download_manager.save_path = save_path
                
                    # 连接信号
                    download_manager.initialized.connect(lambda supports_multi: self.on_download_initialized(row, download_manager))
                    download_manager.block_progress_updated.connect(lambda progress_data: self.on_progress_updated(row, progress_data))
                    download_manager.speed_updated.connect(lambda speed: self.on_speed_updated(row, speed))
                    download_manager.download_completed.connect(lambda: self.on_download_completed(row))
                    download_manager.error_occurred.connect(lambda error: self.on_download_error(row, error))
                    
                    # 更新任务信息
                    task["manager"] = download_manager
                    task["status"] = "下载中"
                
                    # 启动下载
                    download_manager.start()
                
                    # 更新UI - 使用下载窗口或任务窗口
                    if hasattr(self, 'download_window'):
                        self.download_window.update_task_status(row, "下载中")
                    elif hasattr(self, 'task_window') and self.task_window:
                        with self.thread_lock:
                            self.task_window.update_status(row, "下载中")
                    
                    logging.info(f"已恢复任务: {row}")
                    break
        except Exception as e:
            logging.error(f"恢复下载任务失败: {e}")
    
    def cancel_download_task(self, row):
        """取消下载任务"""
        try:
            for task in self.download_tasks:
                if task['row'] == row:
                    # 停止下载
                    if task.get('manager'):
                        task['manager'].stop()
                    
                    # 更新状态
                    task['status'] = '已取消'
                    
                    # 更新UI - 使用下载窗口或任务窗口
                    if hasattr(self, 'download_window'):
                        self.download_window.update_task_status(row, "已取消")
                    elif hasattr(self, 'task_window') and self.task_window:
                        with self.thread_lock:
                            self.task_window.update_status(row, "已取消")
                    
                    logging.info(f"已取消任务: {row}")
                    break
        except Exception as e:
            logging.error(f"取消下载任务失败: {e}")
    
    def switch_page(self, index):
        # 将索引转换为页面ID
        page_id = None
        if index == 0:
            page_id = "downloads"
        elif index == 1:
            page_id = "history"
        elif index == 2:
            page_id = "settings"
        elif index == 3:
            page_id = "about"
        
        # 切换到指定页面
        if page_id:
            self.pages_manager.switch_page(page_id)
    
    def open_settings(self):
        self.pages_manager.switch_page("settings")
        
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
        
    def on_minimize_to_tray(self):
        """处理最小化到托盘的逻辑"""
        # 检查是否有活跃的下载任务
        active_downloads = False
        for task in self.download_tasks:
            if task['status'] == '下载中':
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
                if task['status'] in ['下载中', '已暂停']:
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
        
    def _reinit_browser_download_listener(self):
        """重新初始化浏览器下载监听器"""
        try:
            logging.info("计划在下载任务添加后重新初始化浏览器连接器")
            self.init_browser_download_listener()
        except Exception as e:
            logging.error(f"重新初始化浏览器下载监听器失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 查找活跃下载任务
        active_downloads = [task for task in self.download_tasks if task['status'] == '下载中']
        
        if active_downloads:
            # 自动暂停所有正在下载的任务
            for task in active_downloads:
                try:
                    # 获取任务行号
                    row = task['row']
                    
                    # 更新任务状态为已暂停
                    task['status'] = '已暂停'
                    
                    # 暂停下载而不是停止
                    if task.get('manager'):
                        task['manager'].stop()  # 目前使用stop方法暂停，保留任务信息
                    
                    # 更新UI显示
                    with self.thread_lock:
                        self.task_window.update_status(row, "已暂停")
                    
                    logging.info(f"自动暂停任务: {row}")
                except Exception as e:
                    logging.error(f"自动暂停任务失败: {e}")
            
            # 显示提示信息
            logging.info(f"已自动暂停{len(active_downloads)}个下载任务并准备退出")
            
            # 可选：显示通知
            QMessageBox.information(
                self,
                "下载已暂停",
                f"已自动暂停{len(active_downloads)}个正在进行的下载任务。下次启动应用时可以恢复这些任务。",
                QMessageBox.Ok
            )
        
        # 关闭所有可能的弹窗
        try:
            for widget in QApplication.topLevelWidgets():
                if widget != self and widget.isVisible() and isinstance(widget, QDialog):
                    logging.info(f"关闭子对话框: {widget.__class__.__name__}")
                    widget.close()
        except Exception as e:
            logging.error(f"关闭子对话框失败: {e}")
        
        # 释放下载处理器资源
        if hasattr(self, 'download_handler') and self.download_handler:
            try:
                # 断开信号连接
                if hasattr(self.download_handler, 'downloadCompleted'):
                    try:
                        self.download_handler.downloadCompleted.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                
                # 使用弱引用避免循环引用
                import weakref
                handler_ref = weakref.ref(self.download_handler)
                self.download_handler = None
                
                # 强制清理
                import gc
                gc.collect()
                
                logging.info("已安全释放下载处理器资源")
            except Exception as e:
                logging.error(f"释放下载处理器资源失败: {e}")
        
        # 停止浏览器下载监听器
        if hasattr(self, 'connector') and self.connector:
            try:
                self.connector.stop()
                logging.info("已停止浏览器下载监听器")
            except Exception as e:
                logging.error(f"停止浏览器下载监听器失败: {e}")
        
        # 停止定时器
        if hasattr(self, 'ws_refresh_timer') and self.ws_refresh_timer:
            self.ws_refresh_timer.stop()
        
        # 保存配置
        if hasattr(self, 'config_manager'):
            self.config_manager.save_config()
        
        # 保存下载任务的状态，以便下次启动时恢复
        self.save_application_state()
        
        # 停止天气获取线程
        if hasattr(self, 'weather_thread') and self.weather_thread and self.weather_thread.isRunning():
            try:
                self.weather_thread.stop()
                self.weather_thread.wait(1000)  # 最多等待1秒
                logging.info("已停止天气获取线程")
            except Exception as e:
                logging.error(f"停止天气获取线程失败: {e}")
        
        logging.info("应用程序正常关闭")
        super().closeEvent(event)
    
    def apply_global_font(self):
        """应用全局字体"""
        try:
            # 获取应用程序实例
            app = QApplication.instance()
            if app:
                # 应用字体
                self.font_manager.apply_font(app)
                # 设置默认字体
                app.setFont(self.font_manager.create_optimized_font(is_bold=False, size=12))
                logging.debug("已应用全局字体")
        except Exception as e:
            logging.error(f"应用全局字体失败: {e}")
        
    @staticmethod
    def get_resource_path(relative_path):
        """获取资源文件路径"""
        import os
        import sys
        
        # 统一路径分隔符
        relative_path = relative_path.replace('/', os.sep)
        
        if getattr(sys, 'frozen', False):
            # 打包环境
            base_path = os.path.dirname(sys.executable)
            app_dir = os.path.basename(base_path)
            
            if app_dir != "HanabiDownloadManager":
                parent_dir = os.path.dirname(base_path)
                if os.path.basename(parent_dir) == "HanabiDownloadManager":
                    base_path = parent_dir
            
            # 构建资源路径
            resource_path = os.path.join(base_path, "resources", os.path.basename(relative_path))
            
            if os.path.exists(resource_path):
                return resource_path
                
            # 向上查找
            parent_resource_path = os.path.join(os.path.dirname(base_path), "resources", os.path.basename(relative_path))
            if os.path.exists(parent_resource_path):
                return parent_resource_path
                
            # 直接查找
            direct_resource = os.path.join(base_path, os.path.basename(relative_path))
            if os.path.exists(direct_resource):
                return direct_resource
                
            # 查找特定文件
            if os.path.basename(relative_path) == "logo.png":
                for root, dirs, files in os.walk(base_path, topdown=True):
                    if "logo.png" in files:
                        return os.path.join(root, "logo.png")
            
            return resource_path
        else:
            # 开发环境
            current_dir = os.getcwd()
            resource_path = os.path.join(current_dir, relative_path)
            
            if os.path.exists(resource_path):
                return resource_path
                
            # 项目根目录查找
            base_path = os.path.dirname(os.path.abspath(__file__))
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
        
    def _init_settings_page(self):
        """初始化设置页面"""
        # 创建设置页面
        self.settings_page = SettingsContainer(self.config_manager, self)
        
        # 添加到主布局
        self.stacked_widget.addWidget(self.settings_page)
        
        # 连接信号
        self.settings_page.themeChanged.connect(self.apply_theme)
        self.settings_page.fontChanged.connect(self.apply_font)
        self.settings_page.languageChanged.connect(self.apply_language)
        
        # 连接更新页面信号
        if hasattr(self.settings_page, 'update_page'):
            self.settings_page.update_page.updateFound.connect(self._handle_update_found)
            self.settings_page.update_page.updateError.connect(self._handle_update_error)
            self.settings_page.update_page.addDownloadTask.connect(self._add_update_download_task)

    def _handle_update_error(self, error_msg):
        """处理更新错误"""
        logging.warning(f"检查更新失败: {error_msg}")
        # 可以添加其他错误处理逻辑

    def _handle_update_found(self, version, description):
        """处理发现更新"""
        try:
            logging.info(f"发现新版本: {version}")
            
            # 如果已存在更新按钮，先移除它
            if hasattr(self, 'update_button'):
                if self.update_button in self.title_bar.layout():
                    self.title_bar.layout().removeWidget(self.update_button)
                self.update_button.deleteLater()
                delattr(self, 'update_button')
            
            # 创建更新按钮
            self.update_button = QPushButton()
            self.update_button.setFixedHeight(32)
            self.update_button.setMinimumWidth(130)  # 设置最小宽度，避免文本被截断
            
            # 设置按钮样式
            self.update_button.setStyleSheet("""
                QPushButton {
                    background-color: #673AB7;
                    color: white;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7E57C2;
                }
                QPushButton:pressed {
                    background-color: #5E35B1;
                }
            """)
            
            # 创建水平布局用于图标和文本
            button_layout = QHBoxLayout(self.update_button)
            button_layout.setContentsMargins(10, 0, 10, 0)
            button_layout.setSpacing(5)
            
            # 添加图标
            icon_label = QLabel()
            self.font_manager.apply_icon_font(icon_label, 16)
            icon_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_download_24_filled"))
            icon_label.setStyleSheet("color: white; background-color: transparent;")
            icon_label.setFixedWidth(16)  # 固定图标宽度
            button_layout.addWidget(icon_label)
            
            # 添加文本
            text_label = QLabel("检测到新版本")
            text_label.setStyleSheet("color: white; background-color: transparent;")
            text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 设置对齐方式
            button_layout.addWidget(text_label)
            
            # 连接点击事件
            self.update_button.clicked.connect(lambda: self.open_settings() or self.switch_page(2))
            
            # 添加到标题栏
            # 找到标题栏中标题和控制按钮之间的位置
            title_layout = self.title_bar.layout()
            # 在倒数第4个位置插入(通常是在右侧控制按钮之前)
            title_layout.insertWidget(title_layout.count() - 3, self.update_button)
            
            logging.info("已添加更新提示按钮")
        except Exception as e:
            logging.error(f"创建更新按钮失败: {e}")
            import traceback
            logging.error(traceback.format_exc())

    def _add_update_download_task(self, url, filename, filesize):
        """添加更新下载任务"""
        try:
            # 确保任务窗口已初始化
            if not hasattr(self, 'task_window') or self.task_window is None:
                self._create_task_window()
            
            # 构建下载任务数据
            task_data = {
                "url": url,
                "file_name": filename,  # 修正键名为file_name，与其他方法一致
                "total_size": filesize,  # 修正键名为total_size，与其他方法一致
                "progress": 0,
                "status": "初始化中",
                "speed": "0 B/s",
                "save_path": self.save_path,
                "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "update",  # 标记来源为更新
                "request_id": f"update_{int(time.time() * 1000)}"  # 添加请求ID
            }
            
            # 请求格式，适配download方法的需求
            download_data = {
                "url": url,
                "filename": filename,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                },
                "requestId": task_data["request_id"],
                "type": "update"
            }
            
            # 开始下载任务
            success = self.start_download_with_data(task_data, download_data)
            
            if success:
                # 切换到下载页面
                self.switch_page(0)
                logging.info(f"已添加更新下载任务: {filename}")
                self.show_toast(f"开始下载新版本: {filename}")
            else:
                logging.error(f"添加更新下载任务失败")
                self.show_toast("下载新版本失败，请稍后重试")
                
        except Exception as e:
            logging.error(f"添加更新下载任务失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.show_toast("下载新版本失败，请稍后重试")
        
    def _send_download_count(self):
        """向API发送下载次数统计请求"""
        try:
            # 导入需要的模块
            import uuid
            import threading
            
            # 首先检查用户的统计设置
            stats_option = "local"  # 默认只参与本地统计
            if hasattr(self, 'config_manager') and self.config_manager:
                if hasattr(self.config_manager, 'get_setting'):
                    stats_option = self.config_manager.get_setting("user", "stats_option", "local")
                else:
                    # 直接从config获取
                    user_config = self.config_manager.get("user", {})
                    stats_option = user_config.get("stats_option", "local")
            
            # 记录本地统计
            logging.info(f"下载完成，本地统计记录已添加，统计模式: {stats_option}")
            
            # 如果用户选择只参与本地统计，不发送请求
            if stats_option == "local":
                logging.info("用户已选择仅参与本地统计，不发送全局统计请求")
                return
            
            # 只有当用户选择参与全局统计时，才创建并发送请求
            if stats_option == "global":
                # 创建统计请求的线程
                stats_thread = threading.Thread(
                    target=self._count_download_request,
                    daemon=True
                )
                stats_thread.start()
                
                logging.info("用户已选择参与全局统计，已启动下载统计线程")
            
        except Exception as e:
            logging.error(f"发送下载统计请求失败: {e}")
            
    def _count_download_request(self):
        """发送简单的下载计数请求到API"""
        try:
            import requests
            import uuid
            
            # 获取客户端ID
            client_id = self._get_client_id()
            
            # 记录请求信息
            logging.info(f"准备发送下载统计请求，客户端ID: {client_id}")
            
            # 发送请求到API
            url = f"https://apiv2.xiaoy.asia/hdm/download.php?client_id={client_id}"
            logging.info(f"发送下载统计请求: {url}")
            
            response = requests.get(url, timeout=5)
            
            # 记录响应
            if response.status_code == 200:
                logging.info(f"下载统计请求成功 - 状态码: {response.status_code}")
                # 打印响应内容
                try:
                    response_text = response.text.strip()
                    logging.info(f"API响应: {response_text}")
                    print(f"【下载统计】请求成功，API响应: {response_text}")
                except:
                    logging.info(f"API返回了空响应或无法解析的内容")
            else:
                logging.warning(f"下载统计请求失败 - 状态码: {response.status_code}")
                logging.debug(f"错误响应内容: {response.text}")
                
        except Exception as e:
            logging.error(f"发送下载统计请求失败: {e}")
            print(f"【下载统计】请求失败: {e}")
    
    def _get_client_id(self):
        """获取客户端唯一标识"""
        try:
            import uuid
            import os
            
            # 尝试从配置中获取客户端ID
            if hasattr(self, 'config_manager') and self.config_manager:
                # 检查是否有get_client_id方法
                if hasattr(self.config_manager, 'get_client_id'):
                    client_id = self.config_manager.get_client_id()
                    if client_id:
                        return client_id
                else:
                    # 如果没有方法，尝试直接从配置获取
                    user_config = self.config_manager.get("user", {})
                    client_id = user_config.get("client_id")
                    if client_id:
                        return client_id
                    
            # 如果没有，创建一个新的ID
            machine_id = ""
            try:
                if os.name == 'nt':  # Windows
                    import winreg
                    registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                    key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                    machine_id, _ = winreg.QueryValueEx(key, "MachineGuid")
                else:  # Linux/Mac
                    with open('/etc/machine-id', 'r') as f:
                        machine_id = f.read().strip()
            except Exception as e:
                logging.debug(f"获取设备ID失败: {e}")
                # 如果无法获取设备ID，使用随机UUID
                machine_id = str(uuid.uuid4())
                
            # 基于设备ID创建客户端ID，并添加HDM_前缀
            uuid_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"hanabi.downloader.{machine_id}"))
            client_id = f"HDM_{uuid_str}"
            
            # 保存到配置
            if hasattr(self, 'config_manager') and self.config_manager:
                # 检查set_client_id方法是否存在
                if hasattr(self.config_manager, 'set_client_id'):
                    self.config_manager.set_client_id(client_id)
                else:
                    # 检查set方法的参数数量，以适应不同的实现
                    if hasattr(self.config_manager, 'set'):
                        set_method = getattr(self.config_manager, 'set')
                        sig = inspect.signature(set_method)
                        param_count = len(sig.parameters)
                        
                        if param_count == 3:  # self, section, config
                            # 如果是config.py中的实现
                            if not hasattr(self.config_manager, '_config'):
                                # 确保有user部分
                                self.config_manager.set("user", {"client_id": client_id})
                            else:
                                # 直接修改_config
                                if "user" not in self.config_manager._config:
                                    self.config_manager._config["user"] = {}
                                self.config_manager._config["user"]["client_id"] = client_id
                        elif param_count == 4:  # self, category, key, value
                            # 如果是config_manager.py中的实现
                            self.config_manager.set("user", "client_id", client_id)
                    
                    # 无论哪种情况，确保保存配置
                    if hasattr(self.config_manager, 'save_config'):
                        self.config_manager.save_config()
                
            return client_id
        except Exception as e:
            logging.error(f"获取客户端ID失败: {e}")
            # 返回一个随机ID作为后备，同样添加HDM_前缀
            import uuid
            return f"HDM_{str(uuid.uuid4())}"
        
    def event(self, event):
        """全局事件处理"""
        try:
            # 处理浏览器下载事件
            if isinstance(event, BrowserDownloadEvent):
                logging.info("[main_window.py] 收到浏览器下载事件")
                download_data = event.download_data
                
                # 防止重复处理相同请求
                request_id = download_data.get("requestId", "")
                if not request_id:
                    url = download_data.get("url", "")
                    request_id = f"req_{url}_{int(time.time() * 1000)}"
                    download_data["requestId"] = request_id
                
                # 初始化处理过的请求集合（如果不存在）
                if not hasattr(self, '_processed_browser_requests'):
                    self._processed_browser_requests = set()
                    
                # 检查请求是否已处理
                if request_id in self._processed_browser_requests:
                    logging.warning(f"[main_window.py] 跳过重复的下载事件请求 [ID: {request_id}]")
                    return True
                    
                # 检查是否已在扩展请求记录中
                if hasattr(self, '_processed_extension_requests') and request_id in self._processed_extension_requests:
                    logging.warning(f"[main_window.py] 该请求已被扩展处理过，跳过事件请求 [ID: {request_id}]")
                    return True
                    
                # 记录此请求ID
                if request_id:
                    self._processed_browser_requests.add(request_id)
                    # 添加自动清理机制，防止集合无限增长
                    if len(self._processed_browser_requests) > 100:
                        self._processed_browser_requests = set(list(self._processed_browser_requests)[-50:])
                
                # 添加来源标识
                download_data["download_source"] = "client/ui/client_interface/main_window.py:event"
                
                # 如果有扩展页面，优先使用扩展页面处理
                if hasattr(self, 'extension_page') and self.extension_page:
                    logging.info(f"[main_window.py] 转交下载事件到扩展页面处理 [ID: {request_id}]")
                    # 切换到扩展页面
                    self.pages_manager.switch_page("extension")
                    # 使用计时器延迟处理下载，确保UI已经完全更新
                    # 设置标记表示不要创建新弹窗
                    download_data["handled_by_extension"] = False
                    QTimer.singleShot(200, lambda: self._safe_extension_download(download_data))
                    return True
                
                # 如果没有扩展页面，使用主窗口处理
                # 延迟处理以确保UI刷新
                logging.info(f"[main_window.py] 使用主窗口处理下载事件 [ID: {request_id}]")
                QTimer.singleShot(100, lambda: self._process_browser_download(download_data))
                return True
        except Exception as e:
            logging.error(f"处理全局事件出错: {e}")
            
        # 其他事件交给父类处理
        return super().event(event)
    
    def _safe_extension_download(self, download_data):
        """安全地调用扩展页面的下载处理方法"""
        try:
            # 检查请求ID，防止重复处理
            request_id = download_data.get("requestId", "")
            if not request_id:
                url = download_data.get("url", "")
                request_id = f"req_{url}_{int(time.time() * 1000)}"
                download_data["requestId"] = request_id
                
            # 如果请求已被处理，则直接跳过
            if hasattr(self, '_processed_extension_requests') and request_id in self._processed_extension_requests:
                logging.warning(f"[main_window.py] 该请求已被处理过，跳过扩展下载 [ID: {request_id}]")
                return
                
            # 再次检查扩展页面是否存在
            if not hasattr(self, 'extension_page') or not self.extension_page:
                logging.warning("[main_window.py] 扩展页面不可用，回退到主窗口处理下载")
                self._process_browser_download(download_data)
                return
                
            # 检查扩展页面是否有下载方法
            if hasattr(self.extension_page, 'start_download_from_extension'):
                # 记录请求，防止重复处理
                if not hasattr(self, '_processed_extension_requests'):
                    self._processed_extension_requests = set()
                    
                self._processed_extension_requests.add(request_id)
                if len(self._processed_extension_requests) > 100:
                    self._processed_extension_requests = set(list(self._processed_extension_requests)[-50:])
                
                # 为下载数据添加标记，表明它是从主窗口安全调用的，不需要创建新弹窗
                download_data["download_source"] = "client/ui/client_interface/main_window.py:_safe_extension_download"
                download_data["handled_by_extension"] = False
                
                # 执行下载 - 交由扩展页面处理
                logging.info(f"[main_window.py] 转交下载请求至扩展页面处理 [ID: {request_id}]")
                self.extension_page.start_download_from_extension(download_data)
            else:
                logging.warning("[main_window.py] 扩展页面缺少下载方法，回退到主窗口处理")
                self._process_browser_download(download_data)
        except Exception as e:
            logging.error(f"通过扩展页面处理下载时出错: {e}")
            # 回退到主窗口处理
            QTimer.singleShot(50, lambda: self._process_browser_download(download_data))
    
    def refresh_websocket_connection(self):
        """刷新WebSocket连接"""
        try:
            logging.info("准备刷新WebSocket连接...")
            
            # 检查是否有活跃下载任务
            active_downloads = False
            for task in self.download_tasks:
                if task['status'] == '下载中':
                    active_downloads = True
                    break
            
            # 如果有活跃任务，不立即刷新连接
            if active_downloads:
                logging.info("检测到活跃下载任务，暂不刷新连接")
                return
                
            # 停止现有连接器
            old_connector = None
            if hasattr(self, 'connector') and self.connector:
                logging.info("停止现有连接器")
                old_connector = self.connector
                self.connector = None
            
            # 初始化新连接器
            logging.info("创建新连接器")
            self.init_browser_download_listener()
            
            # 延迟安全关闭旧连接器
            if old_connector:
                QTimer.singleShot(2000, lambda: self._safe_stop_connector(old_connector))
                
        except Exception as e:
            logging.error(f"刷新WebSocket连接失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # 尝试延迟重新初始化
            QTimer.singleShot(5000, self.init_browser_download_listener)
    
    def _safe_stop_connector(self, connector):
        """安全地停止连接器，避免阻塞主线程"""
        try:
            if connector:
                connector.stop()
        except Exception as e:
            logging.error(f"安全停止连接器失败: {e}")
    
    def redownload_from_history(self, history_record):
        """从历史记录重新下载文件"""
        try:
            logging.info(f"重新下载历史记录: {history_record.get('filename', '未知文件')}")
            
            # 使用下载窗口重新下载
            if hasattr(self, 'download_window'):
                row = self.download_window.redownload_from_history(history_record)
                if row >= 0:
                    # 创建下载请求
                    download_data = {
                        "url": history_record.get("url", ""),
                        "filename": history_record.get("filename", ""),
                        "headers": {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                        },
                        "requestId": f"history_{int(time.time() * 1000)}"
                    }
                    
                    # 创建下载管理器
                    connector = FallbackConnector()
                    download_manager = connector.create_download_task(download_data)
                    
                    # 设置保存路径
                    download_manager.save_path = self.save_path
                    
                    # 连接信号
                    download_manager.initialized.connect(lambda supports_multi: self.on_download_initialized(row, download_manager))
                    download_manager.block_progress_updated.connect(lambda progress_data: self.on_progress_updated(row, progress_data))
                    download_manager.speed_updated.connect(lambda speed: self.on_speed_updated(row, speed))
                    download_manager.download_completed.connect(lambda: self.on_download_completed(row))
                    download_manager.error_occurred.connect(lambda error: self.on_download_error(row, error))
                    
                    # 保存任务信息
                    task_id = f"task_{int(time.time() * 1000)}_{len(self.download_tasks)}"
                    self.download_tasks.append({
                        "row": row,
                        "task_id": task_id,
                        "manager": download_manager,
                        "url": history_record.get("url", ""),
                        "save_path": self.save_path,
                        "status": "下载中",
                        "start_time": datetime.datetime.now(),
                        "source": "history"
                    })
                    
                    # 启动下载
                    download_manager.start()
                    
                    # 切换到下载页面
                    self.switch_page(0)
                    
                    logging.info(f"已开始从历史记录重新下载: {history_record.get('filename', '未知文件')}")
                    return True
                else:
                    logging.error("从历史记录重新下载失败")
                    return False
            else:
                # 兼容旧版本
                logging.warning("下载窗口未初始化，使用旧的下载处理方法")
                
                # 获取历史记录中的URL
                url = history_record.get("url", "")
                if not url:
                    self.show_toast("历史记录中没有URL，无法重新下载")
                    return False
                
                # 开始下载
                download_data = {
                    "url": url,
                    "filename": history_record.get("filename", ""),
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                    }
                }
                
                # 使用与浏览器扩展相同的事件系统处理
                event = BrowserDownloadEvent(download_data)
                QCoreApplication.postEvent(self, event)
                
                logging.info(f"已请求从历史记录重新下载: {history_record.get('filename', '未知文件')}")
                
                # 切换到下载页面
                self.switch_page(0)
                
                return True
                
        except Exception as e:
            logging.error(f"从历史记录重新下载失败: {e}")
            self.show_toast(f"重新下载失败: {str(e)}")
            return False
    
    def _connect_extension_page(self):
        """连接浏览器扩展页面信号"""
        if hasattr(self, 'extension_page') and self.extension_page:
            # 不再连接下载请求信号，而是让extension_window自己处理下载
            # 避免重复创建弹窗
            # self.extension_page.extensionDownloadReceived.connect(self._process_browser_download)
            
            # 连接连接状态变化信号
            self.extension_page.connectionStatusChanged.connect(self._on_extension_connection_changed)
            
            # 连接下载完成信号，刷新历史记录
            self.extension_page.downloadCompleted.connect(self._on_extension_download_completed)

    def _on_extension_connection_changed(self, is_connected, server_type):
        """扩展连接状态变化处理"""
        logging.info(f"浏览器扩展连接状态变化: {'已连接' if is_connected else '已断开'}, 服务器类型: {server_type}")
        
        # 如果浏览器连接器已经存在，停止它，避免重复监听
        if hasattr(self, 'connector') and self.connector:
            try:
                self.connector.stop()
                logging.info("已停止主窗口浏览器连接器")
            except Exception as e:
                logging.error(f"停止主窗口浏览器连接器失败: {e}")
            
            # 如果存在相关定时器，也停止它
            if hasattr(self, 'ws_refresh_timer') and self.ws_refresh_timer:
                self.ws_refresh_timer.stop()

    def _on_extension_download_completed(self, download_data):
        """扩展下载完成处理"""
        logging.info(f"浏览器扩展下载完成: {download_data.get('filename', '未知文件')}")
        
        # 刷新历史页面
        self._refresh_history_page()
    
    def _show_system_notification(self, title, message):
        """显示系统通知"""
        try:
            if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'tray_icon'):
                tray_icon = self.title_bar.tray_icon
                if tray_icon and tray_icon.isSystemTrayAvailable():
                    tray_icon.showMessage(
                        title,
                        message,
                        QSystemTrayIcon.Information,
                        3000
                    )
        except Exception as e:
            logging.error(f"显示系统通知失败: {e}")
        
    def _extract_filename_from_url(self, url):
        """从URL中提取文件名
        
        参数:
            url (str): 下载链接
            
        返回:
            str: 提取的文件名，如果无法提取则返回一个基于时间戳的默认文件名
        """
        try:
            if not url:
                return f"download_{int(time.time())}.bin"
                
            # 解析URL
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # 从路径中提取文件名
            if path:
                filename = os.path.basename(path)
                if filename:
                    # 去除查询参数
                    if '?' in filename:
                        filename = filename.split('?')[0]
                        
                    # URL解码
                    try:
                        decoded_filename = unquote(filename)
                        if decoded_filename != filename:
                            filename = decoded_filename
                    except:
                        pass
                        
                    # 确保文件有扩展名
                    if '.' in filename:
                        return filename
            
            # 如果无法提取有效文件名，创建默认名称
            timestamp = int(time.time())
            return f"download_{timestamp}.bin"
            
        except Exception as e:
            logging.warning(f"从URL提取文件名失败: {e}")
            timestamp = int(time.time())
            return f"download_{timestamp}.bin"
    
    def _get_weather_icon(self, weather_condition):
        """根据天气状况返回对应的图标"""
        # 使用font_manager创建图标文本
        icon_name = "ic_fluent_weather_sunny_24_regular"  # 默认晴天图标
        
        # 根据天气状况映射图标
        if "晴" in weather_condition or "晴天" in weather_condition:
            icon_name = "ic_fluent_weather_sunny_24_regular"
        elif "多云" in weather_condition:
            icon_name = "ic_fluent_weather_partly_cloudy_day_24_regular"
        elif "阴" in weather_condition:
            icon_name = "ic_fluent_weather_cloudy_24_regular"
        elif "雨" in weather_condition:
            if "雷" in weather_condition:
                icon_name = "ic_fluent_weather_thunderstorm_24_regular"
            elif "小" in weather_condition:
                icon_name = "ic_fluent_weather_drizzle_24_regular"
            else:
                icon_name = "ic_fluent_weather_rain_24_regular"
        elif "雪" in weather_condition:
            icon_name = "ic_fluent_weather_snow_24_regular"
        elif "雾" in weather_condition or "霾" in weather_condition:
            icon_name = "ic_fluent_weather_fog_24_regular"
        elif "风" in weather_condition or "飓风" in weather_condition:
            icon_name = "ic_fluent_weather_squalls_24_regular"
        
        # 获取图标Unicode字符
        try:
            # 尝试获取图标文本
            if hasattr(self, 'font_manager') and self.font_manager:
                icon_text = self.font_manager.get_icon_text(icon_name)
                if icon_text:
                    # 增大图标尺寸，并添加样式
                    return f"<span style='font-family: FluentSystemIcons-Regular; color: #B39DDB; font-size: 16px; vertical-align: middle; margin-right: 5px;'>{icon_text}</span>"
        except Exception as e:
            logging.warning(f"获取天气图标失败: {e}")
        
        # 如果获取失败或没有图标，返回空字符串
        return ""
    
    def eventFilter(self, watched, event):
        """事件过滤器，处理天气标签的鼠标事件"""
        if watched == self.weather_label:
            if event.type() == QEvent.Enter:
                # 鼠标进入天气标签
                self._show_weather_popup()
                return True
            elif event.type() == QEvent.Leave:
                # 鼠标离开天气标签
                self.weather_popup.prepare_hide()
                return True
        
        # 其他事件交给父类处理
        return super().eventFilter(watched, event)

    def _show_weather_popup(self):
        """显示天气详情悬浮窗"""
        if hasattr(self, 'weather_popup') and self.weather_popup:
            # 更新天气数据
            self.weather_popup.update_weather_data(self.weather_data)
            
            # 计算显示位置 - 在天气标签旁边，根据布局判断
            label_pos = self.weather_label.mapToGlobal(QPoint(0, 0))
            label_width = self.weather_label.width()
            label_height = self.weather_label.height()
            
            # 获取屏幕尺寸，避免显示超出屏幕边界
            screen_rect = QApplication.primaryScreen().availableGeometry()
            
            # 首先尝试在标签右侧显示
            popup_x = label_pos.x() + label_width + 5
            # 如果右侧显示会超出屏幕，则在标签下方显示
            if popup_x + 220 > screen_rect.right():  # 220是悬浮窗的固定宽度
                popup_x = label_pos.x()
                popup_y = label_pos.y() + label_height + 5
            else:
                # 右侧显示时，垂直居中对齐
                popup_y = label_pos.y() - 50  # 向上偏移一些，使内容更居中显示
            
            # 确保不超出屏幕顶部
            if popup_y < screen_rect.top():
                popup_y = screen_rect.top() + 5
            
            # 显示悬浮窗
            self.weather_popup.show_at(QPoint(popup_x, popup_y))

# 添加天气获取线程类
class WeatherFetchThread(QThread):
    """天气数据获取线程，防止在主线程中获取数据导致界面卡顿"""
    
    # 定义信号：成功获取天气数据时发出
    weatherDataReceived = Signal(dict)
    # 定义信号：获取数据失败时发出
    weatherDataFailed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 可以设置一个标志来控制线程运行
        self.is_running = True
    
    def run(self):
        """线程执行函数，负责获取天气数据"""
        try:
            import requests
            # 设置较短的超时时间，避免长时间阻塞
            response = requests.get("http://apiv2.xiaoy.asia/api/v1/?name=weather", timeout=5)
            
            # 检查响应状态
            if response.status_code == 200:
                # 检查响应内容是否为空
                if not response.text.strip():
                    logging.error("API返回空响应")
                    self.weatherDataFailed.emit("API返回空响应")
                    return
                
                # 记录原始响应内容以便调试
                logging.debug(f"天气API原始响应: {response.text}")
                
                try:
                    # 解析JSON响应
                    data = response.json()
                    
                    # 处理不同的API响应格式
                    if data.get("code") == 200:
                        # 获取data字段，可能是字典也可能是其他格式
                        api_data = data.get("data", {})
                        city = ""
                        weather_info = {}
                        
                        # 根据API返回的不同格式分别处理
                        if isinstance(api_data, dict):
                            # 格式1: 嵌套格式
                            if "data" in api_data and isinstance(api_data["data"], list) and len(api_data["data"]) > 0:
                                city = api_data.get("city", "--")
                                weather_info = api_data["data"][0]
                            # 格式2: 直接包含天气信息
                            else:
                                city = api_data.get("city", "--") 
                                weather_info = api_data
                        # 格式3: data直接是天气信息
                        elif isinstance(api_data, list) and len(api_data) > 0:
                            weather_info = api_data[0]
                            city = data.get("city", "--")
                        # 如果都不是，可能是其他格式
                        else:
                            weather_info = data
                            city = data.get("city", "--")
                        
                        # 检查天气信息是否获取成功
                        if not weather_info:
                            logging.warning("无法从API响应中提取天气信息")
                            self.weatherDataFailed.emit("无法从API响应中提取天气信息")
                            return
                        
                        # 解析温度，移除度数符号
                        temp = weather_info.get("temperature", "--")
                        if temp and "°" in temp:
                            temp = temp.replace("°", "")
                        
                        # 创建天气数据字典
                        weather_data = {
                            "city": city,
                            "temperature": temp,
                            "weather": weather_info.get("weather", "--"),
                            "wind": weather_info.get("wind", "--"),
                            "wind_level": weather_info.get("wind_level", "--"),
                            "humidity": weather_info.get("humidity", "--"),
                            "air_quality": weather_info.get("air_quality", "--")
                        }
                        
                        # 记录成功解析的数据
                        logging.info(f"成功获取天气数据: {city} {temp}℃ {weather_info.get('weather', '--')}")
                        
                        # 通过信号发送数据到主线程
                        self.weatherDataReceived.emit(weather_data)
                    else:
                        logging.warning(f"API返回错误状态: {data.get('code')} - {data.get('msg', '未知错误')}")
                        self.weatherDataFailed.emit(f"API返回错误: {data.get('msg', '未知错误')}")
                
                except requests.exceptions.JSONDecodeError as json_err:
                    # JSON解析错误，记录原始响应内容
                    logging.error(f"JSON解析错误: {json_err}")
                    logging.error(f"API返回的原始内容: {response.text[:200]}...")  # 只记录前200个字符
                    self.weatherDataFailed.emit(f"无法解析API响应: {json_err}")
                    
            else:
                logging.warning(f"HTTP错误: {response.status_code} - {response.reason}")
                self.weatherDataFailed.emit(f"HTTP错误: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logging.warning("API请求超时")
            self.weatherDataFailed.emit("API请求超时，请检查网络连接")
            
        except requests.exceptions.ConnectionError as conn_err:
            logging.warning(f"网络连接错误: {conn_err}")
            self.weatherDataFailed.emit("网络连接错误，无法连接到天气服务")
            
        except Exception as e:
            # 发送错误信号
            import traceback
            error_details = traceback.format_exc()
            logging.error(f"获取天气数据时出现未知错误: {e}")
            logging.debug(error_details)  # 详细错误信息记录到debug级别
            self.weatherDataFailed.emit(f"获取天气数据失败: {str(e)}")
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self.wait()  # 等待线程结束
    
# 添加自定义天气悬浮窗类
class WeatherPopup(QWidget):
    """自定义天气悬浮窗，提供美观的动画效果和主题风格"""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 不激活窗口（不抢焦点）
        self.setFocusPolicy(Qt.NoFocus)  # 不接受焦点
        
        # 初始化UI
        self._init_ui()
        
        # 设置动画
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(180)  # 稍微加快动画速度
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)  # 使用OutCubic曲线，开始快结束慢
        
        # 计时器：鼠标离开后延迟隐藏
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)
        
        # 隐藏状态
        self.is_visible = False
        
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(0)
        
        # 内容区域 - 圆角矩形背景
        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("weatherPopupContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(4)
        
        # 添加标题
        self.title_label = QLabel("天气详情", self.content_widget)
        self.title_label.setObjectName("weatherPopupTitle")
        self.content_layout.addWidget(self.title_label, 0, Qt.AlignLeft)
        
        # 添加分隔线
        self.separator = QFrame(self.content_widget)
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        self.separator.setObjectName("weatherPopupSeparator")
        self.content_layout.addWidget(self.separator)
        
        # 添加天气详情网格
        self.details_widget = QWidget(self.content_widget)
        self.details_layout = QGridLayout(self.details_widget)
        self.details_layout.setContentsMargins(0, 6, 0, 0)
        self.details_layout.setHorizontalSpacing(10)
        self.details_layout.setVerticalSpacing(6)
        
        # 创建天气详情标签
        self.city_label = self._create_detail_labels("城市", "--")
        self.weather_label = self._create_detail_labels("天气", "--")
        self.temp_label = self._create_detail_labels("温度", "--")
        self.wind_label = self._create_detail_labels("风向", "--")
        self.wind_level_label = self._create_detail_labels("风力", "--")
        self.humidity_label = self._create_detail_labels("湿度", "--")
        self.air_label = self._create_detail_labels("空气质量", "--")
        
        # 添加到网格
        self.details_layout.addWidget(self.city_label[0], 0, 0)
        self.details_layout.addWidget(self.city_label[1], 0, 1)
        self.details_layout.addWidget(self.weather_label[0], 1, 0)
        self.details_layout.addWidget(self.weather_label[1], 1, 1)
        self.details_layout.addWidget(self.temp_label[0], 2, 0)
        self.details_layout.addWidget(self.temp_label[1], 2, 1)
        self.details_layout.addWidget(self.wind_label[0], 3, 0)
        self.details_layout.addWidget(self.wind_label[1], 3, 1)
        self.details_layout.addWidget(self.wind_level_label[0], 4, 0)
        self.details_layout.addWidget(self.wind_level_label[1], 4, 1)
        self.details_layout.addWidget(self.humidity_label[0], 5, 0)
        self.details_layout.addWidget(self.humidity_label[1], 5, 1)
        self.details_layout.addWidget(self.air_label[0], 6, 0)
        self.details_layout.addWidget(self.air_label[1], 6, 1)
        
        # 添加详情到主布局
        self.content_layout.addWidget(self.details_widget)
        
        # 添加内容区到主布局
        self.main_layout.addWidget(self.content_widget)
        
        # 设置样式
        self._set_styles()
        
        # 调整大小
        self.adjustSize()
        
        # 设置固定宽度，防止太宽
        self.setFixedWidth(220)
    
    def _create_detail_labels(self, title, value):
        """创建详情标签对"""
        title_label = QLabel(title + ":", self.details_widget)
        title_label.setObjectName("weatherDetailTitle")
        
        value_label = QLabel(value, self.details_widget)
        value_label.setObjectName("weatherDetailValue")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        return (title_label, value_label)
    
    def _set_styles(self):
        """设置样式"""
        # 主窗口样式
        self.setStyleSheet("""
            WeatherPopup {
                background-color: transparent;
            }
            
            #weatherPopupContent {
                background-color: #1E1E1E;
                border-radius: 8px;
                border: 1px solid #333333;
            }
            
            #weatherPopupTitle {
                color: #B39DDB;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            #weatherPopupSeparator {
                background-color: #333333;
                max-height: 1px;
            }
            
            #weatherDetailTitle {
                color: #9E9E9E;
                font-size: 12px;
                padding-right: 5px;
            }
            
            #weatherDetailValue {
                color: #FFFFFF;
                font-size: 12px;
            }
        """)
    
    def update_weather_data(self, weather_data):
        """更新天气数据"""
        if not weather_data:
            return
            
        # 更新标签文本
        self.city_label[1].setText(weather_data.get('city', '--'))
        self.weather_label[1].setText(weather_data.get('weather', '--'))
        self.temp_label[1].setText(weather_data.get('temperature', '--') + "℃")
        self.wind_label[1].setText(weather_data.get('wind', '--'))
        self.wind_level_label[1].setText(weather_data.get('wind_level', '--'))
        self.humidity_label[1].setText(weather_data.get('humidity', '--'))
        self.air_label[1].setText(weather_data.get('air_quality', '--'))
        
        # 调整大小
        self.adjustSize()
    
    def show_at(self, pos):
        """在指定位置显示"""
        if self.fade_animation.state() == QPropertyAnimation.Running:
            self.fade_animation.stop()
            
        # 计算位置
        self.move(pos)
        
        # 如果还未显示，设置可见
        if not self.is_visible:
            super().show()
            self.is_visible = True
            
        # 开始淡入动画
        self.start_fade_in()
    
    def start_fade_in(self):
        """开始淡入动画"""
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
    
    def start_fade_out(self):
        """开始淡出动画"""
        self.fade_animation.setStartValue(self.opacity_effect.opacity())
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._hide_complete)
        self.fade_animation.start()
    
    def _hide_complete(self):
        """淡出完成后隐藏窗口"""
        try:
            # 断开连接，避免多次调用
            self.fade_animation.finished.disconnect(self._hide_complete)
        except:
            pass
            
        # 如果动画已经完成，并且不透明度为0，则隐藏窗口
        if self.opacity_effect.opacity() < 0.1:
            super().hide()
            self.is_visible = False
    
    def keep_visible(self):
        """保持可见状态，重置隐藏计时器"""
        # 停止任何现有的计时器
        self.hide_timer.stop()
    
    def prepare_hide(self):
        """准备隐藏，启动隐藏计时器"""
        # 开始计时器，500毫秒后隐藏
        self.hide_timer.start(500)
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self.keep_visible()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.prepare_hide()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """自定义绘制，添加阴影效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置半透明背景
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 10, 10)
        
        # 绘制背景
        painter.fillPath(path, QColor(0, 0, 0, 1))  # 几乎透明的背景
        
        # 添加简单的阴影效果
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
        shadow_color = QColor(0, 0, 0, 30)  # 半透明黑色
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.drawPath(shadow_path)
        
        super().paintEvent(event)

    def closeEvent(self, event):
        """关闭事件处理"""
        # 查找活跃下载任务
        active_downloads = [task for task in self.download_tasks if task['status'] == '下载中']
        
        if active_downloads:
            # 自动暂停所有正在下载的任务
            for task in active_downloads:
                try:
                    # 获取任务行号
                    row = task['row']
                    
                    # 更新任务状态为已暂停
                    task['status'] = '已暂停'
                    
                    # 暂停下载而不是停止
                    if task.get('manager'):
                        task['manager'].stop()  # 目前使用stop方法暂停，保留任务信息
                    
                    # 更新UI显示
                    with self.thread_lock:
                        self.task_window.update_status(row, "已暂停")
                    
                    logging.info(f"自动暂停任务: {row}")
                except Exception as e:
                    logging.error(f"自动暂停任务失败: {e}")
            
            # 显示提示信息
            logging.info(f"已自动暂停{len(active_downloads)}个下载任务并准备退出")
            
            # 可选：显示通知
            QMessageBox.information(
                self,
                "下载已暂停",
                f"已自动暂停{len(active_downloads)}个正在进行的下载任务。下次启动应用时可以恢复这些任务。",
                QMessageBox.Ok
            )
        
        # 关闭所有可能的弹窗
        try:
            for widget in QApplication.topLevelWidgets():
                if widget != self and widget.isVisible() and isinstance(widget, QDialog):
                    logging.info(f"关闭子对话框: {widget.__class__.__name__}")
                    widget.close()
        except Exception as e:
            logging.error(f"关闭子对话框失败: {e}")
        
        # 释放下载处理器资源
        if hasattr(self, 'download_handler') and self.download_handler:
            try:
                # 断开信号连接
                if hasattr(self.download_handler, 'downloadCompleted'):
                    try:
                        self.download_handler.downloadCompleted.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                
                # 使用弱引用避免循环引用
                import weakref
                handler_ref = weakref.ref(self.download_handler)
                self.download_handler = None
                
                # 强制清理
                import gc
                gc.collect()
                
                logging.info("已安全释放下载处理器资源")
            except Exception as e:
                logging.error(f"释放下载处理器资源失败: {e}")
        
        # 停止浏览器下载监听器
        if hasattr(self, 'connector') and self.connector:
            try:
                self.connector.stop()
                logging.info("已停止浏览器下载监听器")
            except Exception as e:
                logging.error(f"停止浏览器下载监听器失败: {e}")
        
        # 停止定时器
        if hasattr(self, 'ws_refresh_timer') and self.ws_refresh_timer:
            self.ws_refresh_timer.stop()
        
        # 保存配置
        if hasattr(self, 'config_manager'):
            self.config_manager.save_config()
        
        # 保存下载任务的状态，以便下次启动时恢复
        self.save_application_state()
        
        # 停止天气获取线程
        if hasattr(self, 'weather_thread') and self.weather_thread and self.weather_thread.isRunning():
            try:
                self.weather_thread.stop()
                self.weather_thread.wait(1000)  # 最多等待1秒
                logging.info("已停止天气获取线程")
            except Exception as e:
                logging.error(f"停止天气获取线程失败: {e}")
        
        # 关闭天气悬浮窗
        if hasattr(self, 'weather_popup') and self.weather_popup:
            self.weather_popup.close()
        
        logging.info("应用程序正常关闭")
        super().closeEvent(event)