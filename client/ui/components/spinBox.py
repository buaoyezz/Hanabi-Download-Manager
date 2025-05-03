from PySide6.QtWidgets import QSpinBox, QStyle
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from core.font.font_manager import FontManager

class CustomSpinBox(QSpinBox):
    """自定义数字输入框组件，符合应用的深色主题设计"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        self.font_manager.apply_font(self)
        
        # 基本属性设置
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(36)  # 设置最小高度
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # 隐藏默认的上下按钮
        
        # 设置样式表
        self.setStyleSheet("""
            CustomSpinBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 3px 12px;
                min-width: 80px;
                font-size: 14px;
            }
            
            CustomSpinBox:hover {
                border: 1px solid #7E57C2;
                background-color: #333337;
            }
            
            CustomSpinBox:focus {
                border: 1px solid #B39DDB;
            }
        """)
    
    def paintEvent(self, event):
        """自定义绘制数字输入框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        
        # 设置背景色
        if self.hasFocus():
            background_color = QColor("#2D2D30")
        elif self.underMouse():
            background_color = QColor("#333337")
        else:
            background_color = QColor("#2D2D30")
        
        # 绘制背景
        painter.fillPath(path, background_color)
        
        # 绘制边框
        if self.hasFocus():
            border_color = QColor("#B39DDB")  # 紫色聚焦边框
        elif self.underMouse():
            border_color = QColor("#7E57C2")  # 较浅的紫色悬停边框
        else:
            border_color = QColor("#3C3C3C")  # 默认边框颜色
        
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # 使用父类绘制文本，必须调用此方法才能正确显示文本
        super().paintEvent(event)
    
    def wheelEvent(self, event):
        """处理鼠标滚轮事件，支持鼠标滚轮调整数值"""
        if self.hasFocus():
            delta = event.angleDelta().y()
            if delta > 0:
                self.stepUp()
            else:
                self.stepDown()
            event.accept()
        else:
            super().wheelEvent(event) 