from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QFrame, QScrollArea, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QFont

from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from core.history.history_manager import HistoryManager

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
        welcome_title = QLabel("欢迎使用 Hanabi 下载管理器")
        welcome_title.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: bold;")
        self.font_manager.apply_font(welcome_title)
        welcome_layout.addWidget(welcome_title)
        
        # 欢迎信息
        welcome_text = QLabel("轻松管理您的下载任务，支持多线程下载和浏览器集成")
        welcome_text.setStyleSheet("color: #B0B0B0; font-size: 14px;")
        welcome_text.setWordWrap(True)
        self.font_manager.apply_font(welcome_text)
        welcome_layout.addWidget(welcome_text)
        
        parent_layout.addWidget(welcome_card)
        
    def _add_stats_section(self, parent_layout):
        # 统计信息标题
        stats_title = QLabel("下载统计")
        stats_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(stats_title)
        parent_layout.addWidget(stats_title)
        
        # 统计卡片容器
        stats_layout = QGridLayout()
        stats_layout.setSpacing(15)
        
        # 添加统计卡片
        stats_data = [
            {"title": "活跃下载", "value": "0", "icon": "ic_fluent_arrow_download_24_regular", "key": "active"},
            {"title": "已完成下载", "value": "0", "icon": "ic_fluent_checkmark_circle_24_regular", "key": "completed"},
            {"title": "总下载量", "value": "0 MB", "icon": "ic_fluent_data_histogram_24_regular", "key": "total_size"},
            {"title": "平均速度", "value": "0 KB/s", "icon": "ic_fluent_arrow_trending_24_regular", "key": "avg_speed"}
        ]
        
        for i, data in enumerate(stats_data):
            card = StatCard(data["title"], data["value"], data["icon"])
            stats_layout.addWidget(card, i // 2, i % 2)
            # 保存卡片引用，以便后续更新
            self.stat_cards[data["key"]] = card
        
        parent_layout.addLayout(stats_layout)
        
    def _add_features_section(self, parent_layout):
        # 功能标题
        features_title = QLabel("主要功能")
        features_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(features_title)
        parent_layout.addWidget(features_title)
        
        # 功能卡片容器
        features_layout = QGridLayout()
        features_layout.setSpacing(15)
        
        # 添加功能卡片
        features_data = [
            {
                "title": "下载管理", 
                "description": "高效管理所有下载任务", 
                "icon": "ic_fluent_arrow_download_24_regular",
                "page": "downloads"
            },
            {
                "title": "浏览器集成", 
                "description": "直接从浏览器添加下载任务", 
                "icon": "ic_fluent_slide_text_24_regular",
                "page": "downloads"
            },
            {
                "title": "历史记录", 
                "description": "查看和管理下载历史", 
                "icon": "ic_fluent_history_24_regular",
                "page": "history"
            },
            {
                "title": "设置中心", 
                "description": "自定义下载管理器设置", 
                "icon": "ic_fluent_settings_24_regular",
                "page": "settings"
            }
        ]
        
        for i, data in enumerate(features_data):
            card = FeatureCard(data["title"], data["description"], data["icon"])
            card.clicked.connect(lambda checked=False, page=data["page"]: self.navigate_to.emit(page))
            features_layout.addWidget(card, i // 2, i % 2)
        
        parent_layout.addLayout(features_layout)
        
    def _add_actions_section(self, parent_layout):
        # 操作标题
        actions_title = QLabel("快捷操作")
        actions_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-top: 10px;")
        self.font_manager.apply_font(actions_title)
        parent_layout.addWidget(actions_title)
        
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
        button_text = QLabel("添加新下载")
        button_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        self.font_manager.apply_font(button_text)
        button_layout.addWidget(button_text)
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
