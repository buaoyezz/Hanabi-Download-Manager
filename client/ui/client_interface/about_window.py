from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QScrollArea, QDialog, QFrame
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QBrush, QColor
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.customNotify import NotifyManager
from client.I18N.i18n import i18n
from client.version.version_manager import VersionManager
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
        
        # 初始化版本管理器
        self.version_manager = VersionManager.get_instance()
        
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
        self.version_label = QLabel(f"{i18n.get_text('version')} Release")
        self.version_label.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        self.font_manager.apply_font(self.version_label)
        header_layout.addWidget(self.version_label)
        
        about_layout.addLayout(header_layout)
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        about_layout.addWidget(separator)
        
        # 软件描述
        self.desc_label = QLabel(i18n.get_text("about_description"))
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #FFFFFF; font-size: 14px; line-height: 1.5;")
        self.font_manager.apply_font(self.desc_label)
        about_layout.addWidget(self.desc_label)
        
        # 特性列表
        self.features_label = QLabel(i18n.get_text("main_features") + ":")
        self.features_label.setStyleSheet("color: #B39DDB; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.features_label)
        about_layout.addWidget(self.features_label)
        
        self.features_content = QLabel(
            i18n.get_text("features_list")
        )
        self.features_content.setStyleSheet("color: #E0E0E0; font-size: 14px; line-height: 1.6;")
        self.features_content.setWordWrap(True)
        self.features_content.setTextFormat(Qt.RichText)
        self.font_manager.apply_font(self.features_content)
        about_layout.addWidget(self.features_content)
        
        # 另一个分隔线
        separator2 = QWidget()
        separator2.setFixedHeight(1)
        separator2.setStyleSheet("background-color: #3C3C3C;")
        about_layout.addWidget(separator2)
        
        # 开发者信息
        self.dev_label = QLabel(i18n.get_text("developer"))
        self.dev_label.setStyleSheet("color: #B39DDB; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.dev_label)
        about_layout.addWidget(self.dev_label)
        
        self.dev_content = QLabel(i18n.get_text("developer_info"))
        self.dev_content.setWordWrap(True)
        self.dev_content.setStyleSheet("color: #E0E0E0; font-size: 14px;")
        self.font_manager.apply_font(self.dev_content)
        about_layout.addWidget(self.dev_content)
        
        # 版权信息
        self.copyright_label = QLabel(i18n.get_text("copyright_info"))
        self.copyright_label.setAlignment(Qt.AlignCenter)
        self.copyright_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.font_manager.apply_font(self.copyright_label)
        about_layout.addWidget(self.copyright_label)
        
        # 相关链接
        links_layout = QHBoxLayout()
        links_layout.setSpacing(15)
        
        self.github_btn = QPushButton(i18n.get_text("github_home"))
        self.github_btn.setStyleSheet("""
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
        self.font_manager.apply_font(self.github_btn)
        links_layout.addWidget(self.github_btn)
        # 优化打开网页和显示通知的逻辑
        self.github_btn.clicked.connect(lambda: self._open_url("https://github.com/buaoyezz", i18n.get_text("opening_github"), "info"))

        self.website_btn = QPushButton(i18n.get_text("official_website"))
        self.website_btn.setStyleSheet("""
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
        self.font_manager.apply_font(self.website_btn)
        links_layout.addWidget(self.website_btn)
        # 优化打开网页和显示通知的逻辑
        self.website_btn.clicked.connect(lambda: self._open_url("https://zzbuaoye.dpdns.org/", i18n.get_text("opening_website"), "success"))

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
        self.thirdparty_title = QLabel(i18n.get_text("third_party_resources"))
        self.thirdparty_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.thirdparty_title)
        thirdparty_title_layout.addWidget(self.thirdparty_title)
        thirdparty_title_layout.addStretch()
        
        thirdparty_layout.addLayout(thirdparty_title_layout)
        
        # 第三方资源描述
        self.thirdparty_desc = QLabel(i18n.get_text("third_party_description"))
        self.thirdparty_desc.setWordWrap(True)
        self.thirdparty_desc.setStyleSheet("color: #E0E0E0; font-size: 14px;")
        self.font_manager.apply_font(self.thirdparty_desc)
        thirdparty_layout.addWidget(self.thirdparty_desc)
        
        # 添加分隔线
        separator3 = QWidget()
        separator3.setFixedHeight(1)
        separator3.setStyleSheet("background-color: #3C3C3C;")
        thirdparty_layout.addWidget(separator3)
        
        # 第三方资源列表
        resources = [
            ("PySide6", i18n.get_text("pyside6_desc"), "https://doc.qt.io/qtforpython/"),
            (i18n.get_text("fluent_ui_icons"), i18n.get_text("fluent_ui_desc"), "https://github.com/microsoft/fluentui-system-icons"),
            ("HarmonyOS Sans", i18n.get_text("harmonyos_desc"), "https://developer.harmonyos.com/cn/design/resource"),
            ("Mulish", i18n.get_text("mulish_desc"), "https://fonts.google.com/specimen/Mulish"),
            ("Xiaoy", i18n.get_text("xiaoy_desc"), "https://apiv2.xiaoy.asia/icons-page/"),
            ("SadIDC", i18n.get_text("sadidc_desc"), "https://sadidc.cn/"),
            ("ClutUI Next Generation", i18n.get_text("clutui_desc"), "https://github.com/buaoyezz/ClutUI-Nextgen")
        ]
        
        # 保存资源控件引用，以便语言更新
        self.resource_labels = []
        
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
            
            # 保存引用
            self.resource_labels.append((name_label, desc_label))
            
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
            link_btn.clicked.connect(lambda checked=False, url=url, name=name: self._open_url(url, f"{i18n.get_text('opening')}: {name}", "info"))
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
        
        # 连接语言变更信号
        i18n.language_changed.connect(self.update_ui_texts)

    def update_ui_texts(self):
        """更新UI上的所有文本以匹配当前语言"""
        # 版本信息
        self.version_label.setText(f"{i18n.get_text('version')} {self.version_manager.get_client_version()} Release")
        
        # 软件描述
        self.desc_label.setText(i18n.get_text("about_description"))
        
        # 特性标题和列表
        self.features_label.setText(i18n.get_text("main_features") + ":")
        self.features_content.setText(i18n.get_text("features_list"))
        
        # 开发者信息
        self.dev_label.setText(i18n.get_text("developer"))
        self.dev_content.setText(i18n.get_text("developer_info"))
        
        # 版权信息
        self.copyright_label.setText(i18n.get_text("copyright_info"))
        
        # 按钮文本
        self.github_btn.setText(i18n.get_text("github_home"))
        self.website_btn.setText(i18n.get_text("official_website"))
        
        # 第三方资源标题和描述
        self.thirdparty_title.setText(i18n.get_text("third_party_resources"))
        self.thirdparty_desc.setText(i18n.get_text("third_party_description"))
        
        # 更新资源描述
        resources_desc = [
            i18n.get_text("pyside6_desc"),
            i18n.get_text("fluent_ui_desc"),
            i18n.get_text("harmonyos_desc"),
            i18n.get_text("mulish_desc"),
            i18n.get_text("xiaoy_desc"),
            i18n.get_text("sadidc_desc"),
            i18n.get_text("clutui_desc")
        ]
        
        # 更新资源标签
        for i, (name_label, desc_label) in enumerate(self.resource_labels):
            if i < len(resources_desc):
                desc_label.setText(resources_desc[i])

    def create_icon_label(self, icon_name, color="#B39DDB"):
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text(icon_name))
        icon_label.setStyleSheet(f"color: {color}; margin: 0; padding: 0;")
        icon_label.setAlignment(Qt.AlignCenter)
        return icon_label

    def _open_url(self, url, message, notify_type="info"):
        """打开URL并显示通知
        
        Args:
            url (str): 要打开的URL
            message (str): 通知消息
            notify_type (str): 通知类型，可以是"info"、"success"、"warning"或"error"
        """
        try:
            # 先尝试打开网页
            webbrowser.open(url)
            
            # 显示通知
            if notify_type == "info":
                NotifyManager.info(message)
            elif notify_type == "success":
                NotifyManager.success(message)
            elif notify_type == "warning":
                NotifyManager.warning(message)
            elif notify_type == "error":
                NotifyManager.error(message)
        except Exception as e:
            # 如果发生错误，显示错误通知
            NotifyManager.error(f"{i18n.get_text('open_link_failed')}: {str(e)}")
