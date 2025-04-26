from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from core.font.font_manager import FontManager

class CustomMessageBox(QDialog):
    def __init__(self, parent=None, title="提示", text="", buttons=None, icon="info"):
        super().__init__(parent)
        
        # 用于窗口拖动
        self._is_dragging = False
        self._drag_start_pos = None
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(400)  # 设置最小宽度
        
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
        
        # 标题区域
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 根据类型选择图标和颜色
        icon_character = ""
        icon_color = "#B39DDB"  # 默认紫色
        
        if icon == "info" or title == "提示":
            icon_character = "\ue88e"  # info
            icon_color = "#B39DDB"
        elif icon == "warning" or title == "警告" or title == "下载提示":
            icon_character = "\ue002"  # warning
            icon_color = "#F9A825"
        elif icon == "error" or title == "错误":
            icon_character = "\ue000"  # error
            icon_color = "#EF5350"
        elif icon == "question" or title == "询问":
            icon_character = "\ue887"  # help
            icon_color = "#4FC3F7"
        
        # 标题图标
        if title == "下载提示":
            # 对下载提示使用更大的警告图标
            icon_label = QLabel()
            icon_font = QFont("Material Icons")
            icon_font.setPixelSize(20)  # 稍微增大图标大小
            icon_label.setFont(icon_font)
            icon_label.setText(icon_character)
            icon_label.setFixedSize(24, 24)  # 固定图标大小
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet(f"color: {icon_color}; background-color: transparent;")
            title_layout.addWidget(icon_label)
        else:
            # 其他类型消息框的图标
            icon_label = QLabel()
            icon_font = QFont("Material Icons")
            icon_font.setPixelSize(18)
            icon_label.setFont(icon_font)
            icon_label.setText(icon_character)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setStyleSheet(f"color: {icon_color}; background-color: transparent;")
            title_layout.addWidget(icon_label)
        
        # 标题文本
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 16px;
            font-weight: bold;
        """)
        self.font_manager.apply_font(title_label)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        self.font_manager.apply_icon_font(close_btn, 16)
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
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        container_layout.addWidget(separator)
        
        # 消息内容
        message_label = QLabel(text)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            color: #CCCCCC;
            font-size: 14px;
            padding: 10px 0;
            min-height: 40px;
        """)
        self.font_manager.apply_font(message_label)
        container_layout.addWidget(message_label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        # 默认按钮
        if not buttons:
            buttons = [("确定", True)]
        
        # 添加按钮
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
        dialog = CustomMessageBox(parent, title, text, buttons, "info")
        return dialog.exec()
    
    @staticmethod
    def warning(parent, title, text, buttons=None):
        dialog = CustomMessageBox(parent, title, text, buttons, "warning")
        return dialog.exec()
    
    @staticmethod
    def error(parent, title, text, buttons=None):
        dialog = CustomMessageBox(parent, title, text, buttons, "error")
        return dialog.exec()
    
    @staticmethod
    def question(parent, title, text, buttons=None):
        if not buttons:
            buttons = [("确定", True), ("取消", False)]
        dialog = CustomMessageBox(parent, title, text, buttons, "question")
        return dialog.exec()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 只在标题栏区域允许拖动
            if event.pos().y() <= 50:  # 标题栏高度大约50像素
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

# 使用示例：
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 信息提示
    CustomMessageBox.info(None, "提示", "这是一条信息提示")
    
    # 警告提示
    CustomMessageBox.warning(None, "警告", "这是一条警告信息")
    
    # 错误提示
    CustomMessageBox.error(None, "错误", "这是一条错误信息")
    
    # 询问对话框
    result = CustomMessageBox.question(None, "询问", "是否确认此操作？")
    print("用户选择：", "确定" if result else "取消")
