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
    
    # 添加静态配置
    POSITION_CONFIG = {
        'margin_right': 25,      # 距离屏幕右侧的边距
        'margin_top': 25,        # 距离屏幕顶部的边距 (新增)
        'margin_bottom': 25,     # 距离屏幕底部的边距
        'spacing': 20,          # 通知之间的间距
        'min_height': 80,       # 通知的最小高度
        'animation_overlap': 0.3, # 通知间动画重叠比例(0-1)
        'stack_from_bottom': True, # 从底部向上堆叠通知
        'replace_previous': True  # 是否替换上一个通知，设为True
    }
    
    # 更新替换动画配置
    REPLACE_ANIMATION = {
        'enabled': True,         # 是否启用替换动画
        'duration': 500,         # 替换动画持续时间
        'slide_offset': 100,     # 增大顶替滑动偏移量
        'fade_duration': 300     # 淡出持续时间
    }
    
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
            
            # 创建内容区域 - 使用简单的 QWidget，不设置特殊效果
            content_frame = QWidget()
            content_frame.setObjectName("content_frame")
            content_widget_layout = QVBoxLayout(content_frame)
            content_widget_layout.setContentsMargins(0, 0, 0, 0)
            content_widget_layout.setSpacing(6)
            content_widget_layout.addLayout(title_layout) 
            content_widget_layout.addWidget(self.text_label)
            
            # 添加到水平布局
            content_layout.addWidget(color_bar)
            content_layout.addWidget(content_frame, 1)
            
            # 将水平布局添加到主布局
            layout.addLayout(content_layout)
            
            # 设置Mica云母效果样式 - 使用更简单的样式，避免复杂的渲染
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
                #content_frame {{
                    background-color: transparent;
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
            
            # 不使用阴影效果，避免 QPainter 错误
            # 改为使用边框和背景色来创建视觉层次感
            content_frame.setStyleSheet(f"""
                #content_frame {{
                    background-color: rgba(40, 40, 40, 0.7);
                    border-radius: 6px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}
            """)
            
        except Exception as e:
            log.error(f"初始化通知UI失败: {e}")
            log.error(traceback.format_exc())
            
    def _create_opacity_effect(self):
        """创建并设置透明度效果"""
        try:
            # 避免使用图形效果，直接设置窗口透明度
            self.setWindowOpacity(self._opacity)
        except Exception as e:
            log.error(f"设置透明度失败: {e}")

    def set_opacity(self, opacity):
        """设置透明度，避免使用 QGraphicsOpacityEffect"""
        self._opacity = max(0.0, min(1.0, opacity))
        try:
            # 直接设置窗口透明度，不使用图形效果
            self.setWindowOpacity(self._opacity)
        except Exception as e:
            log.error(f"设置透明度失败: {e}")
            
    def show_notification(self, start_pos=None, end_pos=None, auto_hide_delay=4000):
        """显示通知动画"""
        try:
            if self.is_animating:
                return False
                
            # 如果正在关闭则不显示
            if hasattr(self, '_is_closing') and self._is_closing:
                return
                
            # 先清除所有其他通知 - 强制替换模式
            if self.POSITION_CONFIG['replace_previous']:
                # 立即关闭所有其他通知
                for notif in Notification.active_notifications[:]:
                    if notif != self and notif.isVisible():
                        try:
                            notif._is_closing = True
                            notif.hide()
                            notif.deleteLater()
                            if notif in Notification.active_notifications:
                                Notification.active_notifications.remove(notif)
                        except Exception as e:
                            log.error(f"关闭旧通知失败: {e}")
                
                # 清空队列，只保留当前通知
                Notification.active_notifications = [n for n in Notification.active_notifications if n == self]
            
            # 调整大小以适应内容
            self.adjustSize()
            
            # 预处理通知位置 - 确保自己在列表的最前面
            self._preprocess_notification_position()
            
            # 使用预处理的位置信息 - 由于是第一个，索引为0
            if end_pos is None:
                end_pos = self._calculate_right_top_position(self.current_index)
                
            # 如果起始位置未指定，默认从右侧滑入
            if start_pos is None:
                start_pos = QPoint(end_pos.x() + 300, end_pos.y())
            
            # 确保窗口可以显示
            self.setWindowOpacity(1.0)
            
            # 先移动到正确位置，避免动画开始前就显示在错误位置
            self.move(start_pos)
            
            # 增强窗口显示 - 确保显示在最前面
            # 设置窗口标志，确保始终在顶层
            self.setWindowFlags(
                Qt.FramelessWindowHint | 
                Qt.Tool | 
                Qt.WindowStaysOnTopHint
            )
            
            # 先显示窗口
            self.show()
            
            # 强制提升到最上层 - 确保新通知始终显示在最前面
            self.raise_()
            
            # 强制处理事件，确保窗口重绘
            QApplication.processEvents()
            
            # 监听显示完成信号
            if not hasattr(self, '_connected_signals'):
                self.show_finished.connect(self._on_show_finished)
                self.hide_finished.connect(self._on_hide_finished)
                self._connected_signals = True
            
            # 如果持续时间超过10秒，限制为10秒，防止通知显示太长时间
            display_duration = min(self.duration, 10000)
            
            # 尝试使用简单的位置动画，避免复杂的动画系统
            try:
                # 创建位置动画
                self.pos_anim = QPropertyAnimation(self, b"pos")
                self.pos_anim.setDuration(800)
                self.pos_anim.setStartValue(start_pos)
                self.pos_anim.setEndValue(end_pos)
                self.pos_anim.setEasingCurve(QEasingCurve.OutCubic)
                
                # 连接动画完成信号
                self.pos_anim.finished.connect(self._on_show_finished)
                
                # 启动动画
                self.pos_anim.start()
                
                # 设置自动隐藏定时器
                QTimer.singleShot(display_duration, self._auto_hide)
                
                log.debug(f"显示通知: {self.text}, 持续时间: {display_duration}ms")
                return True
            except Exception as animation_error:
                log.error(f"通知动画系统错误: {str(animation_error)}")
                log.debug(traceback.format_exc())
                
                # 使用备用显示方式
                self.setup_fallback_display(end_pos, display_duration)
            
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
                Qt.WindowStaysOnTopHint
            )
            
            # 显示和提升
            self.show()
            self.raise_()  # 提升到顶层
            QApplication.processEvents()  # 立即处理事件，确保窗口显示
            
            # 设置简单的淡入效果
            try:
                # 使用窗口透明度属性直接设置，不使用图形效果
                self.setWindowOpacity(0.7)
                QTimer.singleShot(100, lambda: self.setWindowOpacity(0.85))
                QTimer.singleShot(200, lambda: self.setWindowOpacity(1.0))
            except Exception as e:
                log.warning(f"淡入效果创建失败，忽略: {e}")
            
            # 设置自动隐藏
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
                Qt.WindowStaysOnTopHint
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
            
            log.debug(f"使用最简单方式显示通知: {self.text}")
        except Exception as e:
            log.error(f"最简单显示方式也失败: {e}")
            # 不再尝试，直接放弃

    def _on_show_finished(self):
        # 显示动画完成后的回调
        log.debug(f"通知显示动画完成")
        
        # 如果有上一个通知正在等待替换，完成其关闭
        if hasattr(self, '_replacing_notification') and self._replacing_notification:
            prev_notif = self._replacing_notification
            self._replacing_notification = None
            
            # 确保上一个通知被完全关闭
            try:
                if prev_notif.isVisible() and not getattr(prev_notif, '_is_closing', False):
                    # 标记为正在关闭
                    prev_notif._is_closing = True
                    
                    # 从活动通知列表中移除
                    if prev_notif in Notification.active_notifications:
                        Notification.active_notifications.remove(prev_notif)
                        
                    # 确保完全隐藏并删除
                    prev_notif.hide()
                    QTimer.singleShot(200, prev_notif.deleteLater)
            except Exception as e:
                log.error(f"关闭被替换通知失败: {e}")

    def _auto_hide(self):
        """自动隐藏回调"""
        try:
            # 确保对象没有被关闭
            if hasattr(self, '_is_closing') and self._is_closing:
                return
                
            # 尝试隐藏
            self.close()
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
            # 如果通知正在被替换，使用更简单的关闭方式
            if getattr(self, '_being_replaced', False):
                self._is_closing = True
                # 从活动通知列表中移除自己
                if self in Notification.active_notifications:
                    Notification.active_notifications.remove(self)
                # 隐藏并稍后删除
                self.hide()
                QTimer.singleShot(100, self.deleteLater)
                return
                
            if not self._is_closing:
                self._is_closing = True
                
                # 从活动通知列表中移除自己
                if self in Notification.active_notifications:
                    Notification.active_notifications.remove(self)
                    
                # 使用简单的淡出效果
                try:
                    # 使用定时器创建简单的淡出效果
                    self.setWindowOpacity(0.8)
                    QTimer.singleShot(50, lambda: self.setWindowOpacity(0.6))
                    QTimer.singleShot(100, lambda: self._on_hide_finished())
                except Exception as e:
                    log.error(f"淡出动画失败: {e}")
                    # 直接处理
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
                    
                    # 重新调整其他通知的位置 - 延迟执行，确保动画流畅
                    QTimer.singleShot(100, lambda: self._adjust_other_notifications(0))
                        
                except Exception as e:
                    log.error(f"移除通知或调整其他通知位置失败: {e}")
            
            # 隐藏窗口
            self.hide()
            
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
            
            # 强制重新组织位置 - 确保调用_reorganize_notifications()
            # 使用延迟调用，避免在当前事件循环中执行
            QTimer.singleShot(50, lambda: self._reorganize_notifications())
            
        except Exception as e:
            log.error(f"调整其他通知位置失败: {e}")

    def _cleanup(self):
        """清理资源"""
        try:
            # 安全地清除所有引用和连接
            try:
                # 清除动画引用
                if hasattr(self, 'pos_anim'):
                    if self.pos_anim.state() == QPropertyAnimation.Running:
                        self.pos_anim.stop()
                    self.pos_anim = None
                
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
        """重写的通知重排序方法，确保连贯流畅的位置调整"""
        try:
            # 只处理可见且未关闭的通知
            valid_notifications = []
            
            for notif in Notification.active_notifications:
                try:
                    if notif.isVisible() and not getattr(notif, '_is_closing', False):
                        valid_notifications.append(notif)
                except:
                    continue
            
            # 若通知数量为0，无需继续处理
            if not valid_notifications:
                return
                    
            # 计算每个通知的正确位置
            screen = QApplication.primaryScreen().availableGeometry()
            margin_right = self.POSITION_CONFIG['margin_right']
            margin_top = self.POSITION_CONFIG['margin_top']
            margin_bottom = self.POSITION_CONFIG['margin_bottom']
            spacing = self.POSITION_CONFIG['spacing']
            min_height = self.POSITION_CONFIG['min_height']
            stack_from_bottom = self.POSITION_CONFIG['stack_from_bottom']
            
            # 设置动画重叠创建间隔(ms)，使动画更流畅
            anim_delay = 30
            
            # 批量创建所有通知的位置调整动画
            animations = []
            
            # 如果从底部堆叠，反转通知列表
            if stack_from_bottom:
                valid_notifications = list(reversed(valid_notifications))
            
            # 计算每个通知的累计高度
            cumulative_height = 0
            
            # 确保在显示器右侧
            # 更新每个通知的索引并创建动画
            for i, notif in enumerate(valid_notifications):
                try:
                    # 更新索引
                    if stack_from_bottom:
                        # 如果从底部堆叠，索引需要反转
                        notif.current_index = len(valid_notifications) - 1 - i
                    else:
                        notif.current_index = i
                    
                    # 计算新位置
                    real_height = max(notif.height(), min_height)
                    
                    # 设置X坐标 - 右侧对齐
                    x = screen.right() - notif.width() - margin_right
                    
                    # 根据堆叠方向设置Y坐标
                    if stack_from_bottom:
                        # 从底部向上堆叠
                        y = screen.bottom() - margin_bottom - real_height - cumulative_height
                    else:
                        # 从顶部向下堆叠
                        y = screen.top() + margin_top + cumulative_height
                    
                    # 更新累计高度，为下一个通知准备
                    cumulative_height += real_height + spacing
                    
                    # 确保位置在屏幕内
                    x = max(screen.left() + margin_right, min(x, screen.right() - notif.width() - margin_right))
                    
                    if stack_from_bottom:
                        y = max(screen.top() + margin_top, min(y, screen.bottom() - real_height - margin_bottom))
                    else:
                        y = max(screen.top() + margin_top, min(y, screen.bottom() - real_height - margin_bottom))
                    
                    # 创建动画
                    old_pos = notif.pos()
                    new_pos = QPoint(x, y)
                    
                    # 只有位置变化超过5像素才创建动画，避免微小抖动
                    if abs(old_pos.x() - new_pos.x()) > 5 or abs(old_pos.y() - new_pos.y()) > 5:
                        # 创建位置动画
                        try:
                            anim = QPropertyAnimation(notif, b"pos")
                            anim.setDuration(350)  # 适中的动画时长
                            anim.setStartValue(old_pos)
                            anim.setEndValue(new_pos)
                            anim.setEasingCurve(QEasingCurve.OutCubic)
                            
                            # 设置延迟开始时间，使动画交错进行
                            anim.setStartDelay(i * anim_delay)
                            
                            # 将动画添加到列表，稍后统一启动
                            animations.append(anim)
                        except Exception as anim_err:
                            log.error(f"创建调整动画失败: {anim_err}")
                            # 直接设置位置作为备选方案
                            notif.move(new_pos)
                    else:
                        # 位置变化很小，直接设置
                        notif.move(new_pos)
                except Exception as e:
                    log.error(f"处理通知位置时出错: {e}")
                    continue
            
            # 启动所有动画
            for anim in animations:
                try:
                    anim.start()
                except Exception as e:
                    log.error(f"启动位置调整动画失败: {e}")
                    
            # 保存动画引用，避免被垃圾回收
            if animations:
                if not hasattr(self, '_position_animations'):
                    self._position_animations = []
                self._position_animations = animations
                    
        except Exception as e:
            log.error(f"重新组织通知位置失败: {e}")
            
    def _calculate_right_top_position(self, index=0):
        """计算通知在右侧的位置，确保不重叠"""
        try:
            # 获取屏幕尺寸
            screen = QApplication.primaryScreen().availableGeometry()
            
            # 使用类级别的配置，统一计算逻辑
            margin_right = self.POSITION_CONFIG['margin_right']
            margin_top = self.POSITION_CONFIG['margin_top']
            margin_bottom = self.POSITION_CONFIG['margin_bottom']
            spacing = self.POSITION_CONFIG['spacing']
            min_height = self.POSITION_CONFIG['min_height']
            stack_from_bottom = self.POSITION_CONFIG['stack_from_bottom']
            
            # 确保窗口尺寸合理 - 尤其重要的是高度，避免堆叠不正确
            real_height = max(self.height(), min_height)
            
            # 获取有效通知列表
            valid_notifications = []
            for notif in Notification.active_notifications:
                if notif.isVisible() and not getattr(notif, '_is_closing', False):
                    valid_notifications.append(notif)
            
            # 如果从底部堆叠，反转列表和索引
            if stack_from_bottom:
                valid_notifications = list(reversed(valid_notifications))
                if index < len(valid_notifications):
                    index = len(valid_notifications) - 1 - index
            
            # 累计高度，用于计算当前通知的位置
            cumulative_height = 0
            
            # 计算当前通知之前的所有通知高度总和
            for i, notif in enumerate(valid_notifications):
                if i < index and notif != self and notif.isVisible() and not getattr(notif, '_is_closing', False):
                    notif_height = max(notif.height(), min_height)
                    cumulative_height += notif_height + spacing
            
            # 设置X坐标 - 右侧对齐
            x = screen.right() - self.width() - margin_right
            
            # 根据堆叠方向设置Y坐标
            if stack_from_bottom:
                # 从底部向上堆叠
                y = screen.bottom() - margin_bottom - real_height - cumulative_height
            else:
                # 从顶部向下堆叠
                y = screen.top() + margin_top + cumulative_height
            
            # 确保位置在屏幕内
            x = max(screen.left() + margin_right, min(x, screen.right() - self.width() - margin_right))
            
            if stack_from_bottom:
                y = max(screen.top() + margin_top, min(y, screen.bottom() - real_height - margin_bottom))
            else:
                y = max(screen.top() + margin_top, min(y, screen.bottom() - real_height - margin_bottom))
            
            return QPoint(x, y)
        except Exception as e:
            log.error(f"计算通知位置失败: {e}")
            # 返回安全的默认位置
            try:
                screen = QApplication.primaryScreen().availableGeometry()
                if self.POSITION_CONFIG['stack_from_bottom']:
                    return QPoint(screen.right() - self.width() - 20, 
                                 screen.bottom() - self.height() - 20)
                else:
                    return QPoint(screen.right() - self.width() - 20, 
                                 screen.top() + 20)
            except:
                # 最终备用位置
                return QPoint(800, 100)

    def _preprocess_notification_position(self):
        """重写的通知位置预处理，更稳定地排列"""
        try:
            # 获取上一个通知（如果有）
            prev_notification = None
            
            # 如果启用替换上一个通知的功能
            if self.POSITION_CONFIG['replace_previous'] and len(Notification.active_notifications) > 0:
                # 获取最后一个可见的通知
                for notif in reversed(Notification.active_notifications):
                    if (notif != self and notif.isVisible() and not getattr(notif, '_is_closing', False) 
                            and not getattr(notif, '_being_replaced', False)):
                        prev_notification = notif
                        break
            
            # 确保自身在活动列表中
            if self not in Notification.active_notifications:
                # 将新通知添加到列表末尾
                Notification.active_notifications.append(self)
            else:
                # 如果已经在列表中，移动到最后面
                Notification.active_notifications.remove(self)
                Notification.active_notifications.append(self)
            
            # 清理列表中的无效通知
            self._cleanup_notification_list()
            
            # 如果启用了替换功能，则关闭其他所有通知
            if self.POSITION_CONFIG['replace_previous']:
                # 关闭所有其他通知，只保留自己
                for notif in Notification.active_notifications[:]:
                    if notif != self and notif.isVisible() and not getattr(notif, '_is_closing', False):
                        # 标记为将被替换
                        notif._being_replaced = True
                        
                        # 关闭所有通知，不管是哪一个
                        try:
                            notif._is_closing = True
                            notif.hide()
                            QTimer.singleShot(100, notif.deleteLater)
                            if notif in Notification.active_notifications:
                                Notification.active_notifications.remove(notif)
                        except Exception as e:
                            log.error(f"关闭旧通知失败: {e}")
            
            # 更新所有通知的索引
            for i, notif in enumerate(Notification.active_notifications):
                notif.current_index = i
            
            # 标记位置已初始化
            self.position_initialized = True
            
            # 如果有上一个通知并且开启了替换功能，执行替换动画
            if prev_notification and self.POSITION_CONFIG['replace_previous']:
                # 执行替换动画
                self.replace_animation(prev_notification)
            elif len(Notification.active_notifications) > 1:
                # 如果没有替换，但有其他通知，主动调整它们的位置
                QTimer.singleShot(50, lambda: self._reorganize_notifications())
                
        except Exception as e:
            log.error(f"预处理通知位置失败: {e}")
            # 使用安全默认值
            self.current_index = len(Notification.active_notifications) - 1

    def replace_animation(self, prev_notification):
        """执行顶替动画效果，新通知替换旧通知"""
        try:
            if not self.REPLACE_ANIMATION['enabled']:
                return False
                
            if not prev_notification or not prev_notification.isVisible():
                return False
                
            # 获取当前通知位置
            curr_pos = self.pos()
            
            # 获取上一个通知的位置
            prev_pos = prev_notification.pos()
            
            # 设置动画配置
            duration = self.REPLACE_ANIMATION['duration']
            slide_offset = self.REPLACE_ANIMATION['slide_offset']
            
            # 创建上一个通知的动画 - 向右滑出并淡出
            try:
                # 使上一个通知保持在最上层一小段时间
                prev_notification.raise_()
                
                # 创建位置动画 - 向右滑出
                prev_slide = QPropertyAnimation(prev_notification, b"pos")
                prev_slide.setDuration(duration)
                prev_slide.setStartValue(prev_pos)
                prev_slide.setEndValue(QPoint(prev_pos.x() + slide_offset, prev_pos.y()))
                prev_slide.setEasingCurve(QEasingCurve.InOutQuad)
                
                # 透明度动画 - 淡出
                prev_opacity = QPropertyAnimation(prev_notification, b"windowOpacity")
                prev_opacity.setDuration(self.REPLACE_ANIMATION['fade_duration'])
                prev_opacity.setStartValue(1.0)
                prev_opacity.setEndValue(0.0)
                prev_opacity.setEasingCurve(QEasingCurve.InQuad)
                
                # 保存引用防止被垃圾回收
                prev_notification._replace_slide_anim = prev_slide
                prev_notification._replace_opacity_anim = prev_opacity
                
                # 启动动画
                prev_slide.start()
                prev_opacity.start()
                
                # 设置标记，避免被自动清理系统立即关闭
                prev_notification._being_replaced = True
                
                # 当前通知保存引用
                self._replacing_notification = prev_notification
                
                # 确保替换完成后删除旧通知
                prev_opacity.finished.connect(lambda: self._finish_replace_animation(prev_notification))
                
                log.debug(f"执行替换动画：替换通知 {prev_notification.text}")
                return True
                
            except Exception as e:
                log.error(f"创建替换动画失败: {e}")
                return False
                
        except Exception as e:
            log.error(f"执行替换动画失败: {e}")
            return False

    def _finish_replace_animation(self, prev_notification):
        """替换动画结束后的处理"""
        try:
            # 确保上一个通知被彻底关闭
            if prev_notification and not getattr(prev_notification, '_is_closing', False):
                prev_notification._is_closing = True
                
                # 从活动通知列表中移除
                if prev_notification in Notification.active_notifications:
                    Notification.active_notifications.remove(prev_notification)
                    
                # 隐藏并删除
                prev_notification.hide()
                QTimer.singleShot(100, prev_notification.deleteLater)
        except Exception as e:
            log.error(f"结束替换动画处理失败: {e}")

class NotifyManager:
    @staticmethod
    def info(text, duration=8000):
        try:
            # 先清理旧通知
            NotifyManager.clear()
            
            notif = Notification(text=text, type=NotificationType.INFO, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示info通知失败: {str(e)}")
    
    @staticmethod  
    def warning(text, duration=8000):
        try:
            # 先清理旧通知
            NotifyManager.clear()
            
            notif = Notification(text=text, type=NotificationType.WARNING, duration=duration)
            notif.show_notification()
        except Exception as e:
            log.error(f"显示warning通知失败: {str(e)}")
    
    @staticmethod
    def error(text, duration=8000):
        try:
            # 先清理旧通知
            NotifyManager.clear()
            
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
            # 先清理旧通知
            NotifyManager.clear()
            
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
            # 先清理旧通知
            NotifyManager.clear()
            
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
                
            # 最后一个备用清理方法：使用进程查找并清理所有通知窗口
            try:
                import psutil
                import os
                current_pid = os.getpid()
                
                # 查找所有QWidget类型的窗口并关闭
                from PySide6.QtWidgets import QApplication
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, Notification) or (hasattr(widget, 'inherits') and widget.inherits('Notification')):
                        try:
                            widget.hide()
                            widget.deleteLater()
                        except:
                            pass
            except Exception as e:
                log.error(f"进程级通知清理失败: {e}")
                
        except Exception as e:
            log.error(f"清除所有通知失败: {str(e)}")
            
    @staticmethod
    def force_clear():
        """强制清理所有通知，包括可能存在的僵尸通知"""
        try:
            # 常规清理
            NotifyManager.clear()
            
            # 强制GC
            try:
                import gc
                gc.collect()
            except:
                pass
                
            # 强制处理事件队列中的所有事件
            try:
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
            except:
                pass
                
            # 重置静态变量
            Notification.active_notifications = []
            
            log.debug("强制清理所有通知完成")
        except Exception as e:
            log.error(f"强制清理通知失败: {e}")

