from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QSpinBox, QGroupBox, QSlider)
from PySide6.QtCore import Qt, Signal

from core.font.font_manager import FontManager
from client.ui.components.customNotify import NotifyManager


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
            print(f"[ERROR] 加载线程设置失败: {str(e)}")
        
    def setup_ui(self):
        """设置UI组件"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 创建线程设置组
        threads_group = QGroupBox("单任务下载线程")
        threads_group.setStyleSheet("""
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
        self.font_manager.apply_font(threads_group)
        
        threads_layout = QVBoxLayout(threads_group)
        
        # 线程数量说明
        threads_description = QLabel("设置每个下载任务的最大线程数。增加线程数可以提高单文件下载速度，但过多的线程可能导致连接不稳定或被服务器限制。")
        threads_description.setWordWrap(True)
        threads_description.setStyleSheet("color: #9E9E9E;")
        self.font_manager.apply_font(threads_description)
        threads_layout.addWidget(threads_description)
        
        # 线程数量控制
        threads_control_layout = QHBoxLayout()
        
        threads_label = QLabel("每任务线程数:")
        threads_label.setStyleSheet("color: #FFFFFF;")
        self.font_manager.apply_font(threads_label)
        threads_control_layout.addWidget(threads_label)
        
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
        main_layout.addWidget(threads_group)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        # 重置按钮
        self.reset_btn = QPushButton("重置为默认值")
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
        self.apply_btn = QPushButton("应用")
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
    
    def reset_settings(self):
        """重置设置为默认值"""
        self.threads_spinbox.setValue(8)
    
    def apply_settings(self):
        """应用设置"""
        try:
            # 获取当前设置值
            thread_count = self.threads_spinbox.value()
            
            # 保存到配置
            self.config_manager.set_setting("download", "thread_count", thread_count)
            
            self.config_manager.save_config()
            
            # 显示成功通知
            self.notify_manager.show_message("设置已保存", "下载线程设置已成功更新")
            
            # 发送设置变更信号
            self.settingsChanged.emit()
            
        except Exception as e:
            # 显示错误通知
            self.notify_manager.show_message("设置保存失败", f"保存设置时出错: {str(e)}", level="error")
