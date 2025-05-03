from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QRadioButton, QLineEdit, 
    QPushButton, QSpinBox, QComboBox, QCheckBox
)
from PySide6.QtGui import QIntValidator

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager
from client.ui.components.customMessagebox import CustomMessageBox
from client.ui.components.comboBox import CustomComboBox
from client.ui.components.spinBox import CustomSpinBox
from client.ui.components.checkBox import CustomCheckBox

class NetworkControlWidget(QWidget):
    settings_applied = Signal(bool, str)  # 成功/失败, 消息

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        self.setup_ui()
        self.load_config()

    def load_config(self):
        """加载网络配置"""
        try:
            # 获取网络配置
            network_config = self.config_manager.get("network", {})
            
            # 设置UA
            user_agent = network_config.get("user_agent", "")
            self.user_agent_input.setText(user_agent)
            
            # 设置代理
            proxy_config = network_config.get("proxy", {})
            
            # 代理启用状态
            enable_proxy = proxy_config.get("enable", False)
            self.enable_proxy_checkbox.setChecked(enable_proxy)
            
            # 代理类型
            proxy_type = proxy_config.get("type", "http").lower()
            # 使用用户数据设置代理类型
            self.proxy_type_combo.setCurrentByUserData(proxy_type)
            
            # 代理地址和端口
            proxy_host = proxy_config.get("host", "")
            self.proxy_host_input.setText(proxy_host)
            
            proxy_port = proxy_config.get("port", 0)
            self.proxy_port_spinbox.setValue(proxy_port)
            
            # 代理认证
            auth_required = proxy_config.get("auth_required", False)
            self.auth_required_checkbox.setChecked(auth_required)
            
            username = proxy_config.get("username", "")
            self.username_input.setText(username)
            
            password = proxy_config.get("password", "")
            self.password_input.setText(password)
            
            # 更新UI状态
            self.update_ui_state()
            
        except Exception as e:
            self.settings_applied.emit(False, f"加载网络设置失败: {str(e)}")

    def setup_ui(self):
       
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 代理设置组
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QVBoxLayout(proxy_group)
        
        # 启用代理
        self.enable_proxy_checkbox = CustomCheckBox("启用代理")
        self.font_manager.apply_font(self.enable_proxy_checkbox)
        self.enable_proxy_checkbox.toggled.connect(self.update_ui_state)
        proxy_layout.addWidget(self.enable_proxy_checkbox)
        
        # 代理类型
        proxy_type_row = QHBoxLayout()
        proxy_type_label = QLabel("代理类型:")
        proxy_type_label.setMinimumWidth(80)
        self.font_manager.apply_font(proxy_type_label)
        proxy_type_row.addWidget(proxy_type_label)
        
        self.proxy_type_combo = CustomComboBox()
        self.proxy_type_combo.addIconItem("HTTP", "ic_fluent_globe_24_regular", "http")
        self.proxy_type_combo.addIconItem("SOCKS5", "ic_fluent_shield_24_regular", "socks5")
        self.proxy_type_combo.addIconItem("DIRECT", "ic_fluent_arrow_routing_24_regular", "direct")
        self.font_manager.apply_font(self.proxy_type_combo)
        proxy_type_row.addWidget(self.proxy_type_combo)
        proxy_type_row.addStretch()
        proxy_layout.addLayout(proxy_type_row)
        
        # 代理地址和端口
        proxy_server_layout = QHBoxLayout()
        server_label = QLabel("服务器:")
        self.font_manager.apply_font(server_label)
        proxy_server_layout.addWidget(server_label)
        
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("例如: 127.0.0.1")
        self.font_manager.apply_font(self.proxy_host_input)
        proxy_server_layout.addWidget(self.proxy_host_input, 3)
        
        port_label = QLabel("端口:")
        self.font_manager.apply_font(port_label)
        proxy_server_layout.addWidget(port_label)
        
        self.proxy_port_spinbox = CustomSpinBox()
        self.proxy_port_spinbox.setRange(0, 65535)
        self.proxy_port_spinbox.setSingleStep(1)
        self.proxy_port_spinbox.setSuffix("端口")
        self.font_manager.apply_font(self.proxy_port_spinbox)
        proxy_server_layout.addWidget(self.proxy_port_spinbox, 1)
        proxy_layout.addLayout(proxy_server_layout)
        
        # 代理认证
        self.auth_required_checkbox = CustomCheckBox("需要认证")
        self.font_manager.apply_font(self.auth_required_checkbox)
        self.auth_required_checkbox.toggled.connect(self.update_ui_state)
        proxy_layout.addWidget(self.auth_required_checkbox)
        
        # 用户名和密码
        auth_layout = QVBoxLayout()
        
        username_layout = QHBoxLayout()
        username_label = QLabel("用户名:")
        self.font_manager.apply_font(username_label)
        username_layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.font_manager.apply_font(self.username_input)
        username_layout.addWidget(self.username_input)
        auth_layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_label = QLabel("密码:")
        self.font_manager.apply_font(password_label)
        password_layout.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.font_manager.apply_font(self.password_input)
        password_layout.addWidget(self.password_input)
        auth_layout.addLayout(password_layout)
        
        proxy_layout.addLayout(auth_layout)
        main_layout.addWidget(proxy_group)
        
        # 速度限制设置组
        speed_group = QGroupBox("速度限制")
        speed_layout = QVBoxLayout(speed_group)
        
        # 下载速度限制
        download_limit_layout = QHBoxLayout()
        self.download_limit_checkbox = CustomCheckBox("限制下载速度:")
        self.font_manager.apply_font(self.download_limit_checkbox)
        self.download_limit_checkbox.toggled.connect(self.update_ui_state)
        download_limit_layout.addWidget(self.download_limit_checkbox)
        
        self.download_limit_spinbox = CustomSpinBox()
        self.download_limit_spinbox.setRange(0, 1000000)
        self.download_limit_spinbox.setSingleStep(100)
        self.download_limit_spinbox.setSuffix(" KB/s")
        self.font_manager.apply_font(self.download_limit_spinbox)
        download_limit_layout.addWidget(self.download_limit_spinbox)
        download_limit_layout.addStretch()
        speed_layout.addLayout(download_limit_layout)
        
        # 上传速度限制
        upload_limit_layout = QHBoxLayout()
        self.upload_limit_checkbox = CustomCheckBox("限制上传速度:")
        self.font_manager.apply_font(self.upload_limit_checkbox)
        self.upload_limit_checkbox.toggled.connect(self.update_ui_state)
        upload_limit_layout.addWidget(self.upload_limit_checkbox)
        
        self.upload_limit_spinbox = CustomSpinBox()
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

    def update_ui_state(self):
        proxy_enabled = self.enable_proxy_checkbox.isChecked()
        self.proxy_type_combo.setEnabled(proxy_enabled)
        self.proxy_host_input.setEnabled(proxy_enabled)
        self.proxy_port_spinbox.setEnabled(proxy_enabled)
        self.auth_required_checkbox.setEnabled(proxy_enabled)
        
        auth_enabled = proxy_enabled and self.auth_required_checkbox.isChecked()
        self.username_input.setEnabled(auth_enabled)
        self.password_input.setEnabled(auth_enabled)

    def reset_settings(self):
        """重置为默认设置"""
        try:
            # 重置本页面设置
            self.load_config()
            CustomMessageBox.info(self, "重置设置", "已重置本页面设置")
        except Exception as e:
            CustomMessageBox.error(self, "重置设置失败", str(e))
    
    def apply_settings(self):
        """应用网络设置"""
        try:
            # 收集网络设置
            user_agent = self.user_agent_input.text().strip()
            
            # 代理设置
            enable_proxy = self.enable_proxy_checkbox.isChecked()
            # 获取代理类型用户数据
            proxy_type = self.proxy_type_combo.getCurrentUserData() or "http"
            proxy_host = self.proxy_host_input.text().strip()
            proxy_port = self.proxy_port_spinbox.value()
            
            auth_required = self.auth_required_checkbox.isChecked()
            username = self.username_input.text().strip()
            password = self.password_input.text().strip()
            
            # 验证设置
            if enable_proxy:
                if not proxy_host or proxy_port <= 0:
                    raise ValueError("启用代理时，必须提供有效的代理服务器和端口")
                    
                if auth_required and (not username or not password):
                    raise ValueError("启用代理认证时，必须提供用户名和密码")
            
            # 更新网络配置
            network_config = {
                "user_agent": user_agent,
                "proxy": {
                    "enable": enable_proxy,
                "type": proxy_type,
                "host": proxy_host,
                    "port": proxy_port,
                    "auth_required": auth_required,
                    "username": username,
                    "password": password
            }
            }
            
            # 更新配置
            self.config_manager._config["network"] = network_config
            
            # 保存配置
            if self.config_manager.save_config():
                self.settings_applied.emit(True, "网络设置已保存")
            else:
                raise Exception("保存配置失败")
                
        except ValueError as ve:
            self.settings_applied.emit(False, str(ve))
        except Exception as e:
            self.settings_applied.emit(False, f"应用设置失败: {str(e)}")