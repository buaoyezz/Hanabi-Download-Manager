from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QSize, QRect, QPoint, QTimer, Property, QObject
from PySide6.QtWidgets import QWidget


class WindowResizeAnimation(QObject):
    """窗口大小调整动画类
    
    提供平滑的窗口大小变化动画效果，避免窗口调整大小时的生硬感
    """
    
    def __init__(self, parent=None):
        """初始化窗口大小调整动画
        
        参数:
            parent: 父对象
        """
        super().__init__(parent)
        
        # 初始化目标大小和位置属性 - 必须在创建动画之前初始化
        self._target_size = QSize()
        self._target_pos = QPoint()
        
        # 动画持续时间（毫秒）
        self.animation_duration = 200
        
        # 动画缓动曲线
        self.animation_curve = QEasingCurve.OutCubic
        
        # 大小调整动画
        self.size_animation = QPropertyAnimation(self, b"target_size")
        self.size_animation.setEasingCurve(self.animation_curve)
        self.size_animation.setDuration(self.animation_duration)
        
        # 位置调整动画（保持窗口中心不变）
        self.pos_animation = QPropertyAnimation(self, b"target_pos")
        self.pos_animation.setEasingCurve(self.animation_curve)
        self.pos_animation.setDuration(self.animation_duration)
        
        # 目标窗口
        self._target_window = None
        
        # 防抖定时器
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._start_animation)
        self._pending_size = None
        self._pending_pos = None
    
    def set_target_window(self, window):
        """设置目标窗口
        
        参数:
            window: 要应用动画的窗口
        """
        self._target_window = window
    
    def resize_smoothly(self, new_width, new_height, center_on_screen=False):
        """平滑调整窗口大小
        
        参数:
            new_width: 新的宽度
            new_height: 新的高度
            center_on_screen: 是否在屏幕上居中
        """
        if not self._target_window:
            return
            
        # 停止任何正在进行的动画
        self.size_animation.stop()
        self.pos_animation.stop()
        
        # 获取当前大小和位置
        current_size = self._target_window.size()
        current_pos = self._target_window.pos()
        
        # 计算新位置（保持窗口中心不变）
        new_pos = current_pos
        if not center_on_screen:
            # 计算当前窗口中心点
            center_x = current_pos.x() + current_size.width() / 2
            center_y = current_pos.y() + current_size.height() / 2
            
            # 根据新大小计算新位置，保持中心点不变
            new_pos = QPoint(
                int(center_x - new_width / 2),
                int(center_y - new_height / 2)
            )
        
        # 保存待处理的大小和位置
        self._pending_size = QSize(new_width, new_height)
        self._pending_pos = new_pos
        
        # 启动防抖定时器
        self._debounce_timer.start(50)  # 50毫秒防抖
    
    def _start_animation(self):
        """开始动画"""
        if not self._target_window or not self._pending_size:
            return
        
        # 设置动画起始值和结束值
        self.size_animation.setStartValue(self._target_window.size())
        self.size_animation.setEndValue(self._pending_size)
        
        self.pos_animation.setStartValue(self._target_window.pos())
        self.pos_animation.setEndValue(self._pending_pos)
        
        # 启动动画
        self.size_animation.start()
        self.pos_animation.start()
    
    def get_target_size(self):
        """获取目标大小"""
        # 确保属性存在，如果不存在则初始化
        if not hasattr(self, '_target_size'):
            self._target_size = QSize()
        return self._target_size
    
    def set_target_size(self, size):
        """设置目标大小"""
        # 保存大小并应用到窗口
        self._target_size = size
        if self._target_window:
            self._target_window.resize(size)
    
    def get_target_pos(self):
        """获取目标位置"""
        # 确保属性存在，如果不存在则初始化
        if not hasattr(self, '_target_pos'):
            self._target_pos = QPoint()
        return self._target_pos
    
    def set_target_pos(self, pos):
        """设置目标位置"""
        # 保存位置并应用到窗口
        self._target_pos = pos
        if self._target_window:
            self._target_window.move(pos)
    
    # 定义属性，用于QPropertyAnimation
    target_size = Property(QSize, get_target_size, set_target_size)
    target_pos = Property(QPoint, get_target_pos, set_target_pos)


def apply_resize_animation(window, new_width, new_height, center_on_screen=False):
    """应用窗口大小调整动画的便捷函数
    
    参数:
        window: 要调整大小的窗口
        new_width: 新的宽度
        new_height: 新的高度
        center_on_screen: 是否在屏幕上居中
    
    返回:
        WindowResizeAnimation: 动画对象
    """
    # 创建动画对象并保存在窗口上，防止被垃圾回收
    if not hasattr(window, '_resize_animation'):
        window._resize_animation = WindowResizeAnimation(window)
        window._resize_animation.set_target_window(window)
    
    # 应用动画
    window._resize_animation.resize_smoothly(new_width, new_height, center_on_screen)
    return window._resize_animation
