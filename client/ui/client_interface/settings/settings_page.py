from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QMessageBox, QScrollArea
from PySide6.QtCore import Signal, Qt
from client.ui.client_interface.settings.general_control import GeneralControlWidget
from client.ui.client_interface.settings.download_control import DownloadControlWidget
from client.ui.client_interface.settings.network_control import NetworkControlWidget
from client.ui.client_interface.settings.update_page import UpdatePage
from client.ui.components.scrollStyle import ScrollStyle

class SettingsPage(QWidget):
    # 设置消息信号
    settingsMessage = Signal(bool, str)
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setDocumentMode(True)  # 使用扁平化设计
        
        # 设置标签页样式 - 模仿图片中的圆角渐变标签
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1E1E1E;
                padding-top: 0px;
                top: 0px;
            }
            
            QTabBar::tab {
                min-width: 100px;
                min-height: 30px;
                padding: 5px 20px;
                margin-right: 4px;
                border-radius: 15px;
                background: transparent;
                border: none;
                color: #9E9E9E;
            }
            
            QTabBar::tab:selected {
                color: #FFFFFF;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #FF69B4, stop:1 #DA70D6);
                border: none;
            }
            
            QTabBar::tab:hover:!selected {
                background: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            
            QTabBar {
                background-color: #1E1E1E;
                border: none;
            }
            
            QScrollArea, QWidget {
                border: none;
            }
        """)
        # 常规设置页 - 添加滚动区域
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setFrameShape(QScrollArea.NoFrame)
        general_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        general_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(general_scroll, "dark")
        
        self.general_tab = GeneralControlWidget(self.config_manager)
        general_scroll.setWidget(self.general_tab)
        self.tab_widget.addTab(general_scroll, "常规设置")
        
        # 下载设置页 - 添加滚动区域
        download_scroll = QScrollArea()
        download_scroll.setWidgetResizable(True)
        download_scroll.setFrameShape(QScrollArea.NoFrame)
        download_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        download_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(download_scroll, "dark")
        
        self.download_tab = DownloadControlWidget(self.config_manager)
        download_scroll.setWidget(self.download_tab)
        self.tab_widget.addTab(download_scroll, "下载设置")
        
        # 网络设置页 - 添加滚动区域
        network_scroll = QScrollArea()
        network_scroll.setWidgetResizable(True)
        network_scroll.setFrameShape(QScrollArea.NoFrame)
        network_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        network_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(network_scroll, "dark")
        
        self.network_tab = NetworkControlWidget(self.config_manager)
        network_scroll.setWidget(self.network_tab)
        self.tab_widget.addTab(network_scroll, "网络设置")
        
        # 添加高级设置页
        advanced_scroll = QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setFrameShape(QScrollArea.NoFrame)
        advanced_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        advanced_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(advanced_scroll, "dark")
        
        # 高级设置页暂时留空
        advanced_widget = QWidget()
        advanced_widget.setStyleSheet("background-color: #1E1E1E;")
        advanced_scroll.setWidget(advanced_widget)
        self.tab_widget.addTab(advanced_scroll, "高级线程")
        
        # 添加更新检查页
        update_scroll = QScrollArea()
        update_scroll.setWidgetResizable(True)
        update_scroll.setFrameShape(QScrollArea.NoFrame)
        update_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        update_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(update_scroll, "dark")
        
        self.update_tab = UpdatePage(self.config_manager)
        update_scroll.setWidget(self.update_tab)
        self.tab_widget.addTab(update_scroll, "软件更新")
        
        main_layout.addWidget(self.tab_widget)
        
        # 连接信号
        self.general_tab.settings_applied.connect(self._handle_settings_message)
        self.download_tab.settings_applied.connect(self._handle_settings_message)
        self.network_tab.settings_applied.connect(self._handle_settings_message)
        self.update_tab.updateFound.connect(self._handle_update_found)
        self.update_tab.updateError.connect(self._handle_update_error)

    def _handle_settings_message(self, success, message):
        # 直接在设置页面显示消息，不再依赖父组件
        if success:
            QMessageBox.information(self, "设置", message)
        else:
            QMessageBox.warning(self, "设置错误", message)
            
        # 同时发送信号，以便主窗口可以选择性处理
        self.settingsMessage.emit(success, message)
        
    def _handle_update_found(self, version, release_notes):
        # 当找到更新时通知主窗口
        self.settingsMessage.emit(True, f"发现新版本 {version}")
        
    def _handle_update_error(self, error_message):
        # 当更新检查出错时通知主窗口
        self.settingsMessage.emit(False, f"检查更新时出错: {error_message}") 