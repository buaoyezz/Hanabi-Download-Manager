from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager
from client.ui.components.customMessagebox import CustomMessageBox
from client.ui.components.comboBox import CustomComboBox
from client.ui.components.checkBox import CustomCheckBox

class GeneralControlWidget(QWidget):
   
    settings_applied = Signal(bool, str)  # 成功/失败, 消息

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        self.setup_ui()
        self.load_config()

    def load_config(self):
        
        try:
            # 界面设置
            ui_config = self.config_manager.get("ui", {})
            theme = ui_config.get("theme", "dark")
            language = ui_config.get("language", "zh_CN")
            show_notifications = ui_config.get("show_notifications", True)
            
            # 启动设置
            start_config = self.config_manager.get("startup", {})
            auto_start = start_config.get("auto_start", False)
            check_updates = start_config.get("check_update", True)
            restore_tasks = start_config.get("restore_tasks", True)
            
            # 设置控件值
            # 设置主题和语言选择
            self.theme_combo.setCurrentByUserData(theme)
            self.language_combo.setCurrentByUserData(language)
            
            self.show_notifications_checkbox.setChecked(show_notifications)
            self.auto_start_checkbox.setChecked(auto_start)
            self.auto_update_checkbox.setChecked(check_updates)
            self.start_minimized_checkbox.setChecked(restore_tasks)
            self.close_to_tray_checkbox.setChecked(restore_tasks)
            
        except Exception as e:
            self.settings_applied.emit(False, f"加载常规设置失败: {str(e)}")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ===== 界面设置组 =====
        ui_group = QGroupBox("界面设置")
        ui_layout = QVBoxLayout(ui_group)
        
        # 主题选择
        theme_layout = QHBoxLayout()
        theme_label = QLabel("界面主题:")
        self.font_manager.apply_font(theme_label)
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = CustomComboBox()
        self.theme_combo.addIconItem("深色主题", "ic_fluent_dark_theme_24_regular", "dark")
        self.theme_combo.addIconItem("浅色主题", "ic_fluent_dark_theme_24_regular", "light")
        self.font_manager.apply_font(self.theme_combo)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        
        ui_layout.addLayout(theme_layout)
        
        # 语言设置
        language_layout = QHBoxLayout()
        language_label = QLabel("显示语言:")
        self.font_manager.apply_font(language_label)
        language_layout.addWidget(language_label)
        
        self.language_combo = CustomComboBox()
        self.language_combo.addIconItem("简体中文", "ic_fluent_globe_24_regular", "zh_CN")
        self.language_combo.addIconItem("English", "ic_fluent_globe_24_regular", "en")
        self.font_manager.apply_font(self.language_combo)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()
        
        ui_layout.addLayout(language_layout)
        
        # 通知设置
        self.show_notifications_checkbox = CustomCheckBox("显示桌面通知")
        self.font_manager.apply_font(self.show_notifications_checkbox)
        ui_layout.addWidget(self.show_notifications_checkbox)
        
        main_layout.addWidget(ui_group)
        
        # ===== 启动设置组 =====
        startup_group = QGroupBox("启动设置")
        startup_layout = QVBoxLayout(startup_group)
        
        # 开机自启
        self.auto_start_checkbox = CustomCheckBox("开机时自动启动")
        self.font_manager.apply_font(self.auto_start_checkbox)
        startup_layout.addWidget(self.auto_start_checkbox)
        
        # 启动时自动检查更新
        self.auto_update_checkbox = CustomCheckBox("启动时自动检查更新")
        self.font_manager.apply_font(self.auto_update_checkbox)
        startup_layout.addWidget(self.auto_update_checkbox)
        
        # 启动时最小化到系统托盘
        self.start_minimized_checkbox = CustomCheckBox("启动时最小化到系统托盘")
        self.font_manager.apply_font(self.start_minimized_checkbox)
        startup_layout.addWidget(self.start_minimized_checkbox)
        
        # 关闭时最小化到系统托盘
        self.close_to_tray_checkbox = CustomCheckBox("关闭时最小化到系统托盘")
        self.font_manager.apply_font(self.close_to_tray_checkbox)
        startup_layout.addWidget(self.close_to_tray_checkbox)
        
        startup_layout.addStretch()
        main_layout.addWidget(startup_group)
        
        # ===== 操作按钮组 =====
        operation_group = QGroupBox("高级操作")
        operation_layout = QVBoxLayout(operation_group)
        
        # 清除缓存按钮
        clear_layout = QHBoxLayout()
        clear_label = QLabel("清除软件缓存和历史记录:")
        self.font_manager.apply_font(clear_label)
        clear_layout.addWidget(clear_label)
        
        self.clear_cache_button = QPushButton("清除缓存")
        self.font_manager.apply_font(self.clear_cache_button)
        self.clear_cache_button.clicked.connect(self.clear_cache)
        clear_layout.addWidget(self.clear_cache_button)
        clear_layout.addStretch()
        
        operation_layout.addLayout(clear_layout)
        
        # 重置所有设置按钮
        reset_layout = QHBoxLayout()
        reset_label = QLabel("恢复所有设置到默认状态:")
        self.font_manager.apply_font(reset_label)
        reset_layout.addWidget(reset_label)
        
        self.reset_all_button = QPushButton("重置所有设置")
        self.font_manager.apply_font(self.reset_all_button)
        self.reset_all_button.clicked.connect(self.reset_all_settings)
        self.reset_all_button.setStyleSheet("color: #ff5252;")
        reset_layout.addWidget(self.reset_all_button)
        reset_layout.addStretch()
        
        operation_layout.addLayout(reset_layout)
        operation_layout.addStretch()
        
        main_layout.addWidget(operation_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # ===== 底部按钮 =====
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
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)
        
        # 设置样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 15px;
                color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #FFFFFF;
            }
            QCheckBox {
                color: #FFFFFF;
                spacing: 5px;
            }
            QComboBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #3C3C3C;
            }
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3F3F46;
                border: 1px solid #7E57C2;
            }
        """)
    
    def clear_cache(self):
        
        try:
            # 确认是否清除缓存
            reply = CustomMessageBox.question(
                self, "清除缓存", 
                "确定要清除所有缓存和历史记录吗？这将清空下载历史记录。",
                [("确定", True), ("取消", False)]
            )
            
            if reply:
                # 在实际应用中，这里会实现缓存清理逻辑
                self.notify_manager.show_message("清除缓存", "缓存已成功清除")
                self.settings_applied.emit(True, "缓存已清除")
        except Exception as e:
            self.settings_applied.emit(False, f"清除缓存失败: {str(e)}")
    
    def reset_all_settings(self):
       
        try:
            # 确认是否重置所有设置
            reply = CustomMessageBox.question(
                self, "重置设置", 
                "确定要将所有设置恢复到默认状态吗？这将清除所有自定义配置。",
                [("确定", True), ("取消", False)]
            )
            
            if reply:
                # 在实际应用中，这里会实现重置所有设置的逻辑
                self.load_config()  # 重新加载默认配置
                self.notify_manager.show_message("重置设置", "所有设置已恢复到默认状态")
                self.settings_applied.emit(True, "所有设置已重置为默认值")
        except Exception as e:
            self.settings_applied.emit(False, f"重置所有设置失败: {str(e)}")
    
    def reset_settings(self):
       
        try:
            # 重置本页面设置
            self.load_config()
            CustomMessageBox.info(self, "重置设置", "已重置本页面设置")
        except Exception as e:
            CustomMessageBox.error(self, "重置设置失败", str(e))
    
    def apply_settings(self):
       
        try:
            # 收集设置
            ui_config = {
                "theme": self.theme_combo.getCurrentUserData() or "dark",
                "language": self.language_combo.getCurrentUserData() or "zh_CN",
                "show_notifications": self.show_notifications_checkbox.isChecked()
            }
            
            startup_config = {
                "auto_start": self.auto_start_checkbox.isChecked(),
                "check_update": self.auto_update_checkbox.isChecked(),
                "restore_tasks": self.start_minimized_checkbox.isChecked()
            }
            
            # 更新配置
            self.config_manager._config["ui"] = ui_config
            self.config_manager._config["startup"] = startup_config
            
            # 保存配置
            if self.config_manager.save_config():
                # 处理自启动设置
                if self.auto_start_checkbox.isChecked():
                    self._setup_autostart()
                else:
                    self._remove_autostart()
                
                # 只发送信号，不显示额外通知
                self.settings_applied.emit(True, "常规设置已保存")
            else:
                raise Exception("保存配置失败")
        except Exception as e:
            # 只发送信号，不显示额外通知
            self.settings_applied.emit(False, f"应用设置失败: {str(e)}")
            # 不再显示额外的错误对话框
            # CustomMessageBox.error(self, "应用设置失败", str(e))
    
    def _setup_autostart(self):
      
        # 此处应根据不同操作系统实现自启动设置
        # 例如Windows下可以写入注册表，Linux下可以创建desktop文件
        # 简单起见，这里只打印一个信息
        print("设置开机自启动")
    
    def _remove_autostart(self):
     
        # 此处应根据不同操作系统实现移除自启动设置
        print("移除开机自启动") 