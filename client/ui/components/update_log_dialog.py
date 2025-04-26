from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QWidget)
from PySide6.QtCore import Qt
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle

class UpdateLogDialog(QDialog):
    def __init__(self, version, content, update_time, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建内容容器
        container = QWidget(self)
        container.setObjectName("container")
        container.setStyleSheet("""
            QWidget#container {
                background-color: #2C2C2C;
                border: 1px solid #3C3C3C;
                border-radius: 10px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel(f"版本 {version} 更新日志")
        title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 18px;
            font-weight: bold;
        """)
        self.font_manager.apply_font(title_label)
        container_layout.addWidget(title_label)
        
        # 更新时间
        time_label = QLabel(f"更新时间: {update_time}")
        time_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.font_manager.apply_font(time_label)
        container_layout.addWidget(time_label)
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        container_layout.addWidget(separator)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(scroll_area, "dark")
        
        # 更新内容
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 14px;
            line-height: 1.5;
        """)
        self.font_manager.apply_font(content_label)
        content_layout.addWidget(content_label)
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        container_layout.addWidget(scroll_area)
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(120)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #B39DDB;
                color: #121212;
                border: none;
                border-radius: 5px;
                padding: 8px 0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
            QPushButton:pressed {
                background-color: #7E57C2;
            }
        """)
        self.font_manager.apply_font(ok_btn)
        ok_btn.clicked.connect(self.accept)
        
        btn_layout = QVBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(ok_btn)
        container_layout.addLayout(btn_layout)
        
        main_layout.addWidget(container) 