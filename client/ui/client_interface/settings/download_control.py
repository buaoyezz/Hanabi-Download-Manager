from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QSpinBox, QSlider, QLineEdit,
    QFileDialog, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator

from client.ui.components.customNotify import NotifyManager
from client.ui.components.customMessagebox import CustomMessageBox
from core.font.font_manager import FontManager
from pathlib import Path
from client.ui.components.comboBox import CustomComboBox
from client.ui.components.spinBox import CustomSpinBox
from client.ui.components.checkBox import CustomCheckBox
from client.ui.components.slider import CustomSlider
from client.I18N.i18n import i18n  # 添加i18n导入

class DownloadControlWidget(QWidget):
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
        try:
            # 下载设置
            download_config = self.config_manager.get("download", {})
            
            # 线程设置
            thread_count = download_config.get("thread_count", 8)
            dynamic_threads = download_config.get("dynamic_threads", True)
            max_threads = download_config.get("max_thread_count", 32)
            max_tasks = download_config.get("max_tasks", 5) # 从 thread_control 移入
            buffer_size = download_config.get("buffer_size", 8192) # 从 thread_control 移入
            chunk_size = download_config.get("chunk_size", 1024 * 1024) # 从 thread_control 移入
            # 添加默认分段数
            default_segments = download_config.get("default_segments", 8)
            
            # 下载路径设置
            save_path = download_config.get("save_path", 
                                              str(Path.home() / "Downloads"))
            auto_organize = download_config.get("auto_organize", False)
            
            # 下载行为设置
            auto_start = download_config.get("auto_start", True)
            max_retries = download_config.get("max_retries", 3)
            
            # 打印调试信息
            print(f"[DEBUG] {i18n.get_text('load_config')} - {i18n.get_text('thread_count')}: {thread_count}, {i18n.get_text('dynamic_threads')}: {dynamic_threads}")
            print(f"[DEBUG] {i18n.get_text('load_config')} - {i18n.get_text('max_thread_count')}: {max_threads}, {i18n.get_text('default_segments')}: {default_segments}")
            
            # 设置控件值
            self.max_tasks_spinbox.setValue(max_tasks)
            self.thread_count_spinbox.setValue(thread_count)
            self.dynamic_threads_checkbox.setChecked(dynamic_threads)
            self.max_threads_spinbox.setValue(max_threads)
            self.default_segments_spinbox.setValue(default_segments)
            self.buffer_spinbox.setValue(buffer_size // 1024) # KB
            self.chunk_spinbox.setValue(chunk_size // (1024 * 1024)) # MB
            
            self.path_edit.setText(save_path)
            self.auto_organize_checkbox.setChecked(auto_organize)
            
            self.auto_start_checkbox.setChecked(auto_start)
            self.max_retries_spinbox.setValue(max_retries)
            
            # 更新UI状态
            self.update_ui_state()
            
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('download_settings_load_failed')}: {str(e)}")
            print(f"[ERROR] {i18n.get_text('download_settings_load_failed')}: {str(e)}")

    def setup_ui(self):
       
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ===== 并行任务设置组 =====
        self.tasks_group = QGroupBox(i18n.get_text("parallel_download_tasks"))
        self.tasks_group.setStyleSheet("""
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
        tasks_layout = QVBoxLayout(self.tasks_group)
        tasks_layout.setContentsMargins(15, 20, 15, 15)
        tasks_layout.setSpacing(10)

        self.tasks_description = QLabel(i18n.get_text("tasks_description"))
        self.tasks_description.setWordWrap(True)
        self.tasks_description.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(self.tasks_description)
        tasks_layout.addWidget(self.tasks_description)

        tasks_control_layout = QHBoxLayout()
        tasks_control_layout.setSpacing(10)
        self.tasks_label = QLabel(i18n.get_text("max_tasks_count") + ":")
        self.tasks_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.tasks_label)
        tasks_control_layout.addWidget(self.tasks_label)

        self.max_tasks_spinbox = CustomSpinBox()
        self.max_tasks_spinbox.setRange(1, 20)
        self.max_tasks_spinbox.setValue(5)
        self.font_manager.apply_font(self.max_tasks_spinbox)
        tasks_control_layout.addWidget(self.max_tasks_spinbox)

        tasks_slider = CustomSlider(Qt.Horizontal)
        tasks_slider.setRange(1, 20)
        tasks_slider.setValue(5)
        tasks_slider.valueChanged.connect(self.max_tasks_spinbox.setValue)
        self.max_tasks_spinbox.valueChanged.connect(tasks_slider.setValue)
        tasks_control_layout.addWidget(tasks_slider, 1)

        tasks_layout.addLayout(tasks_control_layout)
        main_layout.addWidget(self.tasks_group)
        
        # ===== 线程设置组 =====
        self.thread_group = QGroupBox(i18n.get_text("single_task_thread_settings"))
        self.thread_group.setStyleSheet("""
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
        thread_layout = QVBoxLayout(self.thread_group)
        thread_layout.setContentsMargins(15, 20, 15, 15)
        thread_layout.setSpacing(10)
        
        # 线程数量控制
        thread_count_layout = QHBoxLayout()
        thread_count_layout.setSpacing(10)
        self.thread_count_label = QLabel(i18n.get_text("default_thread_count") + ":")
        self.thread_count_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.thread_count_label)
        thread_count_layout.addWidget(self.thread_count_label)
        
        self.thread_count_spinbox = CustomSpinBox()
        self.thread_count_spinbox.setRange(1, 64)
        self.thread_count_spinbox.setValue(8)
        self.font_manager.apply_font(self.thread_count_spinbox)
        thread_count_layout.addWidget(self.thread_count_spinbox)
        
        thread_slider = CustomSlider(Qt.Horizontal)
        thread_slider.setRange(1, 64)
        thread_slider.setValue(8)
        thread_slider.valueChanged.connect(self.thread_count_spinbox.setValue)
        self.thread_count_spinbox.valueChanged.connect(thread_slider.setValue)
        thread_count_layout.addWidget(thread_slider, 1)
        
        thread_layout.addLayout(thread_count_layout)
        
        # 动态线程
        dynamic_thread_layout = QVBoxLayout()
        dynamic_thread_layout.setSpacing(5)
        self.dynamic_threads_checkbox = CustomCheckBox(i18n.get_text("enable_smart_thread_management"))
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
            }
        """)
        self.font_manager.apply_font(self.dynamic_threads_checkbox)
        dynamic_thread_layout.addWidget(self.dynamic_threads_checkbox)
        
        # 动态线程说明
        self.dynamic_thread_desc = QLabel(i18n.get_text("dynamic_thread_description"))
        self.dynamic_thread_desc.setWordWrap(True)
        self.dynamic_thread_desc.setStyleSheet("color: #9E9E9E; margin-left: 23px;")
        self.font_manager.apply_font(self.dynamic_thread_desc)
        dynamic_thread_layout.addWidget(self.dynamic_thread_desc)
        
        thread_layout.addLayout(dynamic_thread_layout)
        
        # 最大线程数量控制
        max_thread_layout = QHBoxLayout()
        max_thread_layout.setSpacing(10)
        self.max_thread_label = QLabel(i18n.get_text("max_thread_count") + ":")
        self.max_thread_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.max_thread_label)
        max_thread_layout.addWidget(self.max_thread_label)
        
        self.max_threads_spinbox = CustomSpinBox()
        self.max_threads_spinbox.setRange(1, 128)
        self.max_threads_spinbox.setValue(32)
        self.font_manager.apply_font(self.max_threads_spinbox)
        max_thread_layout.addWidget(self.max_threads_spinbox)
        
        max_thread_slider = CustomSlider(Qt.Horizontal)
        max_thread_slider.setRange(1, 128)
        max_thread_slider.setValue(32)
        max_thread_slider.valueChanged.connect(self.max_threads_spinbox.setValue)
        self.max_threads_spinbox.valueChanged.connect(max_thread_slider.setValue)
        max_thread_layout.addWidget(max_thread_slider, 1)
        
        thread_layout.addLayout(max_thread_layout)
        
        # 默认分段数
        segment_layout = QHBoxLayout()
        segment_layout.setSpacing(10)
        self.segment_label = QLabel(i18n.get_text("default_segments") + ":")
        self.segment_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.segment_label)
        segment_layout.addWidget(self.segment_label)
        
        self.default_segments_spinbox = CustomSpinBox()
        self.default_segments_spinbox.setRange(1, 32)
        self.default_segments_spinbox.setValue(8)
        self.font_manager.apply_font(self.default_segments_spinbox)
        segment_layout.addWidget(self.default_segments_spinbox)
        
        segment_slider = CustomSlider(Qt.Horizontal)
        segment_slider.setRange(1, 32)
        segment_slider.setValue(8)
        segment_slider.valueChanged.connect(self.default_segments_spinbox.setValue)
        self.default_segments_spinbox.valueChanged.connect(segment_slider.setValue)
        segment_layout.addWidget(segment_slider, 1)
        
        thread_layout.addLayout(segment_layout)
        
        # 缓冲区大小
        buffer_layout = QHBoxLayout()
        buffer_layout.setSpacing(10)
        self.buffer_label = QLabel(i18n.get_text("buffer_size") + " (KB):")
        self.buffer_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.buffer_label)
        buffer_layout.addWidget(self.buffer_label)
        
        self.buffer_spinbox = CustomSpinBox()
        self.buffer_spinbox.setRange(1, 1024)
        self.buffer_spinbox.setValue(8)
        self.font_manager.apply_font(self.buffer_spinbox)
        buffer_layout.addWidget(self.buffer_spinbox)
        
        buffer_slider = CustomSlider(Qt.Horizontal)
        buffer_slider.setRange(1, 1024)
        buffer_slider.setValue(8)
        buffer_slider.valueChanged.connect(self.buffer_spinbox.setValue)
        self.buffer_spinbox.valueChanged.connect(buffer_slider.setValue)
        buffer_layout.addWidget(buffer_slider, 1)
        
        thread_layout.addLayout(buffer_layout)
        
        # 分块大小
        chunk_layout = QHBoxLayout()
        chunk_layout.setSpacing(10)
        self.chunk_label = QLabel(i18n.get_text("chunk_size") + " (MB):")
        self.chunk_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.chunk_label)
        chunk_layout.addWidget(self.chunk_label)
        
        self.chunk_spinbox = CustomSpinBox()
        self.chunk_spinbox.setRange(1, 64)
        self.chunk_spinbox.setValue(1)
        self.font_manager.apply_font(self.chunk_spinbox)
        chunk_layout.addWidget(self.chunk_spinbox)
        
        chunk_slider = CustomSlider(Qt.Horizontal)
        chunk_slider.setRange(1, 64)
        chunk_slider.setValue(1)
        chunk_slider.valueChanged.connect(self.chunk_spinbox.setValue)
        self.chunk_spinbox.valueChanged.connect(chunk_slider.setValue)
        chunk_layout.addWidget(chunk_slider, 1)
        
        thread_layout.addLayout(chunk_layout)
        
        main_layout.addWidget(self.thread_group)
        
        # ===== 下载路径设置组 =====
        self.path_group = QGroupBox(i18n.get_text("download_path_settings"))
        self.path_group.setStyleSheet("""
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
        path_layout = QVBoxLayout(self.path_group)
        path_layout.setContentsMargins(15, 20, 15, 15)
        path_layout.setSpacing(10)
        
        # 默认下载路径
        path_input_layout = QHBoxLayout()
        path_input_layout.setSpacing(10)
        self.path_label = QLabel(i18n.get_text("default_download_path") + ":")
        self.path_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.path_label)
        path_input_layout.addWidget(self.path_label)
        
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("""
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
        """)
        self.font_manager.apply_font(self.path_edit)
        path_input_layout.addWidget(self.path_edit, 1)
        
        self.browse_button = QPushButton(i18n.get_text("browse"))
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #4C4C4C;
            }
            QPushButton:pressed {
                background-color: #2C2C2C;
            }
        """)
        self.font_manager.apply_font(self.browse_button)
        self.browse_button.clicked.connect(self.browse_folder)
        path_input_layout.addWidget(self.browse_button)
        
        path_layout.addLayout(path_input_layout)
        
        # 自动整理下载
        self.auto_organize_checkbox = CustomCheckBox(i18n.get_text("auto_organize_downloads"))
        self.font_manager.apply_font(self.auto_organize_checkbox)
        path_layout.addWidget(self.auto_organize_checkbox)
        
        # 自动整理说明
        self.organize_desc = QLabel(i18n.get_text("auto_organize_description"))
        self.organize_desc.setWordWrap(True)
        self.organize_desc.setStyleSheet("color: #9E9E9E; margin-left: 23px;")
        self.font_manager.apply_font(self.organize_desc)
        path_layout.addWidget(self.organize_desc)
        
        # 清理恢复文件按钮
        cleanup_layout = QHBoxLayout()
        cleanup_layout.setContentsMargins(0, 10, 0, 0)
        cleanup_layout.setSpacing(10)
        cleanup_desc = QLabel(i18n.get_text("clean_resume_files_description"))
        cleanup_desc.setWordWrap(True)
        cleanup_desc.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(cleanup_desc)
        cleanup_layout.addWidget(cleanup_desc, 1)
        
        self.cleanup_button = QPushButton(i18n.get_text("clean_resume_files"))
        self.cleanup_button.setStyleSheet("""
            QPushButton {
                background-color: #455A64;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:pressed {
                background-color: #37474F;
            }
        """)
        self.font_manager.apply_font(self.cleanup_button)
        self.cleanup_button.clicked.connect(self.on_cleanup_resume_files)
        cleanup_layout.addWidget(self.cleanup_button)
        
        path_layout.addLayout(cleanup_layout)
        
        main_layout.addWidget(self.path_group)
        
        # ===== 下载行为设置组 =====
        self.behavior_group = QGroupBox(i18n.get_text("download_behavior_settings"))
        self.behavior_group.setStyleSheet("""
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
        behavior_layout = QVBoxLayout(self.behavior_group)
        behavior_layout.setContentsMargins(15, 20, 15, 15)
        behavior_layout.setSpacing(10)
        
        # 自动开始下载
        self.auto_start_checkbox = CustomCheckBox(i18n.get_text("auto_start_downloads"))
        self.font_manager.apply_font(self.auto_start_checkbox)
        behavior_layout.addWidget(self.auto_start_checkbox)
        
        # 自动开始说明
        self.auto_start_desc = QLabel(i18n.get_text("auto_start_description"))
        self.auto_start_desc.setWordWrap(True)
        self.auto_start_desc.setStyleSheet("color: #9E9E9E; margin-left: 23px;")
        self.font_manager.apply_font(self.auto_start_desc)
        behavior_layout.addWidget(self.auto_start_desc)
        
        # 最大重试次数
        retry_layout = QHBoxLayout()
        retry_layout.setSpacing(10)
        self.retry_label = QLabel(i18n.get_text("max_retry_count") + ":")
        self.retry_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.retry_label)
        retry_layout.addWidget(self.retry_label)
        
        self.max_retries_spinbox = CustomSpinBox()
        self.max_retries_spinbox.setRange(0, 10)
        self.max_retries_spinbox.setValue(3)
        self.font_manager.apply_font(self.max_retries_spinbox)
        retry_layout.addWidget(self.max_retries_spinbox)
        
        retry_slider = CustomSlider(Qt.Horizontal)
        retry_slider.setRange(0, 10)
        retry_slider.setValue(3)
        retry_slider.valueChanged.connect(self.max_retries_spinbox.setValue)
        self.max_retries_spinbox.valueChanged.connect(retry_slider.setValue)
        retry_layout.addWidget(retry_slider, 1)
        
        behavior_layout.addLayout(retry_layout)
        
        main_layout.addWidget(self.behavior_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # ===== 底部按钮 =====
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        # 重置按钮
        self.reset_button = QPushButton(i18n.get_text("reset"))
        self.reset_button.setStyleSheet("""
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
        """)
        self.font_manager.apply_font(self.reset_button)
        self.reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        # 应用按钮
        self.apply_button = QPushButton(i18n.get_text("apply"))
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #7E57C2;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
            QPushButton:pressed {
                background-color: #673AB7;
            }
        """)
        self.font_manager.apply_font(self.apply_button)
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        main_layout.addLayout(button_layout)

        # 连接信号槽
        self.dynamic_threads_checkbox.stateChanged.connect(self.update_ui_state)
        
    def update_ui_texts(self):
        """更新界面上的所有文本"""
        # 标题和组标题
        self.tasks_group.setTitle(i18n.get_text("parallel_download_tasks"))
        self.thread_group.setTitle(i18n.get_text("single_task_thread_settings"))
        self.path_group.setTitle(i18n.get_text("download_path_settings"))
        self.behavior_group.setTitle(i18n.get_text("download_behavior_settings"))
        
        # 描述和标签
        self.tasks_description.setText(i18n.get_text("tasks_description"))
        self.tasks_label.setText(i18n.get_text("max_tasks_count") + ":")
        self.thread_count_label.setText(i18n.get_text("default_thread_count") + ":")
        self.dynamic_threads_checkbox.setText(i18n.get_text("enable_smart_thread_management"))
        self.dynamic_thread_desc.setText(i18n.get_text("dynamic_thread_description"))
        self.max_thread_label.setText(i18n.get_text("max_thread_count") + ":")
        self.segment_label.setText(i18n.get_text("default_segments") + ":")
        self.buffer_label.setText(i18n.get_text("buffer_size") + " (KB):")
        self.chunk_label.setText(i18n.get_text("chunk_size") + " (MB):")
        
        # 下载路径设置
        self.path_label.setText(i18n.get_text("default_download_path") + ":")
        self.browse_button.setText(i18n.get_text("browse"))
        self.auto_organize_checkbox.setText(i18n.get_text("auto_organize_downloads"))
        self.organize_desc.setText(i18n.get_text("auto_organize_description"))
        self.cleanup_button.setText(i18n.get_text("clean_resume_files"))
        
        # 下载行为设置
        self.auto_start_checkbox.setText(i18n.get_text("auto_start_downloads"))
        self.auto_start_desc.setText(i18n.get_text("auto_start_description"))
        self.retry_label.setText(i18n.get_text("max_retry_count") + ":")
        
        # 按钮
        self.reset_button.setText(i18n.get_text("reset"))
        self.apply_button.setText(i18n.get_text("apply"))
        
    def update_ui_state(self):
        """根据选项状态更新UI"""
        # 动态线程被启用时，禁用手动线程数设置
        dynamic_enabled = self.dynamic_threads_checkbox.isChecked()
        self.thread_count_spinbox.setEnabled(not dynamic_enabled)
        
        # 找到线程数滑块
        thread_count_layout = self.thread_count_spinbox.parent()
        if thread_count_layout:
            for i in range(thread_count_layout.count()):
                item = thread_count_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), CustomSlider):
                    item.widget().setEnabled(not dynamic_enabled)
        
        # 更新默认分段数和最大线程数设置
        self.max_threads_spinbox.setEnabled(dynamic_enabled)
        
        # 找到最大线程数滑块
        max_thread_layout = self.max_threads_spinbox.parent()
        if max_thread_layout:
            for i in range(max_thread_layout.count()):
                item = max_thread_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), CustomSlider):
                    item.widget().setEnabled(dynamic_enabled)
        
    def browse_folder(self):
        """选择下载文件夹"""
        current_path = self.path_edit.text()
        folder = QFileDialog.getExistingDirectory(
            self, 
            i18n.get_text("select_download_folder"),
            current_path or str(Path.home())
        )
        if folder:
            self.path_edit.setText(folder)
            
    def reset_settings(self):
        """重置设置为默认值"""
        self.load_config()
        self.settings_applied.emit(True, i18n.get_text("settings_reset"))
        
    def apply_settings(self):
        """应用设置"""
        try:
            # 获取设置值
            max_tasks = self.max_tasks_spinbox.value()
            thread_count = self.thread_count_spinbox.value()
            dynamic_threads = self.dynamic_threads_checkbox.isChecked()
            max_threads = self.max_threads_spinbox.value()
            default_segments = self.default_segments_spinbox.value()
            buffer_size = self.buffer_spinbox.value() * 1024  # 转换为字节
            chunk_size = self.chunk_spinbox.value() * 1024 * 1024  # 转换为字节
            
            save_path = self.path_edit.text()
            auto_organize = self.auto_organize_checkbox.isChecked()
            
            auto_start = self.auto_start_checkbox.isChecked()
            max_retries = self.max_retries_spinbox.value()
            
            # 验证下载路径
            if not save_path or not os.path.isdir(save_path):
                if not save_path:
                    save_path = str(Path.home() / "Downloads")
                    try:
                        os.makedirs(save_path, exist_ok=True)
                    except Exception as e:
                        self.settings_applied.emit(False, f"{i18n.get_text('create_download_dir_failed')}: {str(e)}")
                        return
                else:
                    self.settings_applied.emit(False, i18n.get_text("invalid_download_path"))
                    return
            
            # 更新配置
            download_config = {
                "thread_count": thread_count,
                "dynamic_threads": dynamic_threads,
                "max_thread_count": max_threads,
                "max_tasks": max_tasks,
                "buffer_size": buffer_size,
                "chunk_size": chunk_size,
                "default_segments": default_segments,
                "save_path": save_path,
                "auto_organize": auto_organize,
                "auto_start": auto_start,
                "max_retries": max_retries
            }
            
            # 保存配置
            self.config_manager.set("download", download_config)
            self.config_manager.save_config()
            
            # 应用动态线程设置
            if not dynamic_threads:
                self.disable_dynamic_threads()
            
            # 通知成功
            self.settings_applied.emit(True, i18n.get_text("download_settings_saved"))
            
        except Exception as e:
            # 通知失败
            self.settings_applied.emit(False, f"{i18n.get_text('save_settings_failed')}: {str(e)}")

    def disable_dynamic_threads(self):
        """禁用动态线程"""
        self.dynamic_threads_checkbox.setChecked(False)
        self.update_ui_state()
        
        # 立即保存更改
        try:
            self.config_manager.set_setting("download", "dynamic_threads", False)
            self.config_manager.save_config()
            self.settings_applied.emit(True, i18n.get_text("dynamic_threads_disabled"))
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('disable_dynamic_threads_failed')}: {str(e)}")

    def on_cleanup_resume_files(self):
        """清理断点续传文件"""
        try:
            # 获取当前下载路径
            save_path = self.path_edit.text()
            if not save_path:
                # 获取配置中的默认下载路径
                save_path = self.config_manager.get_setting("download", "save_path", str(Path.home() / "Downloads"))
            
            # 执行清理
            if save_path:
                from pathlib import Path
                import logging
                
                download_path = Path(save_path)
                if download_path.exists() and download_path.is_dir():
                    # 查找所有.resume文件
                    resume_files = list(download_path.glob("*.resume"))
                    
                    if not resume_files:
                        NotifyManager.info(self, "无需清理", "没有发现断点续传文件")
                        return
                    
                    # 删除所有.resume文件
                    cleaned_count = 0
                    for resume_file in resume_files:
                        try:
                            # 获取对应的主文件名
                            main_file = resume_file.with_suffix("")
                            
                            # 如果主文件存在或resume文件大小不为0，则删除resume文件
                            if main_file.exists() or resume_file.stat().st_size > 0:
                                resume_file.unlink()
                                cleaned_count += 1
                                logging.info(f"已清理断点续传文件: {resume_file}")
                        except Exception as e:
                            logging.warning(f"清理断点续传文件 {resume_file} 失败: {e}")
                    
                    # 提示清理结果
                    if cleaned_count > 0:
                        NotifyManager.success(self, "清理完成", f"成功清理 {cleaned_count} 个断点续传文件")
                    else:
                        NotifyManager.info(self, "清理完成", "未清理任何文件")
                else:
                    NotifyManager.warning(self, "路径不存在", f"下载路径 '{save_path}' 不存在")
            else:
                NotifyManager.warning(self, "无下载路径", "未设置下载路径")
        except Exception as e:
            NotifyManager.error(self, "清理失败", f"清理断点续传文件失败: {e}")
            logging.error(f"清理断点续传文件失败: {e}")