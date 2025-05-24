from PySide6.QtCore import (QPropertyAnimation, QEasingCurve, Property, QPoint, 
                             Signal, QParallelAnimationGroup, QSequentialAnimationGroup,
                             QTimer, QRect, QSize)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect, QApplication
from PySide6.QtGui import QTransform
from core.log.log_manager import log
import math

class ModernNotifyAnimation(QWidget):
    """现代化通知动画系统，提供流畅自然的动画效果"""
    
    # 动画状态信号
    show_started = Signal()
    show_finished = Signal()
    hide_started = Signal()
    hide_finished = Signal()
    position_updated = Signal(int)  # 位置索引更新信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 动画配置
        self.config = {
            'notification_height': 80,
            'spacing': 12,
            'margin_right': 20,
            'margin_bottom': 20,
            'show_duration': 600,
            'hide_duration': 450,
            'position_duration': 400,
            'scale_factor': 0.95,
            'blur_radius': 8
        }
        
        # 状态属性
        self._opacity = 0.0
        self._scale = 1.0
        self._blur_radius = 0.0
        self.current_index = 0
        self.target_index = 0
        self.is_animating = False
        
        # 图形效果
        self._create_opacity_effect()
        
        # 动画组件初始化
        self._init_animations()
        
        # 自动隐藏定时器
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self._auto_hide)
        
    def _create_opacity_effect(self):
        """创建并设置透明度效果"""
        try:
            self.opacity_effect = QGraphicsOpacityEffect(self)
            self.opacity_effect.setOpacity(self._opacity)
            self.setGraphicsEffect(self.opacity_effect)
        except Exception as e:
            log.error(f"创建透明度效果失败: {e}")
            self.opacity_effect = None
            
    def _ensure_timer_exists(self):
        """确保定时器存在"""
        try:
            if not hasattr(self, 'auto_hide_timer') or self.auto_hide_timer is None:
                log.warning("定时器不存在，正在重新创建")
                self.auto_hide_timer = QTimer()
                self.auto_hide_timer.setSingleShot(True)
                self.auto_hide_timer.timeout.connect(self._auto_hide)
                return True
            return False
        except Exception as e:
            log.error(f"创建定时器失败: {e}")
            return False
            
    def __del__(self):
        """析构函数，确保安全清理资源"""
        try:
            # 停止所有动画
            if hasattr(self, 'show_group'):
                self.show_group.stop()
            if hasattr(self, 'hide_group'):
                self.hide_group.stop()
            if hasattr(self, 'position_anim'):
                self.position_anim.stop()
                
            # 停止定时器
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer:
                self.auto_hide_timer.stop()
                
            # 移除信号连接
            try:
                if hasattr(self, 'show_group'):
                    self.show_group.finished.disconnect()
                if hasattr(self, 'hide_group'):
                    self.hide_group.finished.disconnect()
                if hasattr(self, 'position_anim'):
                    self.position_anim.finished.disconnect()
            except:
                pass
                
        except Exception as e:
            log.error(f"动画对象析构时发生错误: {e}")
        
    def _init_animations(self):
        """初始化所有动画组件"""
        
        # === 显示动画组 ===
        self.show_group = QParallelAnimationGroup()
        
        # 位置动画 - 使用更自然的缓动
        self.show_pos_anim = QPropertyAnimation(self, b"pos")
        self.show_pos_anim.setDuration(self.config['show_duration'])
        self.show_pos_anim.setEasingCurve(QEasingCurve.OutBack)  # 回弹效果
        
        # 透明度动画
        self.show_opacity_anim = QPropertyAnimation(self, b"opacity")
        self.show_opacity_anim.setDuration(self.config['show_duration'] - 100)
        self.show_opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 缩放动画 - 从小到大的弹性效果
        self.show_scale_anim = QPropertyAnimation(self, b"scale")
        self.show_scale_anim.setDuration(self.config['show_duration'])
        self.show_scale_anim.setEasingCurve(QEasingCurve.OutBack)
        
        # 模糊动画 - 从模糊到清晰
        self.show_blur_anim = QPropertyAnimation(self, b"blur_radius")
        self.show_blur_anim.setDuration(self.config['show_duration'] // 2)
        self.show_blur_anim.setEasingCurve(QEasingCurve.OutQuad)
        
        self.show_group.addAnimation(self.show_pos_anim)
        self.show_group.addAnimation(self.show_opacity_anim)
        self.show_group.addAnimation(self.show_scale_anim)
        self.show_group.addAnimation(self.show_blur_anim)
        
        # === 隐藏动画组 ===
        self.hide_group = QParallelAnimationGroup()
        
        # 位置动画 - 加速离开
        self.hide_pos_anim = QPropertyAnimation(self, b"pos")
        self.hide_pos_anim.setDuration(self.config['hide_duration'])
        self.hide_pos_anim.setEasingCurve(QEasingCurve.InBack)
        
        # 透明度动画
        self.hide_opacity_anim = QPropertyAnimation(self, b"opacity")
        self.hide_opacity_anim.setDuration(self.config['hide_duration'])
        self.hide_opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        
        # 缩放动画 - 缩小消失
        self.hide_scale_anim = QPropertyAnimation(self, b"scale")
        self.hide_scale_anim.setDuration(self.config['hide_duration'])
        self.hide_scale_anim.setEasingCurve(QEasingCurve.InBack)
        
        # 模糊动画 - 变模糊
        self.hide_blur_anim = QPropertyAnimation(self, b"blur_radius")
        self.hide_blur_anim.setDuration(self.config['hide_duration'] // 2)
        self.hide_blur_anim.setEasingCurve(QEasingCurve.InQuad)
        
        self.hide_group.addAnimation(self.hide_pos_anim)
        self.hide_group.addAnimation(self.hide_opacity_anim)
        self.hide_group.addAnimation(self.hide_scale_anim)
        self.hide_group.addAnimation(self.hide_blur_anim)
        
        # === 位置调整动画 ===
        self.position_anim = QPropertyAnimation(self, b"pos")
        self.position_anim.setDuration(self.config['position_duration'])
        self.position_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 连接信号
        self._connect_signals()
        
    def _connect_signals(self):
        """连接动画信号"""
        # 修复：使用started()方法时而不是信号
        # 原来错误的代码：self.show_group.started.connect(...)
        # 修改为使用自定义方法：
        # 创建开始动画前的函数
        def on_show_animation_start():
            self.is_animating = True
            self.show_started.emit()
            
        # 创建隐藏动画前的函数
        def on_hide_animation_start():
            self.is_animating = True
            self.hide_started.emit()
        
        # 存储回调函数
        self._on_show_animation_start = on_show_animation_start
        self._on_hide_animation_start = on_hide_animation_start
        
        # 连接完成信号
        self.show_group.finished.connect(lambda: (
            setattr(self, 'is_animating', False),
            self.show_finished.emit(),
            self._start_auto_hide_timer()
        ))
        
        self.hide_group.finished.connect(lambda: (
            setattr(self, 'is_animating', False),
            self.hide_finished.emit(),
            self._cleanup()
        ))
        
        self.position_anim.finished.connect(lambda: 
            setattr(self, 'current_index', self.target_index)
        )
        
    # === 属性定义 ===
    def get_opacity(self):
        return self._opacity
        
    def set_opacity(self, opacity):
        self._opacity = max(0.0, min(1.0, opacity))
        try:
            if hasattr(self, 'opacity_effect') and self.opacity_effect is not None:
                try:
                    self.opacity_effect.setOpacity(self._opacity)
                except RuntimeError:
                    # 如果发生运行时错误，可能是对象已删除
                    log.warning("透明度效果对象可能已被删除，尝试重新创建")
                    self._create_opacity_effect()
            else:
                # 如果不存在，创建新的效果对象
                self._create_opacity_effect()
        except Exception as e:
            # 忽略已删除对象的错误
            import traceback
            log.error(f"设置透明度失败: {e}")
            # 重新创建透明度效果
            try:
                self.opacity_effect = QGraphicsOpacityEffect()
                self.setGraphicsEffect(self.opacity_effect)
                self.opacity_effect.setOpacity(self._opacity)
            except Exception as e2:
                log.error(f"重新创建透明度效果失败: {e2}")
        
    opacity = Property(float, get_opacity, set_opacity)
    
    def get_scale(self):
        return self._scale
        
    def set_scale(self, scale):
        self._scale = max(0.1, min(2.0, scale))
        self._update_transform()
        
    scale = Property(float, get_scale, set_scale)
    
    def get_blur_radius(self):
        return self._blur_radius
        
    def set_blur_radius(self, radius):
        self._blur_radius = max(0.0, min(20.0, radius))
        # 这里可以添加模糊效果的实现
        
    blur_radius = Property(float, get_blur_radius, set_blur_radius)
    
    def _update_transform(self):
        """更新变换矩阵"""
        transform = QTransform()
        # 以widget中心为缩放原点
        center_x = self.width() / 2
        center_y = self.height() / 2
        transform.translate(center_x, center_y)
        transform.scale(self._scale, self._scale)
        transform.translate(-center_x, -center_y)
        self.setTransform(transform)
        
    # === 公共动画接口 ===
    def show_notification(self, start_pos=None, end_pos=None, auto_hide_delay=4000):
        """显示通知动画"""
        try:
            if self.is_animating:
                return False
                
            # 计算位置
            if end_pos is None:
                end_pos = self._calculate_position(self.current_index)
                
            if start_pos is None:
                # 从屏幕右侧滑入
                start_pos = QPoint(end_pos.x() + 300, end_pos.y())
                
            # 设置初始状态
            self.move(start_pos)
            self.set_opacity(0.0)
            self.set_scale(self.config['scale_factor'])
            self.set_blur_radius(self.config['blur_radius'])
            
            # 配置动画
            self.show_pos_anim.setStartValue(start_pos)
            self.show_pos_anim.setEndValue(end_pos)
            
            self.show_opacity_anim.setStartValue(0.0)
            self.show_opacity_anim.setEndValue(1.0)
            
            self.show_scale_anim.setStartValue(self.config['scale_factor'])
            self.show_scale_anim.setEndValue(1.0)
            
            self.show_blur_anim.setStartValue(self.config['blur_radius'])
            self.show_blur_anim.setEndValue(0.0)
            
            # 确保定时器存在
            self._ensure_timer_exists()
            
            # 设置自动隐藏延时
            if auto_hide_delay > 0 and hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                try:
                    self.auto_hide_timer.setInterval(auto_hide_delay)
                except Exception as e:
                    log.error(f"设置定时器间隔失败: {e}")
                    # 尝试重新创建定时器
                    self._ensure_timer_exists()
                    try:
                        self.auto_hide_timer.setInterval(auto_hide_delay)
                    except:
                        log.error("再次设置定时器间隔失败，放弃自动隐藏")
            
            # 确保显示在最前面
            self.setWindowOpacity(1.0)
            
            # 显示并开始动画
            self.show()
            self.raise_()  # 提升到顶层
            
            # 使用定时器延迟一下再次提升，确保在其他窗口之上
            QTimer.singleShot(100, lambda: (self.raise_(), QApplication.processEvents()))
            
            # 在启动动画之前调用开始回调
            try:
                if hasattr(self, '_on_show_animation_start'):
                    self._on_show_animation_start()
            except Exception as e:
                log.error(f"动画开始回调执行失败: {e}")
                self.is_animating = True
                self.show_started.emit()
            
            # 启动动画
            try:
                self.show_group.start()
            except Exception as e:
                log.error(f"启动显示动画组失败: {e}")
                # 完成动画效果
                self.is_animating = False
                self.show_finished.emit()
                self._start_auto_hide_timer()
                return False
            
            log.debug(f"现代通知显示动画开始 - 索引: {self.current_index}")
            return True
        except Exception as e:
            log.error(f"显示通知动画异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            
            # 确保动画状态一致
            self.is_animating = False
            try:
                self.show_finished.emit()
            except:
                pass
                
            return False
        
    def hide_notification(self, end_pos=None):
        """隐藏通知动画"""
        try:
            if self.is_animating:
                return False
                
            # 尝试停止定时器
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                try:
                    self.auto_hide_timer.stop()
                except Exception as e:
                    log.error(f"停止定时器失败: {e}")
            
            start_pos = self.pos()
            if end_pos is None:
                # 向右侧滑出
                end_pos = QPoint(start_pos.x() + 300, start_pos.y())
                
            # 配置动画
            self.hide_pos_anim.setStartValue(start_pos)
            self.hide_pos_anim.setEndValue(end_pos)
            
            self.hide_opacity_anim.setStartValue(self._opacity)
            self.hide_opacity_anim.setEndValue(0.0)
            
            self.hide_scale_anim.setStartValue(self._scale)
            self.hide_scale_anim.setEndValue(0.8)
            
            self.hide_blur_anim.setStartValue(0.0)
            self.hide_blur_anim.setEndValue(self.config['blur_radius'])
            
            # 在启动动画之前调用开始回调
            try:
                if hasattr(self, '_on_hide_animation_start'):
                    self._on_hide_animation_start()
            except Exception as e:
                log.error(f"隐藏动画开始回调执行失败: {e}")
                self.is_animating = True
                self.hide_started.emit()
            
            # 开始动画
            try:
                self.hide_group.start()
            except Exception as e:
                log.error(f"启动隐藏动画组失败: {e}")
                # 完成动画效果
                self.is_animating = False
                self.hide_finished.emit()
                self._cleanup()
                return False
            
            log.debug(f"现代通知隐藏动画开始 - 索引: {self.current_index}")
            return True
        except Exception as e:
            log.error(f"隐藏通知动画异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            
            # 确保动画状态一致
            self.is_animating = False
            try:
                self.hide_finished.emit()
                self._cleanup()
            except:
                pass
                
            return False
        
    def update_position(self, new_index):
        """更新通知位置（用于队列重新排列）"""
        if self.is_animating or new_index == self.current_index:
            return False
            
        self.target_index = new_index
        new_pos = self._calculate_position(new_index)
        
        # 添加微妙的缩放效果
        scale_anim = QPropertyAnimation(self, b"scale")
        scale_anim.setDuration(200)
        scale_anim.setStartValue(1.0)
        scale_anim.setKeyValueAt(0.5, 0.98)
        scale_anim.setEndValue(1.0)
        scale_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 位置动画
        self.position_anim.setStartValue(self.pos())
        self.position_anim.setEndValue(new_pos)
        
        # 创建序列动画组
        sequence = QSequentialAnimationGroup()
        parallel = QParallelAnimationGroup()
        parallel.addAnimation(self.position_anim)
        parallel.addAnimation(scale_anim)
        sequence.addAnimation(parallel)
        
        sequence.start()
        self.position_updated.emit(new_index)
        
        log.debug(f"通知位置更新: {self.current_index} -> {new_index}")
        return True
        
    # === 辅助方法 ===
    def _calculate_position(self, index):
        """计算指定索引的位置"""
        if not self.parent():
            return QPoint(100, 100)
            
        parent_rect = self.parent().rect()
        widget_height = self.config['notification_height']
        spacing = self.config['spacing']
        margin_right = self.config['margin_right']
        margin_bottom = self.config['margin_bottom']
        
        x = parent_rect.width() - self.width() - margin_right
        y = (parent_rect.height() - margin_bottom - 
             (index + 1) * (widget_height + spacing))
        
        return QPoint(x, y)
        
    def _start_auto_hide_timer(self):
        """启动自动隐藏定时器"""
        try:
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None and self.auto_hide_timer.interval() > 0:
                self.auto_hide_timer.start()
        except Exception as e:
            log.error(f"启动自动隐藏定时器失败: {e}")
            
    def _auto_hide(self):
        """自动隐藏回调"""
        try:
            self.hide_notification()
        except Exception as e:
            log.error(f"自动隐藏回调失败: {e}")
            # 尝试直接隐藏
            try:
                self.hide()
                self._cleanup()
            except:
                pass
        
    def _cleanup(self):
        """清理资源"""
        self.hide()
        if self.current_index > 0:
            self.current_index -= 1
            
    # === 交互增强 ===
    def pause_auto_hide(self):
        """暂停自动隐藏（鼠标悬停时）"""
        self.auto_hide_timer.stop()
        
    def resume_auto_hide(self, remaining_time=None):
        """恢复自动隐藏"""
        if remaining_time is None:
            remaining_time = 2000  # 默认2秒后隐藏
        self.auto_hide_timer.setInterval(remaining_time)
        self.auto_hide_timer.start()
        
    def set_config(self, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                log.debug(f"动画配置更新: {key} = {value}")
                
    def get_animation_state(self):
        """获取当前动画状态"""
        return {
            'is_animating': self.is_animating,
            'current_index': self.current_index,
            'opacity': self._opacity,
            'scale': self._scale,
            'blur_radius': self._blur_radius
        }

# === 动画管理器 ===
class NotificationAnimationManager:
    """通知动画管理器，协调多个通知的动画"""
    
    def __init__(self):
        self.active_notifications = []
        self.animation_queue = []
        
    def add_notification(self, notification_widget):
        """添加新通知"""
        if not isinstance(notification_widget, ModernNotifyAnimation):
            return False
            
        # 设置索引
        notification_widget.current_index = len(self.active_notifications)
        
        # 连接信号
        notification_widget.hide_finished.connect(
            lambda: self._on_notification_hidden(notification_widget)
        )
        
        self.active_notifications.append(notification_widget)
        
        # 更新其他通知位置
        self._update_positions()
        
        return True
        
    def _on_notification_hidden(self, notification):
        """通知隐藏后的处理"""
        if notification in self.active_notifications:
            index = self.active_notifications.index(notification)
            self.active_notifications.remove(notification)
            
            # 更新后续通知的位置
            for i in range(index, len(self.active_notifications)):
                self.active_notifications[i].update_position(i)
                
    def _update_positions(self):
        """更新所有通知的位置"""
        for i, notification in enumerate(self.active_notifications):
            if notification.current_index != i:
                notification.update_position(i)
                
    def clear_all(self):
        """清除所有通知"""
        for notification in self.active_notifications[:]:
            notification.hide_notification()
        self.active_notifications.clear()