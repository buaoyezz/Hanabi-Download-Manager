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
            # 疯狂模式设置
            crazy_mode = download_config.get("crazy_mode", False)
            
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
            print(f"[DEBUG] {i18n.get_text('load_config')} - Crazy Mode: {crazy_mode}")
            
            # 设置控件值
            self.max_tasks_spinbox.setValue(max_tasks)
            self.thread_count_spinbox.setValue(thread_count)
            self.dynamic_threads_checkbox.setChecked(dynamic_threads)
            self.max_threads_spinbox.setValue(max_threads)
            self.default_segments_spinbox.setValue(default_segments)
            self.buffer_spinbox.setValue(buffer_size // 1024) # KB
            self.chunk_spinbox.setValue(chunk_size // (1024 * 1024)) # MB
            self.crazy_mode_checkbox.setChecked(crazy_mode)
            
            self.path_edit.setText(save_path)
            self.auto_organize_checkbox.setChecked(auto_organize)
            
            self.auto_start_checkbox.setChecked(auto_start)
            self.max_retries_spinbox.setValue(max_retries)
            
            # 更新UI状态
            self.update_ui_state()
            
            # 更新线程范围
            self.update_thread_range()
            
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
        self.thread_count_spinbox.setRange(1, 32)
        self.thread_count_spinbox.setValue(8)
        self.font_manager.apply_font(self.thread_count_spinbox)
        thread_count_layout.addWidget(self.thread_count_spinbox)
        
        thread_slider = CustomSlider(Qt.Horizontal)
        thread_slider.setRange(1, 32)
        thread_slider.setValue(8)
        thread_slider.valueChanged.connect(self.thread_count_spinbox.setValue)
        self.thread_count_spinbox.valueChanged.connect(thread_slider.setValue)
        thread_slider.setObjectName("thread_slider")  # 添加对象名称
        thread_count_layout.addWidget(thread_slider, 1)
        
        thread_layout.addLayout(thread_count_layout)
        
        # 疯狂模式 (Crazy Mode)
        crazy_mode_layout = QVBoxLayout()
        crazy_mode_layout.setSpacing(5)
        self.crazy_mode_checkbox = CustomCheckBox(i18n.get_text("enable_crazy_mode") or "启用疯狂模式 (64-128线程)")
        self.crazy_mode_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FF5252;
                font-weight: bold;
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
                border: 1px solid #FF5252;
                background-color: #FF5252;
                border-radius: 3px;
            }
        """)
        self.font_manager.apply_font(self.crazy_mode_checkbox)
        self.crazy_mode_checkbox.stateChanged.connect(self.update_thread_range)
        crazy_mode_layout.addWidget(self.crazy_mode_checkbox)
        
        # 疯狂模式警告
        self.crazy_mode_warning = QLabel(i18n.get_text("crazy_mode_warning") or "警告：疯狂模式可能导致下载文件损坏、服务器拒绝连接或系统资源耗尽！")
        self.crazy_mode_warning.setWordWrap(True)
        self.crazy_mode_warning.setStyleSheet("color: #FF5252; margin-left: 23px;")
        self.font_manager.apply_font(self.crazy_mode_warning)
        crazy_mode_layout.addWidget(self.crazy_mode_warning)
        
        thread_layout.addLayout(crazy_mode_layout)
        
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
        max_thread_slider.setObjectName("max_thread_slider")  # 添加对象名称
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
        segment_slider.setObjectName("segment_slider")  # 添加对象名称，便于后续查找
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
        
        # 添加分类路径设置按钮
        category_btn_layout = QHBoxLayout()
        category_btn_layout.setContentsMargins(0, 5, 0, 0)
        
        category_label = QLabel(i18n.get_text("category_paths_settings") or "分类路径设置:")
        category_label.setStyleSheet("color: #FFFFFF; margin-left: 23px;")
        self.font_manager.apply_font(category_label)
        category_btn_layout.addWidget(category_label)
        
        self.category_settings_button = QPushButton(i18n.get_text("configure") or "配置")
        self.category_settings_button.setStyleSheet("""
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
        self.font_manager.apply_font(self.category_settings_button)
        self.category_settings_button.clicked.connect(self.show_category_settings)
        category_btn_layout.addWidget(self.category_settings_button)
        category_btn_layout.addStretch()
        
        path_layout.addLayout(category_btn_layout)
        
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
        thread_count_layout = None
        if hasattr(self.thread_count_spinbox, 'parent') and self.thread_count_spinbox.parent():
            thread_count_layout = self.thread_count_spinbox.parent()
            if thread_count_layout and hasattr(thread_count_layout, 'count'):
                for i in range(thread_count_layout.count()):
                    item = thread_count_layout.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), CustomSlider):
                        item.widget().setEnabled(not dynamic_enabled)
        
        # 更新默认分段数和最大线程数设置
        self.max_threads_spinbox.setEnabled(dynamic_enabled)
        
        # 找到最大线程数滑块
        max_thread_layout = None
        if hasattr(self.max_threads_spinbox, 'parent') and self.max_threads_spinbox.parent():
            max_thread_layout = self.max_threads_spinbox.parent()
            if max_thread_layout and hasattr(max_thread_layout, 'count'):
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
        try:
            # 获取当前设置值
            max_tasks = self.max_tasks_spinbox.value()
            thread_count = self.thread_count_spinbox.value()
            dynamic_threads = self.dynamic_threads_checkbox.isChecked()
            max_threads = self.max_threads_spinbox.value()
            default_segments = self.default_segments_spinbox.value()
            buffer_size = self.buffer_spinbox.value() * 1024  # 转换为字节
            chunk_size = self.chunk_spinbox.value() * 1024 * 1024  # 转换为字节
            crazy_mode = self.crazy_mode_checkbox.isChecked()
            
            save_path = self.path_edit.text()
            auto_organize = self.auto_organize_checkbox.isChecked()
            
            auto_start = self.auto_start_checkbox.isChecked()
            max_retries = self.max_retries_spinbox.value()
            
            # 保存设置
            self.config_manager.set_setting("download", "max_tasks", max_tasks)
            self.config_manager.set_setting("download", "thread_count", thread_count)
            self.config_manager.set_setting("download", "dynamic_threads", dynamic_threads)
            self.config_manager.set_setting("download", "max_thread_count", max_threads)
            self.config_manager.set_setting("download", "default_segments", default_segments)
            self.config_manager.set_setting("download", "buffer_size", buffer_size)
            self.config_manager.set_setting("download", "chunk_size", chunk_size)
            self.config_manager.set_setting("download", "crazy_mode", crazy_mode)
            
            self.config_manager.set_setting("download", "save_path", save_path)
            self.config_manager.set_setting("download", "auto_organize", auto_organize)
            
            self.config_manager.set_setting("download", "auto_start", auto_start)
            self.config_manager.set_setting("download", "max_retries", max_retries)
            
            # 保存配置
            if self.config_manager.save_config():
                # 显示成功通知
                self.notify_manager.show_message(i18n.get_text("settings_saved"), i18n.get_text("download_settings_updated"))
                self.settings_applied.emit(True, i18n.get_text("download_settings_updated"))
                
                # 如果启用了疯狂模式，显示警告
                if crazy_mode:
                    CustomMessageBox.warning(
                        self, 
                        i18n.get_text("warning") or "警告", 
                        i18n.get_text("crazy_mode_enabled_warning") or "您已启用疯狂模式！使用过高的线程数可能导致下载文件损坏、服务器拒绝连接或系统资源耗尽。请谨慎使用。"
                    )
            else:
                raise Exception(i18n.get_text("settings_save_failed"))
        except Exception as e:
            self.settings_applied.emit(False, f"{i18n.get_text('error')}: {str(e)}")
            CustomMessageBox.error(self, i18n.get_text("error"), str(e))

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
                        NotifyManager.info("无需清理，没有发现断点续传文件")
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
                        NotifyManager.success(f"清理完成，成功清理 {cleaned_count} 个断点续传文件")
                    else:
                        NotifyManager.info("清理完成，未清理任何文件")
                else:
                    NotifyManager.warning(f"路径不存在，下载路径 '{save_path}' 不存在")
            else:
                NotifyManager.warning("无下载路径，未设置下载路径")
        except Exception as e:
            NotifyManager.error(f"清理失败，清理断点续传文件失败: {e}")
            logging.error(f"清理断点续传文件失败: {e}")

    def update_thread_range(self):
        """更新线程范围"""
        dynamic_enabled = self.dynamic_threads_checkbox.isChecked()
        crazy_mode = self.crazy_mode_checkbox.isChecked()
        
        # 更新线程数范围
        if crazy_mode:
            # 疯狂模式：允许64-128线程
            self.thread_count_spinbox.setRange(1, 128)
            thread_slider = self.findChild(CustomSlider, "thread_slider")
            if thread_slider:
                thread_slider.setRange(1, 128)
            
            # 更新最大线程数范围
            self.max_threads_spinbox.setRange(1, 128)
            max_thread_slider = self.findChild(CustomSlider, "max_thread_slider")
            if max_thread_slider:
                max_thread_slider.setRange(1, 128)
            
            # 更新默认分段数范围，在疯狂模式下也允许更高的分段数
            self.default_segments_spinbox.setRange(1, 64)  # 在疯狂模式下允许最多64个分段
            segment_slider = self.findChild(CustomSlider, "segment_slider")
            if segment_slider:
                segment_slider.setRange(1, 64)
            
            # 显示警告
            self.crazy_mode_warning.setVisible(True)
        else:
            # 普通模式：最多32线程
            self.thread_count_spinbox.setRange(1, 32)
            thread_slider = self.findChild(CustomSlider, "thread_slider")
            if thread_slider:
                thread_slider.setRange(1, 32)
            
            # 更新最大线程数范围
            self.max_threads_spinbox.setRange(1, 32)
            max_thread_slider = self.findChild(CustomSlider, "max_thread_slider")
            if max_thread_slider:
                max_thread_slider.setRange(1, 32)
            
            # 更新默认分段数范围，确保与最大线程数一致
            self.default_segments_spinbox.setRange(1, 32)
            segment_slider = self.findChild(CustomSlider, "segment_slider")
            if segment_slider:
                segment_slider.setRange(1, 32)
            
            # 隐藏警告
            self.crazy_mode_warning.setVisible(False)
        
        # 控制是否启用线程数控件
        self.thread_count_spinbox.setEnabled(not dynamic_enabled)
        self.max_threads_spinbox.setEnabled(dynamic_enabled)

    def show_category_settings(self):
        """显示分类路径设置对话框"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QScrollArea, QWidget
            from core.download_core.file_organizer import get_file_organizer
            
            # 获取文件整理器实例
            organizer = get_file_organizer()
            
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(i18n.get_text("category_paths_settings") or "分类路径设置")
            dialog.setMinimumWidth(500)
            dialog.setMinimumHeight(400)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                }
                QLabel {
                    color: #FFFFFF;
                }
                QPushButton {
                    background-color: #3C3C3C;
                    border: none;
                    border-radius: 4px;
                    color: #FFFFFF;
                    padding: 5px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #4C4C4C;
                }
                QPushButton:pressed {
                    background-color: #2C2C2C;
                }
                QLineEdit {
                    background-color: #2D2D30;
                    border: 1px solid #3C3C3C;
                    border-radius: 4px;
                    color: #FFFFFF;
                    padding: 5px;
                }
            """)
            
            # 主布局
            main_layout = QVBoxLayout(dialog)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(15)
            
            # 说明文本
            description = QLabel(i18n.get_text("category_paths_description") or "为不同类型的文件设置自定义保存路径。如果不设置，将使用默认下载路径下的分类文件夹。")
            description.setWordWrap(True)
            self.font_manager.apply_font(description)
            main_layout.addWidget(description)
            
            # 创建滚动区域
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("""
                QScrollArea {
                    border: 1px solid #3C3C3C;
                    border-radius: 4px;
                    background-color: #1E1E1E;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #2D2D30;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #3C3C3C;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)
            
            # 创建滚动区域内容
            scroll_content = QWidget()
            scroll_layout = QVBoxLayout(scroll_content)
            scroll_layout.setContentsMargins(10, 10, 10, 10)
            scroll_layout.setSpacing(10)
            
            # 获取所有分类
            categories = organizer.DEFAULT_CATEGORIES
            
            # 获取当前配置的分类路径
            category_paths = self.config_manager.get_setting("download", "category_paths", {})
            
            # 创建路径设置控件
            path_widgets = {}
            
            for category in categories:
                # 创建水平布局
                row_layout = QHBoxLayout()
                
                # 分类标签
                label = QLabel(f"{category}:")
                label.setMinimumWidth(80)
                self.font_manager.apply_font(label)
                row_layout.addWidget(label)
                
                # 路径显示标签
                path_label = QLabel(category_paths.get(category, ""))
                path_label.setStyleSheet("color: #9E9E9E;")
                self.font_manager.apply_font(path_label)
                row_layout.addWidget(path_label, 1)
                
                # 浏览按钮
                browse_button = QPushButton(i18n.get_text("browse") or "浏览")
                self.font_manager.apply_font(browse_button)
                row_layout.addWidget(browse_button)
                
                # 清除按钮
                clear_button = QPushButton(i18n.get_text("clear") or "清除")
                clear_button.setStyleSheet("""
                    QPushButton {
                        background-color: #455A64;
                    }
                    QPushButton:hover {
                        background-color: #546E7A;
                    }
                    QPushButton:pressed {
                        background-color: #37474F;
                    }
                """)
                self.font_manager.apply_font(clear_button)
                row_layout.addWidget(clear_button)
                
                # 保存控件引用
                path_widgets[category] = {
                    'label': path_label,
                    'browse_button': browse_button,
                    'clear_button': clear_button
                }
                
                # 添加到布局
                scroll_layout.addLayout(row_layout)
                
                # 连接按钮信号
                def make_browse_handler(cat):
                    return lambda: self.browse_category_path(cat, path_widgets[cat]['label'])
                
                def make_clear_handler(cat):
                    return lambda: self.clear_category_path(cat, path_widgets[cat]['label'])
                
                browse_button.clicked.connect(make_browse_handler(category))
                clear_button.clicked.connect(make_clear_handler(category))
            
            # 添加弹性空间
            scroll_layout.addStretch(1)
            
            # 设置滚动区域的内容
            scroll_area.setWidget(scroll_content)
            main_layout.addWidget(scroll_area)
            
            # 底部按钮
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 10, 0, 0)
            button_layout.setSpacing(10)
            
            # 重置按钮
            reset_button = QPushButton(i18n.get_text("reset") or "重置")
            reset_button.setStyleSheet("""
                QPushButton {
                    background-color: #455A64;
                }
                QPushButton:hover {
                    background-color: #546E7A;
                }
                QPushButton:pressed {
                    background-color: #37474F;
                }
            """)
            self.font_manager.apply_font(reset_button)
            button_layout.addWidget(reset_button)
            
            button_layout.addStretch()
            
            # 关闭按钮
            close_button = QPushButton(i18n.get_text("close") or "关闭")
            close_button.setStyleSheet("""
                QPushButton {
                    background-color: #7E57C2;
                }
                QPushButton:hover {
                    background-color: #9575CD;
                }
                QPushButton:pressed {
                    background-color: #673AB7;
                }
            """)
            self.font_manager.apply_font(close_button)
            button_layout.addWidget(close_button)
            
            main_layout.addLayout(button_layout)
            
            # 连接按钮信号
            reset_button.clicked.connect(lambda: self.reset_category_paths(path_widgets))
            close_button.clicked.connect(dialog.accept)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            logging.error(f"显示分类路径设置对话框失败: {e}")
            NotifyManager.error(f"显示分类路径设置对话框失败: {e}")
    
    def browse_category_path(self, category, path_label):
        """浏览分类路径"""
        try:
            # 获取当前路径
            current_path = path_label.text() or self.path_edit.text() or str(Path.home())
            
            # 打开文件夹选择对话框
            folder = QFileDialog.getExistingDirectory(
                self, 
                i18n.get_text("select_category_folder").format(category=category) or f"选择{category}分类文件夹",
                current_path
            )
            
            if folder:
                # 更新标签
                path_label.setText(folder)
                
                # 更新配置
                category_paths = self.config_manager.get_setting("download", "category_paths", {})
                category_paths[category] = folder
                self.config_manager.set_setting("download", "category_paths", category_paths)
                self.config_manager.save_config()
                
                # 更新文件整理器
                try:
                    from core.download_core.file_organizer import get_file_organizer
                    organizer = get_file_organizer()
                    organizer.set_category_path(category, folder)
                except Exception as e:
                    logging.error(f"更新文件整理器分类路径失败: {e}")
                
                NotifyManager.info(f"{category}分类路径已设置")
        except Exception as e:
            logging.error(f"浏览分类路径失败: {e}")
            NotifyManager.error(f"浏览分类路径失败: {e}")
    
    def clear_category_path(self, category, path_label):
        """清除分类路径"""
        try:
            # 清除标签
            path_label.setText("")
            
            # 更新配置
            category_paths = self.config_manager.get_setting("download", "category_paths", {})
            if category in category_paths:
                del category_paths[category]
                self.config_manager.set_setting("download", "category_paths", category_paths)
                self.config_manager.save_config()
                
                # 更新文件整理器
                try:
                    from core.download_core.file_organizer import get_file_organizer
                    organizer = get_file_organizer()
                    # 重置为默认路径
                    organizer.category_paths.pop(category, None)
                except Exception as e:
                    logging.error(f"重置文件整理器分类路径失败: {e}")
                
                NotifyManager.info(f"{category}分类路径已清除")
        except Exception as e:
            logging.error(f"清除分类路径失败: {e}")
            NotifyManager.error(f"清除分类路径失败: {e}")
    
    def reset_category_paths(self, path_widgets):
        """重置所有分类路径"""
        try:
            # 清除所有标签
            for category, widgets in path_widgets.items():
                widgets['label'].setText("")
            
            # 更新配置
            self.config_manager.set_setting("download", "category_paths", {})
            self.config_manager.save_config()
            
            # 更新文件整理器
            try:
                from core.download_core.file_organizer import get_file_organizer
                organizer = get_file_organizer()
                organizer.category_paths = {}
            except Exception as e:
                logging.error(f"重置文件整理器所有分类路径失败: {e}")
            
            NotifyManager.info("所有分类路径已重置")
        except Exception as e:
            logging.error(f"重置所有分类路径失败: {e}")
            NotifyManager.error(f"重置所有分类路径失败: {e}")