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
from client.I18N.i18n import i18n

class NetworkControlWidget(QWidget):
    settings_applied = Signal(bool, str)  # 成功/失败, 消息

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        self.setup_ui()
        self.load_config()
        
        # 连接语言变更信号，动态更新UI文本
        i18n.language_changed.connect(self.update_ui_texts)

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
            self.settings_applied.emit(False, f"{i18n.get_text('network_settings_load_failed')}: {str(e)}")

    def setup_ui(self):
       
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 代理设置组
        self.proxy_group = QGroupBox(i18n.get_text("proxy_settings"))
        proxy_layout = QVBoxLayout(self.proxy_group)
        
        # 启用代理
        self.enable_proxy_checkbox = CustomCheckBox(i18n.get_text("enable_proxy"))
        self.font_manager.apply_font(self.enable_proxy_checkbox)
        self.enable_proxy_checkbox.toggled.connect(self.update_ui_state)
        proxy_layout.addWidget(self.enable_proxy_checkbox)
        
        # 代理类型
        proxy_type_row = QHBoxLayout()
        self.proxy_type_label = QLabel(i18n.get_text("proxy_type") + ":")
        self.proxy_type_label.setMinimumWidth(80)
        self.font_manager.apply_font(self.proxy_type_label)
        proxy_type_row.addWidget(self.proxy_type_label)
        
        self.proxy_type_combo = CustomComboBox()
        self.proxy_type_combo.addIconItem(i18n.get_text("http_proxy"), "ic_fluent_globe_24_regular", "http")
        self.proxy_type_combo.addIconItem(i18n.get_text("socks5_proxy"), "ic_fluent_shield_24_regular", "socks5")
        self.proxy_type_combo.addIconItem(i18n.get_text("direct_connection"), "ic_fluent_arrow_routing_24_regular", "direct")
        self.font_manager.apply_font(self.proxy_type_combo)
        proxy_type_row.addWidget(self.proxy_type_combo)
        proxy_type_row.addStretch()
        proxy_layout.addLayout(proxy_type_row)
        
        # 代理地址和端口
        proxy_server_layout = QHBoxLayout()
        self.server_label = QLabel(i18n.get_text("server") + ":")
        self.font_manager.apply_font(self.server_label)
        proxy_server_layout.addWidget(self.server_label)
        
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText(i18n.get_text("proxy_host_placeholder"))
        self.font_manager.apply_font(self.proxy_host_input)
        proxy_server_layout.addWidget(self.proxy_host_input, 3)
        
        self.port_label = QLabel(i18n.get_text("port") + ":")
        self.font_manager.apply_font(self.port_label)
        proxy_server_layout.addWidget(self.port_label)
        
        self.proxy_port_spinbox = CustomSpinBox()
        self.proxy_port_spinbox.setRange(0, 65535)
        self.proxy_port_spinbox.setSingleStep(1)
        self.proxy_port_spinbox.setSuffix(i18n.get_text("port"))
        self.font_manager.apply_font(self.proxy_port_spinbox)
        proxy_server_layout.addWidget(self.proxy_port_spinbox, 1)
        proxy_layout.addLayout(proxy_server_layout)
        
        # 代理认证
        self.auth_required_checkbox = CustomCheckBox(i18n.get_text("requires_authentication"))
        self.font_manager.apply_font(self.auth_required_checkbox)
        self.auth_required_checkbox.toggled.connect(self.update_ui_state)
        proxy_layout.addWidget(self.auth_required_checkbox)
        
        # 用户名和密码
        auth_layout = QVBoxLayout()
        
        username_layout = QHBoxLayout()
        self.username_label = QLabel(i18n.get_text("username") + ":")
        self.font_manager.apply_font(self.username_label)
        username_layout.addWidget(self.username_label)
        
        self.username_input = QLineEdit()
        self.font_manager.apply_font(self.username_input)
        username_layout.addWidget(self.username_input)
        auth_layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        self.password_label = QLabel(i18n.get_text("password") + ":")
        self.font_manager.apply_font(self.password_label)
        password_layout.addWidget(self.password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.font_manager.apply_font(self.password_input)
        password_layout.addWidget(self.password_input)
        auth_layout.addLayout(password_layout)
        
        proxy_layout.addLayout(auth_layout)
        main_layout.addWidget(self.proxy_group)
        
        # 速度限制设置组
        self.speed_group = QGroupBox(i18n.get_text("speed_limits"))
        speed_layout = QVBoxLayout(self.speed_group)
        
        # 下载速度限制
        download_limit_layout = QHBoxLayout()
        self.download_limit_checkbox = CustomCheckBox(i18n.get_text("limit_download_speed") + ":")
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
        self.upload_limit_checkbox = CustomCheckBox(i18n.get_text("limit_upload_speed") + ":")
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
        main_layout.addWidget(self.speed_group)
        
        # User-Agent设置组
        self.ua_group = QGroupBox(i18n.get_text("user_agent_settings"))
        ua_layout = QVBoxLayout(self.ua_group)
        
        # 设置UA
        ua_desc_label = QLabel(i18n.get_text("user_agent_description"))
        ua_desc_label.setWordWrap(True)
        self.font_manager.apply_font(ua_desc_label)
        ua_layout.addWidget(ua_desc_label)
        
        ua_input_layout = QHBoxLayout()
        self.ua_label = QLabel("User-Agent:")
        self.font_manager.apply_font(self.ua_label)
        ua_input_layout.addWidget(self.ua_label)
        
        self.user_agent_input = QLineEdit()
        self.user_agent_input.setPlaceholderText(i18n.get_text("user_agent_placeholder"))
        self.font_manager.apply_font(self.user_agent_input)
        ua_input_layout.addWidget(self.user_agent_input)
        ua_layout.addLayout(ua_input_layout)
        
        # 常用UA选择
        ua_presets_layout = QHBoxLayout()
        self.ua_preset_label = QLabel(i18n.get_text("common_user_agents") + ":")
        self.font_manager.apply_font(self.ua_preset_label)
        ua_presets_layout.addWidget(self.ua_preset_label)
        
        self.ua_preset_combo = CustomComboBox()
        self.ua_preset_combo.addItem(i18n.get_text("select_user_agent"))
        self.ua_preset_combo.addItem("Chrome")
        self.ua_preset_combo.addItem("Firefox")
        self.ua_preset_combo.addItem("Edge")
        self.ua_preset_combo.addItem("Safari")
        self.ua_preset_combo.addItem(i18n.get_text("default_downloader"))
        self.font_manager.apply_font(self.ua_preset_combo)
        self.ua_preset_combo.currentIndexChanged.connect(self.on_ua_preset_changed)
        ua_presets_layout.addWidget(self.ua_preset_combo)
        ua_presets_layout.addStretch()
        ua_layout.addLayout(ua_presets_layout)
        
        main_layout.addWidget(self.ua_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        # 重置按钮
        self.reset_button = QPushButton(i18n.get_text("reset"))
        self.font_manager.apply_font(self.reset_button)
        self.reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        # 应用按钮
        self.apply_button = QPushButton(i18n.get_text("apply"))
        self.font_manager.apply_font(self.apply_button)
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)
        
        # 应用样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit {
                background-color: #2D2D30;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #B39DDB;
            }
            QPushButton {
                background-color: #455A64;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:pressed {
                background-color: #37474F;
            }
            QPushButton#apply_button {
                background-color: #7E57C2;
            }
            QPushButton#apply_button:hover {
                background-color: #9575CD;
            }
            QPushButton#apply_button:pressed {
                background-color: #673AB7;
            }
        """)
        
        # 初始化
        self.apply_button.setObjectName("apply_button")
        self.update_ui_state()
        
    def update_ui_texts(self):
        """更新界面上的所有文本"""
        # 更新组标题
        self.proxy_group.setTitle(i18n.get_text("proxy_settings"))
        self.speed_group.setTitle(i18n.get_text("speed_limits"))
        self.ua_group.setTitle(i18n.get_text("user_agent_settings"))
        
        # 更新复选框
        self.enable_proxy_checkbox.setText(i18n.get_text("enable_proxy"))
        self.auth_required_checkbox.setText(i18n.get_text("requires_authentication"))
        self.download_limit_checkbox.setText(i18n.get_text("limit_download_speed") + ":")
        self.upload_limit_checkbox.setText(i18n.get_text("limit_upload_speed") + ":")
        
        # 更新标签
        self.proxy_type_label.setText(i18n.get_text("proxy_type") + ":")
        self.server_label.setText(i18n.get_text("server") + ":")
        self.port_label.setText(i18n.get_text("port") + ":")
        self.username_label.setText(i18n.get_text("username") + ":")
        self.password_label.setText(i18n.get_text("password") + ":")
        self.ua_label.setText("User-Agent:")
        self.ua_preset_label.setText(i18n.get_text("common_user_agents") + ":")
        
        # 更新下拉框
        self.proxy_type_combo.setItemText(0, i18n.get_text("http_proxy"))
        self.proxy_type_combo.setItemText(1, i18n.get_text("socks5_proxy"))
        self.proxy_type_combo.setItemText(2, i18n.get_text("direct_connection"))
        
        # 更新UA预设
        self.ua_preset_combo.setItemText(0, i18n.get_text("select_user_agent"))
        self.ua_preset_combo.setItemText(5, i18n.get_text("default_downloader"))
        
        # 更新输入框提示
        self.proxy_host_input.setPlaceholderText(i18n.get_text("proxy_host_placeholder"))
        self.user_agent_input.setPlaceholderText(i18n.get_text("user_agent_placeholder"))
        
        # 更新按钮
        self.reset_button.setText(i18n.get_text("reset"))
        self.apply_button.setText(i18n.get_text("apply"))
        
        # 更新其他文本
        self.proxy_port_spinbox.setSuffix(i18n.get_text("port"))

    def on_ua_preset_changed(self, index):
        """处理UA预设选择变更"""
        if index == 0:  # "选择常用UA"
            return
        
        ua = ""
        if index == 1:  # Chrome
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        elif index == 2:  # Firefox
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        elif index == 3:  # Edge
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
        elif index == 4:  # Safari
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        elif index == 5:  # 下载器默认
            ua = "HanabiDownloadManager/1.0"
            
        self.user_agent_input.setText(ua)
        self.ua_preset_combo.setCurrentIndex(0)  # 重置为"选择常用UA"

    def update_ui_state(self):
        """根据UI状态更新控件启用/禁用状态"""
        # 代理设置的启用/禁用状态
        proxy_enabled = self.enable_proxy_checkbox.isChecked()
        self.proxy_type_label.setEnabled(proxy_enabled)
        self.proxy_type_combo.setEnabled(proxy_enabled)
        self.server_label.setEnabled(proxy_enabled)
        self.proxy_host_input.setEnabled(proxy_enabled)
        self.port_label.setEnabled(proxy_enabled)
        self.proxy_port_spinbox.setEnabled(proxy_enabled)
        self.auth_required_checkbox.setEnabled(proxy_enabled)
        
        # 认证相关控件
        auth_enabled = proxy_enabled and self.auth_required_checkbox.isChecked()
        self.username_label.setEnabled(auth_enabled)
        self.username_input.setEnabled(auth_enabled)
        self.password_label.setEnabled(auth_enabled)
        self.password_input.setEnabled(auth_enabled)
        
        # 下载限速
        self.download_limit_spinbox.setEnabled(self.download_limit_checkbox.isChecked())
        
        # 上传限速
        self.upload_limit_spinbox.setEnabled(self.upload_limit_checkbox.isChecked())

    def reset_settings(self):
        """重置网络设置"""
        self.load_config()
        self.settings_applied.emit(True, i18n.get_text("network_settings_reset"))

    def apply_settings(self):
        """应用网络设置"""
        try:
            # 获取代理设置
            enable_proxy = self.enable_proxy_checkbox.isChecked()
            proxy_type = self.proxy_type_combo.currentUserData() or "http"
            proxy_host = self.proxy_host_input.text().strip()
            proxy_port = self.proxy_port_spinbox.value()
            
            auth_required = self.auth_required_checkbox.isChecked()
            username = self.username_input.text()
            password = self.password_input.text()
            
            # 获取UA设置
            user_agent = self.user_agent_input.text().strip()
            
            # 获取限速设置
            download_limit_enabled = self.download_limit_checkbox.isChecked()
            download_limit = self.download_limit_spinbox.value() if download_limit_enabled else 0
            
            upload_limit_enabled = self.upload_limit_checkbox.isChecked()
            upload_limit = self.upload_limit_spinbox.value() if upload_limit_enabled else 0
            
            # 验证代理设置
            if enable_proxy and not proxy_host and proxy_type != "direct":
                raise ValueError(i18n.get_text("proxy_host_required"))
            
            if enable_proxy and proxy_type != "direct" and proxy_port <= 0:
                raise ValueError(i18n.get_text("proxy_port_required"))
                
            if enable_proxy and auth_required and not username:
                raise ValueError(i18n.get_text("proxy_username_required"))
            
            # 构建网络配置
            network_config = self.config_manager.get("network", {})
            
            # 更新代理配置
            proxy_config = {
                "enable": enable_proxy,
                "type": proxy_type,
                "host": proxy_host,
                "port": proxy_port,
                "auth_required": auth_required,
                "username": username,
                "password": password
            }
            
            # 更新网络配置
            network_config["proxy"] = proxy_config
            network_config["user_agent"] = user_agent
            network_config["download_limit"] = download_limit if download_limit_enabled else 0
            network_config["upload_limit"] = upload_limit if upload_limit_enabled else 0
            
            # 保存配置
            self.config_manager.set("network", network_config)
            success = self.config_manager.save_config()
            
            if success:
                self.settings_applied.emit(True, i18n.get_text("network_settings_saved"))
            else:
                raise ValueError(i18n.get_text("save_settings_failed"))
                
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('apply_network_settings_failed')}: {str(e)}")