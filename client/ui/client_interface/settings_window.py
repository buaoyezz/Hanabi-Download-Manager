# ====================================================================
# 已废弃 - 设置已集成到主窗口，不再需要单独的设置窗口
# 此文件保留用于参考和向后兼容
# ====================================================================

from PySide6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QSizePolicy, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from client.ui.client_interface.settings.general_control import GeneralControlWidget
from client.ui.client_interface.settings.download_control import DownloadControlWidget
from client.ui.client_interface.settings.network_control import NetworkControlWidget
from client.ui.components.customMessagebox import CustomMessageBox
from core.font.font_manager import FontManager

class IconLabel(QLabel):
    def __init__(self, icon_name, size=24, color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        self.icon_name = icon_name
        self.icon_size = size
        self.icon_color = color
        self.setup_icon()
        
    def setup_icon(self):
        # 确保icon_name前缀正确
        if not self.icon_name.startswith("ic_fluent_"):
            self.icon_name = f"ic_fluent_{self.icon_name}"
            
        # 直接设置图标字体
        icon_font = QFont("FluentSystemIcons-Regular")
        icon_font.setPixelSize(self.icon_size)
        self.setFont(icon_font)
        
        # 获取图标文本并设置
        icon_text = self.font_manager.get_icon_text(self.icon_name)
        
        # 如果找不到图标，使用硬编码的Unicode
        if not icon_text:
            icon_codes = {
                "ic_fluent_settings_24_regular": "\uF8B0", 
                "ic_fluent_download_24_regular": "\uF416",
                "ic_fluent_globe_24_regular": "\uF46A",
                "ic_fluent_checkmark_24_regular": "\uF37C",
                "ic_fluent_dismiss_24_regular": "\uF36A"
            }
            icon_text = icon_codes.get(self.icon_name, "●")
            
        self.setText(icon_text)
        
        # 设置样式和对齐方式
        self.setStyleSheet(f"""
            QLabel {{
                color: {self.icon_color};
                background-color: transparent;
                padding: 2px;
                font-family: "FluentSystemIcons-Regular";
            }}
        """)
        self.setAlignment(Qt.AlignCenter)
        
        # 设置固定大小和可见性
        self.setFixedSize(self.icon_size+8, self.icon_size+8)
        self.setMinimumSize(self.icon_size+8, self.icon_size+8)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.show()

class TabHeader(QWidget):
    def __init__(self, icon_name, text, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)
        
        # 图标标签 - 使用IconLabel
        if not icon_name.startswith("ic_fluent_"):
            icon_name = f"ic_fluent_{icon_name}"
            
        icon_label = IconLabel(icon_name, size=18, parent=self)  # 使用更大的图标尺寸
        
        # 文本标签
        text_label = QLabel(text)
        text_label.setFont(QFont("Microsoft YaHei UI", 10))
        text_label.setStyleSheet("color: #FFFFFF;")
        
        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()
        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

class ActionButton(QPushButton):
    def __init__(self, icon_name, text, primary=True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        
        # 设置按钮样式
        if primary:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #7E57C2;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 120px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #9575CD;
                }
                QPushButton:pressed {
                    background-color: #673AB7;
                }
                QPushButton:disabled {
                    background-color: #424242;
                    color: #757575;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2D2D30;
                    color: #FFFFFF;
                    border: 1px solid #3C3C3C;
                    border-radius: 6px;
                    padding: 8px 16px;
                    min-width: 100px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #3E3E42;
                    border: 1px solid #B39DDB;
                }
                QPushButton:pressed {
                    background-color: #252526;
                }
            """)
        
        # 设置图标Unicode
        icon_codes = {
            "ic_fluent_settings_24_regular": "\uF8B0", 
            "ic_fluent_download_24_regular": "\uF416",
            "ic_fluent_globe_24_regular": "\uF46A",
            "ic_fluent_checkmark_24_regular": "\uF37C",
            "ic_fluent_dismiss_24_regular": "\uF36A"
        }
        icon_code = icon_codes.get(f"ic_fluent_{icon_name}" if not icon_name.startswith("ic_fluent_") else icon_name, "●")
        
        # 设置字体包含Fluent图标和文本
        self.setText(f" {icon_code}  {text}")
        self.setFont(QFont("FluentSystemIcons-Regular, Microsoft YaHei UI", 10))

class SettingsWindow(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        
        # 设置窗口属性
        self.setWindowTitle("Hanabi Download Manager 设置")
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #252526;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2D2D30;
                color: #CCCCCC;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                padding: 8px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #3E3E42;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: #383838;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 常规设置页
        self.general_tab = GeneralControlWidget(self.config_manager)
        general_header = TabHeader("ic_fluent_settings_24_regular", "常规设置")
        self.tab_widget.addTab(self.general_tab, "")
        self.tab_widget.setTabText(0, "常规设置")
        self.tab_widget.tabBar().setTabButton(0, QTabWidget.LeftSide, general_header)
        
        # 下载设置页
        self.download_tab = DownloadControlWidget(self.config_manager)
        download_header = TabHeader("ic_fluent_download_24_regular", "下载设置")
        self.tab_widget.addTab(self.download_tab, "")
        self.tab_widget.setTabText(1, "下载设置")
        self.tab_widget.tabBar().setTabButton(1, QTabWidget.LeftSide, download_header)
        
        # 网络设置页
        self.network_tab = NetworkControlWidget(self.config_manager)
        network_header = TabHeader("ic_fluent_globe_24_regular", "网络设置")
        self.tab_widget.addTab(self.network_tab, "")
        self.tab_widget.setTabText(2, "网络设置")
        self.tab_widget.tabBar().setTabButton(2, QTabWidget.LeftSide, network_header)
        
        layout.addWidget(self.tab_widget)
        
        # 添加底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        # 取消按钮
        self.cancel_button = ActionButton("ic_fluent_dismiss_24_regular", "取消", False)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        button_layout.addStretch()
        
        # 确定按钮
        self.ok_button = ActionButton("ic_fluent_checkmark_24_regular", "确定")
        self.ok_button.clicked.connect(self.accept_and_save)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.general_tab.settings_applied.connect(self._handle_settings_message)
        self.download_tab.settings_applied.connect(self._handle_settings_message)
        self.network_tab.settings_applied.connect(self._handle_settings_message)
    
    def accept_and_save(self):
        # 应用所有页面的设置
        self.general_tab.apply_settings()
        self.download_tab.apply_settings()
        self.network_tab.apply_settings()
        self.accept()
        
    def _handle_settings_message(self, success, message):
        if success:
            CustomMessageBox.information(self, "设置", message)
        else:
            CustomMessageBox.warning(self, "设置错误", message)
