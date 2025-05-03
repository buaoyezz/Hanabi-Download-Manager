from PySide6.QtWidgets import QSlider, QStyle, QWidget
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QBrush, QLinearGradient
from core.font.font_manager import FontManager

class CustomSlider(QSlider):
    """自定义滑动条组件，符合应用的深色主题设计"""
    
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 基本属性设置
        self.setFocusPolicy(Qt.StrongFocus)
        if orientation == Qt.Horizontal:
            self.setMinimumHeight(24)  # 水平滑动条最小高度
        else:
            self.setMinimumWidth(24)   # 垂直滑动条最小宽度
        
        # 自定义颜色
        self.handle_color = QColor("#7E57C2")  # 滑块颜色
        self.handle_hover_color = QColor("#9575CD")  # 滑块悬停颜色
        self.handle_pressed_color = QColor("#5E35B1")  # 滑块按下颜色
        self.groove_color = QColor("#2D2D30")  # 滑动槽颜色
        self.progress_color = QColor("#7E57C2")  # 进度条颜色
        
        # 跟踪鼠标
        self.setMouseTracking(True)
        self.hover_pos = None
        self.is_pressed = False
    
    def paintEvent(self, event):
        """自定义绘制滑动条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 根据方向计算尺寸
        is_horizontal = self.orientation() == Qt.Horizontal
        
        if is_horizontal:
            # 水平滑动条
            groove_rect = QRect(0, (self.height() - 8) // 2, self.width(), 8)
            groove_radius = 4
            
            # 计算滑块位置
            value_range = self.maximum() - self.minimum()
            if value_range == 0:
                value_pos = 0
            else:
                value_pos = (self.value() - self.minimum()) / value_range
                
            handle_x = int(value_pos * (self.width() - 18)) + 9
            handle_rect = QRect(handle_x - 9, (self.height() - 18) // 2, 18, 18)
            
            # 计算填充进度区域
            progress_rect = QRect(groove_rect.left(), groove_rect.top(), 
                                 handle_rect.center().x(), groove_rect.height())
        else:
            # 垂直滑动条
            groove_rect = QRect((self.width() - 8) // 2, 0, 8, self.height())
            groove_radius = 4
            
            # 计算滑块位置
            value_range = self.maximum() - self.minimum()
            if value_range == 0:
                value_pos = 0
            else:
                value_pos = 1.0 - (self.value() - self.minimum()) / value_range
                
            handle_y = int(value_pos * (self.height() - 18)) + 9
            handle_rect = QRect((self.width() - 18) // 2, handle_y - 9, 18, 18)
            
            # 计算填充进度区域
            progress_rect = QRect(groove_rect.left(), handle_rect.center().y(),
                                 groove_rect.width(), groove_rect.bottom() - handle_rect.center().y())
        
        # 绘制滑动槽(背景)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.groove_color))
        painter.drawRoundedRect(groove_rect, groove_radius, groove_radius)
        
        # 绘制进度部分
        painter.setBrush(QBrush(self.progress_color))
        if is_horizontal:
            progress_path = QPainterPath()
            progress_path.addRoundedRect(progress_rect, groove_radius, groove_radius)
            painter.drawPath(progress_path)
        else:
            progress_path = QPainterPath()
            progress_path.addRoundedRect(progress_rect, groove_radius, groove_radius)
            painter.drawPath(progress_path)
        
        # 绘制滑块
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 确定滑块颜色
        if self.is_pressed:
            handle_fill_color = self.handle_pressed_color
        elif self.hover_pos and handle_rect.contains(self.hover_pos):
            handle_fill_color = self.handle_hover_color
        else:
            handle_fill_color = self.handle_color
            
        # 绘制滑块阴影效果
        shadow_rect = handle_rect.adjusted(1, 1, 1, 1)
        shadow_path = QPainterPath()
        shadow_path.addEllipse(shadow_rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawPath(shadow_path)
        
        # 绘制滑块主体
        handle_path = QPainterPath()
        handle_path.addEllipse(handle_rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(handle_fill_color)
        painter.drawPath(handle_path)
        
        # 绘制滑块内部圆形点缀
        inner_rect = handle_rect.adjusted(5, 5, -5, -5)
        inner_path = QPainterPath()
        inner_path.addEllipse(inner_rect)
        painter.setBrush(QColor(255, 255, 255, 50))
        painter.drawPath(inner_path)
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        self.is_pressed = True
        self.update()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        self.hover_pos = event.pos()
        self.update()
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """处理鼠标离开事件"""
        self.hover_pos = None
        self.update()
        super().leaveEvent(event)
    
    def wheelEvent(self, event):
        """处理鼠标滚轮事件"""
        if self.hasFocus():
            delta = event.angleDelta().y()
            if delta > 0:
                self.setValue(self.value() + self.singleStep())
            else:
                self.setValue(self.value() - self.singleStep())
            event.accept()
        else:
            super().wheelEvent(event) 