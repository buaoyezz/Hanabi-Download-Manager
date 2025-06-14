from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QScrollArea, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt
from client.ui.client_interface.settings.general_control import GeneralControlWidget
from client.ui.client_interface.settings.download_control import DownloadControlWidget
from client.ui.client_interface.settings.network_control import NetworkControlWidget
from client.ui.client_interface.settings.update_page import UpdatePage
from client.ui.client_interface.settings.debug_pages import DebugPagesWidget
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.customMessagebox import CustomMessageBox
from core.font.font_manager import FontManager
from client.I18N.i18n import i18n

class SettingsContainer(QWidget):
    """设置页面容器"""
    # 定义信号
    themeChanged = Signal(str)  # 主题变更信号
    fontChanged = Signal(str)   # 字体变更信号
    languageChanged = Signal(str)  # 语言变更信号
    addDownloadTask = Signal(str, str, int)  # 添加下载任务信号：URL, 文件名, 文件大小
    settingsMessage = Signal(bool, str)  # 设置消息信号
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        
        # 设置控制器
        self.controller = None
        
        # 初始化UI
        self.setup_ui()
        
        # 连接更新页面信号
        if hasattr(self, 'update_page'):
            self.update_page.addDownloadTask.connect(self.forward_add_download_task)
            
        # 连接语言变更信号，动态更新UI文本
        i18n.language_changed.connect(self.update_ui_texts)
    
    def forward_add_download_task(self, url, filename, filesize):
        """转发添加下载任务信号"""
        # 简单地将信号转发到父窗口
        if hasattr(self, 'addDownloadTask'):
            self.addDownloadTask.emit(url, filename, filesize)
            
    def setup_ui(self):
        """创建设置界面UI"""
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
        title_label = QLabel(i18n.get_text("settings"))
        title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 18px;
            font-weight: bold;
        """)
        self.font_manager.apply_font(title_label)
        title_layout.addWidget(title_label)
        
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
            "update": "ic_fluent_arrow_sync_24_regular",
            "debug": "ic_fluent_bug_24_regular"  # 添加调试图标
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
        self.update_page = UpdatePage(self.config_manager)
        update_scroll.setWidget(self.update_page)
        update_tab_index = self.tab_widget.addTab(update_scroll, i18n.get_text("software_update"))
        self._set_tab_icon(update_tab_index, icons["update"])
        
        # 添加调试页
        debug_scroll = self._create_tab_scroll_area()
        self.debug_tab = DebugPagesWidget()
        debug_scroll.setWidget(self.debug_tab)
        debug_tab_index = self.tab_widget.addTab(debug_scroll, "调试工具")
        self._set_tab_icon(debug_tab_index, icons["debug"])
        
        tab_layout.addWidget(self.tab_widget)
        main_layout.addWidget(tab_container, 1)
        
        # 连接信号
        self.general_tab.settings_applied.connect(self._handle_settings_message)
        self.download_tab.settings_applied.connect(self._handle_settings_message)
        self.network_tab.settings_applied.connect(self._handle_settings_message)
        self.update_page.updateFound.connect(self._handle_update_found)
        self.update_page.updateError.connect(self._handle_update_error)
    
    def update_ui_texts(self):
        """更新界面上的所有文本"""
        # 当语言变更时调用
        # 更新标题
        for label in self.findChildren(QLabel):
            if label.text() == "设置" or label.text() == "Settings":
                label.setText(i18n.get_text("settings"))
                
        # 更新标签页标题
        for i in range(self.tab_widget.count()):
            tab_text = self.tab_widget.tabText(i)
            if tab_text == "常规设置" or tab_text == "General Settings":
                self.tab_widget.setTabText(i, i18n.get_text("general_settings"))
            elif tab_text == "下载设置" or tab_text == "Download Settings":
                self.tab_widget.setTabText(i, i18n.get_text("download_settings"))
            elif tab_text == "网络设置" or tab_text == "Network Settings":
                self.tab_widget.setTabText(i, i18n.get_text("network_settings"))
            elif tab_text == "高级线程" or tab_text == "Advanced Threads":
                self.tab_widget.setTabText(i, i18n.get_text("advanced_settings"))
            elif tab_text == "软件更新" or tab_text == "Software Update":
                self.tab_widget.setTabText(i, i18n.get_text("software_update"))
            # 保留调试工具标签不变
            elif tab_text == "调试工具" or tab_text == "Debug Tools":
                self.tab_widget.setTabText(i, "调试工具")
    
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
                icon_label.setStyleSheet("color: #CCCCCC;")
                tab_layout.addWidget(icon_label)
                
                # 设置到左侧
                self.tab_widget.tabBar().setTabButton(tab_index, left_side, tab_button)
        except Exception as e:
            print(f"设置标签图标失败: {e}")
            # 如果设置失败，继续而不中断
            pass
            
    def _handle_settings_message(self, success, message):
        """处理设置消息"""
        # 转发消息到主窗口
        self.settingsMessage.emit(success, message)
        
    def _handle_update_found(self, version, release_notes):
        """处理发现更新"""
        # 这里不需要做太多，因为主窗口会直接从update_page获取信号
        pass
        
    def _handle_update_error(self, error_message):
        """处理更新错误"""
        # 这里不需要做太多，因为主窗口会直接从update_page获取信号
        CustomMessageBox.warning(self, i18n.get_text("update_check_failed"), 
                                f"{i18n.get_text('update_check_error')}: {error_message}")