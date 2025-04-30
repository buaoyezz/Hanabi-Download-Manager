from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QDialog, QFrame
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QThread
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QBrush, QColor
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.customNotify import NotifyManager
from core.update.update_log_manager import UpdateLogManager
from client.ui.components.update_log_dialog import UpdateLogDialog
import webbrowser
import time

class UpdateCheckThread(QThread):
    update_found = Signal()
    no_update = Signal()
    error = Signal(str)
    
    def run(self):
        try:
            # 模拟检查更新过程
            time.sleep(2)
            # 这里添加实际的更新检查逻辑
            self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))

class RoundedContainer(QWidget):
    def __init__(self, parent=None, radius=15, bg_color="#2C2C2C"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect, self.radius, self.radius)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)

class AboutWindow(QWidget):
    # 添加信号用于状态同步
    update_status_changed = Signal(str, str)  # (status_text, status_color)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 初始化更新日志管理器
        self.update_log_manager = UpdateLogManager()
        
        # 初始化更新检查线程
        self.update_thread = None
        
        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 连接状态更新信号
        self.update_status_changed.connect(self.update_status_display)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 应用自定义滚动条样式
        ScrollStyle.apply_to_widget(scroll_area, "dark")
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)
        
        # 关于卡片
        about_card = RoundedContainer(radius=20, bg_color="#252525")
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(30, 30, 30, 30)
        about_layout.setSpacing(25)
        
        # Logo和标题部分
        header_layout = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        try:
            pixmap = QPixmap("resources/logo2.png")
            scaled_pixmap = pixmap.scaled(QSize(160, 40), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        except:
            logo_label = QLabel("Hanabi")
            logo_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #B39DDB;")
            self.font_manager.apply_font(logo_label)
            
        header_layout.addWidget(logo_label)
        header_layout.addStretch(1)
        
        # 版本信息
        version_label = QLabel("版本 1.0.1 Release")
        version_label.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        self.font_manager.apply_font(version_label)
        header_layout.addWidget(version_label)
        
        about_layout.addLayout(header_layout)
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        about_layout.addWidget(separator)
        
        # 软件描述
        desc_label = QLabel("Hanabi Download Manager 使用部分ClutUI NG[PySide6]的组件,在原始上进行创新和自研的Download Manager，搭配自研Hanabi Downlaod Core，提供更高效的下载体验")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #FFFFFF; font-size: 14px; line-height: 1.5;")
        self.font_manager.apply_font(desc_label)
        about_layout.addWidget(desc_label)
        
        # 特性列表
        features_label = QLabel("主要特性:")
        features_label.setStyleSheet("color: #B39DDB; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(features_label)
        about_layout.addWidget(features_label)
        
        features_content = QLabel(
            "• 多线程下载加速\n"
            "• 自动调整线程数量\n"
            "• 断点续传功能\n"
            "• 浏览器扩展集成\n"
            "• 现代化界面设计\n"
            "• 下载任务管理"
        )
        features_content.setStyleSheet("color: #E0E0E0; font-size: 14px; line-height: 1.6;")
        self.font_manager.apply_font(features_content)
        about_layout.addWidget(features_content)
        
        # 另一个分隔线
        separator2 = QWidget()
        separator2.setFixedHeight(1)
        separator2.setStyleSheet("background-color: #3C3C3C;")
        about_layout.addWidget(separator2)
        
        # 开发者信息
        dev_label = QLabel("开发者 Developer")
        dev_label.setStyleSheet("color: #B39DDB; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(dev_label)
        about_layout.addWidget(dev_label)
        
        dev_content = QLabel("本软件ZZBuAoYe开发,感谢使用")
        dev_content.setWordWrap(True)
        dev_content.setStyleSheet("color: #E0E0E0; font-size: 14px;")
        self.font_manager.apply_font(dev_content)
        about_layout.addWidget(dev_content)
        
        # 版权信息
        copyright_label = QLabel("© 2025 ZZBuAoYe - 保留所有权利")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.font_manager.apply_font(copyright_label)
        about_layout.addWidget(copyright_label)
        
        # 相关链接
        links_layout = QHBoxLayout()
        links_layout.setSpacing(15)
        
        # 检查更新日志按钮
        check_update_btn = QPushButton("检查更新日志")
        check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.font_manager.apply_font(check_update_btn)
        check_update_btn.clicked.connect(self.check_update_logs)
        links_layout.addWidget(check_update_btn)
        
        github_btn = QPushButton("GitHub Home")
        github_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.font_manager.apply_font(github_btn)
        links_layout.addWidget(github_btn)
        # 先打开网页，再显示通知
        github_btn.clicked.connect(lambda: webbrowser.open("https://github.com/buaoyezz"))
        
        # 延迟显示通知，避免可能的错误影响网页打开
        github_btn.clicked.connect(lambda: QTimer.singleShot(500, lambda: NotifyManager.info("正在打开GitHub主页")))

        website_btn = QPushButton("Official Website")
        website_btn.setStyleSheet("""
            QPushButton {
                background-color: #B39DDB;
                color: #121212;
                border: none;
                border-radius: 15px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
        """)
        self.font_manager.apply_font(website_btn)
        links_layout.addWidget(website_btn)
        # 先打开网页，再显示通知
        website_btn.clicked.connect(lambda: webbrowser.open("https://zzbuaoye.dpdns.org/"))
        
        # 延迟显示通知，避免可能的错误影响网页打开
        website_btn.clicked.connect(lambda: QTimer.singleShot(500, lambda: NotifyManager.success("正在打开官方网站")))

        links_layout.addStretch(1)
        about_layout.addLayout(links_layout)
        
        # 添加卡片到内容布局
        content_layout.addWidget(about_card)
        
        # 软件更新卡片
        update_card = RoundedContainer(radius=20, bg_color="#252525")
        update_layout = QVBoxLayout(update_card)
        update_layout.setContentsMargins(30, 30, 30, 30)
        update_layout.setSpacing(20)
        
        # 软件更新标题区域
        update_title_layout = QHBoxLayout()
        update_title_layout.setSpacing(10)
        
        # 软件更新图标
        update_icon = QLabel()
        update_icon.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(update_icon, 24)
        update_icon.setText(self.font_manager.get_icon_text("system_update"))
        update_icon.setStyleSheet("color: #B39DDB;")
        update_title_layout.addWidget(update_icon)
        
        # 软件更新标题
        update_title = QLabel("软件更新")
        update_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(update_title)
        update_title_layout.addWidget(update_title)
        update_title_layout.addStretch()
        
        # 版本信息
        version_info = QLabel("当前版本: 1.0.1")
        version_info.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        self.font_manager.apply_font(version_info)
        update_title_layout.addWidget(version_info)
        
        update_layout.addLayout(update_title_layout)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        # 检查更新按钮
        check_update_btn = QPushButton("检查更新")
        check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #B39DDB;
                color: #121212;
                border: none;
                border-radius: 15px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.font_manager.apply_font(check_update_btn)
        check_update_btn.clicked.connect(self.check_update)
        buttons_layout.addWidget(check_update_btn)
        self.check_update_btn = check_update_btn
        
        # 自动检查更新按钮
        auto_check_btn = QPushButton("自动检查更新")
        auto_check_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #222222;
                color: #666666;
            }
        """)
        self.font_manager.apply_font(auto_check_btn)
        auto_check_btn.clicked.connect(self.toggle_auto_check)
        buttons_layout.addWidget(auto_check_btn)
        self.auto_check_btn = auto_check_btn
        
        buttons_layout.addStretch()
        update_layout.addLayout(buttons_layout)
        
        # 更新状态
        status_label = QLabel("您当前使用的已是最新版本")
        status_label.setStyleSheet("color: #4CAF50; font-size: 14px;")
        self.font_manager.apply_font(status_label)
        update_layout.addWidget(status_label)
        self.status_label = status_label  # 保存引用
        
        content_layout.addWidget(update_card)
        
        # 更新日志卡片
        log_card = RoundedContainer(radius=20, bg_color="#252525")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(30, 30, 30, 30)
        log_layout.setSpacing(20)
        
        # 更新日志标题区域
        log_title_layout = QHBoxLayout()
        log_title_layout.setSpacing(10)
        
        # 更新日志图标
        log_icon = QLabel()
        log_icon.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(log_icon, 24)
        log_icon.setText(self.font_manager.get_icon_text("description"))
        log_icon.setStyleSheet("color: #B39DDB;")
        log_title_layout.addWidget(log_icon)
        
        # 更新日志标题
        log_title = QLabel("更新日志")
        log_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(log_title)
        log_title_layout.addWidget(log_title)
        log_title_layout.addStretch()
        
        log_layout.addLayout(log_title_layout)
        
        # 更新日志内容
        log_content = QLabel("暂无更新日志信息，请检查更新\n检查更新后将在此处显示最新版本信息")
        log_content.setWordWrap(True)
        log_content.setStyleSheet("color: #9E9E9E; font-size: 14px; line-height: 1.5;")
        self.font_manager.apply_font(log_content)
        log_layout.addWidget(log_content)
        
        content_layout.addWidget(log_card)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)

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
                self.update_log_manager.clean_old_logs()
                NotifyManager.success("更新日志已确认")
        else:
            NotifyManager.info("暂无新的更新日志")

    def check_update(self):
        self.check_update_btn.setEnabled(False)
        self.auto_check_btn.setEnabled(False)
        
        status_text = "正在检查更新..."
        status_color = "#2196F3"
        self.update_status_changed.emit(status_text, status_color)
        
        self.update_thread = UpdateCheckThread()
        self.update_thread.update_found.connect(self.handle_update_found)
        self.update_thread.no_update.connect(self.handle_no_update)
        self.update_thread.error.connect(self.handle_update_error)
        self.update_thread.finished.connect(self.update_check_finished)
        self.update_thread.start()
    
    def handle_update_found(self):
        status_text = "发现新版本！"
        status_color = "#4CAF50"
        self.update_status_changed.emit(status_text, status_color)
        self.check_update_btn.setEnabled(True)
        self.auto_check_btn.setEnabled(True)
    
    def handle_no_update(self):
        status_text = "您当前使用的已是最新版本"
        status_color = "#4CAF50"
        self.update_status_changed.emit(status_text, status_color)
        self.check_update_btn.setEnabled(True)
        self.auto_check_btn.setEnabled(True)
    
    def handle_update_error(self, error):
        status_text = f"检查更新失败: {error}"
        status_color = "#f44336"
        self.update_status_changed.emit(status_text, status_color)
        self.check_update_btn.setEnabled(True)
        self.auto_check_btn.setEnabled(True)
        NotifyManager.error(f"检查更新失败: {error}")
    
    def update_check_finished(self):
        # 重新启用按钮
        self.check_update_btn.setEnabled(True)
        self.auto_check_btn.setEnabled(True)
        
        # 清理线程
        if self.update_thread:
            self.update_thread.deleteLater()
            self.update_thread = None
    
    def toggle_auto_check(self):
        # TODO: 实现自动检查更新的开关功能
        NotifyManager.info("自动检查更新功能开发中")

    def update_status_display(self, text, color):
        if hasattr(self, 'status_label'):
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"color: {color}; font-size: 14px;")

    def create_icon_label(self, icon_name, color="#B39DDB"):
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text(icon_name))
        icon_label.setStyleSheet(f"color: {color}; margin: 0; padding: 0;")
        icon_label.setAlignment(Qt.AlignCenter)
        return icon_label

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题区域
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 标题图标
        title_icon = self.create_icon_label("info")
        title_layout.addWidget(title_icon)
        
        # 标题文本
        title_label = QLabel("关于 Hanabi 下载管理器")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1976D2;")
        self.font_manager.apply_font(title_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        main_layout.addLayout(title_layout)

        # 版本信息
        version_label = QLabel("版本 1.0.1")
        version_label.setStyleSheet("font-size: 16px; color: #424242;")
        self.font_manager.apply_font(version_label)
        main_layout.addWidget(version_label, alignment=Qt.AlignCenter)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #E0E0E0;")
        main_layout.addWidget(line)

        # 更新检查区域
        update_layout = QVBoxLayout()
        update_layout.setSpacing(10)

        # 更新检查标题区域
        update_title_layout = QHBoxLayout()
        update_title_layout.setSpacing(10)
        
        # 更新图标
        update_icon = self.create_icon_label("system_update")
        update_title_layout.addWidget(update_icon)
        
        # 更新标题
        update_title = QLabel("软件更新")
        update_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2;")
        self.font_manager.apply_font(update_title)
        update_title_layout.addWidget(update_title)
        update_title_layout.addStretch()
        
        update_layout.addLayout(update_title_layout)

        # 状态标签
        self.status_label = QLabel("点击按钮检查更新")
        self.status_label.setStyleSheet("color: #757575; font-size: 14px;")
        self.font_manager.apply_font(self.status_label)
        update_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # 检查更新按钮
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.font_manager.apply_font(self.check_update_btn)
        self.check_update_btn.clicked.connect(self.check_update)
        button_layout.addWidget(self.check_update_btn)

        # 自动检查按钮
        self.auto_check_btn = QPushButton("自动检查")
        self.auto_check_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:pressed {
                background-color: #1B5E20;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.font_manager.apply_font(self.auto_check_btn)
        button_layout.addWidget(self.auto_check_btn)

        update_layout.addLayout(button_layout)
        main_layout.addLayout(update_layout)
        
        # 更新日志区域
        log_layout = QVBoxLayout()
        log_layout.setSpacing(10)
        
        # 更新日志标题区域
        log_title_layout = QHBoxLayout()
        log_title_layout.setSpacing(10)
        
        # 更新日志图标
        log_icon = self.create_icon_label("description")
        log_title_layout.addWidget(log_icon)
        
        # 更新日志标题
        log_title = QLabel("更新日志")
        log_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1976D2;")
        self.font_manager.apply_font(log_title)
        log_title_layout.addWidget(log_title)
        log_title_layout.addStretch()
        
        log_layout.addLayout(log_title_layout)
        
        # 更新日志内容
        log_content = QLabel("暂无更新日志信息，请检查更新\n检查更新后将在此处显示最新版本信息")
        log_content.setWordWrap(True)
        log_content.setStyleSheet("color: #757575; font-size: 14px;")
        self.font_manager.apply_font(log_content)
        log_layout.addWidget(log_content)
        
        main_layout.addLayout(log_layout)

        # 版权信息
        copyright_label = QLabel("© 2024 Hanabi Team. All rights reserved.")
        copyright_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.font_manager.apply_font(copyright_label)
        main_layout.addWidget(copyright_label, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)
        self.setWindowTitle("关于")
