from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager

class GeneralControlWidget(QWidget):
    """常规设置页面"""
    settings_applied = Signal(bool, str)  # 成功/失败, 消息

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        self.setup_ui()
        self.load_config()

    def load_config(self):
        """从配置文件加载设置"""
        try:
            # 界面设置
            ui_config = self.config_manager.get("ui", {})
            theme = ui_config.get("theme", "dark")
            language = ui_config.get("language", "zh_CN")
            show_notifications = ui_config.get("show_notifications", True)
            
            # 启动设置
            start_config = self.config_manager.get("app", {})
            auto_start = start_config.get("auto_start", False)
            check_updates = start_config.get("check_updates", True)
            restore_tasks = start_config.get("restore_tasks", True)
            
            # 设置控件值
            theme_index = 0 if theme == "dark" else 1
            self.theme_combo.setCurrentIndex(theme_index)
            
            lang_index = 0
            if language == "en":
                lang_index = 1
            self.language_combo.setCurrentIndex(lang_index)
            
            self.show_notifications_checkbox.setChecked(show_notifications)
            self.auto_start_checkbox.setChecked(auto_start)
            self.check_updates_checkbox.setChecked(check_updates)
            self.restore_tasks_checkbox.setChecked(restore_tasks)
            
        except Exception as e:
            self.settings_applied.emit(False, f"加载常规设置失败: {str(e)}")

    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ===== 界面设置组 =====
        ui_group = QGroupBox("界面设置")
        ui_layout = QVBoxLayout(ui_group)
        
        # 主题设置
        theme_layout = QHBoxLayout()
        theme_label = QLabel("界面主题:")
        self.font_manager.apply_font(theme_label)
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色主题", "浅色主题"])
        self.font_manager.apply_font(self.theme_combo)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        
        ui_layout.addLayout(theme_layout)
        
        # 语言设置
        language_layout = QHBoxLayout()
        language_label = QLabel("显示语言:")
        self.font_manager.apply_font(language_label)
        language_layout.addWidget(language_label)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["简体中文", "English"])
        self.font_manager.apply_font(self.language_combo)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()
        
        ui_layout.addLayout(language_layout)
        
        # 通知设置
        self.show_notifications_checkbox = QCheckBox("显示桌面通知")
        self.font_manager.apply_font(self.show_notifications_checkbox)
        ui_layout.addWidget(self.show_notifications_checkbox)
        
        main_layout.addWidget(ui_group)
        
        # ===== 启动设置组 =====
        startup_group = QGroupBox("启动设置")
        startup_layout = QVBoxLayout(startup_group)
        
        # 开机自启
        self.auto_start_checkbox = QCheckBox("开机时自动启动")
        self.font_manager.apply_font(self.auto_start_checkbox)
        startup_layout.addWidget(self.auto_start_checkbox)
        
        # 检查更新
        self.check_updates_checkbox = QCheckBox("启动时检查更新")
        self.font_manager.apply_font(self.check_updates_checkbox)
        startup_layout.addWidget(self.check_updates_checkbox)
        
        # 恢复任务
        self.restore_tasks_checkbox = QCheckBox("恢复未完成的下载任务")
        self.font_manager.apply_font(self.restore_tasks_checkbox)
        startup_layout.addWidget(self.restore_tasks_checkbox)
        
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
        """)
    
    def clear_cache(self):
        """清除缓存和历史记录"""
        try:
            # 在实际应用中，这里会实现缓存清理逻辑
            self.notify_manager.show_message("清除缓存", "缓存已成功清除")
            self.settings_applied.emit(True, "缓存已清除")
        except Exception as e:
            self.settings_applied.emit(False, f"清除缓存失败: {str(e)}")
    
    def reset_all_settings(self):
        """重置所有设置到默认状态"""
        try:
            # 在实际应用中，这里会实现重置所有设置的逻辑
            self.load_config()  # 重新加载默认配置
            self.notify_manager.show_message("重置设置", "所有设置已恢复到默认状态")
            self.settings_applied.emit(True, "所有设置已重置为默认值")
        except Exception as e:
            self.settings_applied.emit(False, f"重置所有设置失败: {str(e)}")
    
    def reset_settings(self):
        """重置当前页面设置"""
        try:
            self.theme_combo.setCurrentIndex(0)  # 深色主题
            self.language_combo.setCurrentIndex(0)  # 简体中文
            self.show_notifications_checkbox.setChecked(True)
            self.auto_start_checkbox.setChecked(False)
            self.check_updates_checkbox.setChecked(True)
            self.restore_tasks_checkbox.setChecked(True)
            
            self.settings_applied.emit(True, "已重置为默认设置")
        except Exception as e:
            self.settings_applied.emit(False, f"重置设置失败: {str(e)}")
    
    def apply_settings(self):
        """应用设置"""
        try:
            # 收集设置
            theme = "dark" if self.theme_combo.currentIndex() == 0 else "light"
            language = "zh_CN" if self.language_combo.currentIndex() == 0 else "en"
            show_notifications = self.show_notifications_checkbox.isChecked()
            
            auto_start = self.auto_start_checkbox.isChecked()
            check_updates = self.check_updates_checkbox.isChecked()
            restore_tasks = self.restore_tasks_checkbox.isChecked()
            
            # 保存界面设置
            ui_config = {
                "theme": theme,
                "language": language,
                "show_notifications": show_notifications
            }
            self.config_manager.set("ui", "theme", theme)
            self.config_manager.set("ui", "language", language)
            self.config_manager.set("ui", "show_notifications", show_notifications)
            
            # 保存启动设置
            self.config_manager.set("app", "auto_start", auto_start)
            self.config_manager.set("app", "check_updates", check_updates)
            self.config_manager.set("app", "restore_tasks", restore_tasks)
            
            # 保存配置
            self.config_manager.save_config()
            
            # 如果设置了开机自启动
            if auto_start:
                self._setup_autostart()
            else:
                self._remove_autostart()
            
            self.settings_applied.emit(True, "常规设置已成功保存")
        except Exception as e:
            self.settings_applied.emit(False, f"保存设置失败: {str(e)}")
    
    def _setup_autostart(self):
        """设置开机自启动"""
        # 此处应根据不同操作系统实现自启动设置
        # 例如Windows下可以写入注册表，Linux下可以创建desktop文件
        # 简单起见，这里只打印一个信息
        print("设置开机自启动")
    
    def _remove_autostart(self):
        """移除开机自启动"""
        # 此处应根据不同操作系统实现移除自启动设置
        print("移除开机自启动") 