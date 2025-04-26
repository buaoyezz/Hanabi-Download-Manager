from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QRadioButton, QLineEdit, 
    QPushButton, QSpinBox, QComboBox, QCheckBox
)
from PySide6.QtGui import QIntValidator

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager

class NetworkControlWidget(QWidget):
    """网络控制设置页面"""
    settings_applied = Signal(bool, str)  # 成功/失败, 消息

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        self.setup_ui()
        self.load_config()

    def load_config(self):
        """从配置文件加载网络设置"""
        try:
            # 获取网络配置
            network_config = self.config_manager.get("network", {})
            
            # 代理设置
            proxy_config = network_config.get("proxy", {})
            proxy_enabled = proxy_config.get("enabled", False)
            proxy_type = proxy_config.get("type", "http")
            proxy_host = proxy_config.get("host", "")
            proxy_port = proxy_config.get("port", 1080)
            proxy_auth = proxy_config.get("auth", False)
            proxy_username = proxy_config.get("username", "")
            proxy_password = proxy_config.get("password", "")
            
            # 速度限制
            speed_config = network_config.get("speed_limit", {})
            download_limit_enabled = speed_config.get("download_enabled", False)
            download_limit = speed_config.get("download_limit", 0)
            upload_limit_enabled = speed_config.get("upload_enabled", False)
            upload_limit = speed_config.get("upload_limit", 0)
            
            # 设置UI控件值
            self.proxy_enabled_checkbox.setChecked(proxy_enabled)
            self._set_proxy_type(proxy_type)
            self.proxy_host_edit.setText(proxy_host)
            self.proxy_port_edit.setText(str(proxy_port))
            self.proxy_auth_checkbox.setChecked(proxy_auth)
            self.proxy_username_edit.setText(proxy_username)
            self.proxy_password_edit.setText(proxy_password)
            
            self.download_limit_checkbox.setChecked(download_limit_enabled)
            self.download_limit_spinbox.setValue(download_limit)
            self.upload_limit_checkbox.setChecked(upload_limit_enabled)
            self.upload_limit_spinbox.setValue(upload_limit)
            
            # 更新UI状态
            self._update_proxy_ui_state()
            self._update_speed_limit_ui_state()
        except Exception as e:
            self.settings_applied.emit(False, f"加载网络设置失败: {str(e)}")

    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 代理设置组
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QVBoxLayout(proxy_group)
        
        # 启用代理
        self.proxy_enabled_checkbox = QCheckBox("启用代理")
        self.font_manager.apply_font(self.proxy_enabled_checkbox)
        self.proxy_enabled_checkbox.toggled.connect(self._update_proxy_ui_state)
        proxy_layout.addWidget(self.proxy_enabled_checkbox)
        
        # 代理类型
        proxy_type_layout = QHBoxLayout()
        proxy_type_label = QLabel("代理类型:")
        self.font_manager.apply_font(proxy_type_label)
        proxy_type_layout.addWidget(proxy_type_label)
        
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["HTTP", "SOCKS5", "SOCKS4"])
        self.font_manager.apply_font(self.proxy_type_combo)
        proxy_type_layout.addWidget(self.proxy_type_combo)
        proxy_type_layout.addStretch()
        proxy_layout.addLayout(proxy_type_layout)
        
        # 代理地址和端口
        proxy_server_layout = QHBoxLayout()
        server_label = QLabel("服务器:")
        self.font_manager.apply_font(server_label)
        proxy_server_layout.addWidget(server_label)
        
        self.proxy_host_edit = QLineEdit()
        self.proxy_host_edit.setPlaceholderText("例如: 127.0.0.1")
        self.font_manager.apply_font(self.proxy_host_edit)
        proxy_server_layout.addWidget(self.proxy_host_edit, 3)
        
        port_label = QLabel("端口:")
        self.font_manager.apply_font(port_label)
        proxy_server_layout.addWidget(port_label)
        
        self.proxy_port_edit = QLineEdit()
        self.proxy_port_edit.setValidator(QIntValidator(1, 65535))
        self.proxy_port_edit.setPlaceholderText("1080")
        self.proxy_port_edit.setMaximumWidth(80)
        self.font_manager.apply_font(self.proxy_port_edit)
        proxy_server_layout.addWidget(self.proxy_port_edit, 1)
        proxy_layout.addLayout(proxy_server_layout)
        
        # 代理认证
        self.proxy_auth_checkbox = QCheckBox("需要认证")
        self.font_manager.apply_font(self.proxy_auth_checkbox)
        self.proxy_auth_checkbox.toggled.connect(self._update_proxy_ui_state)
        proxy_layout.addWidget(self.proxy_auth_checkbox)
        
        # 用户名和密码
        auth_layout = QVBoxLayout()
        
        username_layout = QHBoxLayout()
        username_label = QLabel("用户名:")
        self.font_manager.apply_font(username_label)
        username_layout.addWidget(username_label)
        
        self.proxy_username_edit = QLineEdit()
        self.font_manager.apply_font(self.proxy_username_edit)
        username_layout.addWidget(self.proxy_username_edit)
        auth_layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_label = QLabel("密码:")
        self.font_manager.apply_font(password_label)
        password_layout.addWidget(password_label)
        
        self.proxy_password_edit = QLineEdit()
        self.proxy_password_edit.setEchoMode(QLineEdit.Password)
        self.font_manager.apply_font(self.proxy_password_edit)
        password_layout.addWidget(self.proxy_password_edit)
        auth_layout.addLayout(password_layout)
        
        proxy_layout.addLayout(auth_layout)
        main_layout.addWidget(proxy_group)
        
        # 速度限制设置组
        speed_group = QGroupBox("速度限制")
        speed_layout = QVBoxLayout(speed_group)
        
        # 下载速度限制
        download_limit_layout = QHBoxLayout()
        self.download_limit_checkbox = QCheckBox("限制下载速度:")
        self.font_manager.apply_font(self.download_limit_checkbox)
        self.download_limit_checkbox.toggled.connect(self._update_speed_limit_ui_state)
        download_limit_layout.addWidget(self.download_limit_checkbox)
        
        self.download_limit_spinbox = QSpinBox()
        self.download_limit_spinbox.setRange(0, 1000000)
        self.download_limit_spinbox.setSingleStep(100)
        self.download_limit_spinbox.setSuffix(" KB/s")
        self.font_manager.apply_font(self.download_limit_spinbox)
        download_limit_layout.addWidget(self.download_limit_spinbox)
        download_limit_layout.addStretch()
        speed_layout.addLayout(download_limit_layout)
        
        # 上传速度限制
        upload_limit_layout = QHBoxLayout()
        self.upload_limit_checkbox = QCheckBox("限制上传速度:")
        self.font_manager.apply_font(self.upload_limit_checkbox)
        self.upload_limit_checkbox.toggled.connect(self._update_speed_limit_ui_state)
        upload_limit_layout.addWidget(self.upload_limit_checkbox)
        
        self.upload_limit_spinbox = QSpinBox()
        self.upload_limit_spinbox.setRange(0, 1000000)
        self.upload_limit_spinbox.setSingleStep(100)
        self.upload_limit_spinbox.setSuffix(" KB/s")
        self.font_manager.apply_font(self.upload_limit_spinbox)
        upload_limit_layout.addWidget(self.upload_limit_spinbox)
        upload_limit_layout.addStretch()
        speed_layout.addLayout(upload_limit_layout)
        
        speed_layout.addStretch()
        main_layout.addWidget(speed_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        self.reset_button = QPushButton("重置")
        self.font_manager.apply_font(self.reset_button)
        self.reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.apply_button = QPushButton("应用")
        self.font_manager.apply_font(self.apply_button)
        self.apply_button.clicked.connect(self.apply_settings)
        self.apply_button.setDefault(True)
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)

        # 设置样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #aaa;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #e0e0e0;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 5px;
            }
            QLineEdit {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555;
            }
            QPushButton {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #444;
                border: 1px solid #0078D7;
            }
            QSpinBox {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
            }
        """)

    def _set_proxy_type(self, proxy_type):
        """设置代理类型下拉框"""
        index = 0
        if proxy_type.lower() == "http":
            index = 0
        elif proxy_type.lower() == "socks5":
            index = 1
        elif proxy_type.lower() == "socks4":
            index = 2
        self.proxy_type_combo.setCurrentIndex(index)

    def _get_proxy_type(self):
        """获取当前选择的代理类型"""
        index = self.proxy_type_combo.currentIndex()
        if index == 0:
            return "http"
        elif index == 1:
            return "socks5"
        elif index == 2:
            return "socks4"
        return "http"

    def _update_proxy_ui_state(self):
        """更新代理设置UI的启用状态"""
        proxy_enabled = self.proxy_enabled_checkbox.isChecked()
        self.proxy_type_combo.setEnabled(proxy_enabled)
        self.proxy_host_edit.setEnabled(proxy_enabled)
        self.proxy_port_edit.setEnabled(proxy_enabled)
        self.proxy_auth_checkbox.setEnabled(proxy_enabled)
        
        auth_enabled = proxy_enabled and self.proxy_auth_checkbox.isChecked()
        self.proxy_username_edit.setEnabled(auth_enabled)
        self.proxy_password_edit.setEnabled(auth_enabled)

    def _update_speed_limit_ui_state(self):
        """更新速度限制UI的启用状态"""
        self.download_limit_spinbox.setEnabled(self.download_limit_checkbox.isChecked())
        self.upload_limit_spinbox.setEnabled(self.upload_limit_checkbox.isChecked())

    def reset_settings(self):
        """重置设置为当前配置值"""
        self.load_config()
        self.settings_applied.emit(True, "网络设置已重置")

    def apply_settings(self):
        """应用当前设置"""
        try:
            # 收集代理设置
            proxy_config = {
                "enabled": self.proxy_enabled_checkbox.isChecked(),
                "type": self._get_proxy_type(),
                "host": self.proxy_host_edit.text().strip(),
                "port": int(self.proxy_port_edit.text() or "1080"),
                "auth": self.proxy_auth_checkbox.isChecked(),
                "username": self.proxy_username_edit.text(),
                "password": self.proxy_password_edit.text()
            }
            
            # 收集速度限制设置
            speed_config = {
                "download_enabled": self.download_limit_checkbox.isChecked(),
                "download_limit": self.download_limit_spinbox.value(),
                "upload_enabled": self.upload_limit_checkbox.isChecked(),
                "upload_limit": self.upload_limit_spinbox.value()
            }
            
            # 保存到配置
            self.config_manager.set("network", "proxy", proxy_config)
            self.config_manager.set("network", "speed_limit", speed_config)
            self.config_manager.save_config()
            
            self.notify_manager.show_message("网络设置", "网络设置已成功应用")
            self.settings_applied.emit(True, "网络设置已成功应用")
        except Exception as e:
            self.notify_manager.show_message("网络设置", f"应用网络设置失败: {str(e)}", level="error")
            self.settings_applied.emit(False, f"应用网络设置失败: {str(e)}") 