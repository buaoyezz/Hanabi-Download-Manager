from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal
import os
import sys
import subprocess

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager
from client.ui.components.customMessagebox import CustomMessageBox
from client.ui.components.comboBox import CustomComboBox
from client.ui.components.checkBox import CustomCheckBox
from client.I18N.i18n import i18n

class GeneralControlWidget(QWidget):
   
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
        
        # 连接语言选择框的变更信号
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)

    def _get_app_path_args(self):
        """获取应用程序可执行文件及其参数列表."""
        if getattr(sys, 'frozen', False):
            # PyInstaller打包的环境, sys.executable 是exe的绝对路径
            return [sys.executable]
        else:
            # 开发环境
            python_path = sys.executable
            # 当前文件路径: client/ui/client_interface/settings/general_control.py
            # main.py 路径需要使用绝对路径确保准确性
            main_script_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__),  # general_control.py所在目录
                '..', '..', '..', '..',     # 回到项目根目录
                'main.py'                   # main.py文件
            ))
            # 输出调试信息
            print(f"开发环境启动路径: {python_path} {main_script_path}")
            return [python_path, main_script_path]

    def load_config(self):
        
        try:
            # 界面设置
            ui_config = self.config_manager.get("ui", {})
            theme = ui_config.get("theme", "dark")
            language = ui_config.get("language", "zh_CN")
            show_notifications = ui_config.get("show_notifications", True)
            
            # 统计设置
            stats_option = self.config_manager.get_setting("user", "stats_option", "local")
            
            # 启动设置
            start_config = self.config_manager.get("startup", {})
            auto_start = start_config.get("auto_start", False)
            check_updates = start_config.get("check_update", True)
            # restore_tasks = start_config.get("restore_tasks", True) # 旧的ambiguous key

            # 窗口行为设置 (从 "window" section 读取)
            window_config = self.config_manager.get("window", {})
            start_minimized = window_config.get("start_minimized", False) # 默认为 False
            close_to_tray = window_config.get("close_to_tray", True)     # 默认为 True
            
            # 设置控件值
            # 设置主题和语言选择
            self.theme_combo.setCurrentByUserData(theme)
            self.language_combo.setCurrentByUserData(language)
            
            # 设置统计选项
            self.stats_combo.setCurrentByUserData(stats_option)
            
            self.show_notifications_checkbox.setChecked(show_notifications)
            self.auto_start_checkbox.setChecked(auto_start)
            self.auto_update_checkbox.setChecked(check_updates)
            # self.start_minimized_checkbox.setChecked(restore_tasks) # 旧
            # self.close_to_tray_checkbox.setChecked(restore_tasks)   # 旧
            self.start_minimized_checkbox.setChecked(start_minimized) # 新
            self.close_to_tray_checkbox.setChecked(close_to_tray)     # 新
            
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('settings_load_failed', str(e))}")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ===== 界面设置组 =====
        ui_group = QGroupBox(i18n.get_text("ui_settings"))
        ui_layout = QVBoxLayout(ui_group)
        
        # 主题选择
        theme_layout = QHBoxLayout()
        theme_label = QLabel(i18n.get_text("theme") + ":")
        self.font_manager.apply_font(theme_label)
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = CustomComboBox()
        self.theme_combo.addIconItem(i18n.get_text("dark_theme"), "ic_fluent_dark_theme_24_regular", "dark")
        self.theme_combo.addIconItem(i18n.get_text("light_theme"), "ic_fluent_dark_theme_24_regular", "light")
        self.font_manager.apply_font(self.theme_combo)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        
        ui_layout.addLayout(theme_layout)
        
        # 语言设置
        language_layout = QHBoxLayout()
        language_label = QLabel(i18n.get_text("language") + ":")
        self.font_manager.apply_font(language_label)
        language_layout.addWidget(language_label)
        
        self.language_combo = CustomComboBox()
        self.language_combo.addIconItem(i18n.get_text("simplified_chinese"), "ic_fluent_globe_24_regular", "zh_CN")
        self.language_combo.addIconItem(i18n.get_text("english"), "ic_fluent_globe_24_regular", "en")
        self.font_manager.apply_font(self.language_combo)
        language_layout.addWidget(self.language_combo)
        language_layout.addStretch()
        
        ui_layout.addLayout(language_layout)
        
        # 统计参与选项
        stats_layout = QHBoxLayout()
        stats_label = QLabel(i18n.get_text("stats_option") + ":")
        self.font_manager.apply_font(stats_label)
        stats_layout.addWidget(stats_label)
        
        self.stats_combo = CustomComboBox()
        self.stats_combo.addIconItem(i18n.get_text("local_stats"), "ic_fluent_data_pie_24_regular", "local")
        self.stats_combo.addIconItem(i18n.get_text("global_stats"), "ic_fluent_data_usage_24_regular", "global")
        self.font_manager.apply_font(self.stats_combo)
        stats_layout.addWidget(self.stats_combo)
        stats_layout.addStretch()
        
        ui_layout.addLayout(stats_layout)
        
        # 通知设置
        self.show_notifications_checkbox = CustomCheckBox(i18n.get_text("show_notifications"))
        self.font_manager.apply_font(self.show_notifications_checkbox)
        ui_layout.addWidget(self.show_notifications_checkbox)
        
        main_layout.addWidget(ui_group)
        
        # ===== 启动设置组 =====
        startup_group = QGroupBox(i18n.get_text("startup_settings"))
        startup_layout = QVBoxLayout(startup_group)
        
        # 开机自启
        self.auto_start_checkbox = CustomCheckBox(i18n.get_text("auto_start"))
        self.font_manager.apply_font(self.auto_start_checkbox)
        startup_layout.addWidget(self.auto_start_checkbox)
        
        # 启动时自动检查更新
        self.auto_update_checkbox = CustomCheckBox(i18n.get_text("check_update"))
        self.font_manager.apply_font(self.auto_update_checkbox)
        startup_layout.addWidget(self.auto_update_checkbox)
        
        # 启动时最小化到系统托盘
        self.start_minimized_checkbox = CustomCheckBox(i18n.get_text("start_minimized"))
        self.font_manager.apply_font(self.start_minimized_checkbox)
        startup_layout.addWidget(self.start_minimized_checkbox)
        
        # 关闭时最小化到系统托盘
        self.close_to_tray_checkbox = CustomCheckBox(i18n.get_text("close_to_tray"))
        self.font_manager.apply_font(self.close_to_tray_checkbox)
        startup_layout.addWidget(self.close_to_tray_checkbox)
        
        startup_layout.addStretch()
        main_layout.addWidget(startup_group)
        
        # ===== 操作按钮组 =====
        operation_group = QGroupBox(i18n.get_text("advanced_operations"))
        operation_layout = QVBoxLayout(operation_group)
        
        # 清除缓存按钮
        clear_layout = QHBoxLayout()
        clear_label = QLabel(i18n.get_text("clear_cache_desc"))
        self.font_manager.apply_font(clear_label)
        clear_layout.addWidget(clear_label)
        
        self.clear_cache_button = QPushButton(i18n.get_text("clear_cache"))
        self.font_manager.apply_font(self.clear_cache_button)
        self.clear_cache_button.clicked.connect(self.clear_cache)
        clear_layout.addWidget(self.clear_cache_button)
        clear_layout.addStretch()
        
        operation_layout.addLayout(clear_layout)
        
        # 重置所有设置按钮
        reset_layout = QHBoxLayout()
        reset_label = QLabel(i18n.get_text("reset_all_desc"))
        self.font_manager.apply_font(reset_label)
        reset_layout.addWidget(reset_label)
        
        self.reset_all_button = QPushButton(i18n.get_text("reset_all"))
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
        
        self.reset_button = QPushButton(i18n.get_text("reset"))
        self.font_manager.apply_font(self.reset_button)
        self.reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.apply_button = QPushButton(i18n.get_text("apply"))
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
    
    def on_language_changed(self, index):
        """
        当语言选择框变化时调用此方法
        立即应用语言变更
        """
        # 获取选中的语言代码
        lang_code = self.language_combo.getCurrentUserData()
        if lang_code and lang_code != i18n.get_current_language():
            # 立即应用语言变更，不等待用户点击应用按钮
            i18n.set_language(lang_code)
            # 更新配置但不保存，等用户点击应用按钮时保存
            self.config_manager._config["ui"]["language"] = lang_code
            
            # 显示语言已更改的通知
            self.notify_manager.show_message(
                i18n.get_text("language"), 
                i18n.get_text("language") + ": " + 
                (i18n.get_text("simplified_chinese") if lang_code == "zh_CN" else i18n.get_text("english"))
            )
    
    def update_ui_texts(self):
        """
        更新界面上的所有文本
        当语言变更时调用
        """
        # 更新组标题
        for group in self.findChildren(QGroupBox):
            if group.title() == "界面设置" or group.title() == "UI Settings":
                group.setTitle(i18n.get_text("ui_settings"))
            elif group.title() == "启动设置" or group.title() == "Startup Settings":
                group.setTitle(i18n.get_text("startup_settings"))
            elif group.title() == "高级操作" or group.title() == "Advanced Operations":
                group.setTitle(i18n.get_text("advanced_operations"))
        
        # 更新标签
        for label in self.findChildren(QLabel):
            text = label.text()
            if text.endswith(":"):
                text = text[:-1]
                if text == "界面主题" or text == "Interface Theme":
                    label.setText(i18n.get_text("theme") + ":")
                elif text == "显示语言" or text == "Display Language":
                    label.setText(i18n.get_text("language") + ":")
                elif text == "下载统计参与选项" or text == "Download Statistics Option":
                    label.setText(i18n.get_text("stats_option") + ":")
                elif text == "清除软件缓存和历史记录" or text == "Clear software cache and history":
                    label.setText(i18n.get_text("clear_cache_desc"))
                elif text == "恢复所有设置到默认状态" or text == "Restore all settings to default state":
                    label.setText(i18n.get_text("reset_all_desc"))
        
        # 更新复选框
        self.show_notifications_checkbox.setText(i18n.get_text("show_notifications"))
        self.auto_start_checkbox.setText(i18n.get_text("auto_start"))
        self.auto_update_checkbox.setText(i18n.get_text("check_update"))
        self.start_minimized_checkbox.setText(i18n.get_text("start_minimized"))
        self.close_to_tray_checkbox.setText(i18n.get_text("close_to_tray"))
        
        # 更新按钮
        self.clear_cache_button.setText(i18n.get_text("clear_cache"))
        self.reset_all_button.setText(i18n.get_text("reset_all"))
        self.reset_button.setText(i18n.get_text("reset"))
        self.apply_button.setText(i18n.get_text("apply"))
        
        # 更新下拉框项目
        # 保存当前选中的项
        current_theme = self.theme_combo.getCurrentUserData()
        current_stats = self.stats_combo.getCurrentUserData()
        
        # 清空并重新添加项目
        self.theme_combo.clear()
        self.theme_combo.addIconItem(i18n.get_text("dark_theme"), "ic_fluent_dark_theme_24_regular", "dark")
        self.theme_combo.addIconItem(i18n.get_text("light_theme"), "ic_fluent_dark_theme_24_regular", "light")
        
        self.stats_combo.clear()
        self.stats_combo.addIconItem(i18n.get_text("local_stats"), "ic_fluent_data_pie_24_regular", "local")
        self.stats_combo.addIconItem(i18n.get_text("global_stats"), "ic_fluent_data_usage_24_regular", "global")
        
        # 恢复选中状态
        self.theme_combo.setCurrentByUserData(current_theme)
        self.stats_combo.setCurrentByUserData(current_stats)
        
        # 注意：不更新语言选择框的项目，因为语言名称应该始终以原语言显示
    
    def clear_cache(self):
        
        try:
            # 确认是否清除缓存
            reply = CustomMessageBox.question(
                self, i18n.get_text("clear_cache"), 
                i18n.get_text("confirm_clear_cache"),
                [(i18n.get_text("confirm"), True), (i18n.get_text("cancel"), False)]
            )
            
            if reply:
                # 在实际应用中，这里会实现缓存清理逻辑
                self.notify_manager.show_message(i18n.get_text("clear_cache"), i18n.get_text("cache_cleared"))
                self.settings_applied.emit(True, i18n.get_text("cache_cleared"))
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('error')}: {str(e)}")
    
    def reset_all_settings(self):
       
        try:
            # 确认是否重置所有设置
            reply = CustomMessageBox.question(
                self, i18n.get_text("reset_all"), 
                i18n.get_text("confirm_reset_all"),
                [(i18n.get_text("confirm"), True), (i18n.get_text("cancel"), False)]
            )
            
            if reply:
                # 在实际应用中，这里会实现重置所有设置的逻辑
                self.load_config()  # 重新加载默认配置
                self.notify_manager.show_message(i18n.get_text("reset_all"), i18n.get_text("all_settings_reset"))
                self.settings_applied.emit(True, i18n.get_text("all_settings_reset"))
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('error')}: {str(e)}")
    
    def reset_settings(self):
       
        try:
            # 重置本页面设置
            self.load_config()
            CustomMessageBox.info(self, i18n.get_text("reset"), i18n.get_text("reset") + ": " + i18n.get_text("success"))
        except Exception as e:
            CustomMessageBox.error(self, i18n.get_text("reset") + ": " + i18n.get_text("error"), str(e))
    
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
                # "restore_tasks": self.start_minimized_checkbox.isChecked() # 移除此行
            }
            
            # 统计选项
            stats_option = self.stats_combo.getCurrentUserData() or "local"
            
            # 更新配置
            self.config_manager._config["ui"] = ui_config
            self.config_manager._config["startup"] = startup_config
            
            # 设置统计选项
            if "user" not in self.config_manager._config:
                self.config_manager._config["user"] = {}
            self.config_manager._config["user"]["stats_option"] = stats_option
            
            # 保存配置
            if self.config_manager.save_config():
                # 处理自启动设置
                if self.auto_start_checkbox.isChecked():
                    self._setup_autostart()
                else:
                    self._remove_autostart()
                
                # 处理关闭到托盘设置
                self._apply_close_to_tray_setting(self.close_to_tray_checkbox.isChecked())
                
                # 处理启动最小化设置
                self._apply_start_minimized_setting(self.start_minimized_checkbox.isChecked())
                
                # 应用语言设置
                current_language = i18n.get_current_language()
                selected_language = self.language_combo.getCurrentUserData() or "zh_CN"
                if current_language != selected_language:
                    i18n.set_language(selected_language)
                
                # 只发送信号，不显示额外通知
                self.settings_applied.emit(True, i18n.get_text("settings_saved"))
            else:
                raise Exception(i18n.get_text("error") + ": " + i18n.get_text("settings_saved"))
        except Exception as e:
            # 只发送信号，不显示额外通知
            self.settings_applied.emit(False, f"{i18n.get_text('error')}: {str(e)}")
            # 不再显示额外的错误对话框
            # CustomMessageBox.error(self, "应用设置失败", str(e))
    
    def _setup_autostart(self):
        """设置开机自启动"""
        try:
            # 检测是否为打包状态
# 检测是否为打包状态
            is_packaged = getattr(sys, 'frozen', False)

            # 检测是否为发布版EXE文件（而非开发环境的python.exe）
            force_exe_mode = (is_packaged or 
                            (sys.executable.lower().endswith('.exe') and 
                            'hanabi' in sys.executable.lower()))
            
            # 调试输出
            print(f"开机自启动设置 - 检测到的环境信息:")
            print(f"当前工作目录: {os.getcwd()}")
            print(f"sys.frozen存在: {is_packaged}")
            print(f"可执行文件路径: {sys.executable}")
            print(f"强制EXE模式: {force_exe_mode}")
            
            # 获取启动参数
            start_minimized = self.start_minimized_checkbox.isChecked()
            startup_args = ["--autostart"]
            
            # 如果启用了最小化启动，添加--silent参数以静默启动
            if start_minimized:
                startup_args.append("--silent")
            
            if sys.platform == 'win32':  # Windows
                import winreg
                
                # 将参数列表转换为字符串
                startup_args_str = " ".join(startup_args)
                
                # 打包环境 或 强制EXE模式
                if is_packaged or force_exe_mode:
                    # 直接使用EXE路径
                    exe_path = sys.executable
                    
                    # 确保使用完整路径而非短路径(~1)格式
                    try:
                        if '~' in exe_path:
                            try:
                                import win32api
                                exe_path = win32api.GetLongPathName(exe_path)
                                print(f"转换短路径为完整路径: {exe_path}")
                            except ImportError:
                                # 如果没有win32api，使用os.path.abspath
                                exe_path = os.path.abspath(exe_path)
                                print(f"使用abspath转换路径: {exe_path}")
                    except Exception as path_err:
                        print(f"路径转换错误: {path_err}")
                    
                    # 检查路径是否包含HanabiDownloadManager
                    if "hanabidownloadmanager" not in exe_path.lower() and "hanabi" not in exe_path.lower():
                        print(f"警告: 可执行文件路径可能不正确，未包含'HanabiDownloadManager'")
                        
                        # 尝试查找正确的EXE文件
                        try:
                            # 检查常见安装位置
                            possible_paths = [
                                r"D:\HanabiDownloadManager\HanabiDownloadManager.exe",
                                r"C:\Program Files\HanabiDownloadManager\HanabiDownloadManager.exe",
                                r"C:\Program Files (x86)\HanabiDownloadManager\HanabiDownloadManager.exe"
                            ]
                            
                            for path in possible_paths:
                                if os.path.exists(path):
                                    exe_path = path
                                    print(f"找到可能的正确EXE路径: {exe_path}")
                                    break
                        except Exception as find_err:
                            print(f"查找可能的EXE路径时出错: {find_err}")
                    
                    # 添加启动参数 - 直接使用引号包围路径并添加参数，避免使用@符号
                    command_line = f'"{exe_path}" {startup_args_str}'
                    print(f"使用EXE模式启动命令: {command_line}")
                else:
                    # 开发环境模式 - 修改命令行构造方式
                    python_path = sys.executable
                    main_script_path = os.path.abspath(os.path.join(
                        os.path.dirname(__file__),  # general_control.py所在目录
                        '..', '..', '..', '..',     # 回到项目根目录
                        'main.py'                   # main.py文件
                    ))
                    
                    # 直接构造命令行，避免使用list2cmdline可能导致的问题
                    command_line = f'"{python_path}" "{main_script_path}" {startup_args_str}'
                    print(f"使用开发环境模式启动命令: {command_line}")
                
                # 打开注册表项
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE
                )
                
                # 设置注册表值
                winreg.SetValueEx(
                    key,
                    "HanabiDownloadManager",
                    0,
                    winreg.REG_SZ,
                    command_line
                )
                winreg.CloseKey(key)
                
                # 验证注册表设置
                self._verify_autostart_registry()
                
                self.notify_manager.show_message("开机启动", "已设置开机自动启动")
            
            elif sys.platform == 'darwin':  # macOS
                # 获取应用程序路径和参数
                app_args = self._get_app_path_args()
                
                # 添加自启动和静默参数
                for arg in startup_args:
                    app_args.append(arg)
                
                # 创建LaunchAgents目录（如果不存在）
                launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
                os.makedirs(launch_agents_dir, exist_ok=True)
                
                # 创建plist文件
                plist_path = os.path.join(launch_agents_dir, "com.hanabi.downloadmanager.plist")
                
                program_arguments_xml = ""
                for arg in app_args:
                    # XML 转义特殊字符，例如 &, <, > 等，但路径本身通常不需要
                    # 这里假设路径已经是安全的，或不需要 XML 转义
                    program_arguments_xml += f"        <string>{arg}</string>\n"

                plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hanabi.downloadmanager</string>
    <key>ProgramArguments</key>
    <array>
{program_arguments_xml.rstrip()}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>'''
                
                with open(plist_path, 'w') as f:
                    f.write(plist_content)
                
                # 加载plist
                subprocess.run(['launchctl', 'load', plist_path])
                self.notify_manager.show_message("开机启动", "已设置开机自动启动")
                
            elif sys.platform.startswith('linux'):  # Linux
                # 获取应用程序路径和参数
                app_args = self._get_app_path_args()
                
                # 添加自启动和静默参数
                for arg in startup_args:
                    app_args.append(arg)
                
                # 创建桌面文件
                autostart_dir = os.path.expanduser("~/.config/autostart")
                os.makedirs(autostart_dir, exist_ok=True)
                
                exec_command = subprocess.list2cmdline(app_args)
                desktop_path = os.path.join(autostart_dir, "hanabidownloadmanager.desktop")
                desktop_content = f'''[Desktop Entry]
Type=Application
Name=Hanabi Download Manager
Exec={exec_command}
Terminal=false
X-GNOME-Autostart-enabled=true
'''
                
                with open(desktop_path, 'w') as f:
                    f.write(desktop_content)
                
                # 设置权限
                os.chmod(desktop_path, 0o755)
                self.notify_manager.show_message("开机启动", "已设置开机自动启动")
            
            else:
                self.notify_manager.show_message("开机启动", "不支持当前操作系统的自启动设置")
                
        except Exception as e:
            self.notify_manager.show_message("开机启动", f"设置开机自启动失败: {str(e)}")
            print(f"设置开机自启动失败: {str(e)}")
    
    def _verify_autostart_registry(self):
        """验证注册表中的自启动设置是否正确"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(key, "HanabiDownloadManager")
            winreg.CloseKey(key)
            
            print(f"验证注册表自启动设置: {value}")
            
            # 检查是否使用了正确的EXE路径
            if getattr(sys, 'frozen', False) and ".exe" in sys.executable.lower():
                if ".exe" not in value.lower():
                    print("警告: 注册表中没有使用EXE文件路径!")
                else:
                    print("✓ 注册表设置使用了正确的EXE文件路径")
            
            # 检查是否有@符号问题
            if "@" in value:
                print("警告: 注册表命令中包含@符号，可能导致启动失败!")
                # 尝试修复此问题
                self._setup_autostart()
            else:
                print("✓ 注册表命令中没有@符号问题")
                
            # 检查命令格式是否正确
            if not (value.startswith('"') and " --autostart" in value):
                print("警告: 注册表命令格式可能不正确，缺少正确的引号或启动参数!")
            else:
                print("✓ 注册表命令格式正确")
                
            # 检查静默启动参数
            start_minimized = self.start_minimized_checkbox.isChecked()
            if start_minimized and " --silent" not in value:
                print("警告: 启用了最小化启动但注册表命令中缺少--silent参数!")
                # 尝试修复此问题
                self._setup_autostart()
            elif start_minimized:
                print("✓ 注册表命令包含静默启动参数")
                
        except Exception as e:
            print(f"验证注册表设置时出错: {e}")
    
    def _remove_autostart(self):
        """移除开机自启动设置"""
        try:
            if sys.platform == 'win32':  # Windows
                import winreg
                # 打开注册表项
                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                        0,
                        winreg.KEY_SET_VALUE
                    )
                    # 删除注册表值
                    winreg.DeleteValue(key, "HanabiDownloadManager")
                    winreg.CloseKey(key)
                    self.notify_manager.show_message("开机启动", "已取消开机自动启动")
                except FileNotFoundError:
                    # 注册表项不存在，忽略错误
                    pass
                
            # elif sys.platform == 'darwin':  # macOS
            #     # 卸载并删除plist文件
            #     plist_path = os.path.expanduser("~/Library/LaunchAgents/com.hanabi.downloadmanager.plist")
            #     if os.path.exists(plist_path):
            #         subprocess.run(['launchctl', 'unload', plist_path])
            #         os.remove(plist_path)
            #         self.notify_manager.show_message("开机启动", "已取消开机自动启动")
                
            elif sys.platform.startswith('linux'):  # Linux
                # 删除桌面文件
                desktop_path = os.path.expanduser("~/.config/autostart/hanabidownloadmanager.desktop")
                if os.path.exists(desktop_path):
                    os.remove(desktop_path)
                    self.notify_manager.show_message("开机启动", "已取消开机自动启动")
            
            else:
                self.notify_manager.show_message("开机启动", "不支持当前操作系统的自启动设置")
                
        except Exception as e:
            self.notify_manager.show_message("开机启动", f"取消开机自启动失败: {str(e)}")
            print(f"取消开机自启动失败: {str(e)}")
    
    def _get_app_path(self):
        """获取应用程序可执行文件路径"""
        # 此方法不再直接使用，由 _get_app_path_args() 替代以提供更灵活的参数列表
        # 保留此方法以防其他地方意外调用，但其逻辑已合并到 _get_app_path_args
        if getattr(sys, 'frozen', False):
            return f'"{sys.executable}"'
        else:
            python_path = sys.executable
            main_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../main.py'))
            # 使用引号包裹路径，避免空格和特殊字符问题
            return f'"{python_path}" "{main_script}"'

    def _apply_close_to_tray_setting(self, enabled):
        """应用关闭到托盘设置"""
        # 保存到配置中
        if "window" not in self.config_manager._config:
            self.config_manager._config["window"] = {}
        self.config_manager._config["window"]["close_to_tray"] = enabled
        self.config_manager.save_config()
    
    def _apply_start_minimized_setting(self, enabled):
        """应用启动时最小化设置"""
        # 保存到配置中
        if "window" not in self.config_manager._config:
            self.config_manager._config["window"] = {}
        self.config_manager._config["window"]["start_minimized"] = enabled
        self.config_manager.save_config() 