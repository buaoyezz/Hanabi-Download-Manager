from PySide6.QtWidgets import (
    QWidget, 
    QLabel, 
    QVBoxLayout, 
    QHBoxLayout, 
    QApplication, 
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, 
    QTimer, 
    QPoint, 
    QPropertyAnimation,
    Property,
    QEasingCurve
)
from PySide6.QtGui import QColor, QFont
from core.animations.notify_animation import NotifyAnimation
from core.font.font_manager import FontManager
from core.log.log_manager import log
from enum import Enum, auto

class NotificationType:
    INFO = "Tips"
    TIPS = "提示"
    WARNING = "警告"
    WARN = "Warn"
    ERROR = "错误"
    FAILED = "失败"
    SUCCESS = "成功"
# 更新通知样式，使用Mica风格的颜色
NOTIFICATION_STYLES = {
    NotificationType.INFO: ("#0D6EFD", "rgba(13, 110, 253, 0.5)"),
    NotificationType.TIPS: ("#0D6EFD", "rgba(13, 110, 253, 0.5)"),
    NotificationType.WARNING: ("#FFC107", "rgba(255, 193, 7, 0.5)"),
    NotificationType.WARN: ("#FFC107", "rgba(255, 193, 7, 0.5)"),
    NotificationType.ERROR: ("#DC3545", "rgba(220, 53, 69, 0.5)"),
    NotificationType.FAILED: ("#DC3545", "rgba(220, 53, 69, 0.5)"),
    NotificationType.SUCCESS: ("#28A745", "rgba(40, 167, 69, 0.5)")
}

# 图标映射
NOTIFICATION_ICONS = {
    NotificationType.INFO: 'info',
    NotificationType.TIPS: 'info',
    NotificationType.WARNING: 'warning',
    NotificationType.WARN: 'warning',
    NotificationType.ERROR: 'error',
    NotificationType.FAILED: 'error',
    NotificationType.SUCCESS: 'check'
}

class Notification(NotifyAnimation):
    # 类级别的通知队列管理
    active_notifications = []
    
    @classmethod
    def clear_all_notifications(cls):
        # 清理所有活动的通知
        for notification in cls.active_notifications[:]:
            try:
                notification.close()
                notification.deleteLater()
            except:
                pass
        cls.active_notifications.clear()
    
    def __init__(self, text="", title=None, type=NotificationType.TIPS, duration=8000, parent=None):
        try:
            super().__init__(parent)
            
            # 设置窗口属性
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # 动画时长设置
            self.show_animation_duration = 800
            self.hide_animation_duration = 600
            self.adjust_animation_duration = 500
            
            # 保存参数
            self.text = text
            self.title = title
            self.notification_type = type
            self.duration = duration
            
            # 保存类型和获取对应的图标
            self.icon_name = NOTIFICATION_ICONS.get(type, 'info')
            
            # 初始化字体管理器
            self.font_manager = FontManager()
            self.font_pages_manager = FontManager()
            
            # 初始化UI
            self._init_ui()
            
            # 创建定时器
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.on_timeout)
            
            # 标记动画状态
            self._show_animation_finished = False
            self._is_closing = False
        except Exception as e:
            log.error(f"初始化通知失败: {str(e)}")
            raise

    def _init_ui(self):
        # 获取通知样式
        text_color, highlight_color = NOTIFICATION_STYLES.get(
            self.notification_type, 
            NOTIFICATION_STYLES[NotificationType.TIPS]
        )
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        
        # 创建标题和内容标签
        title = self.title if self.title else self.notification_type
        
        # 创建水平布局用于图标和标题
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # 添加图标标签
        self.icon_label = QLabel()
        # 创建并设置Material Icons字体
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(22)
        self.icon_label.setFont(icon_font)
        
        # 设置图标
        self.icon_label.setText(self.font_manager.get_icon_text(self.icon_name))
        self.icon_label.setStyleSheet(f"color: {text_color};")
        
        self.title_label = QLabel(title)
        self.text_label = QLabel(self.text)
        self.text_label.setWordWrap(True)
        
        # 使用字体管理器，调整字体粗细
        self.font_pages_manager.apply_font(self.title_label)
        self.title_label.setStyleSheet(f"color: {text_color}; font-weight: 600;")
        
        self.font_pages_manager.apply_font(self.text_label)
        self.text_label.setStyleSheet("color: rgba(255, 255, 255, 0.95);")
        
        # 添加图标和标题到水平布局
        title_layout.addWidget(self.icon_label)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # 创建水平布局用于图标和内容
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(10, 8, 10, 8)

        # 创建左侧颜色条
        color_bar = QWidget()
        color_bar.setFixedWidth(4)
        color_bar.setStyleSheet(f"""
            background-color: {text_color};
            border-radius: 2px;
        """)
        
        # 创建内容区域
        content_widget = QWidget()
        content_widget_layout = QVBoxLayout(content_widget)
        content_widget_layout.setContentsMargins(0, 0, 0, 0)
        content_widget_layout.setSpacing(6)
        content_widget_layout.addLayout(title_layout) 
        content_widget_layout.addWidget(self.text_label)
        
        # 添加到水平布局
        content_layout.addWidget(color_bar)
        content_layout.addWidget(content_widget, 1)
        
        # 将水平布局添加到主布局
        layout.addLayout(content_layout)
        
        # 设置Mica云母效果样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(32, 32, 32, 0.65);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        
        # 设置标题标签的可访问名称以应用特定样式
        self.title_label.setAccessibleName("title")
        
        # 设置固定宽度和最大高度
        self.setFixedWidth(360)
        self.setMaximumHeight(160)
        
        # 设置窗口透明度
        self.setWindowOpacity(0.95)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
    def show_notification(self):
        try:
            # 如果正在关闭则不显示
            if self._is_closing:
                return
                
            # 调整大小以适应内容
            self.adjustSize()
            
            # 获取屏幕尺寸
            screen = QApplication.primaryScreen().availableGeometry()
            
            # 计算基础位置
            margin = 25
            start_x = screen.right() - self.width() - margin
            
            # 修改这里：限制最大偏移量，防止超出系统限制
            total_height = self.height() + margin
            active_count = len([n for n in Notification.active_notifications if n.isVisible()])
            max_notifications = min(active_count, 15)  # 限制最大通知数量为15个
            offset = max_notifications * total_height
            
            # 确保y坐标不会超出系统限制（32767）
            max_y = min(screen.top() + offset + total_height, 32700)  # 留一些余量
            end_y = min(screen.top() + offset + margin, 32700)
            
            # 将自己添加到活动通知列表
            if self not in Notification.active_notifications:
                Notification.active_notifications.append(self)
            
            # 开始显示动画
            self.pos_animation.setDuration(self.show_animation_duration)
            self.opacity_animation.setDuration(self.show_animation_duration)
            
            self.show_animation(
                QPoint(start_x, max_y),
                QPoint(start_x, end_y)
            )
            
            # 等待显示动画完成后再开始计时
            def start_timer():
                if not self._is_closing:
                    self._show_animation_finished = True
                    log.debug(f"通知显示动画完成，开始计时 {self.duration}ms")
                    self.timer.start(self.duration)
                
            QTimer.singleShot(self.show_animation_duration + 100, start_timer)
            log.debug(f"显示通知: {self.text_label.text()}, 持续时间: {self.duration}ms")
        except Exception as e:
            log.error(f"显示通知失败: {str(e)}")
            self.close()

    def close(self):
        try:
            if not self._is_closing:
                self._is_closing = True
                self.timer.stop()
                if self in Notification.active_notifications:
                    Notification.active_notifications.remove(self)
                super().close()
                self.deleteLater()
        except Exception as e:
            log.error(f"关闭通知失败: {str(e)}")
            
    def on_timeout(self):
        try:
            if self._is_closing:
                return
                
            if not self._show_animation_finished:
                log.debug("显示动画未完成，延迟隐藏")
                QTimer.singleShot(500, self.on_timeout)
                return
                
            # 计算隐藏动画的位置
            screen = QApplication.primaryScreen().availableGeometry()
            margin = 25  # 与显示通知边距保持一致
            start_x = screen.right() - self.width() - margin
            current_y = self.y()
            end_y = current_y - self.height() - margin  # 向上滑出
            
            log.debug(f"通知开始隐藏，显示时长: {self.duration}ms")
            # 开始隐藏动画
            self.hide_animation(
                QPoint(start_x, current_y),
                QPoint(start_x, end_y)
            )
        except Exception as e:
            log.error(f"隐藏通知失败: {str(e)}")
            self.close()

    def _on_hide_finished(self):
        try:
            if self._is_closing:
                return
                
            self._is_closing = True
            # 从活动通知列表中移除自己
            if self in Notification.active_notifications:
                index = Notification.active_notifications.index(self)
                Notification.active_notifications.pop(index)
                
                # 重新调整其他通知的位置
                self._adjust_other_notifications(0)
            
            # 最后删除自己
            self.deleteLater()
        except Exception as e:
            log.error(f"通知隐藏完成处理失败: {str(e)}")
            self.close()

    def _adjust_other_notifications(self, start_index):
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 25  # 与其他边距保持一致
        total_height = self.height() + margin
        
        # 修改这里：只调整可见的通知，并限制最大数量
        visible_notifications = [n for n in Notification.active_notifications if n.isVisible()][:15]
        
        # 从顶部开始重新排列所有可见通知
        for i, notif in enumerate(visible_notifications):
            # 确保y坐标不会超出系统限制
            target_y = min(screen.top() + (i * total_height) + margin, 32700)
            current_x = notif.x()
            
            # 创建位置动画
            anim = QPropertyAnimation(notif, b"pos", notif)
            anim.setDuration(self.adjust_animation_duration)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.setStartValue(notif.pos())
            anim.setEndValue(QPoint(current_x, target_y))
            anim.start()

class NotifyManager:
    @staticmethod
    def info(text, duration=8000):
        notif = Notification(text=text, type=NotificationType.INFO, duration=duration)
        notif.show_notification()
    
    @staticmethod  
    def warning(text, duration=8000):
        notif = Notification(text=text, type=NotificationType.WARNING, duration=duration)
        notif.show_notification()
    
    @staticmethod
    def error(text, duration=8000):
        notif = Notification(text=text, type=NotificationType.ERROR, duration=duration)
        notif.show_notification()
    
    @staticmethod
    def show_message(title, message, level="info", duration=8000):
        """显示带有标题的消息通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别，可以是 "info", "warning", "error", "success"
            duration: 显示持续时间(毫秒)
        """
        notification_type = NotificationType.INFO
        if level == "warning":
            notification_type = NotificationType.WARNING
        elif level == "error":
            notification_type = NotificationType.ERROR
        elif level == "success":
            notification_type = NotificationType.SUCCESS
            
        notif = Notification(text=message, title=title, type=notification_type, duration=duration)
        notif.show_notification()
        
    @staticmethod
    def success(text, duration=8000):
        notif = Notification(text=text, type=NotificationType.SUCCESS, duration=duration)
        notif.show_notification()
        
    @staticmethod
    def clear():
        Notification.clear_all_notifications()

