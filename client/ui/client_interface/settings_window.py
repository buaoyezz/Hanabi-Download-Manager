# ====================================================================
# 已废弃 - 设置已集成到主窗口，不再需要单独的设置窗口
# 此文件保留用于参考和向后兼容
# ====================================================================

from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QMessageBox
from client.ui.client_interface.settings.general_control import GeneralControlWidget
from client.ui.client_interface.settings.download_control import DownloadControlWidget
from client.ui.client_interface.settings.network_control import NetworkControlWidget

class SettingsWindow(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        # 设置窗口属性
        self.setWindowTitle("Hanabi Download Manager 设置")
        self.resize(800, 600)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        
        # 常规设置页
        self.general_tab = GeneralControlWidget(self.config_manager)
        self.tab_widget.addTab(self.general_tab, "常规设置")
        
        # 下载设置页
        self.download_tab = DownloadControlWidget(self.config_manager)
        self.tab_widget.addTab(self.download_tab, "下载设置")
        
        # 网络设置页
        self.network_tab = NetworkControlWidget(self.config_manager)
        self.tab_widget.addTab(self.network_tab, "网络设置")
        
        layout.addWidget(self.tab_widget)
        
        # 连接信号
        self.general_tab.settings_applied.connect(self._handle_settings_message)
        self.download_tab.settings_applied.connect(self._handle_settings_message)
        self.network_tab.settings_applied.connect(self._handle_settings_message)
        
    def _handle_settings_message(self, success, message):
        if success:
            QMessageBox.information(self, "设置", message)
        else:
            QMessageBox.warning(self, "设置错误", message)
