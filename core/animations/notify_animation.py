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
            'notification_height': 80,   # 通知的标准高度
            'spacing': 12,               # 通知间距
            'margin_right': 20,          # 右边距
            'margin_bottom': 20,         # 底边距
            'show_duration': 600,        # 显示动画时长
            'hide_duration': 450,        # 隐藏动画时长
            'position_duration': 400,    # 位置调整动画时长
            'scale_factor': 0.95,        # 缩放比例
            'blur_radius': 8,            # 模糊半径
            'position_ease': QEasingCurve.OutCubic,  # 位置动画缓动类型
            'replace_mode': True,        # 是否启用替换模式 - 强制设为True
            'replace_duration': 500,     # 替换动画时长
            'replace_slide_offset': 100  # 增大替换滑动偏移量
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
            # 使用hasattr和getattr的组合来安全检查对象是否还存在
            # 避免直接访问可能已删除的C++对象
            
            # 安全地停止所有动画
            animations_to_check = ['show_group', 'hide_group', 'position_anim']
            for anim_name in animations_to_check:
                if hasattr(self, anim_name):
                    try:
                        # 不直接访问对象，而是使用更安全的方式检查
                        animation = getattr(self, anim_name, None)
                        if animation is not None:
                            # 使用异常处理来安全地尝试停止
                            try:
                                animation.stop()
                            except RuntimeError:
                                # 忽略C++对象已删除的错误
                                pass
                    except Exception:
                        # 忽略所有错误
                        pass
            
            # 停止定时器
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer:
                try:
                    self.auto_hide_timer.stop()
                except Exception:
                    pass
                
            # 不尝试移除信号连接 - 这很可能导致访问已删除的C++对象
            # 信号连接会在对象被GC时自动清理
                
        except Exception as e:
            # 捕获但不记录错误，避免在析构过程中产生更多日志
            pass
        
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
                end_pos = self._calculate_right_bottom_position(self.current_index)
                
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
                # 向右侧滑出并淡出
                end_pos = QPoint(start_pos.x() + 200, start_pos.y())
                
            # 配置动画
            self.hide_pos_anim.setStartValue(start_pos)
            self.hide_pos_anim.setEndValue(end_pos)
            
            self.hide_opacity_anim.setStartValue(self._opacity)
            self.hide_opacity_anim.setEndValue(0.0)
            self.hide_opacity_anim.setDuration(self.config['hide_duration'] - 50)  # 稍微提前完成透明度变化
            
            self.hide_scale_anim.setStartValue(self._scale)
            self.hide_scale_anim.setEndValue(0.85)  # 稍微缩小，更自然
            self.hide_scale_anim.setEasingCurve(QEasingCurve.OutQuint)  # 更平滑的缓动
            
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
        try:
            # 检查条件：是否正在动画中或索引未变
            if self.is_animating or new_index == self.current_index:
                return False
                
            self.target_index = new_index
            new_pos = self._calculate_position(new_index)
            
            # 安全性检查：确保动画对象有效
            animations_valid = True
            
            # 检查位置动画是否有效
            if not hasattr(self, 'position_anim') or self.position_anim is None:
                log.warning(f"位置动画对象无效，重新创建")
                try:
                    self.position_anim = QPropertyAnimation(self, b"pos")
                    self.position_anim.setDuration(self.config['position_duration'])
                    self.position_anim.setEasingCurve(self.config['position_ease'])
                    self.position_anim.finished.connect(lambda: 
                        setattr(self, 'current_index', self.target_index)
                    )
                except Exception as e:
                    log.error(f"重新创建位置动画失败: {e}")
                    animations_valid = False
            
            # 如果动画不可用，直接移动位置
            if not animations_valid:
                self.move(new_pos)
                self.current_index = new_index
                self.position_updated.emit(new_index)
                log.debug(f"通知位置直接更新(无动画): {self.current_index} -> {new_index}")
                return True
            
            # 尝试创建和启动动画 - 使用try-except确保安全
            try:
                # 计算动画时长 - 基于移动距离调整
                move_distance = math.sqrt(
                    (self.pos().x() - new_pos.x())**2 + 
                    (self.pos().y() - new_pos.y())**2
                )
                
                # 动态调整动画时长，最小200ms，最大600ms
                adjusted_duration = min(
                    600, 
                    max(200, int(self.config['position_duration'] * move_distance / 400))
                )
                
                # 添加微妙的缩放效果，增加视觉吸引力
                scale_anim = QPropertyAnimation(self, b"scale")
                scale_anim.setDuration(adjusted_duration * 0.7)  # 比位置动画略短
                scale_anim.setStartValue(1.0)
                scale_anim.setKeyValueAt(0.5, 0.98)  # 轻微缩小
                scale_anim.setEndValue(1.0)
                scale_anim.setEasingCurve(QEasingCurve.InOutQuad)
                
                # 位置动画，使用适应性动画时长
                self.position_anim.stop()  # 停止可能正在进行的动画
                self.position_anim.setStartValue(self.pos())
                self.position_anim.setEndValue(new_pos)
                self.position_anim.setDuration(adjusted_duration)
                
                # 创建并行动画组
                parallel = QParallelAnimationGroup(self)
                parallel.addAnimation(self.position_anim)
                parallel.addAnimation(scale_anim)
                
                # 保存对动画组的引用，防止被垃圾回收
                self._current_position_anim_group = parallel
                
                # 连接动画结束信号
                parallel.finished.connect(lambda: self.position_updated.emit(new_index))
                
                # 启动动画
                parallel.start()
                
                log.debug(f"通知位置更新(增强动画): {self.current_index} -> {new_index}, 距离: {move_distance:.2f}px, 时长: {adjusted_duration}ms")
                return True
            except Exception as e:
                log.error(f"创建或启动位置更新动画失败: {e}")
                # 动画失败时的备用方案：直接移动
                try:
                    self.move(new_pos)
                    self.current_index = new_index
                    self.position_updated.emit(new_index)
                    log.debug(f"通知位置直接更新(动画失败): {self.current_index} -> {new_index}")
                    return True
                except Exception as e2:
                    log.error(f"直接更新位置也失败: {e2}")
                    return False
        except Exception as e:
            log.error(f"更新位置时发生异常: {e}")
            return False
        
    # === 辅助方法 ===
    def _calculate_position(self, index):
        """计算指定索引的位置 - 使用增强的位置计算算法"""
        return self._calculate_right_bottom_position(index)
        
    def _calculate_right_bottom_position(self, index):
        """增强的右上角位置计算，更稳定一致"""
        # 获取配置参数
        widget_height = max(self.height(), self.config['notification_height'])
        spacing = self.config['spacing']
        margin_right = self.config['margin_right']
        margin_bottom = self.config['margin_bottom']
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # 计算当前通知之前的所有通知高度总和
        total_height_before = 0
        
        # 假设这里有一个通知列表，我们需要计算索引之前的通知高度
        # 由于ModernNotifyAnimation类本身没有维护通知列表，这里使用一个估计值
        # 实际应用中应该从外部传入通知列表或使用其他方式获取
        estimated_height_per_notification = widget_height + spacing
        total_height_before = index * estimated_height_per_notification
        
        # 计算右上角位置
        x = screen_width - self.width() - margin_right
        y = screen.top() + margin_bottom + total_height_before
        
        # 确保位置在屏幕安全区域内
        x = max(10, min(x, screen_width - self.width() - 10))
        y = max(10, min(y, screen_height - widget_height - 10))
        
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

    def replace_animation(self, prev_notification):
        """创建一个替换动画，用新通知替换旧通知
        
        Args:
            prev_notification: 要被替换的上一个通知对象
            
        Returns:
            bool: 替换动画是否成功启动
        """
        try:
            # 强制启用替换模式，忽略配置
            self.config['replace_mode'] = True
            
            if not prev_notification:
                return False
                
            # 确保目标通知可见
            if not prev_notification.isVisible():
                return False
                
            # 获取当前位置
            current_pos = prev_notification.pos()
            slide_offset = self.config['replace_slide_offset']
            duration = self.config['replace_duration']
            
            # 创建位置动画 - 让前一个通知向右滑出
            prev_pos_anim = QPropertyAnimation(prev_notification, b"pos")
            prev_pos_anim.setDuration(duration)
            prev_pos_anim.setStartValue(current_pos)
            prev_pos_anim.setEndValue(QPoint(current_pos.x() + slide_offset, current_pos.y()))
            prev_pos_anim.setEasingCurve(QEasingCurve.OutQuad)
            
            # 创建透明度动画 - 让前一个通知淡出
            if hasattr(prev_notification, 'set_opacity'):
                # 使用set_opacity方法
                prev_opacity_anim = QPropertyAnimation(prev_notification, b"opacity")
                prev_opacity_anim.setDuration(max(duration - 100, 300))
                prev_opacity_anim.setStartValue(1.0)
                prev_opacity_anim.setEndValue(0.0)
                prev_opacity_anim.setEasingCurve(QEasingCurve.InQuad)
            else:
                # 使用窗口透明度
                prev_opacity_anim = QPropertyAnimation(prev_notification, b"windowOpacity")
                prev_opacity_anim.setDuration(max(duration - 100, 300))
                prev_opacity_anim.setStartValue(1.0)
                prev_opacity_anim.setEndValue(0.0)
                prev_opacity_anim.setEasingCurve(QEasingCurve.InQuad)
            
            # 创建动画组
            anim_group = QParallelAnimationGroup()
            anim_group.addAnimation(prev_pos_anim)
            anim_group.addAnimation(prev_opacity_anim)
            
            # 保存引用防止被垃圾回收
            prev_notification._replace_anim_group = anim_group
            
            # 设置标记，表示正在被替换
            prev_notification._being_replaced = True
            
            # 记住被替换的通知
            self._replacing_notification = prev_notification
            
            # 启动动画
            anim_group.start()
            
            # 延迟一段时间后关闭前一个通知
            QTimer.singleShot(duration + 100, 
                lambda: self._finish_replace_animation(prev_notification))
            
            log.debug(f"替换动画开始 - 替换索引: {getattr(prev_notification, 'current_index', -1)}")
            return True
            
        except Exception as e:
            log.error(f"创建替换动画失败: {e}")
            import traceback
            log.error(traceback.format_exc())
            
            # 发生错误时，直接关闭旧通知
            try:
                # 直接设置为关闭状态
                prev_notification._is_closing = True
                prev_notification.hide()
                QTimer.singleShot(100, prev_notification.deleteLater)
            except:
                pass
            
            return False
            
    def _finish_replace_animation(self, notification):
        """完成替换动画后的清理工作"""
        try:
            # 强制关闭通知
            try:
                # 设置关闭标志
                notification._is_closing = True
                
                # 移除所有引用
                if hasattr(self, '_replacing_notification') and self._replacing_notification == notification:
                    self._replacing_notification = None
                    
                # 彻底隐藏
                notification.hide()
                
                # 确保从活动通知列表中移除
                if hasattr(notification, 'active_notifications'):
                    if notification in notification.active_notifications:
                        notification.active_notifications.remove(notification)
                
                # 设置延迟删除
                QTimer.singleShot(100, notification.deleteLater)
            except Exception as e:
                log.error(f"强制关闭通知失败: {e}")
                
                # 最后尝试直接删除
                try:
                    notification.deleteLater()
                except:
                    pass
        except Exception as e:
            log.error(f"完成替换动画时出错: {e}")

# === 动画管理器 ===
class NotificationAnimationManager:
    """通知动画管理器，协调多个通知的动画"""
    
    def __init__(self):
        self.active_notifications = []
        self.animation_queue = []
        self.update_in_progress = False  # 添加更新状态跟踪
        self.replacement_mode = True  # 强制启用替换模式
        
    def add_notification(self, notification_widget):
        """添加新通知"""
        if not isinstance(notification_widget, ModernNotifyAnimation):
            return False
            
        # 如果开启了替换模式并且有活动通知，替换最后一个通知
        if self.replacement_mode and self.active_notifications:
            # 获取最后一个活动通知
            last_notification = self.active_notifications[-1]
            
            # 添加新通知
            notification_widget.current_index = 0
            self.active_notifications.append(notification_widget)
            
            # 连接信号
            notification_widget.hide_finished.connect(
                lambda: self._on_notification_hidden(notification_widget)
            )
            
            # 替换动画 - 仅当两个通知都存在时执行
            if hasattr(notification_widget, 'replace_animation'):
                try:
                    # 尝试调用替换动画方法
                    notification_widget.replace_animation(last_notification)
                    
                    # 设置短延迟后关闭上一个通知
                    QTimer.singleShot(500, lambda: self._replace_notification(last_notification))
                    
                    # 立即返回，不执行常规添加逻辑
                    return True
                except Exception as e:
                    log.error(f"执行替换动画失败: {e}")
                    # 出错时继续使用常规添加方式
            
        # 常规添加通知逻辑（原有代码）
        notification_widget.current_index = len(self.active_notifications)
        
        # 连接信号
        notification_widget.hide_finished.connect(
            lambda: self._on_notification_hidden(notification_widget)
        )
        
        self.active_notifications.append(notification_widget)
        
        # 使用延迟更新，确保通知UI已完全初始化
        QTimer.singleShot(50, self._update_positions)
        
        return True
    
    def _replace_notification(self, notification):
        """替换并关闭指定的通知"""
        try:
            # 直接关闭被替换的通知
            if hasattr(notification, 'close'):
                notification.close()
            elif hasattr(notification, 'hide_notification'):
                notification.hide_notification()
            else:
                # 如果没有合适的方法，尝试移除并隐藏
                if notification in self.active_notifications:
                    self.active_notifications.remove(notification)
                notification.hide()
        except Exception as e:
            log.error(f"替换关闭通知失败: {e}")
        
    def _on_notification_hidden(self, notification):
        """通知隐藏后的处理"""
        try:
            if notification in self.active_notifications:
                index = self.active_notifications.index(notification)
                self.active_notifications.remove(notification)
                
                # 设置一个小延迟再更新位置，以确保隐藏动画完成
                QTimer.singleShot(100, self._update_positions)
        except Exception as e:
            log.error(f"通知隐藏处理函数发生异常: {e}")
    
    def set_replacement_mode(self, enabled):
        """设置是否启用替换模式"""
        # 强制启用替换模式，忽略参数
        self.replacement_mode = True
        
    def _update_positions(self):
        """更新所有通知的位置，优化后的稳定版本"""
        if self.update_in_progress:
            # 防止重复调用
            return
            
        try:
            self.update_in_progress = True
            
            # 首先进行清理 - 移除已关闭或无效的通知
            valid_notifications = []
            for notif in self.active_notifications[:]:
                try:
                    if hasattr(notif, 'isVisible') and notif.isVisible():
                        valid_notifications.append(notif)
                    else:
                        # 从列表中移除无效通知
                        self.active_notifications.remove(notif)
                except Exception:
                    # 移除异常通知
                    if notif in self.active_notifications:
                        self.active_notifications.remove(notif)
            
            # 按Y位置排序（从下到上）- 确保正确的顺序
            try:
                valid_notifications.sort(key=lambda n: getattr(n, 'y', lambda: 0)(), reverse=True)
            except Exception as sort_err:
                log.error(f"通知排序失败: {sort_err}")
            
            # 计算最佳的动画延迟间隔 - 确保视觉平滑
            base_delay = 30  # 毫秒
            
            # 批量创建所有通知的位置动画
            for i, notification in enumerate(valid_notifications):
                try:
                    # 只在索引发生变化时更新位置
                    if getattr(notification, 'current_index', -1) != i:
                        # 计算延迟 - 使通知移动呈现波浪效果
                        delay = i * base_delay
                        
                        # 延迟调用，创建波浪效果
                        QTimer.singleShot(delay, lambda n=notification, idx=i: n.update_position(idx))
                except Exception as e:
                    log.error(f"更新通知位置失败: {e}")
            
            # 最后一次更新后，重置状态标志
            reset_delay = 500  # 固定延迟，确保所有动画有足够时间完成
            if valid_notifications:
                try:
                    reset_delay = valid_notifications[0].config['position_duration'] + 200
                except:
                    pass
                
            QTimer.singleShot(reset_delay, lambda: setattr(self, 'update_in_progress', False))
                
        except Exception as e:
            log.error(f"更新所有通知位置时发生异常: {e}")
            self.update_in_progress = False
            
    def clear_all(self):
        """清除所有通知"""
        for notification in self.active_notifications[:]:
            try:
                notification.hide_notification()
            except:
                pass
        self.active_notifications.clear()
        self.update_in_progress = False