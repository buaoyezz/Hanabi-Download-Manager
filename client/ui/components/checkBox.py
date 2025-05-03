from PySide6.QtWidgets import QCheckBox, QStyle
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from core.font.font_manager import FontManager

class CustomCheckBox(QCheckBox):
    """自定义勾选框组件，符合应用的深色主题设计"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        self.font_manager.apply_font(self)
        
        # 基本属性设置
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(30)  # 设置最小高度
        
        # 设置样式表
        self.setStyleSheet("""
            CustomCheckBox {
                color: #FFFFFF;
                spacing: 8px;
                outline: none;
                font-size: 14px;
            }
            
            CustomCheckBox:hover {
                color: #CCCCFF;
            }
            
            CustomCheckBox:focus {
                color: #B39DDB;
            }
        """)
    
    def paintEvent(self, event):
        """自定义绘制勾选框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取文本和勾选框的尺寸
        checkbox_rect = QRect(0, (self.height() - 20) // 2, 20, 20)
        
        # 绘制勾选框
        path = QPainterPath()
        path.addRoundedRect(checkbox_rect, 4, 4)
        
        # 设置背景色
        if self.isChecked():
            if self.hasFocus():
                bg_color = QColor("#9575CD")  # 紫色选中+聚焦状态
            else:
                bg_color = QColor("#7E57C2")  # 紫色选中状态
        else:
            bg_color = QColor("#2D2D30")  # 未选中状态
        
        # 绘制背景
        painter.fillPath(path, bg_color)
        
        # 绘制边框
        if self.hasFocus():
            border_color = QColor("#B39DDB")  # 紫色聚焦边框
        elif self.isChecked():
            border_color = QColor("#9575CD")  # 较浅的紫色选中边框
        elif self.underMouse():
            border_color = QColor("#7E57C2")  # 悬停边框
        else:
            border_color = QColor("#3C3C3C")  # 默认边框颜色
        
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # 如果被选中，绘制勾选标记
        if self.isChecked():
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            # 绘制对勾
            check_padding = 4
            painter.drawLine(
                checkbox_rect.left() + check_padding,
                checkbox_rect.top() + checkbox_rect.height() // 2,
                checkbox_rect.left() + checkbox_rect.width() // 2 - 1,
                checkbox_rect.bottom() - check_padding
            )
            painter.drawLine(
                checkbox_rect.left() + checkbox_rect.width() // 2 - 1,
                checkbox_rect.bottom() - check_padding,
                checkbox_rect.right() - check_padding,
                checkbox_rect.top() + check_padding
            )
        
        # 绘制文本
        text_rect = self.rect().adjusted(checkbox_rect.width() + 8, 0, 0, 0)
        if self.hasFocus():
            text_color = QColor("#B39DDB")
        elif self.underMouse():
            text_color = QColor("#CCCCFF")
        else:
            text_color = QColor("#FFFFFF")
        
        painter.setPen(text_color)
        painter.setFont(self.font())
        painter.drawText(text_rect, Qt.AlignVCenter, self.text())
    
    def sizeHint(self):
        """返回控件的建议尺寸"""
        size = super().sizeHint()
        return QSize(size.width(), max(30, size.height())) 