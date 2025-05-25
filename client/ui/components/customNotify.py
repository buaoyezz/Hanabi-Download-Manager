from PySide6.QtWidgets import (
    QWidget, 
    QLabel, 
    QVBoxLayout, 
    QHBoxLayout, 
    QApplication, 
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, 
    QTimer, 
    QPoint, 
    QPropertyAnimation,
    Property,
    QEasingCurve,
    QRect
)
from PySide6.QtGui import QColor, QFont, QTransform
from core.animations.notify_animation import ModernNotifyAnimation
from core.font.font_manager import FontManager
from core.log.log_manager import log
from enum import Enum, auto
import traceback  # 添加traceback模块

# 尝试导入sip模块，如果不可用则忽略
try:
    import sip
    HAS_SIP = True
except ImportError:
    HAS_SIP = False
    log.warning("未找到sip模块，将使用替代方法检测对象有效性")

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

class Notification(ModernNotifyAnimation):
    # 类级别的通知队列管理
    active_notifications = []
    
    @classmethod
    def clear_all_notifications(cls):
        # 清理所有活动的通知
        for notification in cls.active_notifications[:]:
            try:
                # 使用新的隐藏动画，不要直接调用close
                if notification.isVisible() and not notification._is_closing:
                    notification.close()
                else:
                    notification.deleteLater()
            except Exception as e:
                log.error(f"清理通知失败: {str(e)}")
        cls.active_notifications.clear()
    
    def __init__(self, text="", title=None, type=NotificationType.TIPS, duration=8000, parent=None):
        try:
            super().__init__(parent)
            
            # 设置窗口属性 - 增强可见性
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            
            # 设置Z顺序为最上层
            try:
                self.raise_()
            except:
                pass
            
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
            
            # 初始化索引属性
            self.current_index = 0
            self.position_initialized = False
            
            # 初始化UI
            self._init_ui()
            
            # 设置定时器（使用新动画系统的自动隐藏功能）
            self.auto_hide_timer = None
            self._is_closing = False
            
            # 添加变换兼容性支持
            self._transform = QTransform()
            
        except Exception as e:
            log.error(f"初始化通知失败: {str(e)}")
            log.error(traceback.format_exc())
            raise

    def _init_ui(self):
        try:
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
            
            # 创建并使用FontManager的方法设置图标字体
            try:
                # 使用字体管理器设置图标
                self.font_manager.apply_icon_font(self.icon_label, 22)
                self.icon_label.setText(self.font_manager.get_icon_text(self.icon_name))
            except Exception as icon_error:
                log.error(f"设置图标字体失败: {icon_error}")
                # 备用方案：手动设置图标字体
                try:
                    icon_font = QFont("Material Icons")
                    icon_font.setPixelSize(22)
                    self.icon_label.setFont(icon_font)
                    
                    # 设置图标文本 - 使用简单字符
                    if self.icon_name in ['info', 'warning', 'error', 'check']:
                        self.icon_label.setText({
                            'info': 'ℹ',
                            'warning': '⚠',
                            'error': '✘',
                            'check': '✓'
                        }.get(self.icon_name, 'ℹ'))
                except:
                    # 最后的备用方案：使用纯文本
                    self.icon_label.setText(self.icon_name[0].upper())
            
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
            
            # 设置阴影效果
            try:
                shadow = QGraphicsDropShadowEffect(self)
                shadow.setBlurRadius(20)
                shadow.setColor(QColor(0, 0, 0, 50))
                shadow.setOffset(0, 2)
                self.setGraphicsEffect(shadow)
            except Exception as e:
                log.warning(f"设置阴影效果失败: {e}")
            
        except Exception as e:
            log.error(f"初始化通知UI失败: {e}")
            log.error(traceback.format_exc())
            
    def _create_opacity_effect(self):
        """创建并设置透明度效果"""
        try:
            # 检查是否已存在效果且是否有效
            if hasattr(self, 'opacity_effect') and self.opacity_effect is not None:
                try:
                    # 检查对象是否已被删除
                    if HAS_SIP and hasattr(sip, 'isdeleted') and sip.isdeleted(self.opacity_effect):
                        # 对象已被删除，创建新的
                        self.opacity_effect = QGraphicsOpacityEffect(self)
                        self.opacity_effect.setOpacity(self._opacity)
                        self.setGraphicsEffect(self.opacity_effect)
                    else:
                        # 使用替代检测方法
                        try:
                            # 尝试调用对象方法来测试是否有效
                            self.opacity_effect.opacity()
                            # 如果没抛出异常，对象有效
                            return
                        except RuntimeError:
                            # 对象无效，创建新的
                            self.opacity_effect = QGraphicsOpacityEffect(self)
                            self.opacity_effect.setOpacity(self._opacity)
                            self.setGraphicsEffect(self.opacity_effect)
                except:
                    # 其他异常情况，创建新的
                    self.opacity_effect = QGraphicsOpacityEffect(self)
                    self.opacity_effect.setOpacity(self._opacity)
                    self.setGraphicsEffect(self.opacity_effect)
            else:
                # 不存在，创建新的
                self.opacity_effect = QGraphicsOpacityEffect(self)
                self.opacity_effect.setOpacity(self._opacity)
                self.setGraphicsEffect(self.opacity_effect)
        except Exception as e:
            log.error(f"创建透明度效果失败: {e}")
            self.opacity_effect = None

    def _ensure_timer_exists(self):
        """确保定时器存在且可用"""
        try:
            if not hasattr(self, 'auto_hide_timer') or self.auto_hide_timer is None:
                log.warning("定时器不存在，正在重新创建")
                self.auto_hide_timer = QTimer()
                self.auto_hide_timer.setSingleShot(True)
                self.auto_hide_timer.timeout.connect(self._auto_hide)
                return True
            
            # 检查定时器是否有效
            try:
                self.auto_hide_timer.isActive()  # 测试是否可用
            except RuntimeError:
                # 定时器无效，重新创建
                log.warning("定时器无效，正在重新创建")
                self.auto_hide_timer = QTimer()
                self.auto_hide_timer.setSingleShot(True)
                self.auto_hide_timer.timeout.connect(self._auto_hide)
                return True
                
            return False
        except Exception as e:
            log.error(f"检查/创建定时器失败: {e}")
            try:
                # 最后尝试创建
                self.auto_hide_timer = QTimer()
                self.auto_hide_timer.setSingleShot(True)
                self.auto_hide_timer.timeout.connect(self._auto_hide)
            except:
                log.error("创建定时器完全失败")
            return False

    def set_opacity(self, opacity):
        self._opacity = max(0.0, min(1.0, opacity))
        try:
            if hasattr(self, 'opacity_effect') and self.opacity_effect is not None:
                try:
                    # 检查对象是否已删除
                    need_recreate = False
                    
                    if HAS_SIP and hasattr(sip, 'isdeleted'):
                        # 使用sip检测
                        if sip.isdeleted(self.opacity_effect):
                            need_recreate = True
                    else:
                        # 尝试使用异常检测方法
                        try:
                            # 调用方法测试对象有效性
                            opacity_value = self.opacity_effect.opacity()
                        except (RuntimeError, ReferenceError):
                            # 对象已被删除或无效
                            need_recreate = True
                        
                    if need_recreate:
                        # 重新创建效果
                        self._create_opacity_effect()
                        return
                        
                    # 尝试设置透明度
                    self.opacity_effect.setOpacity(self._opacity)
                except Exception as e:
                    # 如果发生任何错误，尝试重新创建
                    log.warning(f"透明度效果出现问题，尝试重新创建: {e}")
                    self._create_opacity_effect()
                    # 确保新创建的对象设置了正确的透明度
                    if self.opacity_effect is not None:
                        self.opacity_effect.setOpacity(self._opacity)
            else:
                # 如果不存在，创建新的效果对象
                self._create_opacity_effect()
        except Exception as e:
            # 忽略已删除对象的错误
            log.error(f"设置透明度失败: {e}")
            # 重新创建透明度效果
            try:
                self._create_opacity_effect()
            except Exception as e2:
                log.error(f"重新创建透明度效果失败: {e2}")

    def show_notification(self, start_pos=None, end_pos=None, auto_hide_delay=4000):
        """显示通知动画"""
        try:
            if self.is_animating:
                return False
                
            # 如果正在关闭则不显示
            if self._is_closing:
                return
                
            # 调整大小以适应内容
            self.adjustSize()
            
            # 预处理通知位置
            self._preprocess_notification_position()
            
            # 使用预处理的位置信息
            if end_pos is None:
                end_pos = self._calculate_right_bottom_position(self.current_index)
                
            # 如果起始位置未指定，默认从右侧滑入
            if start_pos is None:
                start_pos = QPoint(end_pos.x() + 300, end_pos.y())
            
            # 确保窗口可以显示
            self.setWindowOpacity(1.0)
            
            # 先移动到正确位置，避免动画开始前就显示在错误位置
            self.move(start_pos)
            self.raise_()  # 提升到顶层
            
            # 增强窗口显示 - 确保显示在最前面
            # 设置窗口标志，确保始终在顶层
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint | 
                Qt.X11BypassWindowManagerHint  # 增加此标志以绕过窗口管理器
            )
            
            # 先显示窗口
            self.show()
            self.raise_()
            
            # 强制处理事件，确保窗口重绘
            QApplication.processEvents()
            
            # 使用定时器延迟一下再次提升，确保在其他窗口之上
            QTimer.singleShot(20, lambda: self.raise_())
            QTimer.singleShot(100, lambda: (self.raise_(), QApplication.processEvents()))
            QTimer.singleShot(300, lambda: (self.raise_(), QApplication.processEvents()))
            
            # 监听显示完成信号
            if not hasattr(self, '_connected_signals'):
                self.show_finished.connect(self._on_show_finished)
                self.hide_finished.connect(self._on_hide_finished)
                self._connected_signals = True
            
            # 如果持续时间超过10秒，限制为10秒，防止通知显示太长时间
            display_duration = min(self.duration, 10000)
            
            # 尝试使用新动画系统
            success = False
            
            try:
                # 启动显示动画 - 增加错误处理
                success = super().show_notification(start_pos, end_pos, display_duration)
                if success:
                    log.debug(f"显示通知: {self.text}, 持续时间: {display_duration}ms")
                else:
                    log.warning("通知动画启动失败，使用备用显示方式")
                    raise Exception("动画启动失败")
            except Exception as animation_error:
                log.error(f"通知动画系统错误: {str(animation_error)}")
                log.debug(traceback.format_exc())
                success = False
            
            # 如果新动画系统失败，使用备用方法
            if not success:
                # 使用备用显示方式
                self.setup_fallback_display(end_pos, display_duration)
            
            # 确保定时器存在
            self._ensure_timer_exists()
            
            # 设置自动隐藏延时
            if auto_hide_delay > 0 and hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                try:
                    self.auto_hide_timer.setInterval(auto_hide_delay)
                except Exception as e:
                    log.error(f"设置定时器间隔失败: {e}")
                    # 尝试重新创建定时器
                    if self._ensure_timer_exists():
                        try:
                            self.auto_hide_timer.setInterval(auto_hide_delay)
                        except:
                            log.error("再次设置定时器间隔失败，放弃自动隐藏")
            
        except Exception as e:
            log.error(f"显示通知失败: {str(e)}")
            log.error(traceback.format_exc())
            try:
                # 最后的备用尝试
                self.setup_simple_display(display_duration if 'display_duration' in locals() else 8000)
            except Exception as final_error:
                log.error(f"所有显示方法均失败: {final_error}")
                # 完全失败时，确保通知被清理
                try:
                    self.close()
                except:
                    # 如果连close都失败，使用最最基本的方法清理
                    try:
                        self.hide()
                        self.deleteLater()
                    except:
                        # 如果一切都失败了，放弃
                        pass
                
    def setup_fallback_display(self, end_pos, duration):
        """设置备用显示方式，当主动画系统失败时使用"""
        try:
            # 直接设置位置并显示
            self.move(end_pos)
            self.setWindowOpacity(1.0)
            
            # 确保显示并保持在顶层 - 增强可见性
            # 重新设置窗口标志，确保置顶
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint | 
                Qt.X11BypassWindowManagerHint
            )
            
            # 显示和提升
            self.show()
            self.raise_()  # 提升到顶层
            QApplication.processEvents()  # 立即处理事件，确保窗口显示
            
            # 设置简单的淡入效果
            try:
                fade_in = QPropertyAnimation(self, b"windowOpacity")
                fade_in.setStartValue(0.7)  # 起始值更高，确保可见
                fade_in.setEndValue(1.0)
                fade_in.setDuration(300)
                fade_in.start()
                
                # 保存引用防止被回收
                if not hasattr(self, '_fade_animations'):
                    self._fade_animations = []
                self._fade_animations.append(fade_in)
            except Exception as e:
                log.warning(f"淡入动画创建失败，忽略: {e}")
            
            # 设置自动隐藏
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer:
                try:
                    self.auto_hide_timer.stop()  # 停止现有定时器
                except:
                    pass
                    
            # 创建新定时器
            try:
                # 使用新定时器避免共享对象可能带来的问题
                close_timer = QTimer(self)
                close_timer.setSingleShot(True)
                close_timer.timeout.connect(self.close)
                close_timer.start(duration)
                # 保存引用，避免被垃圾回收
                self.close_timer = close_timer
            except Exception as timer_error:
                log.error(f"创建关闭定时器失败: {timer_error}")
                # 使用单次调用的形式
                QTimer.singleShot(duration, self.close)
            
            # 确保通知显示前再次提升
            QTimer.singleShot(100, lambda: self.raise_())
            QTimer.singleShot(300, lambda: self.raise_())
            
            log.debug(f"使用备用方式显示通知: {self.text}, 持续时间: {duration}ms")
        except Exception as e:
            log.error(f"备用显示方式失败: {e}")
            self.setup_simple_display(duration)
    
    def setup_simple_display(self, duration):
        """最简单的显示方式，作为最后的备用选项"""
        try:
            # 重设窗口标志，强制显示在最前面
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint |
                Qt.X11BypassWindowManagerHint
            )
            
            # 设置不透明度为完全不透明
            self.setWindowOpacity(1.0)
            
            # 无特效直接显示
            try:
                # 尝试直接设置一个安全的位置 - 使用右下角
                screen = QApplication.primaryScreen().availableGeometry()
                x_pos = screen.right() - self.width() - 20
                y_pos = screen.bottom() - self.height() - 20
                self.move(x_pos, y_pos)
                self.show()
                self.raise_()  # 提升到顶层
                QApplication.processEvents()  # 立即处理事件
            except:
                # 如果连位置都设不了，直接show
                self.show()
                self.raise_()
                QApplication.processEvents()
            
            # 简单定时器关闭
            try:
                QTimer.singleShot(duration, self.close)
            except:
                # 如果定时器创建失败，使用最简单的延迟关闭
                def delayed_close():
                    import time
                    time.sleep(duration / 1000.0)  # 毫秒转秒
                    try:
                        self.close()
                    except:
                        pass
                # 启动后台线程处理
                from threading import Thread
                close_thread = Thread(target=delayed_close)
                close_thread.daemon = True
                close_thread.start()
            
            # 强制最终显示确认 - 增加多次尝试
            QTimer.singleShot(50, lambda: (self.raise_(), QApplication.processEvents()))
            QTimer.singleShot(200, lambda: (self.raise_(), QApplication.processEvents()))
            QTimer.singleShot(500, lambda: (self.raise_(), QApplication.processEvents()))
            
            log.debug(f"使用最简单方式显示通知: {self.text}")
        except Exception as e:
            log.error(f"最简单显示方式也失败: {e}")
            # 不再尝试，直接放弃

    def _on_show_finished(self):
        # 显示动画完成后的回调
        log.debug(f"通知显示动画完成")

    def _start_auto_hide_timer(self):
        """启动自动隐藏定时器"""
        try:
            if self._ensure_timer_exists():
                # 如果定时器被重新创建，直接开启
                self.auto_hide_timer.start()
                return
                
            # 使用已有定时器
            if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                try:
                    # 检查定时器是否有效
                    interval = self.auto_hide_timer.interval()
                    if interval > 0:
                        self.auto_hide_timer.start()
                except Exception as e:
                    log.error(f"启动已有定时器失败: {e}")
                    # 重新创建并启动
                    if self._ensure_timer_exists():
                        self.auto_hide_timer.start()
        except Exception as e:
            log.error(f"启动自动隐藏定时器失败: {e}")
            
    def _auto_hide(self):
        """自动隐藏回调"""
        try:
            # 确保对象没有被关闭
            if hasattr(self, '_is_closing') and self._is_closing:
                return
                
            # 尝试隐藏
            self.hide_notification()
        except Exception as e:
            log.error(f"自动隐藏回调失败: {e}")
            # 尝试直接隐藏
            try:
                self.hide()
                self._cleanup()
            except Exception as inner_e:
                log.error(f"备用隐藏也失败: {inner_e}")
                # 放弃并尝试删除自己
                try:
                    self.deleteLater()
                except:
                    pass

    def close(self):
        try:
            if not self._is_closing:
                self._is_closing = True
                
                # 停止自动隐藏计时器
                try:
                    if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                        if self.auto_hide_timer.isActive():
                            self.auto_hide_timer.stop()
                except Exception as e:
                    log.error(f"停止定时器失败: {e}")
                
                # 从活动通知列表中移除自己
                if self in Notification.active_notifications:
                    Notification.active_notifications.remove(self)
                    
                # 使用新的隐藏动画
                try:
                    if self.isVisible():
                        # 计算隐藏位置
                        screen = QApplication.primaryScreen().availableGeometry()
                        margin = 25
                        start_x = screen.right() - self.width() - margin
                        current_y = self.y()
                        end_y = current_y - self.height() - margin  # 向上滑出
                        
                        # 尝试使用动画，失败则使用备用方法
                        if not self.hide_notification(QPoint(start_x, end_y)):
                            raise Exception("隐藏动画启动失败")
                    else:
                        # 如果不可见，直接处理
                        self._on_hide_finished()
                except Exception as e:
                    log.error(f"隐藏动画失败，使用备用方法: {e}")
                    
                    # 使用淡出动画作为备用
                    try:
                        fade_out = QPropertyAnimation(self, b"windowOpacity")
                        fade_out.setStartValue(self.windowOpacity())
                        fade_out.setEndValue(0.0)
                        fade_out.setDuration(200)
                        fade_out.finished.connect(self._on_hide_finished)
                        fade_out.start()
                    except:
                        # 如果动画也失败，直接隐藏并释放
                        self.hide()
                        self._on_hide_finished()
            else:
                # 如果已经在关闭中，直接调用父类close
                try:
                    super().close()
                except:
                    pass
                self.deleteLater()
        except Exception as e:
            log.error(f"关闭通知失败: {str(e)}")
            try:
                self.hide()
                self.deleteLater()
            except:
                pass

    def _on_hide_finished(self):
        try:
            if not self._is_closing:
                self._is_closing = True
                
            # 从活动通知列表中移除自己
            if self in Notification.active_notifications:
                try:
                    index = Notification.active_notifications.index(self)
                    Notification.active_notifications.pop(index)
                    
                    # 重新调整其他通知的位置 - 使用新动画系统的方法
                    self._adjust_other_notifications(0)
                except Exception as e:
                    log.error(f"移除通知或调整其他通知位置失败: {e}")
            
            # 最后删除自己
            try:
                QTimer.singleShot(100, self.deleteLater)
            except Exception as e:
                log.error(f"设置延迟删除失败: {e}")
                # 直接尝试删除
                try:
                    self.deleteLater()
                except:
                    pass
        except Exception as e:
            log.error(f"通知隐藏完成处理失败: {str(e)}")
            try:
                self.deleteLater()
            except:
                pass

    def _adjust_other_notifications(self, start_index):
        """调整其他通知的位置"""
        try:
            # 先清理通知列表
            self._cleanup_notification_list()
            
            # 然后重新组织位置
            self._reorganize_notifications()
            
        except Exception as e:
            log.error(f"调整其他通知位置失败: {e}")

    # 添加transform兼容性方法
    def setTransform(self, transform):
        """
        兼容性方法：设置变换矩阵
        在ModernNotifyAnimation已经实现该方法时，此方法会被忽略
        """
        self._transform = transform
        if not hasattr(super(), "setTransform"):
            # 如果父类没有实现，我们手动应用变换
            try:
                self.setGeometry(QRect(
                    self.x(),
                    self.y(),
                    self.width() * transform.m11(),  # 水平缩放
                    self.height() * transform.m22()  # 垂直缩放
                ))
            except Exception as e:
                log.error(f"应用变换失败: {str(e)}")

    def _cleanup(self):
        """清理资源"""
        try:
            # 安全地清除所有引用和连接
            try:
                # 清除动画引用
                if hasattr(self, '_animations'):
                    self._animations.clear()
                if hasattr(self, '_fade_animations'):
                    self._fade_animations.clear()
                if hasattr(self, '_current_position_anim_group'):
                    try:
                        self._current_position_anim_group.stop()
                    except:
                        pass
                    self._current_position_anim_group = None
                
                # 清除定时器
                if hasattr(self, 'auto_hide_timer') and self.auto_hide_timer is not None:
                    try:
                        self.auto_hide_timer.stop()
                        self.auto_hide_timer = None
                    except:
                        pass
                
                # 设置标志表明对象正在被清理
                self._is_closing = True
            except Exception as e:
                log.error(f"清理资源时出错: {e}")
        except:
            pass
            
        # 隐藏窗口
        self.hide()
        
        # 尝试降低索引
        if self.current_index > 0:
            self.current_index -= 1

    def _cleanup_notification_list(self):
        """清理通知列表，移除无效通知"""
        try:
            # 移除无效通知
            to_remove = []
            for notif in Notification.active_notifications:
                try:
                    # 检查通知是否有效
                    if not notif.isVisible() or getattr(notif, '_is_closing', False):
                        to_remove.append(notif)
                except:
                    # 如果访问属性失败，通知可能已被删除
                    to_remove.append(notif)
                    
            # 从列表中移除
            for notif in to_remove:
                if notif in Notification.active_notifications:
                    Notification.active_notifications.remove(notif)
                    
        except Exception as e:
            log.error(f"清理通知列表失败: {e}")
            
    def _reorganize_notifications(self):
        """重新组织通知位置"""
        try:
            # 只处理可见且未关闭的通知
            valid_notifications = []
            
            for notif in Notification.active_notifications:
                try:
                    if notif.isVisible() and not getattr(notif, '_is_closing', False):
                        valid_notifications.append(notif)
                except:
                    continue
                    
            # 先按位置排序，再按创建时间排序（这样确保位置一致性）
            try:
                # 主要按照Y坐标排序
                valid_notifications.sort(key=lambda n: n.y(), reverse=True)
            except:
                # 如果排序失败，至少确保有一致的顺序
                pass
            
            # 更新每个通知的索引并立即移动到正确位置
            for i, notif in enumerate(valid_notifications):
                try:
                    old_pos = notif.pos()
                    notif.current_index = i
                    target_pos = notif._calculate_right_bottom_position(i)
                    
                    # 只有位置变化超过5像素才移动，避免抖动
                    if abs(old_pos.x() - target_pos.x()) > 5 or abs(old_pos.y() - target_pos.y()) > 5:
                        notif.move(target_pos)
                except:
                    continue
                    
        except Exception as e:
            log.error(f"重新组织通知位置失败: {e}")

    def _calculate_right_bottom_position(self, index=0):
        """自定义位置计算 - 右下角定位"""
        try:
            # 获取屏幕尺寸
            screen = QApplication.primaryScreen().availableGeometry()
            
            # 固定参数
            margin = 25  # 距离屏幕边缘的边距
            spacing = 20  # 通知之间的间距
            
            # 确保窗口有合理的高度值
            height = max(self.height(), 80)  # 如果高度太小，使用最小值80
            
            # 计算右下角位置
            x = screen.right() - self.width() - margin
            
            # 使用固定间距和高度值，避免重叠
            y = screen.bottom() - height - margin - (index * (height + spacing))
            
            # 确保位置在屏幕内
            x = max(screen.left() + margin, min(x, screen.right() - self.width() - margin))
            y = max(screen.top() + margin, min(y, screen.bottom() - height - margin))
            
            return QPoint(x, y)
        except Exception as e:
            log.error(f"计算右下角位置失败: {e}")
            # 返回安全的默认位置(屏幕右下角)
            try:
                screen = QApplication.primaryScreen().availableGeometry()
                return QPoint(screen.right() - self.width() - 20, 
                             screen.bottom() - self.height() - 20)
            except:
                # 最终备用位置
                return QPoint(800, 600)

    def _preprocess_notification_position(self):
        """预处理通知位置，在显示前排列好所有通知"""
        try:
            # 清理已关闭的通知
            self._cleanup_notification_list()
            
            # 如果不在活动通知列表中，添加自己
            if self not in Notification.active_notifications:
                Notification.active_notifications.append(self)
            
            # 收集有效通知
            valid_notifications = []
            for notif in Notification.active_notifications:
                try:
                    if notif != self and notif.isVisible() and not getattr(notif, '_is_closing', False):
                        valid_notifications.append(notif)
                except:
                    continue
            
            # 根据Y坐标排序现有通知
            valid_notifications.sort(key=lambda n: n.y(), reverse=True)
            
            # 分配索引
            for i, notif in enumerate(valid_notifications):
                try:
                    notif.current_index = i
                    # 立即移动到正确位置
                    target_pos = notif._calculate_right_bottom_position(i)
                    notif.move(target_pos)
                except:
                    pass
            
            # 新通知的索引应该是当前可见通知数量
            self.current_index = len(valid_notifications)
            
            # 标记位置已初始化
            self.position_initialized = True
            
        except Exception as e:
            log.error(f"预处理通知位置失败: {e}")
            # 使用安全默认值
            self.current_index = len(Notification.active_notifications) - 1

class NotifyManager:
    @staticmethod
    def info(text, duration=8000):
        try:
            notif = Notification(text=text, type=NotificationType.INFO, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示info通知失败: {str(e)}")
    
    @staticmethod  
    def warning(text, duration=8000):
        try:
            notif = Notification(text=text, type=NotificationType.WARNING, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示warning通知失败: {str(e)}")
    
    @staticmethod
    def error(text, duration=8000):
        try:
            notif = Notification(text=text, type=NotificationType.ERROR, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示error通知失败: {str(e)}")
    
    @staticmethod
    def show_message(title, message, level="info", duration=8000):
        """显示带有标题的消息通知
        
        Args:
            title: 通知标题
            message: 通知内容
            level: 通知级别，可以是 "info", "warning", "error", "success"
            duration: 显示持续时间(毫秒)
        """
        try:
            notification_type = NotificationType.INFO
            if level == "warning":
                notification_type = NotificationType.WARNING
            elif level == "error":
                notification_type = NotificationType.ERROR
            elif level == "success":
                notification_type = NotificationType.SUCCESS
                
            notif = Notification(text=message, title=title, type=notification_type, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示带标题通知失败: {str(e)}")
        
    @staticmethod
    def success(text, duration=8000):
        try:
            notif = Notification(text=text, type=NotificationType.SUCCESS, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示success通知失败: {str(e)}")
        
    @staticmethod
    def clear():
        try:
            try:
                # 首先尝试常规方式清除
                Notification.clear_all_notifications()
            except Exception as e:
                log.error(f"常规方式清除通知失败: {e}")
                
                # 备用方式：直接处理每个通知
                for notification in Notification.active_notifications[:]:
                    try:
                        if notification.isVisible():
                            notification.hide()
                        notification.deleteLater()
                    except:
                        pass
                
                # 清空列表
                Notification.active_notifications.clear()
                
        except Exception as e:
            log.error(f"清除所有通知失败: {str(e)}")

