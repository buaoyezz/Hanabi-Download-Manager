from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QSpinBox, QGroupBox, QSlider)
from PySide6.QtCore import Qt, Signal

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager
from client.I18N.i18n import i18n


class ThreadControlWidget(QWidget):
    # 设置变更信号
    settingsChanged = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器和配置管理器
        self.font_manager = FontManager()
        self.notify_manager = NotifyManager()
        
        # 加载当前配置
        self.load_config()
        
        # 创建UI
        self.setup_ui()
        
        # 连接语言变更信号，动态更新UI文本
        i18n.language_changed.connect(self.update_ui_texts)
        
    def load_config(self):
        """从配置文件加载下载线程相关设置"""
        from client.ui.client_interface.settings.config import config
        self.config_manager = config
        
        try:
            download_config = self.config_manager.get("download", {})
            # self.max_tasks = download_config.get("max_tasks", 5) # Moved to DownloadControlWidget
            self.max_threads_per_task = download_config.get("thread_count", 8)
            # self.buffer_size = download_config.get("buffer_size", 8192)  # Moved to DownloadControlWidget
            # self.chunk_size = download_config.get("chunk_size", 1024 * 1024)  # Moved to DownloadControlWidget
            
            # 更新UI控件值（如果已经初始化）
            if hasattr(self, 'threads_spinbox'):
                self.threads_spinbox.setValue(self.max_threads_per_task)
                
        except Exception as e:
            print(f"[ERROR] {i18n.get_text('thread_settings_load_failed')}: {str(e)}")
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 创建线程设置组
        self.threads_group = QGroupBox(i18n.get_text("single_task_threads"))
        self.threads_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                margin-top: 15px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        self.font_manager.apply_font(self.threads_group)
        
        threads_layout = QVBoxLayout(self.threads_group)
        
        # 线程数量说明
        self.threads_description = QLabel(i18n.get_text("threads_description"))
        self.threads_description.setWordWrap(True)
        self.threads_description.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(self.threads_description)
        threads_layout.addWidget(self.threads_description)
        
        # 线程数量控制
        threads_control_layout = QHBoxLayout()
        
        self.threads_label = QLabel(i18n.get_text("threads_per_task") + ":")
        self.threads_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(self.threads_label)
        threads_control_layout.addWidget(self.threads_label)
        
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(1, 32)
        self.threads_spinbox.setValue(self.max_threads_per_task)
        self.threads_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 3px;
                padding: 5px;
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
        self.font_manager.apply_font(self.threads_spinbox)
        threads_control_layout.addWidget(self.threads_spinbox)
        
        threads_slider = QSlider(Qt.Horizontal)
        threads_slider.setRange(1, 32)
        threads_slider.setValue(self.max_threads_per_task)
        threads_slider.setStyleSheet("""
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
        threads_slider.valueChanged.connect(self.threads_spinbox.setValue)
        self.threads_spinbox.valueChanged.connect(threads_slider.setValue)
        threads_control_layout.addWidget(threads_slider, 1)
        
        threads_layout.addLayout(threads_control_layout)
        main_layout.addWidget(self.threads_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        # 重置按钮
        self.reset_btn = QPushButton(i18n.get_text("reset_to_default"))
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #0078D7;
            }
        """)
        self.font_manager.apply_font(self.reset_btn)
        self.reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_btn)
        
        button_layout.addStretch(1)
        
        # 应用按钮
        self.apply_btn = QPushButton(i18n.get_text("apply"))
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #1C97EA;
            }
        """)
        self.font_manager.apply_font(self.apply_btn)
        self.apply_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_btn)
        
        main_layout.addLayout(button_layout)
    
    def update_ui_texts(self):
        """更新界面上的所有文本"""
        # 更新组标题
        self.threads_group.setTitle(i18n.get_text("single_task_threads"))
        
        # 更新描述
        self.threads_description.setText(i18n.get_text("threads_description"))
        
        # 更新标签
        self.threads_label.setText(i18n.get_text("threads_per_task") + ":")
        
        # 更新按钮
        self.reset_btn.setText(i18n.get_text("reset_to_default"))
        self.apply_btn.setText(i18n.get_text("apply"))
    
    def reset_settings(self):
        self.threads_spinbox.setValue(8)
    
    def apply_settings(self):
        try:
            # 获取当前设置值
            thread_count = self.threads_spinbox.value()
            
            # 保存到配置
            self.config_manager.set_setting("download", "thread_count", thread_count)
            
            self.config_manager.save_config()
            
            # 显示成功通知
            self.notify_manager.show_message(i18n.get_text("settings_saved"), i18n.get_text("thread_settings_updated"))
            
            # 发送设置变更信号
            self.settingsChanged.emit()
            
        except Exception as e:
            # 显示错误通知
            self.notify_manager.show_message(i18n.get_text("settings_error"), f"{i18n.get_text('save_settings_failed')}: {str(e)}", is_error=True)
