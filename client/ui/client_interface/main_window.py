from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLineEdit, QTableWidget, 
                              QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
                              QSplitter, QFrame, QLabel, QSizePolicy, QStackedWidget, QScrollArea, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPainterPath, QBrush, QMouseEvent, QFontDatabase

from client.ui.components.progressBar import ProgressBar
from client.ui.title_styles.titleStyles import TitleBar
from core.download_core.download_kernel import TransferManager
from core.font.font_manager import FontManager
from client.ui.client_interface.about_window import AboutWindow
from client.ui.client_interface.settings.settings_page import SettingsPage
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.download_log_dialog import DownloadLogDialog
from client.ui.components.update_log_dialog import UpdateLogDialog
from core.update.update_log_manager import UpdateLogManager


import os
import threading

# 字体管理器已经在font_manager.py中自行加载，此处不需要重复加载
# def load_material_icons():
#     font_id = QFontDatabase.addApplicationFont("core/font/font/MaterialIcons-Regular.ttf")
#     if font_id != -1:
#         font_families = QFontDatabase.applicationFontFamilies(font_id)
#         if font_families:
#             return True
#     return False

class RoundedWidget(QWidget):
    def __init__(self, parent=None, radius=10, bg_color="#2C2C2C", corners="all"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.corners = corners  # 可以是 "all", "left", "right", "top", "bottom", "top-left", "bottom-left" 等
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
        
class CategoryButton(QPushButton):
    def __init__(self, text, parent=None, icon_code=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.icon_code = icon_code
        self.text_content = text
        
        # 使用布局来放置图标和文本
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(10)
        
        # 创建图标标签
        if icon_code:
            self.icon_label = QLabel()
            self.font_manager = FontManager()
            
            # 直接创建并设置字体，确保是Material Icons
            icon_font = QFont("Material Icons")  # 使用确切的字体名称
            icon_font.setPixelSize(16)
            self.icon_label.setFont(icon_font)
            
            # 使用Unicode值直接设置图标
            icon_text = self.font_manager.get_icon_text(icon_code)
            if not icon_text:
                # 如果图标代码无效，显示一个通用图标
                icon_text = "\ue5d4"  # info_outline 图标
                
            self.icon_label.setText(icon_text)
            self.layout.addWidget(self.icon_label)
        
        # 创建文本标签
        self.text_label = QLabel(text)
        self.layout.addWidget(self.text_label)
        self.layout.addStretch()
        
        # 设置基本样式
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 15px;
                padding: 5px 0px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:checked {
                background-color: rgba(179, 157, 219, 0.2);
            }
        """)
        
        # 单独设置标签样式
        self.updateStyle(self.isChecked())
    
    def setChecked(self, checked):
        super().setChecked(checked)
        self.updateStyle(checked)
    
    def updateStyle(self, checked):
        if checked:
            if hasattr(self, 'icon_label'):
                self.icon_label.setStyleSheet("color: #B39DDB; background-color: transparent; font-weight: bold;")
            self.text_label.setStyleSheet("color: #B39DDB; background-color: transparent; font-weight: bold; font-size: 14px;")
        else:
            if hasattr(self, 'icon_label'):
                self.icon_label.setStyleSheet("color: #9E9E9E; background-color: transparent; font-size: 14px;")
            self.text_label.setStyleSheet("color: #9E9E9E; background-color: transparent; font-size: 14px;")
            
        # 鼠标悬停状态由QPushButton的样式表处理

class DownloadManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化更新日志管理器
        self.update_log_manager = UpdateLogManager()
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 初始化配置管理器
        from client.ui.client_interface.settings.config import config
        self.config_manager = config
        
        # 设置窗口基本属性
        self.setWindowTitle("Hanabi Download Manager")
        self.resize(1050, 650)
        
        # 属性
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置应用深色主题 - 注意这里不要设置主窗口背景色，由paintEvent处理
        self.setStyleSheet("""
            QWidget {
                color: #FFFFFF;
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
            }
            QLabel, QPushButton, QLineEdit, QTableWidget, QHeaderView {
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
            }
            QTableWidget::item {
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei"; 
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
        main_layout.addWidget(self.title_bar)
        
        # 内容区布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)  # 去掉顶部间距
        content_layout.setSpacing(12)  # 增加侧边栏和内容区之间的间距
        
        # 创建左侧导航栏 - 使用RoundedWidget实现左侧圆角
        self.sidebar = RoundedWidget(radius=25, bg_color="#1E1E1E", corners="left")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 25)
        sidebar_layout.setSpacing(20)
        
        # 品牌Logo和标题
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(5)
        
        # 使用真实logo
        logo_label = QLabel()
        try:
            logo_pixmap = QIcon("resources/logo2.png").pixmap(QSize(180, 40))
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignLeft)
        except:
            # 如果加载失败，使用文本
            brand_label = QLabel("Hanabi")
            brand_label.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: bold; background-color: transparent;")
            self.font_manager.apply_font(brand_label)
            logo_layout.addWidget(brand_label)
        
        logo_layout.addWidget(logo_label)
        
        slogan_label = QLabel("高效、优雅的多线程下载管理器")
        slogan_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.font_manager.apply_font(slogan_label)
        logo_layout.addWidget(slogan_label)
        
        year_label = QLabel("2025")
        year_label.setStyleSheet("color: #9E9E9E; font-size: 12px; margin-top: 5px; background-color: transparent;")
        self.font_manager.apply_font(year_label)
        logo_layout.addWidget(year_label)
        
        sidebar_layout.addLayout(logo_layout)
        sidebar_layout.addSpacing(25)
        
        # 导航按钮
        self.nav_buttons_layout = QVBoxLayout()
        self.nav_buttons_layout.setSpacing(8)
        
        # 使用Material Icons字体图标 - 使用名称而不是直接使用图标码
        self.downloads_btn = CategoryButton("下载", icon_code="download")
        self.downloads_btn.setChecked(True)
        self.downloads_btn.clicked.connect(lambda: self.switch_page(0))  # 0表示下载页
        self.nav_buttons_layout.addWidget(self.downloads_btn)
        
        self.finished_btn = CategoryButton("已完成", icon_code="done_all")
        self.finished_btn.clicked.connect(lambda: self.switch_page(1))  # 1表示已完成页
        self.nav_buttons_layout.addWidget(self.finished_btn)
        
        self.settings_btn = CategoryButton("设置", icon_code="settings")
        self.settings_btn.clicked.connect(self.open_settings)  # 调用open_settings方法
        self.nav_buttons_layout.addWidget(self.settings_btn)
        
        self.about_btn = CategoryButton("关于", icon_code="info")
        self.about_btn.clicked.connect(lambda: self.switch_page(3))  # 3表示关于页
        self.nav_buttons_layout.addWidget(self.about_btn)
        
        sidebar_layout.addLayout(self.nav_buttons_layout)
        sidebar_layout.addStretch(1)
        
        # 下载类型过滤器
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(10)
        
        filter_title = QLabel("下载类型")
        filter_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(filter_title)
        filter_layout.addWidget(filter_title)
        
        # 下载类型按钮组
        self.filter_buttons_layout = QHBoxLayout()
        self.filter_buttons_layout.setSpacing(8)
        
        # 辅助函数：创建带有图标的过滤按钮
        def create_filter_button(text, icon_code):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setMinimumWidth(60)
            
            # 使用布局来放置图标和文本
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(10, 5, 10, 5)
            btn_layout.setSpacing(5)
            
            # 创建图标标签
            icon_label = QLabel()
            
            # 直接创建并设置字体，确保是Material Icons
            icon_font = QFont("Material Icons")
            icon_font.setPixelSize(14)
            icon_label.setFont(icon_font)
            
            # 使用Unicode值直接设置图标
            icon_text = self.font_manager.get_icon_text(icon_code)
            if not icon_text:
                # 如果图标代码无效，显示一个通用图标
                icon_text = "\ue5d4"  # info_outline 图标
            
            icon_label.setText(icon_text)
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            btn_layout.addWidget(text_label)
            
            # 设置基本按钮样式
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 0px;
                }
                QPushButton:checked {
                    background-color: rgba(179, 157, 219, 0.2);
                }
            """)
            
            # 更新标签样式函数
            def update_style(checked):
                if checked:
                    icon_label.setStyleSheet("color: #B39DDB; background-color: transparent;")
                    text_label.setStyleSheet("color: #B39DDB; background-color: transparent;")
                else:
                    icon_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
                    text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            
            # 连接按钮状态变化信号
            btn.toggled.connect(update_style)
            
            # 初始化样式
            update_style(btn.isChecked())
            
            return btn
        
        # 创建过滤按钮
        self.all_filter_btn = create_filter_button("全部", "apps")
        self.all_filter_btn.setChecked(True)
        self.filter_buttons_layout.addWidget(self.all_filter_btn)
        
        self.video_filter_btn = create_filter_button("视频", "movie")
        self.filter_buttons_layout.addWidget(self.video_filter_btn)
        
        self.audio_filter_btn = create_filter_button("音频", "music_note")
        self.filter_buttons_layout.addWidget(self.audio_filter_btn)
        
        filter_layout.addLayout(self.filter_buttons_layout)
        
        sidebar_layout.addLayout(filter_layout)
        
        # 添加左侧导航栏到内容布局
        content_layout.addWidget(self.sidebar)
        
        # 右侧内容区域
        self.content_area = RoundedWidget(radius=20, bg_color="#1E1E1E", corners="all")
        
        # 创建一个堆栈窗口用于切换不同页面
        self.stacked_widget = QStackedWidget()
        content_area_layout = QVBoxLayout(self.content_area)
        content_area_layout.setContentsMargins(10, 10, 10, 10)
        content_area_layout.addWidget(self.stacked_widget)
        
        # 下载页面
        self.download_page = QWidget()
        
        # 创建滚动区域
        download_scroll = QScrollArea()
        download_scroll.setWidgetResizable(True)
        download_scroll.setFrameShape(QScrollArea.NoFrame)
        download_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        download_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(download_scroll, "dark")
        
        # 创建内容容器
        download_content = QWidget()
        download_page_layout = QVBoxLayout(download_content)
        download_page_layout.setContentsMargins(15, 15, 15, 15)
        download_page_layout.setSpacing(20)
        
        # 设置滚动区域的内容
        download_scroll.setWidget(download_content)
        
        # 将滚动区域添加到下载页面
        download_layout = QVBoxLayout(self.download_page)
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.addWidget(download_scroll)
        
        # 顶部URL输入和按钮区域
        top_card = RoundedWidget(radius=15)
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
        
        # 按钮样式
        button_style = """
            QPushButton {
                background-color: #B39DDB;
                color: #121212;
                border: none;
                border-radius: 8px;
                padding: 5px 15px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
            QPushButton:pressed {
                background-color: #7E57C2;
            }
        """
        
        # 下载按钮
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setMinimumWidth(100)
        # 设置尺寸策略为水平扩展
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setSizePolicy(size_policy)
        self.download_btn.setStyleSheet(button_style)
        
        # 使用布局方式设置图标和文本
        download_btn_layout = QHBoxLayout(self.download_btn)
        download_btn_layout.setContentsMargins(15, 0, 15, 0)
        download_btn_layout.setSpacing(8)
        
        # 创建图标标签
        download_icon = QLabel()
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(16)
        download_icon.setFont(icon_font)
        
        # 设置下载图标
        download_icon.setText(self.font_manager.get_icon_text("download"))
        download_icon.setStyleSheet("color: #121212; background-color: transparent;")
        download_btn_layout.addWidget(download_icon)
        
        # 创建文本标签
        download_text = QLabel("下载")
        download_text.setStyleSheet("color: #121212; background-color: transparent; font-weight: bold;")
        download_btn_layout.addWidget(download_text)
        
        self.download_btn.clicked.connect(self.start_download)
        url_input_layout.addWidget(self.download_btn, 2)
        
        # 选择保存路径按钮
        self.path_btn = QPushButton()
        self.path_btn.setMinimumHeight(45)
        self.path_btn.setMinimumWidth(150)  # 再次增加最小宽度
        # 设置尺寸策略为水平扩展
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.path_btn.setSizePolicy(size_policy)
        self.path_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 5px;  /* 减小内边距 */
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
        path_btn_layout.setContentsMargins(10, 0, 10, 0)  # 减小内边距
        path_btn_layout.setSpacing(5)  # 减小间距
        
        # 创建图标标签
        folder_icon = QLabel()
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(16)
        folder_icon.setFont(icon_font)
        
        # 设置文件夹图标
        folder_icon.setText(self.font_manager.get_icon_text("folder"))
        folder_icon.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_btn_layout.addWidget(folder_icon)
        
        # 创建文本标签
        path_text = QLabel("保存位置")
        path_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        # 设置文本标签为固定尺寸
        path_text.setMinimumWidth(70)
        path_text.setAlignment(Qt.AlignCenter)
        path_btn_layout.addWidget(path_text)
        
        self.path_btn.clicked.connect(self.select_save_path)
        url_input_layout.addWidget(self.path_btn, 3)
        
        top_card_layout.addLayout(url_input_layout)
        
        # 当前保存路径
        self.save_path = os.path.expanduser("~/Downloads")
        
        # 添加顶部区域到内容布局
        download_page_layout.addWidget(top_card)
        
        # 下载列表区域
        download_list_card = RoundedWidget(radius=15)
        download_list_layout = QVBoxLayout(download_list_card)
        download_list_layout.setContentsMargins(20, 20, 20, 20)
        download_list_layout.setSpacing(15)
        
        # 下载列表标题 - 居中
        download_title = QLabel("下载列表")
        download_title.setAlignment(Qt.AlignCenter)
        download_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(download_title)
        download_list_layout.addWidget(download_title)
        
        # 控制按钮布局
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        control_button_style = """
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 3px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """
        
        # 创建带图标按钮的辅助函数
        def create_control_button(text, icon_code):
            btn = QPushButton()
            btn.setStyleSheet(control_button_style)
            
            # 使用布局方式设置图标和文本
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(8, 0, 8, 0)
            btn_layout.setSpacing(5)
            
            # 创建图标标签
            icon_label = QLabel()
            icon_font = QFont("Material Icons")
            icon_font.setPixelSize(14)
            icon_label.setFont(icon_font)
            
            # 设置图标
            icon_label.setText(self.font_manager.get_icon_text(icon_code))
            icon_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(text_label)
            
            return btn
        
        # 暂停按钮
        self.pause_btn = create_control_button("暂停", "pause")
        self.pause_btn.clicked.connect(self.pause_download)
        
        # 恢复按钮
        self.resume_btn = create_control_button("恢复", "play_arrow")
        self.resume_btn.clicked.connect(self.resume_download)
        
        # 取消按钮
        self.cancel_btn = create_control_button("取消", "close")
        self.cancel_btn.clicked.connect(self.cancel_download)
        
        # 按钮居中布局
        control_layout.addStretch(1)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addWidget(self.cancel_btn)
        control_layout.addStretch(1)
        
        download_list_layout.addLayout(control_layout)
        
        # 创建下载任务表格
        self.download_table = QTableWidget(0, 6)  # 0行，6列，增加一列用于操作按钮
        self.download_table.setHorizontalHeaderLabels(["文件名", "大小", "进度", "速度", "状态", "操作"])
        self.download_table.setShowGrid(False)
        self.download_table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: none;
                color: #FFFFFF;
                gridline-color: transparent;
            }
            QTableWidget::item {
                padding: 10px 5px;
                border-bottom: 1px solid #333333;
            }
            QHeaderView::section {
                background-color: transparent;
                color: #9E9E9E;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.font_manager.apply_font(self.download_table)
        
        # 设置表格列宽
        header = self.download_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 文件名列自适应宽度
        self.download_table.setColumnWidth(1, 100)  # 大小列固定宽度
        self.download_table.setColumnWidth(2, 200)  # 进度列固定宽度
        self.download_table.setColumnWidth(3, 100)  # 速度列固定宽度
        self.download_table.setColumnWidth(4, 100)  # 状态列固定宽度
        self.download_table.setColumnWidth(5, 100)  # 操作列固定宽度
        
        # 表格行高
        self.download_table.verticalHeader().setDefaultSectionSize(60)
        self.download_table.verticalHeader().setVisible(False)  # 隐藏行号
        
        # 添加表格到下载列表区域
        download_list_layout.addWidget(self.download_table)
        
        # 添加下载列表区域到内容布局
        download_page_layout.addWidget(download_list_card, 1)
        
        # 将下载页面添加到堆栈窗口
        self.stacked_widget.addWidget(self.download_page)
        
        # 已完成页面 - 暂时为空页面
        self.finished_page = QWidget()
        
        # 创建滚动区域
        finished_scroll = QScrollArea()
        finished_scroll.setWidgetResizable(True)
        finished_scroll.setFrameShape(QScrollArea.NoFrame)
        finished_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        finished_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(finished_scroll, "dark")
        
        # 创建内容容器
        finished_content = QWidget()
        finished_layout = QVBoxLayout(finished_content)
        finished_layout.setContentsMargins(15, 15, 15, 15)
        
        finished_label = QLabel("已完成的下载任务将显示在这里")
        finished_label.setAlignment(Qt.AlignCenter)
        finished_layout.addWidget(finished_label)
        
        # 设置滚动区域的内容
        finished_scroll.setWidget(finished_content)
        
        # 将滚动区域添加到页面
        finished_page_layout = QVBoxLayout(self.finished_page)
        finished_page_layout.setContentsMargins(0, 0, 0, 0)
        finished_page_layout.addWidget(finished_scroll)
        
        self.stacked_widget.addWidget(self.finished_page)
        
        # 设置页面
        self.settings_page = SettingsPage(self.config_manager, self)
        # 连接设置页面消息信号
        self.settings_page.settingsMessage.connect(self.handle_settings_message)
        
        self.stacked_widget.addWidget(self.settings_page)
        
        # 关于页面
        self.about_page = AboutWindow()
        self.stacked_widget.addWidget(self.about_page)
        
        # 添加内容布局到主布局
        content_layout.addWidget(self.content_area, 1)
        
        # 添加内容布局到主布局
        main_layout.addLayout(content_layout, 1)
    
    def select_save_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.save_path = folder_path
            QMessageBox.information(self, "保存位置", f"已选择保存位置: {self.save_path}")
    
    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入下载链接")
            return
        
        # 从配置管理器获取线程数和最大线程数
        thread_count = self.config_manager.get_download_thread_count()
        dynamic_threads = self.config_manager.get_dynamic_threads()
        
        # 打印调试信息
        print(f"[DEBUG] 开始下载 - 从配置获取 线程数: {thread_count}, 动态线程: {dynamic_threads}")
        
        # 创建新的下载任务行
        row_position = self.download_table.rowCount()
        self.download_table.insertRow(row_position)
        
        # 设置初始显示状态
        filename_item = QTableWidgetItem("准备中...")
        filename_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        size_item = QTableWidgetItem("获取中...")
        size_item.setTextAlignment(Qt.AlignCenter)
        
        # 创建进度条
        progress_bar = ProgressBar()
        # 应用字体管理器到进度条
        self.font_manager.apply_font(progress_bar)
        progress_bar.setFixedHeight(15)  # 增加高度使分段更明显
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #2D2D30;
                border-radius: 5px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #B39DDB;
                border-radius: 5px;
            }
        """)
        progress_bar.setProgress(0)
        
        speed_item = QTableWidgetItem("0 KB/s")
        speed_item.setTextAlignment(Qt.AlignCenter)
        status_item = QTableWidgetItem("初始化")
        status_item.setTextAlignment(Qt.AlignCenter)
        
        # 创建操作按钮单元格
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(5, 2, 5, 2)
        action_layout.setSpacing(5)
        
        # 日志按钮
        log_btn = QPushButton()
        log_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 3px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        
        # 使用Material Icons
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(14)
        log_btn.setFont(icon_font)
        log_btn.setText(self.font_manager.get_icon_text("list_alt"))  # 使用列表图标表示日志
        log_btn.setToolTip("查看下载日志")
        
        # 存储行号作为属性
        log_btn.setProperty("row", row_position)
        log_btn.clicked.connect(self.show_download_log)
        
        action_layout.addWidget(log_btn)
        action_layout.addStretch()
        
        # 添加组件到表格
        self.download_table.setItem(row_position, 0, filename_item)
        self.download_table.setItem(row_position, 1, size_item)
        self.download_table.setCellWidget(row_position, 2, progress_bar)
        self.download_table.setItem(row_position, 3, speed_item)
        self.download_table.setItem(row_position, 4, status_item)
        self.download_table.setCellWidget(row_position, 5, action_widget)
        
        # 创建下载线程
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        
        # 创建下载管理器
        transfer_manager = TransferManager(
            url=url,
            headers=headers,
            maxThreads=thread_count,
            savePath=self.save_path,
            filename=self.download_table.item(row_position, 0).text() if self.download_table.item(row_position, 0).text() != "准备中..." else None,
            dynamicThreads=dynamic_threads
        )
        
        # 连接信号
        transfer_manager.initComplete.connect(lambda supports_multi_threading: 
                                              self.update_file_size(row_position, transfer_manager.fileSize))
        transfer_manager.segmentProgressChanged.connect(lambda progress: self.update_progress(row_position, progress))
        transfer_manager.transferSpeedChanged.connect(lambda speed: self.update_speed(row_position, speed))
        transfer_manager.downloadComplete.connect(lambda: self.download_completed(row_position))
        transfer_manager.errorOccurred.connect(lambda error: self.download_error(row_position, error))
        
        # 保存下载管理器对象
        download_task = {
            'manager': transfer_manager,
            'row': row_position,
            'status': 'running'
        }
        self.download_tasks.append(download_task)
        
        # 启动下载
        transfer_manager.start()
    
    def update_file_size(self, row, size):
        size_text = self.get_readable_size(size)
        self.download_table.item(row, 1).setText(size_text)
        self.download_table.item(row, 1).setTextAlignment(Qt.AlignCenter)
    
    def update_progress(self, row, progress_data):
        try:
            progress_bar = self.download_table.cellWidget(row, 2)
            if not progress_bar:
                return
                
            # 获取任务对应的下载管理器，以获取文件大小
            file_size = 0
            for task in self.download_tasks:
                if task['row'] == row:
                    file_size = task['manager'].fileSize
                    # 文件名更新
                    if self.download_table.item(row, 0).text() == "准备中...":
                        filename = task['manager'].filename
                        if filename:
                            self.download_table.item(row, 0).setText(filename)
                    break
            
            # 不支持多线程时收到的是空列表
            if not progress_data:
                # 尝试直接从下载管理器获取进度
                for task in self.download_tasks:
                    if task['row'] == row:
                        manager = task['manager']
                        if hasattr(manager, 'progress') and hasattr(manager, 'fileSize') and manager.fileSize > 0:
                            percentage = int((manager.progress / manager.fileSize) * 100)
                            progress_bar.setProgress(percentage)
                            
                            # 更新状态显示
                            if percentage < 100:
                                status_item = self.download_table.item(row, 4)
                                status_item.setText(f"下载中: {percentage}%")
                                status_item.setTextAlignment(Qt.AlignCenter)
                        break
                return
                
            # 使用进度条的分段功能显示下载进度
            if file_size > 0:
                progress_bar.updateFromDownloadSegments(progress_data, file_size)
                
                # 计算总进度百分比
                total_progress = 0
                if isinstance(progress_data[0], dict):
                    total_size = sum([segment.get('endPos', 0) - segment.get('startPos', 0) for segment in progress_data])
                    current_progress = sum([segment.get('progress', 0) - segment.get('startPos', 0) for segment in progress_data])
                    if total_size > 0:
                        total_progress = int((current_progress / total_size) * 100)
                elif isinstance(progress_data[0], (list, tuple)) and len(progress_data[0]) >= 3:
                    total_size = sum([segment[2] - segment[0] for segment in progress_data])
                    current_progress = sum([segment[1] - segment[0] for segment in progress_data])
                    if total_size > 0:
                        total_progress = int((current_progress / total_size) * 100)
                
                # 更新状态显示
                if total_progress < 100:
                    status_item = self.download_table.item(row, 4)
                    status_item.setText(f"下载中: {total_progress}%")
                    status_item.setTextAlignment(Qt.AlignCenter)
                
        except Exception as e:
            print(f"更新进度时出错: {e}")
    
    def update_speed(self, row, speed_bytes):
        speed_text = self.get_readable_size(speed_bytes) + "/s"
        self.download_table.item(row, 3).setText(speed_text)
        self.download_table.item(row, 3).setTextAlignment(Qt.AlignCenter)
    
    def download_completed(self, row):
        status_item = self.download_table.item(row, 4)
        status_item.setText("已完成")
        status_item.setTextAlignment(Qt.AlignCenter)
        
        progress_bar = self.download_table.cellWidget(row, 2)
        if progress_bar:
            # 保留分段显示，但确保总进度为100%
            progress_bar.setProgress(100)
            
            # 使用IDM风格的完成效果 - 绿色块
            try:
                # 创建完整的分段 - 使用IDM风格的绿色
                progress_bar.setShowSegments(True)
                
                # 创建单个完整分段，使用IDM风格的绿色
                segments = [(0, 100, "#1FB15F")]  # IDM风格的绿色
                progress_bar.setSegments(segments)
            except:
                # 如果出错，至少确保进度显示为100%
                progress_bar.setProgress(100)
        
        # 更新任务状态
        for task in self.download_tasks:
            if task['row'] == row:
                task['status'] = 'completed'
                break
    
    def download_error(self, row, error):
        status_item = self.download_table.item(row, 4)
        status_item.setText(f"错误: {error}")
        status_item.setTextAlignment(Qt.AlignCenter)
        
        # 更新任务状态
        for task in self.download_tasks:
            if task['row'] == row:
                task['status'] = 'error'
                break
    
    def pause_download(self):
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            for task in self.download_tasks:
                if task['row'] == row and task['status'] == 'running':
                    task['manager'].stop()
                    task['status'] = 'paused'
                    status_item = self.download_table.item(row, 4)
                    status_item.setText("已暂停")
                    status_item.setTextAlignment(Qt.AlignCenter)
    
    def resume_download(self):
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            for task in self.download_tasks:
                if task['row'] == row and task['status'] == 'paused':
                    # 需要重新创建下载任务，TransferManager不支持恢复
                    # 这里只是界面示例，实际功能需要在下载核心支持恢复功能
                    status_item = self.download_table.item(row, 4)
                    status_item.setText("已恢复")
                    status_item.setTextAlignment(Qt.AlignCenter)
                    task['status'] = 'running'
    
    def cancel_download(self):
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            for task in self.download_tasks:
                if task['row'] == row:
                    task['manager'].stop()
                    task['status'] = 'canceled'
                    status_item = self.download_table.item(row, 4)
                    status_item.setText("已取消")
                    status_item.setTextAlignment(Qt.AlignCenter)
    
    def get_selected_rows(self):
        indexes = self.download_table.selectedIndexes()
        rows = set()
        for index in indexes:
            rows.add(index.row())
        return list(rows)
    
    @staticmethod
    def get_readable_size(size_in_bytes):
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_in_bytes >= 1024 and i < len(size_names) - 1:
            size_in_bytes /= 1024
            i += 1
        return f"{size_in_bytes:.2f} {size_names[i]}"
        
    def add_download_from_extension(self, download_data):
        url = download_data.get('url')
        if not url:
            return
            
        # 创建新的下载任务行
        row_position = self.download_table.rowCount()
        self.download_table.insertRow(row_position)
        
        # 设置初始显示状态
        filename = download_data.get('filename', "准备中...")
        filename_item = QTableWidgetItem(filename)
        filename_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        size_item = QTableWidgetItem("获取中...")
        size_item.setTextAlignment(Qt.AlignCenter)
        
        # 创建进度条
        progress_bar = ProgressBar()
        # 应用字体管理器到进度条
        self.font_manager.apply_font(progress_bar)
        progress_bar.setFixedHeight(15)  # 增加高度使分段更明显
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #2D2D30;
                border-radius: 5px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #B39DDB;
                border-radius: 5px;
            }
        """)
        progress_bar.setProgress(0)
        
        speed_item = QTableWidgetItem("0 KB/s")
        speed_item.setTextAlignment(Qt.AlignCenter)
        status_item = QTableWidgetItem("初始化")
        status_item.setTextAlignment(Qt.AlignCenter)
        
        # 创建操作按钮单元格
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(5, 2, 5, 2)
        action_layout.setSpacing(5)
        
        # 日志按钮
        log_btn = QPushButton()
        log_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 3px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        
        # 使用Material Icons
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(14)
        log_btn.setFont(icon_font)
        log_btn.setText(self.font_manager.get_icon_text("list_alt"))  # 使用列表图标表示日志
        log_btn.setToolTip("查看下载日志")
        
        # 存储行号作为属性
        log_btn.setProperty("row", row_position)
        log_btn.clicked.connect(self.show_download_log)
        
        action_layout.addWidget(log_btn)
        action_layout.addStretch()
        
        # 添加组件到表格
        self.download_table.setItem(row_position, 0, filename_item)
        self.download_table.setItem(row_position, 1, size_item)
        self.download_table.setCellWidget(row_position, 2, progress_bar)
        self.download_table.setItem(row_position, 3, speed_item)
        self.download_table.setItem(row_position, 4, status_item)
        self.download_table.setCellWidget(row_position, 5, action_widget)
        
        # 从请求中提取HTTP头信息
        headers = download_data.get('headers', {})
        if not headers:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            
        # 创建下载管理器
        transfer_manager = TransferManager(
            url=url,
            headers=headers,
            maxThreads=self.config_manager.get_download_thread_count(),
            savePath=self.save_path,
            filename=filename if filename != "准备中..." else None,
            dynamicThreads=self.config_manager.get_dynamic_threads()
        )
        
        # 连接信号
        transfer_manager.initComplete.connect(lambda supports_multi_threading: 
                                              self.update_file_size(row_position, transfer_manager.fileSize))
        transfer_manager.segmentProgressChanged.connect(lambda progress: self.update_progress(row_position, progress))
        transfer_manager.transferSpeedChanged.connect(lambda speed: self.update_speed(row_position, speed))
        transfer_manager.downloadComplete.connect(lambda: self.download_completed(row_position))
        transfer_manager.errorOccurred.connect(lambda error: self.download_error(row_position, error))
        
        # 保存下载管理器对象
        download_task = {
            'manager': transfer_manager,
            'row': row_position,
            'status': 'running'
        }
        self.download_tasks.append(download_task)
        
        # 启动下载
        transfer_manager.start()

    def switch_page(self, index):
        # 更新按钮状态
        self.downloads_btn.setChecked(index == 0)
        self.finished_btn.setChecked(index == 1)
        self.settings_btn.setChecked(index == 2)
        self.about_btn.setChecked(index == 3)
        
        # 切换堆栈窗口到指定页面
        self.stacked_widget.setCurrentIndex(index)

    def show_download_log(self):
        # 获取发送信号的按钮
        sender = self.sender()
        if not sender or not hasattr(sender, 'property'):
            return
            
        # 获取行号
        row = sender.property("row")
        if row is None:
            return
            
        # 查找对应的下载任务
        download_info = None
        for task in self.download_tasks:
            if task['row'] == row:
                download_info = task
                break
                
        if download_info:
            # 创建并显示日志对话框
            log_dialog = DownloadLogDialog(self, download_info)
            log_dialog.exec()

    def open_settings(self):
        self.switch_page(2)  # 切换到设置页面（索引2）

    def handle_settings_message(self, success, message):
        if success:
            QMessageBox.information(self, "设置", message)
        else:
            QMessageBox.warning(self, "设置错误", message)

    def get_download_progress(self, row):
        if row < 0 or row >= self.download_table.rowCount():
            return 0
        progress_item = self.download_table.item(row, 2)
        if progress_item:
            progress_text = progress_item.text().strip('%')
            return int(progress_text) if progress_text else 0
        return 0
        
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
        