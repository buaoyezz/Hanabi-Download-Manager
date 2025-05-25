from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QFrame, QScrollArea, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QFont

from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from core.history.history_manager import HistoryManager
from client.ui.extension_interface.extension_window import ExtensionWindow
from client.I18N.i18n import i18n

class StatCard(QFrame):
    """统计信息卡片"""
    
    def __init__(self, title, value, icon_name=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.icon_name = icon_name
        self.font_manager = FontManager()
        
        self.setObjectName("statCard")
        self.setStyleSheet("""
            QFrame#statCard {
                background-color: #252526;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 标题和图标
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        if self.icon_name:
            icon_label = QLabel()
            self.font_manager.apply_icon_font(icon_label, self.icon_name, size=20)
            icon_label.setStyleSheet("color: #B39DDB;")
            header_layout.addWidget(icon_label)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #D0D0D0; font-size: 14px;")
        self.font_manager.apply_font(title_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 数值
        value_label = QLabel(self.value)
        value_label.setStyleSheet("color: #B39DDB; font-size: 28px; font-weight: bold;")
        self.font_manager.apply_font(value_label)
        layout.addWidget(value_label)


class FeatureCard(QFrame):
    """功能卡片"""
    clicked = Signal()
    
    def __init__(self, title, description, icon_name, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.icon_name = icon_name
        self.font_manager = FontManager()
        
        self.setObjectName("featureCard")
        self.setStyleSheet("""
            QFrame#featureCard {
                background-color: #252526;
                border-radius: 10px;
                padding: 15px;
            }
            QFrame#featureCard:hover {
                background-color: #2D2D30;
                border: 1px solid #B39DDB;
            }
        """)
        
        self.setCursor(Qt.PointingHandCursor)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel()
        self.font_manager.apply_icon_font(icon_label, self.icon_name, size=28)
        icon_label.setStyleSheet("color: #B39DDB;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        self.font_manager.apply_font(title_label)
        layout.addWidget(title_label)
        
        # 描述
        description_label = QLabel(self.description)
        description_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setWordWrap(True)
        self.font_manager.apply_font(description_label)
        layout.addWidget(description_label)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            super().mousePressEvent(event)


class HomeWindow(QWidget):
    """首页窗口"""
    
    # 定义信号，用于打开特定页面
    navigate_to = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        
        # 初始化历史记录管理器
        self.history_manager = HistoryManager()
        
        # 保存统计卡片的引用
        self.stat_cards = {}
        
        # 请求处理记录集合
        self._processed_requests = set()
        
        # 初始化UI
        self.setup_ui()
        
        # 加载历史数据并更新统计信息
        self.load_history_stats()
        
        # 连接语言变更信号
        i18n.language_changed.connect(self.update_ui_texts)
    
    def update_ui_texts(self):
        """更新UI上的所有文本以匹配当前语言"""
        # 欢迎标题和文本
        self.welcome_title.setText(i18n.get_text("app_name"))
        self.welcome_text.setText(i18n.get_text("stable_channel_version"))
        
        # 统计信息标题
        self.stats_title.setText("| " + i18n.get_text("download_statistics"))
        
        # 功能标题
        self.features_title.setText("| " + i18n.get_text("main_features"))
        
        # 操作标题
        self.actions_title.setText(i18n.get_text("quick_actions"))
        
        # 添加新下载按钮
        self.button_text.setText(i18n.get_text("add_new_download"))
        
        # 更新统计卡片标题
        for key, card in self.stat_cards.items():
            if key == "active":
                # 使用布局中的第一个控件（标题标签）
                layout = card.layout()
                if layout and layout.count() > 0:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and widget.text() == "活跃下载":
                            widget.setText(i18n.get_text("active_downloads"))
                            break
            elif key == "completed":
                layout = card.layout()
                if layout and layout.count() > 0:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and widget.text() == "已完成下载":
                            widget.setText(i18n.get_text("completed_downloads"))
                            break
            elif key == "total_size":
                layout = card.layout()
                if layout and layout.count() > 0:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and widget.text() == "总下载量":
                            widget.setText(i18n.get_text("total_downloads"))
                            break
            elif key == "avg_speed":
                layout = card.layout()
                if layout and layout.count() > 0:
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and widget.text() == "平均速度":
                            widget.setText(i18n.get_text("average_speed"))
                            break
        
        # 更新功能卡片
        if hasattr(self, 'feature_cards'):
            for card, page in self.feature_cards:
                if page == "downloads":
                    card.title = i18n.get_text("downloads")
                    card.description = i18n.get_text("downloads_description")
                elif page == "extension":
                    card.title = i18n.get_text("browser_integration")
                    card.description = i18n.get_text("browser_integration_description")
                elif page == "history":
                    card.title = i18n.get_text("history")
                    card.description = i18n.get_text("history_description")
                elif page == "settings":
                    card.title = i18n.get_text("settings")
                    card.description = i18n.get_text("settings_description")
                
                # 更新卡片UI
                for i in range(card.layout().count()):
                    widget = card.layout().itemAt(i).widget()
                    if isinstance(widget, QLabel):
                        if i == 1:  # 标题是第二个widget
                            widget.setText(card.title)
                        elif i == 2:  # 描述是第三个widget
                            widget.setText(card.description)
        
    def setup_ui(self):
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background-color: transparent;")
        ScrollStyle.apply_to_widget(scroll_area, "dark")
        
        # 内容容器
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)
        content_layout.setContentsMargins(15, 20, 15, 20)
        
        # 添加欢迎信息
        self._add_welcome_section(content_layout)
        
        # 添加统计信息
        self._add_stats_section(content_layout)
        
        # 添加快捷功能
        self._add_features_section(content_layout)
        
        # 添加常用操作
        self._add_actions_section(content_layout)
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
    def _add_welcome_section(self, parent_layout):
        # 欢迎卡片
        welcome_card = QFrame()
        welcome_card.setObjectName("welcomeCard")
        welcome_card.setStyleSheet("""
            QFrame#welcomeCard {
                background-color: #292930;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        
        welcome_layout = QVBoxLayout(welcome_card)
        welcome_layout.setContentsMargins(25, 25, 25, 25)
        welcome_layout.setSpacing(15)
        
        # 欢迎标题
        self.welcome_title = QLabel(i18n.get_text("app_name"))
        self.welcome_title.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: bold;")
        self.font_manager.apply_font(self.welcome_title)
        welcome_layout.addWidget(self.welcome_title)
        
        # 欢迎信息
        self.welcome_text = QLabel(i18n.get_text("stable_channel_version"))
        self.welcome_text.setStyleSheet("color: #B0B0B0; font-size: 14px;")
        self.welcome_text.setWordWrap(True)
        self.font_manager.apply_font(self.welcome_text)
        welcome_layout.addWidget(self.welcome_text)
        
        parent_layout.addWidget(welcome_card)
        
    def _add_stats_section(self, parent_layout):
        # 统计信息标题
        self.stats_title = QLabel("| " + i18n.get_text("download_statistics"))
        self.stats_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(self.stats_title)
        parent_layout.addWidget(self.stats_title)
        
        # 统计卡片容器
        stats_layout = QGridLayout()
        stats_layout.setSpacing(15)
        
        # 添加统计卡片
        stats_data = [
            {"title": i18n.get_text("active_downloads"), "value": "0", "icon": "ic_fluent_arrow_download_24_regular", "key": "active"},
            {"title": i18n.get_text("completed_downloads"), "value": "0", "icon": "ic_fluent_checkmark_circle_24_regular", "key": "completed"},
            {"title": i18n.get_text("total_downloads"), "value": "0 MB", "icon": "ic_fluent_data_histogram_24_regular", "key": "total_size"},
            {"title": i18n.get_text("average_speed"), "value": "0 KB/s", "icon": "ic_fluent_arrow_trending_24_regular", "key": "avg_speed"}
        ]
        
        for i, data in enumerate(stats_data):
            card = StatCard(data["title"], data["value"], data["icon"])
            stats_layout.addWidget(card, i // 2, i % 2)
            # 保存卡片引用，以便后续更新
            self.stat_cards[data["key"]] = card
        
        parent_layout.addLayout(stats_layout)
        
    def _add_features_section(self, parent_layout):
        # 功能标题
        self.features_title = QLabel("| " + i18n.get_text("main_features"))
        self.features_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(self.features_title)
        parent_layout.addWidget(self.features_title)
        
        # 功能卡片容器
        features_layout = QGridLayout()
        features_layout.setSpacing(15)
        
        # 添加功能卡片
        features_data = [
            {
                "title": i18n.get_text("downloads"), 
                "description": i18n.get_text("downloads_description"), 
                "icon": "ic_fluent_arrow_download_24_regular",
                "page": "downloads"
            },
            {
                "title": i18n.get_text("browser_integration"), 
                "description": i18n.get_text("browser_integration_description"), 
                "icon": "ic_fluent_slide_text_24_regular",
                "page": "extension"
            },
            {
                "title": i18n.get_text("history"), 
                "description": i18n.get_text("history_description"), 
                "icon": "ic_fluent_history_24_regular",
                "page": "history"
            },
            {
                "title": i18n.get_text("settings"), 
                "description": i18n.get_text("settings_description"), 
                "icon": "ic_fluent_settings_24_regular",
                "page": "settings"
            }
        ]
        
        # 保存卡片引用，以便语言更新
        self.feature_cards = []
        
        for i, data in enumerate(features_data):
            card = FeatureCard(data["title"], data["description"], data["icon"])
            card.clicked.connect(lambda checked=False, page=data["page"]: self.navigate_to.emit(page))
            features_layout.addWidget(card, i // 2, i % 2)
            self.feature_cards.append((card, data["page"]))
        
        parent_layout.addLayout(features_layout)
        
    def _add_actions_section(self, parent_layout):
        # 操作标题
        self.actions_title = QLabel(i18n.get_text("quick_actions"))
        self.actions_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(self.actions_title)
        parent_layout.addWidget(self.actions_title)
        
        # 操作按钮容器
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)
        
        # 添加新下载按钮
        add_download_btn = QPushButton("")
        add_download_btn.setObjectName("primaryButton")
        add_download_btn.setStyleSheet("""
            QPushButton#primaryButton {
                background-color: #B39DDB;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #9C7EBD;
            }
            QPushButton#primaryButton:pressed {
                background-color: #8667AB;
            }
        """)
        self.font_manager.apply_font(add_download_btn)
        add_download_btn.clicked.connect(lambda: self.navigate_to.emit("downloads"))
        
        # 设置图标
        icon_label = self.font_manager.create_icon_label(
            parent=add_download_btn,
            icon_name="ic_fluent_arrow_download_24_regular",
            size=16,
            color="#FFFFFF"
        )
        
        # 创建水平布局来放置图标和文本
        button_layout = QHBoxLayout(add_download_btn)
        button_layout.setContentsMargins(10, 0, 10, 0)
        button_layout.setSpacing(8)
        button_layout.addWidget(icon_label)
        
        # 添加文本标签
        self.button_text = QLabel(i18n.get_text("add_new_download"))
        self.button_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        self.font_manager.apply_font(self.button_text)
        button_layout.addWidget(self.button_text)
        button_layout.addStretch()
        
        actions_layout.addWidget(add_download_btn)
        actions_layout.addStretch()
        
        parent_layout.addLayout(actions_layout)
    
    def update_stats(self, active_downloads=0, completed_downloads=0, total_size="0 MB", avg_speed="0 KB/s"):
        """更新统计信息"""
        # 更新每个统计卡片的值
        stats_update = {
            "active": str(active_downloads),
            "completed": str(completed_downloads),
            "total_size": total_size,
            "avg_speed": avg_speed
        }
        
        # 遍历所有统计卡片并更新
        for key, value in stats_update.items():
            if key in self.stat_cards:
                # 找到对应的值标签并更新
                card = self.stat_cards[key]
                # 值标签通常是卡片布局中的最后一个控件
                layout = card.layout()
                if layout and layout.count() > 0:
                    # 获取最后一个控件（通常是值标签）
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QLabel) and not widget.text() == card.title:
                            widget.setText(value)
                            break
    
    def load_history_stats(self):
        """从历史记录中加载并计算统计数据"""
        # 获取全部历史记录
        history_records = self.history_manager.get_all_records(force_reload=True)
        
        # 统计变量
        completed_downloads = 0
        total_size_bytes = 0
        active_downloads = 0  # 这个可能需要从其他地方获取
        
        # 速度统计
        speeds = []
        total_speed = 0
        
        # 遍历历史记录
        for record in history_records:
            # 统计已完成的下载
            if record.get('status') == 'completed':
                completed_downloads += 1
                
                # 累计下载大小
                file_size = record.get('file_size', 0)
                if isinstance(file_size, str):
                    # 如果是字符串，尝试转换为数字
                    try:
                        # 提取数字部分
                        size_parts = file_size.split()
                        if len(size_parts) >= 1:
                            size_value = float(size_parts[0])
                            # 根据单位转换为字节
                            if 'KB' in file_size:
                                size_value *= 1024
                            elif 'MB' in file_size:
                                size_value *= 1024 * 1024
                            elif 'GB' in file_size:
                                size_value *= 1024 * 1024 * 1024
                            total_size_bytes += size_value
                    except (ValueError, IndexError):
                        pass
                else:
                    # 如果是数字，直接累加
                    total_size_bytes += file_size
                
                # 处理速度信息
                if 'speed' in record:
                    speed_str = record.get('speed', '')
                    if speed_str and isinstance(speed_str, str):
                        try:
                            # 提取速度值
                            speed_parts = speed_str.split()
                            if len(speed_parts) >= 1:
                                speed_value = float(speed_parts[0])
                                # 统一转换为KB/s
                                if 'B/s' in speed_str:
                                    speed_value /= 1024  # 转为KB/s
                                elif 'MB/s' in speed_str:
                                    speed_value *= 1024  # 转为KB/s
                                elif 'GB/s' in speed_str:
                                    speed_value *= 1024 * 1024  # 转为KB/s
                                
                                speeds.append(speed_value)
                                total_speed += speed_value
                        except (ValueError, IndexError):
                            pass
        
        # 格式化总大小
        if total_size_bytes < 1024:
            total_size = f"{total_size_bytes} B"
        elif total_size_bytes < 1024 * 1024:
            total_size = f"{total_size_bytes / 1024:.2f} KB"
        elif total_size_bytes < 1024 * 1024 * 1024:
            total_size = f"{total_size_bytes / (1024 * 1024):.2f} MB"
        else:
            total_size = f"{total_size_bytes / (1024 * 1024 * 1024):.2f} GB"
        
        # 计算平均速度
        avg_speed_str = "0 KB/s"
        if speeds:
            avg_speed = total_speed / len(speeds)
            # 格式化平均速度
            if avg_speed < 1:  # 小于1KB/s
                avg_speed_str = f"{avg_speed * 1024:.2f} B/s"
            elif avg_speed < 1024:  # KB/s范围
                avg_speed_str = f"{avg_speed:.2f} KB/s"
            elif avg_speed < 1024 * 1024:  # MB/s范围
                avg_speed_str = f"{avg_speed / 1024:.2f} MB/s"
            else:  # GB/s范围
                avg_speed_str = f"{avg_speed / (1024 * 1024):.2f} GB/s"
        
        # 更新统计信息
        self.update_stats(
            active_downloads=active_downloads,
            completed_downloads=completed_downloads,
            total_size=total_size,
            avg_speed=avg_speed_str
        )
