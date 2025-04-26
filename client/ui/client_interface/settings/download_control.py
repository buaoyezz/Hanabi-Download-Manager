from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QSpinBox, QSlider, QLineEdit,
    QFileDialog, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator

from client.ui.components.customNotify import NotifyManager
from core.font.font_manager import FontManager
from pathlib import Path

class DownloadControlWidget(QWidget):
    """下载控制设置页面，整合线程、网络和文件保存设置"""
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
            # 下载设置
            download_config = self.config_manager.get("download", {})
            
            # 线程设置
            thread_count = download_config.get("thread_count", 8)
            dynamic_threads = download_config.get("dynamic_threads", True)
            max_threads = download_config.get("max_thread_count", 32)
            min_segment_size = download_config.get("min_segment_size", 10)
            max_tasks = download_config.get("max_tasks", 5) # 从 thread_control 移入
            buffer_size = download_config.get("buffer_size", 8192) # 从 thread_control 移入
            chunk_size = download_config.get("chunk_size", 1024 * 1024) # 从 thread_control 移入
            
            # 下载路径设置
            save_path = download_config.get("save_path", 
                                              str(Path.home() / "Downloads"))
            auto_organize = download_config.get("auto_organize", False)
            
            # 下载行为设置
            auto_start = download_config.get("auto_start", True)
            max_retries = download_config.get("max_retries", 3)
            
            # 打印调试信息
            print(f"[DEBUG] 加载配置 - 线程数: {thread_count}, 动态线程: {dynamic_threads}")
            print(f"[DEBUG] 加载配置 - 最大线程数: {max_threads}, 最小分段大小: {min_segment_size}MB")
            
            # 设置控件值
            self.max_tasks_spinbox.setValue(max_tasks)
            self.thread_count_spinbox.setValue(thread_count)
            self.dynamic_threads_checkbox.setChecked(dynamic_threads)
            self.max_threads_spinbox.setValue(max_threads)
            self.segment_size_spinbox.setValue(min_segment_size)
            self.buffer_spinbox.setValue(buffer_size // 1024) # KB
            self.chunk_spinbox.setValue(chunk_size // (1024 * 1024)) # MB
            
            self.path_edit.setText(save_path)
            self.auto_organize_checkbox.setChecked(auto_organize)
            
            self.auto_start_checkbox.setChecked(auto_start)
            self.max_retries_spinbox.setValue(max_retries)
            
            # 更新UI状态
            self.update_ui_state()
            
        except Exception as e:
            self.settings_applied.emit(False, f"加载下载设置失败: {str(e)}")
            print(f"[ERROR] 加载下载设置失败: {str(e)}")

    def setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ===== 并行任务设置组 =====
        tasks_group = QGroupBox("并行下载任务")
        tasks_group.setStyleSheet("""
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
        """)
        tasks_layout = QVBoxLayout(tasks_group)
        tasks_layout.setContentsMargins(15, 20, 15, 15)
        tasks_layout.setSpacing(10)

        tasks_description = QLabel("设置同时可以执行的下载任务数量。增加任务数可以同时下载更多文件，但会消耗更多系统资源。")
        tasks_description.setWordWrap(True)
        tasks_description.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(tasks_description)
        tasks_layout.addWidget(tasks_description)

        tasks_control_layout = QHBoxLayout()
        tasks_control_layout.setSpacing(10)
        tasks_label = QLabel("最大任务数:")
        tasks_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(tasks_label)
        tasks_control_layout.addWidget(tasks_label)

        self.max_tasks_spinbox = QSpinBox()
        self.max_tasks_spinbox.setRange(1, 20)
        self.max_tasks_spinbox.setValue(5)
        self.max_tasks_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                min-width: 60px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3E3E42;
                width: 16px;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #525257;
            }
        """)
        self.font_manager.apply_font(self.max_tasks_spinbox)
        tasks_control_layout.addWidget(self.max_tasks_spinbox)

        tasks_slider = QSlider(Qt.Horizontal)
        tasks_slider.setRange(1, 20)
        tasks_slider.setValue(5)
        tasks_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3C3C3C;
                height: 8px;
                background: #2D2D30;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #B39DDB;
                border: 1px solid #B39DDB;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #9575CD;
            }
        """)
        tasks_slider.valueChanged.connect(self.max_tasks_spinbox.setValue)
        self.max_tasks_spinbox.valueChanged.connect(tasks_slider.setValue)
        tasks_control_layout.addWidget(tasks_slider, 1)

        tasks_layout.addLayout(tasks_control_layout)
        main_layout.addWidget(tasks_group)
        
        # ===== 线程设置组 =====
        thread_group = QGroupBox("单任务线程设置")
        thread_group.setStyleSheet("""
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
        """)
        thread_layout = QVBoxLayout(thread_group)
        thread_layout.setContentsMargins(15, 20, 15, 15)
        thread_layout.setSpacing(10)
        
        # 线程数量控制
        thread_count_layout = QHBoxLayout()
        thread_count_layout.setSpacing(10)
        thread_count_label = QLabel("默认线程数:")
        thread_count_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(thread_count_label)
        thread_count_layout.addWidget(thread_count_label)
        
        self.thread_count_spinbox = QSpinBox()
        self.thread_count_spinbox.setRange(1, 64)
        self.thread_count_spinbox.setValue(8)
        self.thread_count_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                min-width: 60px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3E3E42;
                width: 16px;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #525257;
            }
        """)
        self.font_manager.apply_font(self.thread_count_spinbox)
        thread_count_layout.addWidget(self.thread_count_spinbox)
        
        thread_slider = QSlider(Qt.Horizontal)
        thread_slider.setRange(1, 64)
        thread_slider.setValue(8)
        thread_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3C3C3C;
                height: 8px;
                background: #2D2D30;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #B39DDB;
                border: 1px solid #B39DDB;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #9575CD;
            }
        """)
        thread_slider.valueChanged.connect(self.thread_count_spinbox.setValue)
        self.thread_count_spinbox.valueChanged.connect(thread_slider.setValue)
        thread_count_layout.addWidget(thread_slider, 1)
        
        thread_layout.addLayout(thread_count_layout)
        
        # 动态线程
        dynamic_thread_layout = QVBoxLayout()
        dynamic_thread_layout.setSpacing(5)
        self.dynamic_threads_checkbox = QCheckBox("启用智能线程管理（根据网络情况自动调整线程数）")
        self.dynamic_threads_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #3C3C3C;
                background: #2D2D30;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #B39DDB;
                background-color: #B39DDB;
                border-radius: 3px;
                image: url(resources/icons/check.png);
            }
        """)
        self.font_manager.apply_font(self.dynamic_threads_checkbox)
        self.dynamic_threads_checkbox.toggled.connect(self.update_ui_state)
        dynamic_thread_layout.addWidget(self.dynamic_threads_checkbox)
        
        # 添加关闭动态自动线程调节按钮
        self.disable_auto_threads_btn = QPushButton("关闭动态自动线程调节")
        self.disable_auto_threads_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a3c4c;
                color: #e0e0e0;
                border: 1px solid #6a526d;
                border-radius: 3px;
                padding: 5px 15px;
                margin-left: 25px;
            }
            QPushButton:hover {
                background-color: #6a526d;
            }
        """)
        self.font_manager.apply_font(self.disable_auto_threads_btn)
        self.disable_auto_threads_btn.clicked.connect(self.disable_dynamic_threads)
        dynamic_thread_layout.addWidget(self.disable_auto_threads_btn)
        
        thread_layout.addLayout(dynamic_thread_layout)
        
        # 高级线程设置 (最大线程数, 最小分段)
        advanced_thread_layout = QHBoxLayout()
        advanced_thread_layout.setSpacing(10)
        
        max_threads_label = QLabel("最大线程数:")
        max_threads_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(max_threads_label)
        advanced_thread_layout.addWidget(max_threads_label)
        
        self.max_threads_spinbox = QSpinBox()
        self.max_threads_spinbox.setRange(4, 64)
        self.max_threads_spinbox.setValue(32)
        self.max_threads_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                min-width: 60px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3E3E42;
                width: 16px;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #525257;
            }
        """)
        self.font_manager.apply_font(self.max_threads_spinbox)
        advanced_thread_layout.addWidget(self.max_threads_spinbox)
        
        segment_size_label = QLabel("最小分段大小(MB):")
        segment_size_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(segment_size_label)
        advanced_thread_layout.addWidget(segment_size_label)
        
        self.segment_size_spinbox = QSpinBox()
        self.segment_size_spinbox.setRange(1, 100)
        self.segment_size_spinbox.setValue(10)
        self.segment_size_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
                min-width: 60px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3E3E42;
                width: 16px;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #525257;
            }
        """)
        self.font_manager.apply_font(self.segment_size_spinbox)
        advanced_thread_layout.addWidget(self.segment_size_spinbox)
        
        advanced_thread_layout.addStretch()
        
        thread_layout.addLayout(advanced_thread_layout)
        main_layout.addWidget(thread_group)

        # ===== 缓冲与分块设置组 =====
        buffer_group = QGroupBox("下载缓冲与分块")
        buffer_group.setStyleSheet("""
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
        """)
        buffer_layout = QVBoxLayout(buffer_group)
        buffer_layout.setContentsMargins(15, 20, 15, 15)
        buffer_layout.setSpacing(10)

        buffer_description = QLabel("缓冲区大小和分块大小控制下载过程中的内存使用和效率。较大的值可能提高下载速度，但会占用更多内存。")
        buffer_description.setWordWrap(True)
        buffer_description.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(buffer_description)
        buffer_layout.addWidget(buffer_description)

        buffer_size_layout = QHBoxLayout()
        buffer_label = QLabel("缓冲区大小(KB):")
        self.font_manager.apply_font(buffer_label)
        buffer_size_layout.addWidget(buffer_label)

        self.buffer_spinbox = QSpinBox()
        self.buffer_spinbox.setRange(1, 64)
        self.buffer_spinbox.setValue(8) # 默认8KB
        self.font_manager.apply_font(self.buffer_spinbox)
        buffer_size_layout.addWidget(self.buffer_spinbox)
        buffer_size_layout.addStretch()
        buffer_layout.addLayout(buffer_size_layout)

        chunk_size_layout = QHBoxLayout()
        chunk_label = QLabel("分块大小(MB):")
        self.font_manager.apply_font(chunk_label)
        chunk_size_layout.addWidget(chunk_label)

        self.chunk_spinbox = QSpinBox()
        self.chunk_spinbox.setRange(1, 32)
        self.chunk_spinbox.setValue(1) # 默认1MB
        self.font_manager.apply_font(self.chunk_spinbox)
        chunk_size_layout.addWidget(self.chunk_spinbox)
        chunk_size_layout.addStretch()
        buffer_layout.addLayout(chunk_size_layout)
        main_layout.addWidget(buffer_group)
        
        # ===== 保存路径设置组 =====
        path_group = QGroupBox("保存路径")
        path_layout = QVBoxLayout(path_group)
        
        # 下载路径
        path_input_layout = QHBoxLayout()
        path_label = QLabel("默认下载位置:")
        self.font_manager.apply_font(path_label)
        path_input_layout.addWidget(path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(Path.home() / "Downloads"))
        self.font_manager.apply_font(self.path_edit)
        path_input_layout.addWidget(self.path_edit, 1)
        
        self.browse_button = QPushButton("浏览...")
        self.font_manager.apply_font(self.browse_button)
        self.browse_button.clicked.connect(self.browse_folder)
        path_input_layout.addWidget(self.browse_button)
        
        path_layout.addLayout(path_input_layout)
        
        # 自动整理文件
        self.auto_organize_checkbox = QCheckBox("根据文件类型自动整理到不同文件夹")
        self.font_manager.apply_font(self.auto_organize_checkbox)
        path_layout.addWidget(self.auto_organize_checkbox)
        
        main_layout.addWidget(path_group)
        
        # ===== 下载行为设置组 =====
        behavior_group = QGroupBox("下载行为")
        behavior_layout = QVBoxLayout(behavior_group)
        
        # 自动开始下载
        self.auto_start_checkbox = QCheckBox("添加任务后自动开始下载")
        self.font_manager.apply_font(self.auto_start_checkbox)
        behavior_layout.addWidget(self.auto_start_checkbox)
        
        # 重试设置
        retry_layout = QHBoxLayout()
        retry_label = QLabel("最大重试次数:")
        self.font_manager.apply_font(retry_label)
        retry_layout.addWidget(retry_label)
        
        self.max_retries_spinbox = QSpinBox()
        self.max_retries_spinbox.setRange(0, 10)
        self.max_retries_spinbox.setValue(3)
        self.font_manager.apply_font(self.max_retries_spinbox)
        retry_layout.addWidget(self.max_retries_spinbox)
        
        retry_layout.addStretch()
        behavior_layout.addLayout(retry_layout)
        
        main_layout.addWidget(behavior_group)
        
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
            QLineEdit {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
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
            QPushButton#apply_button {
                background-color: #0078D7;
                border: none;
            }
            QPushButton#apply_button:hover {
                background-color: #1C97EA;
            }
            QSpinBox {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 3px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3C3C3C;
                height: 8px;
                background: #2D2D30;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078D7;
                border: 1px solid #0078D7;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #1C97EA;
            }
        """)
    
    def update_ui_state(self):
        """更新UI状态"""
        dynamic_enabled = self.dynamic_threads_checkbox.isChecked()
        self.max_threads_spinbox.setEnabled(dynamic_enabled)
        # 默认线程数在非动态时启用，动态时禁用
        self.thread_count_spinbox.setEnabled(not dynamic_enabled)
        # 更新关闭动态自动线程调节按钮状态
        self.disable_auto_threads_btn.setEnabled(dynamic_enabled)
    
    def browse_folder(self):
        """打开文件夹浏览对话框"""
        current_path = self.path_edit.text()
        folder = QFileDialog.getExistingDirectory(
            self, 
            "选择下载保存位置", 
            current_path
        )
        if folder:
            self.path_edit.setText(folder)
    
    def reset_settings(self):
        """重置设置为默认值"""
        self.max_tasks_spinbox.setValue(5)
        self.thread_count_spinbox.setValue(8)
        self.dynamic_threads_checkbox.setChecked(True)
        self.max_threads_spinbox.setValue(32)
        self.segment_size_spinbox.setValue(10)
        self.buffer_spinbox.setValue(8) # 8KB
        self.chunk_spinbox.setValue(1) # 1MB
        
        self.path_edit.setText(str(Path.home() / "Downloads"))
        self.auto_organize_checkbox.setChecked(False)
        
        self.auto_start_checkbox.setChecked(True)
        self.max_retries_spinbox.setValue(3)
        
        self.update_ui_state()
        self.settings_applied.emit(True, "已重置为默认设置")
    
    def apply_settings(self):
        """应用设置"""
        try:
            # 获取当前设置值
            max_tasks = self.max_tasks_spinbox.value()
            thread_count = self.thread_count_spinbox.value()
            dynamic_threads = self.dynamic_threads_checkbox.isChecked()
            max_threads = self.max_threads_spinbox.value()
            min_segment_size = self.segment_size_spinbox.value()
            buffer_size = self.buffer_spinbox.value() * 1024  # 转换为字节
            chunk_size = self.chunk_spinbox.value() * 1024 * 1024  # 转换为字节
            save_path = self.path_edit.text()
            auto_organize = self.auto_organize_checkbox.isChecked()
            auto_start = self.auto_start_checkbox.isChecked()
            max_retries = self.max_retries_spinbox.value()
            
            # 记录操作日志
            print(f"[INFO] 应用下载设置: 线程数={thread_count}, 最大线程数={max_threads}, 任务数={max_tasks}")
            
            # 保存到配置
            self.config_manager.set_setting("download", "max_tasks", max_tasks)
            self.config_manager.set_setting("download", "thread_count", thread_count)
            self.config_manager.set_setting("download", "dynamic_threads", dynamic_threads)
            self.config_manager.set_setting("download", "max_thread_count", max_threads)
            self.config_manager.set_setting("download", "min_segment_size", min_segment_size)
            self.config_manager.set_setting("download", "buffer_size", buffer_size)
            self.config_manager.set_setting("download", "chunk_size", chunk_size)
            self.config_manager.set_setting("download", "save_path", save_path)
            self.config_manager.set_setting("download", "auto_organize", auto_organize)
            self.config_manager.set_setting("download", "auto_start", auto_start)
            self.config_manager.set_setting("download", "max_retries", max_retries)
            
            # 保存配置到文件
            success = self.config_manager.save_config()
            
            if success:
                # 发送设置应用成功的信号
                self.settings_applied.emit(True, "下载设置已成功应用")
                self.notify_manager.show_message("设置已保存", "下载设置已成功更新")
            else:
                self.settings_applied.emit(False, "保存设置时出错")
                self.notify_manager.show_message("设置保存失败", "保存设置时出错", level="error")
            
        except Exception as e:
            # 记录错误
            print(f"[ERROR] 保存下载设置失败: {str(e)}")
            # 发送设置应用失败的信号
            self.settings_applied.emit(False, f"应用设置时出错: {str(e)}")
            # 显示错误通知
            self.notify_manager.show_message("设置保存失败", f"保存设置时出错: {str(e)}", level="error")

    def disable_dynamic_threads(self):
        """关闭动态自动线程调节"""
        self.dynamic_threads_checkbox.setChecked(False)
        self.update_ui_state()
        
        # 立即保存更改
        try:
            self.config_manager.set_setting("download", "dynamic_threads", False)
            self.config_manager.save_config()
            self.settings_applied.emit(True, "已关闭动态自动线程调节")
        except Exception as e:
            self.settings_applied.emit(False, f"保存设置失败: {str(e)}")