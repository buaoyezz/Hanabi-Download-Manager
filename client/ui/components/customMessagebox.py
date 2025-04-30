from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from core.font.font_manager import FontManager

class CustomMessageBox(QDialog):
    def __init__(self, parent=None, title="提示", text="", buttons=None, icon=None):
        super().__init__(parent)
        
        self._is_dragging = False
        self._drag_start_pos = None
        
        self.font_manager = FontManager()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(400)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
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
        
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 图标映射
        icon_map = {
            "info": "info",
            "warning": "warning_amber",
            "error": "error",
            "help": "help"
        }
        
        # 图标颜色映射
        icon_color = {
            "info": "#4CAF50",     # 绿色(信息)
            "warning": "#FFC107",   # 黄色警告
            "error": "#F44336",     # 红色错误
            "help": "#2196F3"       # 蓝色问题
        }
        
        # 添加图标到标题栏左侧
        if icon and icon in icon_map:
            # 创建图标标签
            icon_label = QLabel()
            icon_label.setFixedSize(28, 28)  # 放大容器尺寸
            
            # 使用FontManager获取图标
            self.font_manager.apply_icon_font(icon_label, 20)  # 保持16的字体大小
            icon_label.setText(self.font_manager.get_icon_text(icon_map[icon]))
            
            # 设置图标颜色和居中对齐
            if icon in icon_color:
                icon_label.setStyleSheet(f"""
                    color: {icon_color[icon]};
                    font-size: 16px;
                    qproperty-alignment: AlignCenter;
                    padding: 2px;
                """)
        
            title_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 16px;
            font-weight: bold;
        """)
        self.font_manager.apply_font(title_label)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 创建关闭按钮
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        
        # 使用字体管理器设置图标字体
        self.font_manager.apply_icon_font(close_btn, 16)
        
        # 设置关闭图标
        close_btn.setText(self.font_manager.get_icon_text("close"))
        close_btn.setStyleSheet("""
            QPushButton {
                color: #9E9E9E;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
            QPushButton:pressed {
                color: #7E57C2;
            }
        """)
        close_btn.clicked.connect(self.reject)
        title_layout.addWidget(close_btn)
        
        container_layout.addLayout(title_layout)
        
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        container_layout.addWidget(separator)
        
        # 内容区域
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            color: #CCCCCC;
            font-size: 14px;
            min-height: 40px;
            padding-left: 10px;
        """)
        self.font_manager.apply_font(message_label)
        content_layout.addWidget(message_label, 1)
        
        container_layout.addLayout(content_layout)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        if not buttons:
            buttons = [("确定", True)]
        
        for btn_text, is_default in buttons:
            btn = QPushButton(btn_text)
            self.font_manager.apply_font(btn)
            if is_default:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #7E57C2;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                        font-weight: bold;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #9575CD;
                    }
                    QPushButton:pressed {
                        background-color: #673AB7;
                    }
                """)
                btn.clicked.connect(self.accept)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #424242;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background-color: #4E4E4E;
                    }
                    QPushButton:pressed {
                        background-color: #383838;
                    }
                """)
                btn.clicked.connect(self.reject)
            button_layout.addWidget(btn)
        
        container_layout.addLayout(button_layout)
        main_layout.addWidget(container)
    
    @staticmethod
    def info(parent, title, text, buttons=None):
        dialog = CustomMessageBox(parent, title, text, buttons, icon="info")
        return dialog.exec()
    
    @staticmethod
    def warning(parent, title, text, buttons=None):
        dialog = CustomMessageBox(parent, title, text, buttons, icon="warning")
        return dialog.exec()
    
    @staticmethod
    def error(parent, title, text, buttons=None):
        dialog = CustomMessageBox(parent, title, text, buttons, icon="error")
        return dialog.exec()
    
    @staticmethod
    def question(parent, title, text, buttons=None):
        if not buttons:
            buttons = [("确定", True), ("取消", False)]
        dialog = CustomMessageBox(parent, title, text, buttons, icon="help")
        return dialog.exec()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.pos().y() <= 50:
                self._is_dragging = True
                self._drag_start_pos = event.globalPos() - self.pos()
                event.accept()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()
    
    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    CustomMessageBox.info(None, "提示", "这是一条信息提示")
    
    CustomMessageBox.warning(None, "警告", "这是一条警告信息")
    
    CustomMessageBox.error(None, "错误", "这是一条错误信息")
    
    result = CustomMessageBox.question(None, "询问", "是否确认此操作？")
    print("用户选择：", "确定" if result else "取消")
