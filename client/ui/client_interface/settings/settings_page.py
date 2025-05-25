from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QScrollArea, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt
from client.ui.client_interface.settings.general_control import GeneralControlWidget
from client.ui.client_interface.settings.download_control import DownloadControlWidget
from client.ui.client_interface.settings.network_control import NetworkControlWidget
from client.ui.client_interface.settings.update_page import UpdatePage
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.customMessagebox import CustomMessageBox
from core.font.font_manager import FontManager
from client.I18N.i18n import i18n

class SettingsPage(QWidget):
    # 设置消息信号
    settingsMessage = Signal(bool, str)
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.setup_ui()
        
        # 连接语言变更信号，动态更新UI文本
        i18n.language_changed.connect(self.update_ui_texts)
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建标题栏
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(5, 5, 5, 10)
        title_layout.setSpacing(10)
        
        # 设置图标
        icon_label = QLabel()
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text("ic_fluent_settings_24_regular"))
        icon_label.setStyleSheet("color: #B39DDB; padding: 5px;")
        title_layout.addWidget(icon_label)
        
        # 设置标题
        self.title_label = QLabel(i18n.get_text("settings"))
        self.title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 18px;
            font-weight: bold;
        """)
        self.font_manager.apply_font(self.title_label)
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        main_layout.addLayout(title_layout)
        
        # 创建标签页容器
        tab_container = QWidget()
        tab_container.setObjectName("tabContainer")
        tab_container.setStyleSheet("""
            #tabContainer {
                background-color: #2C2C2C;
                border: 1px solid #3C3C3C;
                border-radius: 12px;
            }
        """)
        
        tab_layout = QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(8, 10, 8, 8)
        tab_layout.setSpacing(0)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)  # 使用扁平化设计
        self.tab_widget.setTabPosition(QTabWidget.North)
        
        # 设置标签页样式 - 模仿customMessagebox的样式
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
                padding-top: 10px;
            }
            
            QTabBar::tab {
                min-width: 120px;
                min-height: 40px;
                padding: 5px 15px;
                margin-right: 5px;
                margin-bottom: 3px;
                border-radius: 8px;
                background-color: #252525;
                color: #CCCCCC;
                font-size: 14px;
            }
            
            QTabBar::tab:selected {
                color: #FFFFFF;
                background-color: #7E57C2;
                font-weight: bold;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #383838;
                color: #FFFFFF;
            }
            
            QTabBar {
                background-color: transparent;
                border: none;
            }
            
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            
            QWidget {
                background-color: transparent;
            }
        """)
        
        # 为每个标签页创建图标
        icons = {
            "general": "ic_fluent_settings_24_regular",
            "download": "ic_fluent_arrow_download_24_regular",
            "network": "ic_fluent_globe_24_regular",
            "advanced": "ic_fluent_diagram_24_regular",
            "update": "ic_fluent_arrow_sync_24_regular"
        }
        
        # 常规设置页 - 添加滚动区域和图标
        general_scroll = self._create_tab_scroll_area()
        self.general_tab = GeneralControlWidget(self.config_manager)
        general_scroll.setWidget(self.general_tab)
        general_tab_index = self.tab_widget.addTab(general_scroll, i18n.get_text("general_settings"))
        self._set_tab_icon(general_tab_index, icons["general"])
        
        # 下载设置页 - 添加滚动区域和图标
        download_scroll = self._create_tab_scroll_area()
        self.download_tab = DownloadControlWidget(self.config_manager)
        download_scroll.setWidget(self.download_tab)
        download_tab_index = self.tab_widget.addTab(download_scroll, i18n.get_text("download_settings"))
        self._set_tab_icon(download_tab_index, icons["download"])
        
        # 网络设置页 - 添加滚动区域和图标
        network_scroll = self._create_tab_scroll_area()
        self.network_tab = NetworkControlWidget(self.config_manager)
        network_scroll.setWidget(self.network_tab)
        network_tab_index = self.tab_widget.addTab(network_scroll, i18n.get_text("network_settings"))
        self._set_tab_icon(network_tab_index, icons["network"])
        
        # 添加高级设置页
        advanced_scroll = self._create_tab_scroll_area()
        # 高级设置页暂时留空
        advanced_widget = QWidget()
        advanced_scroll.setWidget(advanced_widget)
        advanced_tab_index = self.tab_widget.addTab(advanced_scroll, i18n.get_text("advanced_settings"))
        self._set_tab_icon(advanced_tab_index, icons["advanced"])
        
        # 添加更新检查页
        update_scroll = self._create_tab_scroll_area()
        self.update_tab = UpdatePage(self.config_manager)
        update_scroll.setWidget(self.update_tab)
        update_tab_index = self.tab_widget.addTab(update_scroll, i18n.get_text("software_update"))
        self._set_tab_icon(update_tab_index, icons["update"])
        
        tab_layout.addWidget(self.tab_widget)
        main_layout.addWidget(tab_container, 1)
        
        # 连接信号
        self.general_tab.settings_applied.connect(self._handle_settings_message)
        self.download_tab.settings_applied.connect(self._handle_settings_message)
        self.network_tab.settings_applied.connect(self._handle_settings_message)
        self.update_tab.updateFound.connect(self._handle_update_found)
        self.update_tab.updateError.connect(self._handle_update_error)

    def update_ui_texts(self):
        """更新界面上的所有文本"""
        # 当语言变更时调用
        self.title_label.setText(i18n.get_text("settings"))
        
        # 更新标签页标题
        self.tab_widget.setTabText(0, i18n.get_text("general_settings"))
        self.tab_widget.setTabText(1, i18n.get_text("download_settings"))
        self.tab_widget.setTabText(2, i18n.get_text("network_settings"))
        self.tab_widget.setTabText(3, i18n.get_text("advanced_settings"))
        self.tab_widget.setTabText(4, i18n.get_text("software_update"))

    def _create_tab_scroll_area(self):
        """创建标准化的滚动区域"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(scroll, "dark")
        return scroll
    
    def _set_tab_icon(self, tab_index, icon_name):
        """设置标签页图标"""
        try:
            # 尝试从QTabBar获取枚举值
            from PySide6.QtWidgets import QTabBar
            left_side = QTabBar.ButtonPosition.LeftSide 
            
            # 创建标签布局
            tab_button = self.tab_widget.tabBar().tabButton(tab_index, left_side)
            if not tab_button:
                tab_button = QWidget()
                tab_layout = QHBoxLayout(tab_button)
                tab_layout.setContentsMargins(0, 0, 5, 0)
                tab_layout.setSpacing(6)
                
                # 创建图标
                icon_label = QLabel()
                self.font_manager.apply_icon_font(icon_label, 16)
                icon_label.setText(self.font_manager.get_icon_text(icon_name))
                icon_label.setStyleSheet("color: white;")
                tab_layout.addWidget(icon_label)
                
                # 创建空标签用于文字（由QTabBar本身处理）
                spacer = QLabel("")
                tab_layout.addWidget(spacer)
                
                # 设置按钮
                self.tab_widget.tabBar().setTabButton(tab_index, left_side, tab_button)
        except Exception as e:
            # 如果设置图标失败，只记录错误，不影响程序运行
            print(f"设置标签页图标失败: {e}")

    def _handle_settings_message(self, success, message):
        # 直接在设置页面显示消息，不再依赖父组件
        if success:
            # 如果是"常规设置已保存"消息，添加闪光图标
            if message == i18n.get_text("general_settings_saved"):
                font_manager = FontManager()
                icon_text = font_manager.get_icon_text("ic_fluent_sparkle_32_regular")
                CustomMessageBox.info(self, i18n.get_text("settings"), f"{icon_text} {message}")
            else:
                CustomMessageBox.info(self, i18n.get_text("settings"), message)
        else:
            CustomMessageBox.warning(self, i18n.get_text("settings_error"), message)
            
        # 同时发送信号，以便主窗口可以选择性处理
        self.settingsMessage.emit(success, message)
        
    def _handle_update_found(self, version, release_notes):
        # 当找到更新时通知主窗口
        self.settingsMessage.emit(True, f"{i18n.get_text('update_found')} {version}")
        
    def _handle_update_error(self, error_message):
        # 当更新检查出错时通知主窗口
        self.settingsMessage.emit(False, f"{i18n.get_text('update_check_error')}: {error_message}") 