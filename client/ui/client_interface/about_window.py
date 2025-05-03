from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QDialog, QFrame
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QBrush, QColor
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.customNotify import NotifyManager
import webbrowser

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
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        
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
        version_label = QLabel("版本 1.0.2 Release")
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
        
        # 第三方资源卡片
        thirdparty_card = RoundedContainer(radius=20, bg_color="#252525")
        thirdparty_layout = QVBoxLayout(thirdparty_card)
        thirdparty_layout.setContentsMargins(30, 30, 30, 30)
        thirdparty_layout.setSpacing(20)
        
        # 第三方资源标题区域
        thirdparty_title_layout = QHBoxLayout()
        thirdparty_title_layout.setSpacing(10)
        
        # 第三方资源图标
        thirdparty_icon = QLabel()
        thirdparty_icon.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(thirdparty_icon, 24)
        thirdparty_icon.setText(self.font_manager.get_icon_text("ic_fluent_leaf_three_16_regular"))
        thirdparty_icon.setStyleSheet("color: #B39DDB;")
        thirdparty_title_layout.addWidget(thirdparty_icon)
        
        # 第三方资源标题
        thirdparty_title = QLabel("第三方资源")
        thirdparty_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(thirdparty_title)
        thirdparty_title_layout.addWidget(thirdparty_title)
        thirdparty_title_layout.addStretch()
        
        thirdparty_layout.addLayout(thirdparty_title_layout)
        
        # 第三方资源描述
        thirdparty_desc = QLabel("本软件使用了以下优秀的第三方资源：")
        thirdparty_desc.setWordWrap(True)
        thirdparty_desc.setStyleSheet("color: #E0E0E0; font-size: 14px;")
        self.font_manager.apply_font(thirdparty_desc)
        thirdparty_layout.addWidget(thirdparty_desc)
        
        # 添加分隔线
        separator3 = QWidget()
        separator3.setFixedHeight(1)
        separator3.setStyleSheet("background-color: #3C3C3C;")
        thirdparty_layout.addWidget(separator3)
        
        # 第三方资源列表
        resources = [
            ("PySide6", "Qt for Python GUI框架", "https://doc.qt.io/qtforpython/"),
            ("Microsoft Fluent UI Icons", "现代化图标系统", "https://github.com/microsoft/fluentui-system-icons"),
            ("HarmonyOS Sans", "华为鸿蒙字体", "https://developer.harmonyos.com/cn/design/resource"),
            ("Mulish", "开源无衬线字体", "https://fonts.google.com/specimen/Mulish"),
            ("Xiaoy", "感谢晓宇提供服务器供我部署图标在线查询", "https://apiv2.xiaoy.asia/icons-page/"),
            ("ClutUI Next Generation", "使用了部分ClutUI NG的控件", "https://github.com/buaoyezz/ClutUI-Nextgen")
        ]
        
        for name, desc, url in resources:
            resource_layout = QVBoxLayout()
            resource_layout.setSpacing(4)
        
            # 资源名称
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #B39DDB; font-size: 15px; font-weight: bold;")
            self.font_manager.apply_font(name_label)
            resource_layout.addWidget(name_label)
            
            # 资源描述
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
            self.font_manager.apply_font(desc_label)
            resource_layout.addWidget(desc_label)
            
            # 资源链接行
            link_layout = QHBoxLayout()
            link_layout.setSpacing(5)
            
            # 链接图标
            link_icon = QLabel()
            self.font_manager.apply_icon_font(link_icon, 16)
            link_icon.setText(self.font_manager.get_icon_text("ic_fluent_link_24_regular"))
            link_icon.setStyleSheet("color: #9E9E9E;")
            link_layout.addWidget(link_icon)
            
            # 链接按钮
            link_btn = QPushButton(url)
            link_btn.setStyleSheet("""
            QPushButton {
                    color: #9E9E9E;
                    background: transparent;
                border: none;
                    text-align: left;
                    font-size: 12px;
            }
            QPushButton:hover {
                    color: #B39DDB;
                    text-decoration: underline;
            }
        """)
            self.font_manager.apply_font(link_btn)
            # 为每个按钮创建一个单独的lambda，捕获当前url值
            link_btn.clicked.connect(lambda checked=False, url=url: webbrowser.open(url))
            link_layout.addWidget(link_btn)
            link_layout.addStretch()
            
            resource_layout.addLayout(link_layout)
            thirdparty_layout.addLayout(resource_layout)
        
            # 添加资源间分隔线，最后一个资源除外
            if name != resources[-1][0]:
                separator = QWidget()
                separator.setFixedHeight(1)
                separator.setStyleSheet("background-color: #333333;")
                thirdparty_layout.addWidget(separator)
        
        # 添加第三方资源卡片到内容布局
        content_layout.addWidget(thirdparty_card)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)

    def create_icon_label(self, icon_name, color="#B39DDB"):
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text(icon_name))
        icon_label.setStyleSheet(f"color: {color}; margin: 0; padding: 0;")
        icon_label.setAlignment(Qt.AlignCenter)
        return icon_label
