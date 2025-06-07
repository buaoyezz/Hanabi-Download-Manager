import os
import sys
import time
import json
import gc
import threading
import datetime
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QProgressBar, QFrame, QFileDialog, QLineEdit,
                               QGraphicsDropShadowEffect, QSpacerItem, QSizePolicy, QCheckBox,
                               QScrollArea, QApplication, QMessageBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QWidget, QToolButton,QGridLayout)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QThread, QObject, QEvent, QStandardPaths, QMargins, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPen, QFont, QIcon, QPixmap, QMouseEvent, QCursor, QFontMetrics, QRegion, QTransform

from core.animations.window_auto_resize_animation import apply_resize_animation
from client.ui.client_interface.utils.file_icons_get import FileIconGetter

from core.download_core.Hanabi_NSF_Kernel import DownloadEngine
from core.download_core.Hanabi_AS_Kernel import HanabiASKernel
from connect.fallback_connector import FallbackConnector
from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle

class ShadowFrame(QFrame):
    """带阴影效果的圆角边框"""
    def __init__(self, parent=None, radius=12, bg_color="#252526"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        
        # 设置阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)
        
        # 透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        # 绘制圆角矩形
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建路径
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self.radius, self.radius)
        
        # 填充背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)

class DownloadPopDialog(QDialog):
    """下载弹窗对话框"""
    
    # 定义信号
    downloadRequested = Signal(dict)   # 请求下载
    downloadCancelled = Signal(str)    # 取消下载
    downloadPaused = Signal(str)       # 暂停下载
    downloadResumed = Signal(str)      # 恢复下载
    fileOpened = Signal(str)           # 打开文件
    folderOpened = Signal(str)         # 打开文件夹
    downloadCompleted = Signal(dict)   # 下载完成信号
    
    # 辅助方法：安全检查UI控件是否已被销毁
    @staticmethod
    def _is_destroyed(widget):
        """检查Qt控件是否已被销毁
        
        参数:
            widget: Qt控件对象
            
        返回:
            bool: 如果控件已被销毁则返回True，否则返回False
        """
        try:
            # 对于Qt对象，我们可以尝试访问其属性来检查是否已销毁
            # 此处使用对象的metaObject或objectName等属性进行测试
            # 如果已销毁，将引发RuntimeError
            if widget is None:
                return True
                
            # 尝试访问Qt对象属性
            if hasattr(widget, 'objectName'):
                widget.objectName()
                return False
            elif hasattr(widget, 'isVisible'):
                widget.isVisible()
                return False
            else:
                # 如果无法确定，假设未销毁
                return False
        except (RuntimeError, AttributeError, Exception):
            # 如果访问属性时出错，则认为对象已销毁
            return True
    
    @staticmethod
    def create_and_show(download_data=None, parent=None, auto_start=False):
        """创建并显示下载弹窗
        
        参数:
            download_data (dict): 下载数据，如果为None则显示添加下载界面
            parent: 父窗口
            auto_start (bool): 是否自动开始下载，默认为False (通常设为False以显示确认界面)
            
        返回:
            DownloadPopDialog: 创建的弹窗对象
        """
        # 记录弹窗创建的来源
        download_source = "未知来源"
        request_id = "无ID"
        download_kernel = "未知核心"
        
        if download_data:
            download_source = download_data.get("download_source", "未知来源")
            request_id = download_data.get("requestId", "无ID")
            logging.info(f"[pop_dialog.py] 创建下载弹窗 [ID: {request_id}] [来源: {download_source}] [自动下载: {auto_start}]")
        
        # 检查父窗口状态
        parent_minimized = False
        has_parent = False
        if parent and hasattr(parent, 'isMinimized'):
            has_parent = True
            try:
                parent_minimized = parent.isMinimized()
            except Exception:
                pass
                
        # 关键修改: 当主窗口最小化时，完全不设置父窗口关系
        # 这是解决问题的核心 - 创建完全独立的顶级窗口
        if has_parent and parent_minimized:
            # 创建完全独立的窗口，没有父子关系
            dialog = DownloadPopDialog(None)  # 显式传入None
            
            # 保存原始父窗口引用只用于通信，不建立Qt父子关系
            dialog.original_parent = parent
            
            # 标记为在最小化状态创建
            dialog.parent_was_minimized = True
            
            # 显式设置为顶级窗口 - 核心修复
            dialog.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            
            # 确保这个窗口不会被当作应用程序的主窗口
            dialog.setAttribute(Qt.WA_QuitOnClose, False)
        else:
            # 正常情况下创建对话框
            dialog = DownloadPopDialog(parent)
            dialog.parent_was_minimized = False
            
            # 设置为非模态对话框
            dialog.setModal(False)
            
            # 最上层
            dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        
        # 通用窗口设置
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)  # 确保关闭时删除自身
        
        # 记录当前创建时的窗口状态，便于后续处理
        dialog.was_created_when_minimized = parent_minimized
        
        # 标记需要移除置顶标志的属性
        dialog.remove_top_hint = True
        
        if download_data:
            # 预处理下载数据
            task_data = dialog._process_download_data(download_data)
            
            if auto_start:
                # 自动开始下载模式
                logging.info(f"[pop_dialog.py] 自动开始下载模式 [ID: {request_id}]")
                
                # 直接切换到下载UI并开始下载
                dialog._create_downloading_ui(task_data)
                dialog._start_download(task_data)
            else:
                # 显示添加下载界面，但填入URL和文件名
                dialog._create_add_download_ui()
                
                # 填入URL
                if "url" in task_data and dialog.url_input:
                    dialog.url_input.setText(task_data.get("url", ""))
                    
                # 填入文件名
                if "file_name" in task_data and dialog.filename_input:
                    dialog.filename_input.setText(task_data.get("file_name", ""))
                    
                # 填入保存路径
                if "save_path" in task_data and dialog.save_path_input:
                    dialog.save_path_input.setText(task_data.get("save_path", ""))
                    
                # 多线程选项
                if "multi_thread" in task_data and dialog.multi_thread_checkbox:
                    dialog.multi_thread_checkbox.setChecked(task_data.get("multi_thread", True))
                    
                # 保存任务数据，以便下载按钮使用
                dialog.pending_task_data = task_data
        
        # 显示窗口
        dialog.showNormal()
        
        # 强制激活窗口
        dialog.raise_()
        dialog.activateWindow()
        
        # 延迟执行居中和边界检查，确保窗口大小已经计算完成
        QTimer.singleShot(100, lambda: dialog.move(
            (QApplication.primaryScreen().availableGeometry().width() - dialog.width()) // 2,
            (QApplication.primaryScreen().availableGeometry().height() - dialog.height()) // 2
        ))
        QTimer.singleShot(150, dialog._ensure_visible_on_screen)
        
        return dialog
    
    def __init__(self, parent=None):
        # 先处理最小化状态
        parent_minimized = False
        if parent and hasattr(parent, 'isMinimized'):
            try:
                parent_minimized = parent.isMinimized()
            except Exception:
                pass

        # 如果父窗口已最小化，我们需要特殊处理
        if parent_minimized:
            # === 关键修复：对于最小化状态，创建完全独立的窗口 ===
            # 初始化为独立窗口，没有父子关系，避免级联关闭问题
            super().__init__(None)  # 显式传入None作为父窗口
            
            # 保存原始父窗口引用，只用于通信，不建立Qt父子关系
            import weakref
            self._parent_ref_strong = parent  # 保留一个强引用用于通信
            self.original_parent = parent
            
            # 标记为在最小化状态创建
            self.parent_was_minimized = True
            
            # 额外的关键设置：确保窗口不会影响应用程序生命周期
            self.setAttribute(Qt.WA_QuitOnClose, False)  # 关闭时不会退出应用程序
            
            # 设置为顶级窗口，完全独立于父窗口
            # 使用Qt.Window确保窗口完全独立
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            
            # 允许窗口显示但不强制激活，避免干扰用户
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            
            # 启用透明背景
            self.setAttribute(Qt.WA_TranslucentBackground)
        else:
            # 正常情况下维持父子关系
            super().__init__(parent)
            self.original_parent = parent
            self.parent_was_minimized = False
            
            # 窗口属性配置
            self.setAttribute(Qt.WA_TranslucentBackground)
            
            # 修改：添加WindowStaysOnTopHint标志确保窗口总是在最上层
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            
            # 即使是常规对话框，也确保关闭时不会影响应用程序
            self.setAttribute(Qt.WA_QuitOnClose, False)
            
            # 标记需要移除置顶标志的属性
            self.remove_top_hint = True
        
        # 窗口大小 - 根据不同状态动态设置
        # 注意：不再设置固定的最小尺寸，而是在各个创建UI的方法中设置具体尺寸
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 初始化文件图标获取器
        self.file_icon_getter = FileIconGetter()
        
        # 添加缓存变量，用于平滑更新进度和大小显示
        self.last_progress = 0
        self.last_downloaded_size = 0
        self.last_total_size = 0
        self.last_status_text = ""
        self.last_size_text = ""
        self.last_segment_statuses = {}
        
        # 初始化UI
        self._setup_ui()
        
        # 任务ID和状态
        self.task_id = ""
        self.current_state = "add"  # add, downloading, completed
        
        # 下载引擎
        self.download_engine = None
        
        # 线程锁
        self.thread_lock = threading.Lock()
        
        # 鼠标拖动相关
        self.dragging = False
        self.drag_position = QPoint()
        
        # 拖动性能优化相关
        self.last_move_time = 0
        self.last_move_pos = QPoint()
        self.last_update_time = 0
        
        # 设置应用程序级别的处理策略，使拖动更加流畅
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        
        # 定时关闭 - 5秒后自动关闭完成弹窗
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close)
        
        # 进度更新定时器
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_download_info)
        
        # 分段信息区域是否显示，默认折叠
        self.show_segments = False
        
        # 已移除自动关闭功能
        
        # 待处理的任务数据
        self.pending_task_data = None
        
        # 安装事件过滤器以确保窗口可以正常关闭
        self.installEventFilter(self)
        
        # 下载引擎和任务相关属性
        self.nct_kernel = None
        self.as_kernel = None
        self.kernel_type = "未知"  # 添加核心类型属性
        self.kernel_fullname = ""  # 核心全名
        self.task_id = ""
        self.task_data = {}
        self.pending_task_data = {}
        self.nct_download_started = False
        self.nct_download_progress = 0
        self.nct_download_speed = 0
        self.nct_file_size = 0
        self.nct_downloaded = 0
        self.nct_last_update_time = 0
        
        # 初始化状态平滑处理所需的属性
        self._previous_block_statuses = {}  # 用于记录每个块的上一个状态
        self._status_stable_counter = {}    # 状态稳定计数器
        self._last_segments_update = 0      # 上次段信息更新时间
        self._segment_status_history = {}   # 存储每个段的状态历史
        self._status_transition_count = {}  # 存储状态转换计数
        self._status_last_change_time = {}  # 存储状态最后变化时间
        self._last_resize_time = 0          # 上次窗口大小调整时间
        self.last_progress = 0              # 上次进度值
        self.last_status_text = ""          # 上次状态文本
    
    def eventFilter(self, obj, event):
        """事件过滤器，确保窗口可以正常响应事件并支持从标题栏子控件拖动"""
        try:
            # 首先检查参数类型是否有效
            if not hasattr(event, 'type'):
                return False
                
            # 处理标题栏中子控件的拖动
            if isinstance(obj, QObject) and (isinstance(obj, QLabel) or isinstance(obj, QPushButton)):
                # 检查父对象是否是标题栏
                parent = obj.parent()
                if parent and isinstance(parent, QObject) and parent.objectName() == "title_bar":
                    # 处理鼠标事件
                    if event.type() == event.Type.MouseButtonPress and hasattr(event, 'button') and event.button() == Qt.LeftButton:
                        # 触发拖动
                        self.dragging = True
                        if hasattr(event, 'globalPosition'):
                            self.drag_position = event.globalPosition().toPoint() - self.pos()
                            self.setCursor(Qt.ClosedHandCursor)
                            return True
                    elif event.type() == event.Type.MouseMove and hasattr(event, 'buttons') and (event.buttons() & Qt.LeftButton) and self.dragging:
                        # 移动窗口
                        if hasattr(event, 'globalPosition'):
                            new_pos = event.globalPosition().toPoint() - self.drag_position
                            
                            # 限制窗口不要移出屏幕
                            screen = QApplication.primaryScreen().availableGeometry()
                            new_pos.setX(max(0, min(new_pos.x(), screen.width() - self.width())))
                            new_pos.setY(max(0, min(new_pos.y(), screen.height() - self.height())))
                            
                            self.setGeometry(new_pos.x(), new_pos.y(), self.width(), self.height())
                            return True
                    elif event.type() == event.Type.MouseButtonRelease and hasattr(event, 'button') and event.button() == Qt.LeftButton and self.dragging:
                        # 停止拖动
                        self.dragging = False
                        self.setCursor(Qt.ArrowCursor)
                        return False  # 不拦截释放事件，让按钮能正常响应点击
                        
            return False
        except Exception as e:
            # 捕获所有异常，确保事件过滤器不会崩溃
            logging.debug(f"事件过滤器异常: {e}")
            return False
    
    def closeEvent(self, event):
        """关闭窗口事件处理"""
        try:
            # ===== 关键修复 =====
            # 第一步：确保窗口不会导致应用程序退出
            # 1. 显式标记此窗口关闭时不会退出应用程序
            self.setAttribute(Qt.WA_QuitOnClose, False)
            
            # 2. 显式设置为独立窗口，确保关闭事件不会级联到父窗口
            if hasattr(self, 'parent_was_minimized') and self.parent_was_minimized:
                current_flags = self.windowFlags()
                if not (current_flags & Qt.Window):
                    self.setWindowFlags(current_flags | Qt.Window)
            
            # 3. 清除任何可能的Qt.WA_DeleteOnClose属性，使其不会被立即销毁
            # 由我们的代码决定何时销毁，避免Qt框架自动处理
            self.setAttribute(Qt.WA_DeleteOnClose, False)
            
            # ==== 常规清理逻辑 ====
            # 关闭前停止所有定时器
            if hasattr(self, 'auto_close_timer') and self.auto_close_timer:
                try:
                    self.auto_close_timer.stop()
                except Exception:
                    pass
                
            if hasattr(self, 'progress_timer') and self.progress_timer:
                try:
                    self.progress_timer.stop()
                except Exception:
                    pass
                
            # 标记已取消 - 确保不会触发后续处理
            self.cancelled = True
            
            # ===== 修复核心：停止下载引擎和AS内核 =====
            # 先处理AS内核
            if hasattr(self, 'as_kernel') and self.as_kernel is not None:
                try:
                    logging.info("关闭窗口: 停止AS内核下载任务")
                    
                    # 如果当前是NSF内核
                    if self.as_kernel.current_kernel_type == "NSF" and self.as_kernel.nsf_kernel:
                        # 先断开所有信号
                        if hasattr(self.download_engine, 'initialized'):
                            try:
                                if hasattr(self.download_engine.initialized, 'receivers') and self.download_engine.initialized.receivers() > 0:
                                    self.download_engine.initialized.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'block_progress_updated'):
                            try:
                                if hasattr(self.download_engine.block_progress_updated, 'receivers') and self.download_engine.block_progress_updated.receivers() > 0:
                                    self.download_engine.block_progress_updated.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'speed_updated'):
                            try:
                                if hasattr(self.download_engine.speed_updated, 'receivers') and self.download_engine.speed_updated.receivers() > 0:
                                    self.download_engine.speed_updated.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'download_completed'):
                            try:
                                if hasattr(self.download_engine.download_completed, 'receivers') and self.download_engine.download_completed.receivers() > 0:
                                    self.download_engine.download_completed.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'error_occurred'):
                            try:
                                if hasattr(self.download_engine.error_occurred, 'receivers') and self.download_engine.error_occurred.receivers() > 0:
                                    self.download_engine.error_occurred.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'file_name_changed'):
                            try:
                                if hasattr(self.download_engine.file_name_changed, 'receivers') and self.download_engine.file_name_changed.receivers() > 0:
                                    self.download_engine.file_name_changed.disconnect()
                            except:
                                pass
                            
                        # 安全停止NSF内核
                        try:
                            self.as_kernel.nsf_kernel.stop()
                            
                            # === 修复：增加线程等待和终止逻辑 ===
                            # 等待线程停止，增加超时时间
                            if hasattr(self.as_kernel.nsf_kernel, 'wait') and callable(self.as_kernel.nsf_kernel.wait):
                                # 先等待3秒
                                if not self.as_kernel.nsf_kernel.wait(3000):
                                    logging.warning("NSF内核线程停止等待超时(3秒)，尝试额外方法停止线程")
                                    
                                    # 尝试用quit
                                    if hasattr(self.as_kernel.nsf_kernel, 'quit') and callable(self.as_kernel.nsf_kernel.quit):
                                        try:
                                            self.as_kernel.nsf_kernel.quit()
                                            # 再等待2秒
                                            if not self.as_kernel.nsf_kernel.wait(2000):
                                                logging.warning("NSF内核线程quit后等待超时(2秒)，尝试强制终止")
                                                
                                                # 如果还在运行，尝试terminate强制终止（最后手段）
                                                if hasattr(self.as_kernel.nsf_kernel, 'terminate') and callable(self.as_kernel.nsf_kernel.terminate):
                                                    try:
                                                        self.as_kernel.nsf_kernel.terminate()
                                                        # 等待终止完成
                                                        if hasattr(self.as_kernel.nsf_kernel, 'wait') and callable(self.as_kernel.nsf_kernel.wait):
                                                            self.as_kernel.nsf_kernel.wait(1000)
                                                    except Exception as term_error:
                                                        logging.error(f"强制终止NSF内核线程出错: {term_error}")
                                        except Exception as quit_error:
                                            logging.error(f"退出NSF内核线程出错: {quit_error}")
                        except Exception as e:
                            logging.error(f"停止NSF内核出错: {e}")
                    
                    # 如果是NCT内核
                    elif self.as_kernel.current_kernel_type == "NCT" and self.as_kernel.nct_kernel:
                        # 使用异步停止方法
                        try:
                            import asyncio
                            
                            # 创建专用于关闭的事件循环
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            # 异步停止下载
                            async def async_stop_nct():
                                try:
                                    await self.as_kernel.stop_download()
                                    return True
                                except Exception as e:
                                    logging.error(f"NCT内核停止失败: {e}")
                                    return False
                            
                            # 执行异步停止
                            try:
                                loop.run_until_complete(async_stop_nct())
                            except Exception as e:
                                logging.error(f"执行NCT内核停止时出错: {e}")
                            finally:
                                loop.close()
                        except Exception as e:
                            logging.error(f"停止NCT内核出错: {e}")
                    
                    # 显式删除AS内核引用
                    self.as_kernel = None
                except Exception as e:
                    logging.error(f"关闭AS内核出错: {e}")
            
            # 然后处理下载引擎 (可能已经在AS内核处理中被停止，但再次确认)
            if hasattr(self, 'download_engine') and self.download_engine is not None:
                try:
                    logging.info("关闭窗口: 停止下载引擎")
                    
                    # 停止下载引擎 (如果还在运行)
                    if hasattr(self.download_engine, 'isRunning') and callable(self.download_engine.isRunning):
                        if self.download_engine.isRunning():
                            try:
                                self.download_engine.stop()
                                
                                # === 修复：增加更完善的线程等待和终止策略 ===
                                # 等待线程停止，使用更长的超时时间
                                if hasattr(self.download_engine, 'wait') and callable(self.download_engine.wait):
                                    # 先等待3秒
                                    if not self.download_engine.wait(3000):
                                        logging.warning("下载引擎线程停止等待超时(3秒)，尝试额外方法停止线程")
                                        
                                        # 尝试使用quit优雅退出线程
                                        if hasattr(self.download_engine, 'quit') and callable(self.download_engine.quit):
                                            try:
                                                self.download_engine.quit()
                                                # 再等待2秒
                                                if not self.download_engine.wait(2000):
                                                    logging.warning("下载引擎线程quit后等待超时(2秒)，尝试强制终止")
                                                    
                                                    # 如果还在运行，尝试terminate强制终止（最后手段）
                                                    if hasattr(self.download_engine, 'terminate') and callable(self.download_engine.terminate):
                                                        try:
                                                            self.download_engine.terminate()
                                                            # 等待终止完成
                                                            self.download_engine.wait(1000)
                                                        except Exception as term_error:
                                                            logging.error(f"强制终止下载引擎线程出错: {term_error}")
                                            except Exception as quit_error:
                                                logging.error(f"退出下载引擎线程出错: {quit_error}")
                            except Exception as stop_error:
                                logging.error(f"停止下载引擎出错: {stop_error}")
                    
                    # 确保断开所有信号连接
                    try:
                        if hasattr(self.download_engine, 'initialized'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.initialized, 'receivers') and self.download_engine.initialized.receivers() > 0:
                                    self.download_engine.initialized.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'block_progress_updated'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.block_progress_updated, 'receivers') and self.download_engine.block_progress_updated.receivers() > 0:
                                    self.download_engine.block_progress_updated.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'speed_updated'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.speed_updated, 'receivers') and self.download_engine.speed_updated.receivers() > 0:
                                    self.download_engine.speed_updated.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'download_completed'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.download_completed, 'receivers') and self.download_engine.download_completed.receivers() > 0:
                                    self.download_engine.download_completed.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'error_occurred'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.error_occurred, 'receivers') and self.download_engine.error_occurred.receivers() > 0:
                                    self.download_engine.error_occurred.disconnect()
                            except:
                                pass
                            
                        if hasattr(self.download_engine, 'file_name_changed'):
                            try:
                                # 检查信号是否有接收者
                                if hasattr(self.download_engine.file_name_changed, 'receivers') and self.download_engine.file_name_changed.receivers() > 0:
                                    self.download_engine.file_name_changed.disconnect()
                            except:
                                pass
                    except Exception as signal_error:
                        logging.warning(f"断开下载引擎信号时出错: {signal_error}")
                    
                    # 显式删除下载引擎引用
                    self.download_engine = None
                except Exception as e:
                    logging.error(f"关闭下载引擎出错: {e}")
            
            # 处理NCT下载线程 (如果存在)
            if hasattr(self, 'nct_download_thread') and self.nct_download_thread is not None:
                try:
                    # 标记NCT下载状态为已停止
                    self.nct_download_started = False
                    
                    # === 修复：添加Python线程终止逻辑 ===
                    # 注意：Python线程没有内置的终止方法，但我们可以设置标志并清除引用
                    if hasattr(self.nct_download_thread, 'is_alive') and callable(self.nct_download_thread.is_alive):
                        if self.nct_download_thread.is_alive():
                            logging.warning("NCT下载线程仍在运行，无法直接终止Python线程，只能清除引用")
                    
                    # 清除引用
                    self.nct_download_thread = None
                except Exception as e:
                    logging.error(f"清理NCT下载线程出错: {e}")
            
            # 清除布局内容
            self._clear_content()
                
            # 强制垃圾回收，尝试释放线程资源
            import gc
            gc.collect()
            
            # === 修复：强制第二次垃圾回收，增加清理机会 ===
            # 短暂延时后再次执行垃圾回收
            import time
            time.sleep(0.1)  # 给100毫秒让系统处理资源
            gc.collect()
            
            # === 最终的安全关闭处理 ===
            try:
                # 保存关键状态
                parent_was_minimized = False
                if hasattr(self, 'parent_was_minimized'):
                    parent_was_minimized = self.parent_was_minimized
                
                # 断开与UI的所有连接
                # 彻底分离信号和槽
                try:
                    # 分离所有已知信号 - 只断开已连接的信号
                    for signal_name in ['downloadRequested', 'downloadCancelled', 'downloadPaused', 
                                       'downloadResumed', 'fileOpened', 'folderOpened', 'downloadCompleted']:
                        if hasattr(self, signal_name):
                            signal = getattr(self, signal_name)
                            if hasattr(signal, 'disconnect') and callable(signal.disconnect):
                                # 检查信号是否有连接
                                try:
                                    # 使用receivers方法检查是否有连接的槽
                                    if hasattr(signal, 'receivers') and signal.receivers() > 0:
                                        signal.disconnect()  # 只有在有接收者时断开
                                except (TypeError, RuntimeError, AttributeError):
                                    # 静默失败，继续处理其他信号
                                    pass
                except Exception as e:
                    logging.debug(f"断开信号连接时出错: {e}")
                
                # 最彻底的处理：如果是在最小化状态创建的窗口
                if parent_was_minimized:
                    # 1. 强制使其成为独立窗口
                    self.setParent(None)
                    self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
                    
                    # 2. 清除所有可能导致应用程序退出的属性
                    self.setAttribute(Qt.WA_QuitOnClose, False)
                    
                    # 3. 使用延迟销毁，确保与主窗口完全分离
                    self.setAttribute(Qt.WA_DeleteOnClose, False)  # 暂时禁用自动删除
                    
                    # 4. 清除原始父窗口引用 - 使用弱引用保留必要信息
                    if hasattr(self, 'original_parent') and self.original_parent:
                        import weakref
                        self._parent_ref_weak = weakref.ref(self.original_parent)
                        self.original_parent = None
                    
                    # 5. 使用独立的完全销毁顺序
                    # 首先隐藏窗口，使其对用户不可见
                    self.hide()
                    
                    # 6. 安排延迟销毁，确保完全脱离事件循环
                    def delayed_destroy():
                        try:
                            # === 修复：最后再次检查线程并强制GC ===
                            import gc
                            gc.collect()
                            
                            # 使用Qt的deleteLater方法彻底销毁窗口
                            self.deleteLater()
                        except:
                            pass
                    
                    # 延迟500毫秒执行销毁，给线程更多时间完成
                    QTimer.singleShot(500, delayed_destroy)
                else:
                    # 对于普通状态创建的对话框，使用标准关闭流程
                    # 断开父窗口关系
                    self.setParent(None)
                    self.hide()
                    
                    # === 修复：延迟调用deleteLater，给线程更多时间结束 ===
                    def delayed_delete():
                        # 最后再次执行垃圾回收
                        import gc
                        gc.collect()
                        # 删除窗口
                        self.deleteLater()
                    
                    # 延迟300毫秒再删除
                    QTimer.singleShot(300, delayed_delete)
            except Exception as e:
                logging.error(f"关闭处理最终阶段出错: {e}")
                # 尝试标准关闭逻辑作为后备
                try:
                    self.hide()
                    self.deleteLater()
                except:
                    pass
            
            # 始终接受关闭事件
            event.accept()
        except Exception as e:
            # 捕获所有异常，确保窗口能被关闭
            logging.error(f"关闭窗口时发生意外错误: {e}")
            import traceback
            traceback.print_exc()
            event.accept()  # 仍然接受关闭事件
    
    def _setup_ui(self):
        """初始化UI"""
        # 设置窗口属性，提高渲染性能
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)  # 禁用不透明绘制，提高性能
        self.setAttribute(Qt.WA_NoSystemBackground, True)  # 禁用系统背景
        self.setFocusPolicy(Qt.StrongFocus)  # 设置强焦点策略
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 创建内容框架
        self.frame = ShadowFrame(self, radius=15, bg_color="#252526")
        self.main_layout.addWidget(self.frame)
        
        # 框架布局
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(25, 15, 25, 15)  # 增加左右边距，保持上下边距不变
        self.frame_layout.setSpacing(10)  # 保持间距
        
        # 顶部区域 - 标题栏
        self._create_title_bar()
        
        # 内容区域 - 根据状态动态创建
        self.content_widget = QFrame()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 5, 0, 5)  # 缩小边距
        self.content_layout.setSpacing(10)  # 减小间距
        self.frame_layout.addWidget(self.content_widget)
        
        # 底部区域 - 按钮
        self.button_widget = QFrame()
        self.button_layout = QHBoxLayout(self.button_widget)
        self.button_layout.setContentsMargins(0, 5, 0, 0)  # 缩小边距
        self.button_layout.setSpacing(10)  # 减小间距
        self.frame_layout.addWidget(self.button_widget)
        
        # 启用窗口自动调整大小 - 根据内容自动伸缩
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 默认显示添加下载UI
        self._create_add_download_ui()
    
    def _create_title_bar(self):
        """创建标题栏"""
        title_bar = QFrame()
        title_bar.setObjectName("title_bar")  # 设置对象名称，方便在鼠标事件中找到
        title_bar.setFixedHeight(40)
        title_bar.setCursor(Qt.ArrowCursor)  # 设置默认光标
        # 设置标题栏样式 - 移除悬停效果
        title_bar.setStyleSheet("""
            QFrame#title_bar {
                background-color: transparent;
                border: none;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)
        title_layout.setSpacing(10)
        
        # 标题图标
        self.title_icon = QLabel()
        self.title_icon.setFixedSize(24, 24)
        # 使用字体图标替代图片
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(self.title_icon, "ic_fluent_arrow_download_24_regular", size=22)
            self.title_icon.setStyleSheet("color: #B39DDB;")
        else:
            self.title_icon.setStyleSheet("background-image: url(assets/icons/icon_download_purple.png); background-position: center; background-repeat: no-repeat;")
        # 安装事件过滤器支持拖动
        self.title_icon.installEventFilter(self)
        title_layout.addWidget(self.title_icon)
        
        # 标题文本
        self.title_label = QLabel("添加下载")
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.title_label)
        # 安装事件过滤器支持拖动
        self.title_label.installEventFilter(self)
        title_layout.addWidget(self.title_label, 1)
        
        # 关闭按钮
        self.close_button = QPushButton()
        self.close_button.setFixedSize(30, 30)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(self.close_button, "ic_fluent_dismiss_24_regular", size=16)
            self.close_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                    color: #AAAAAA;
                    border-radius: 15px;
                }
                QPushButton:hover {
                    background-color: #3E3E42;
                    color: #FFFFFF;
                }
            """)
        else:
            self.close_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                    background-image: url(assets/icons/icon_close.png);
                    background-position: center;
                    background-repeat: no-repeat;
                }
                QPushButton:hover {
                    background-color: #3E3E42;
                    border-radius: 15px;
                }
            """)
        self.close_button.clicked.connect(self.close)
        # 安装事件过滤器支持拖动
        self.close_button.installEventFilter(self)
        title_layout.addWidget(self.close_button)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3C3C3C;")
        
        # 添加到布局
        title_container = QVBoxLayout()
        title_container.setContentsMargins(0, 0, 0, 0)
        title_container.setSpacing(5)
        title_container.addWidget(title_bar)
        title_container.addWidget(separator)
        
        self.frame_layout.addLayout(title_container)
    
    def _create_add_download_ui(self):
        """创建添加下载UI"""
        # 清空内容区域
        self._clear_content()
        
        # 设置标题
        self.title_label.setText("添加下载")
        
        # 创建一个总容器
        main_container = QFrame()
        main_container.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 增加容器边距
        main_layout.setSpacing(12)  # 增加间距
        
        # URL输入区域
        url_layout = QHBoxLayout()
        url_layout.setSpacing(5)
        
        url_label = QLabel("下载链接")
        url_label.setFixedWidth(75)  # 增加标签宽度
        url_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(url_label)
        url_layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入下载链接...")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.url_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.url_input)
        url_layout.addWidget(self.url_input)
        
        main_layout.addLayout(url_layout)
        
        # 文件名区域
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(5)
        
        filename_label = QLabel("文件名")
        filename_label.setFixedWidth(75)  # 增加标签宽度
        filename_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(filename_label)
        filename_layout.addWidget(filename_label)
        
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("自动获取文件名...")
        self.filename_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.filename_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.filename_input)
        filename_layout.addWidget(self.filename_input)
        
        main_layout.addLayout(filename_layout)
        
        # 保存路径区域
        save_path_layout = QHBoxLayout()
        save_path_layout.setSpacing(5)
        
        save_path_label = QLabel("保存位置")
        save_path_label.setFixedWidth(75)  # 增加标签宽度
        save_path_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(save_path_label)
        save_path_layout.addWidget(save_path_label)
        
        self.save_path_input = QLineEdit()
        self.save_path_input.setText(os.path.join(os.path.expanduser("~"), "Downloads"))
        self.save_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #8A7CEC;
            }
        """)
        self.save_path_input.setFixedHeight(28)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.save_path_input)
        save_path_layout.addWidget(self.save_path_input)
        
        self.browse_button = QPushButton("浏览")
        self.browse_button.setFixedSize(70, 28)  # 增加按钮宽度
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        self.browse_button.clicked.connect(self._on_browse)
        save_path_layout.addWidget(self.browse_button)
        
        main_layout.addLayout(save_path_layout)
        
        # 多线程选项
        self.multi_thread_checkbox = QCheckBox("使用多线程下载")
        self.multi_thread_checkbox.setChecked(True)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.multi_thread_checkbox)
        
        self.multi_thread_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 2px;
                border: 1px solid #555555;
                background: #333333;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #8A7CEC;
            }
            QCheckBox::indicator:checked {
                background: #8A7CEC;
                border: 1px solid #8A7CEC;
            }
        """)
        main_layout.addWidget(self.multi_thread_checkbox)
        
        # 添加到主内容区域
        self.content_layout.addWidget(main_container)
        
        # 底部按钮
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        
        button_layout.addStretch(1)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(90, 32)  # 增加按钮宽度
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 13px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel_download)
        button_layout.addWidget(self.cancel_button)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedSize(90, 32)  # 增加按钮宽度
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #8A7CEC;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #9E8FEF;
            }
            QPushButton:pressed {
                background-color: #7A6CD8;
            }
        """)
        self.download_button.clicked.connect(self._on_download)
        button_layout.addWidget(self.download_button)
        
        self.content_layout.addWidget(button_container)
        
        # 设置当前状态
        self.current_state = "add"
        
        # 为URL输入框添加内容变化处理
        self.url_input.textChanged.connect(self._on_url_changed)
        
        # 设置添加下载页面的窗口大小下限，但允许自动伸缩
        QTimer.singleShot(0, lambda: self._auto_resize())
    
    def _create_downloading_ui(self, task_data):
        """创建下载中UI"""
        # 清空内容区域 - 确保先前的UI完全清除
        self._clear_content()
        
        # 设置标题
        self.title_label.setText("正在下载")
        
        # 文件名和图标区域
        file_info_frame = QFrame()
        file_info_frame.setObjectName("file_info_frame")  # 设置对象名，方便以后查找
        file_info_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        file_info_layout = QHBoxLayout(file_info_frame)
        file_info_layout.setContentsMargins(20, 12, 20, 12)  # 增加左右边距
        file_info_layout.setSpacing(15)
        
        # 文件图标
        file_icon = QLabel()
        file_icon.setObjectName("file_icon")  # 设置对象名，方便以后查找
        file_icon.setFixedSize(36, 36)
        
        # 获取文件名和路径
        file_name = task_data.get("file_name", "")
        file_path = os.path.join(task_data.get("save_path", ""), file_name)
        
        # 获取文件扩展名，如果没有扩展名则显示"No"
        file_ext_raw = os.path.splitext(file_name)[1]
        file_ext = file_ext_raw.lstrip('.') if file_ext_raw else "No"
        
        # 直接为EXE文件使用Fluent Icons
        if file_ext.lower() == 'exe':
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_icon_font(file_icon, "ic_fluent_app_24_regular", size=28)
                file_icon.setStyleSheet("color: #FF9800; background-color: transparent;")
                logging.info("下载完成UI - 应用EXE图标")
            else:
                # 使用emoji作为备用
                emoji = "⚙️"
                color = "#FF9800"  # 橙色
                pixmap = self.file_icon_getter.create_pixmap_with_emoji(emoji, size=36, bg_color=color) if hasattr(self, 'file_icon_getter') else None
                if pixmap:
                    file_icon.setPixmap(pixmap)
                    file_icon.setScaledContents(True)
                    logging.info("下载完成UI - 应用EXE备用图标")
                else:
                    file_icon.setText(emoji)
                    file_icon.setAlignment(Qt.AlignCenter)
                    file_icon.setStyleSheet(f"color: {color}; background-color: transparent; font-size: 24px;")
                    logging.info("下载完成UI - 应用EXE文本图标")
        else:
            # 对于非EXE文件，尝试获取系统图标或使用Fluent图标
            icon = None
            if hasattr(self, 'file_icon_getter'):
                try:
                    # 先清除可能的缓存
                    if hasattr(self.file_icon_getter, 'icon_cache') and file_path in self.file_icon_getter.icon_cache:
                        del self.file_icon_getter.icon_cache[file_path]
                    
                    # 优先使用扩展名安全获取图标
                    icon = self.file_icon_getter.get_icon_by_ext_safe(file_ext)
                    logging.info(f"下载完成UI - 尝试通过扩展名获取图标: {file_ext}")
                    
                    # 如果通过扩展名无法获取图标，再尝试从文件路径获取
                    if (not icon or icon.isNull()) and os.path.exists(file_path):
                        try:
                            icon = self.file_icon_getter.get_file_icon(file_path=file_path, file_ext=file_ext)
                            logging.info(f"下载完成UI - 尝试通过文件路径获取图标: {file_path}")
                        except Exception as e:
                            logging.warning(f"从文件路径获取图标失败: {e}")
                except Exception as e:
                    logging.warning(f"获取图标过程出错: {e}")
            
            # 如果获取到了有效的图标，则使用它
            if icon and not icon.isNull():
                try:
                    pixmap = icon.pixmap(32, 32)
                    if not pixmap.isNull():
                        file_icon.setPixmap(pixmap)
                        file_icon.setScaledContents(True)
                        logging.info("下载完成UI - 成功应用系统图标")
                    else:
                        logging.warning("下载完成UI - 系统图标pixmap为空")
                        raise Exception("空pixmap")
                except Exception as e:
                    logging.warning(f"应用系统图标失败: {e}")
                    icon = None
            
            # 如果没有获取到有效图标，使用Fluent图标
            if not icon or icon.isNull():
                logging.info("下载完成UI - 使用Fluent图标替代")
                if hasattr(self, 'font_manager'):
                    # 根据文件类型选择合适的Fluent图标
                    icon_name = "document_24_regular"  # 默认文档图标
                    icon_color = "#B39DDB"  # 默认紫色
                    
                    if file_ext.lower() == 'msi':
                        icon_name = "app_store_24_regular"
                        icon_color = "#FF9800"  # 橙色
                    elif file_ext.lower() in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
                        icon_name = "archive_24_regular"
                        icon_color = "#FFCA28"  # 黄色
                    elif file_ext.lower() in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']:
                        icon_name = "image_24_regular"
                        icon_color = "#B39DDB"  # 紫色
                    elif file_ext.lower() in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']:
                        icon_name = "music_note_2_24_regular"
                        icon_color = "#66BB6A"  # 绿色
                    elif file_ext.lower() in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
                        icon_name = "video_24_regular"
                        icon_color = "#FF7043"  # 红色
                    elif file_ext.lower() in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                        icon_name = "document_24_regular"
                        icon_color = "#42A5F5"  # 蓝色
                    
                    try:
                        self.font_manager.apply_icon_font(file_icon, f"ic_fluent_{icon_name}", size=28)
                        file_icon.setStyleSheet(f"color: {icon_color}; background-color: transparent;")
                        logging.info(f"下载完成UI - 应用Fluent图标: {icon_name}")
                    except Exception as e:
                        logging.error(f"应用Fluent图标失败: {e}")
                        # 使用备用方案
                        file_icon.setText("📄")
                        file_icon.setAlignment(Qt.AlignCenter)
                        file_icon.setStyleSheet(f"color: {icon_color}; background-color: transparent; font-size: 24px;")
                        logging.info("下载完成UI - 应用文本图标作为备用")
                else:
                    # 使用emoji作为备用
                    emoji = "📄"
                    color = "#B39DDB"  # 紫色
                    try:
                        if hasattr(self, 'file_icon_getter'):
                            emoji = self.file_icon_getter.get_file_emoji(filename)
                            color = self.file_icon_getter.get_file_color(filename)
                            logging.info(f"下载完成UI - 获取到emoji: {emoji}, 颜色: {color}")
                    except Exception as e:
                        logging.warning(f"获取emoji或颜色失败: {e}")
                    
                    try:
                        pixmap = self.file_icon_getter.create_pixmap_with_emoji(emoji, size=36, bg_color=color) if hasattr(self, 'file_icon_getter') else None
                        if pixmap and not pixmap.isNull():
                            file_icon.setPixmap(pixmap)
                            file_icon.setScaledContents(True)
                            logging.info("下载完成UI - 应用emoji图标")
                        else:
                            raise Exception("创建emoji pixmap失败")
                    except Exception as e:
                        logging.warning(f"应用emoji图标失败: {e}")
                        file_icon.setText(emoji)
                        file_icon.setAlignment(Qt.AlignCenter)
                        file_icon.setStyleSheet(f"color: {color}; background-color: transparent; font-size: 24px;")
                        logging.info("下载完成UI - 应用文本emoji")
        
        file_info_layout.addWidget(file_icon)
        
        # 文件信息区域
        file_text_layout = QVBoxLayout()
        file_text_layout.setSpacing(4)
        
        # 文件名和扩展名布局
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(8)
        
        # 文件名
        self.filename_label = QLabel(task_data.get("file_name", "未知文件"))
        self.filename_label.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.filename_label)
        self.filename_label.setWordWrap(True)
        self.filename_label.setMaximumWidth(320)  # 减小最大宽度，为扩展名标签留出空间
        filename_layout.addWidget(self.filename_label, 1)
        
        # 文件扩展名标签
        self.ext_label = QLabel(file_ext)
        ext_bg_color = self.file_icon_getter.get_file_color(file_name) if hasattr(self, 'file_icon_getter') else "#808080"
        self.ext_label.setStyleSheet(f"""
            background-color: {ext_bg_color};
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
            font-weight: bold;
        """)
        self.ext_label.setAlignment(Qt.AlignCenter)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.ext_label)
        filename_layout.addWidget(self.ext_label)
        
        file_text_layout.addLayout(filename_layout)
        
        # 文件大小和状态
        size_status_layout = QHBoxLayout()
        size_status_layout.setSpacing(15)
        
        # 文件大小
        self.size_label = QLabel("大小: 获取中...")
        self.size_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.size_label)
        size_status_layout.addWidget(self.size_label)
        
        # 下载状态
        self.status_label = QLabel("初始化中...")
        self.status_label.setStyleSheet("color: #8A7CEC; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.status_label)
        size_status_layout.addWidget(self.status_label)
        
        size_status_layout.addStretch(1)
        file_text_layout.addLayout(size_status_layout)
        
        file_info_layout.addLayout(file_text_layout, 1)
        self.content_layout.addWidget(file_info_frame)
        
        # 进度信息区域
        progress_frame = QFrame()
        progress_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(20, 15, 20, 15)  # 增加左右边距
        progress_layout.setSpacing(15)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3A3A3A;
                border: none;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8A7CEC, stop:1 #B39DDB);
                border-radius: 5px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # 下载详情布局
        details_layout = QHBoxLayout()
        details_layout.setSpacing(20)
        
        # 速度信息
        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(6)
        
        # 速度图标
        speed_icon = QLabel()
        speed_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(speed_icon, "ic_fluent_arrow_trending_24_regular", size=14)
            speed_icon.setStyleSheet("color: #B0B0B0;")
        else:
            speed_icon.setStyleSheet("background-image: url(assets/icons/icon_speed.png); background-position: center; background-repeat: no-repeat;")
        speed_layout.addWidget(speed_icon)
        
        # 速度文本
        self.speed_label = QLabel("0 B/s")
        self.speed_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.speed_label)
        speed_layout.addWidget(self.speed_label)
        
        details_layout.addLayout(speed_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        separator.setStyleSheet("background-color: #505050;")
        separator.setFixedWidth(1)
        details_layout.addWidget(separator)
        
        # 剩余时间信息
        time_layout = QHBoxLayout()
        time_layout.setSpacing(6)
        
        # 时间图标
        time_icon = QLabel()
        time_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(time_icon, "ic_fluent_clock_24_regular", size=14)
            time_icon.setStyleSheet("color: #B0B0B0;")
        else:
            time_icon.setStyleSheet("background-image: url(assets/icons/icon_time.png); background-position: center; background-repeat: no-repeat;")
        time_layout.addWidget(time_icon)
        
        # 时间文本
        self.time_label = QLabel("计算中...")
        self.time_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.time_label)
        time_layout.addWidget(self.time_label)
        
        details_layout.addLayout(time_layout)
        
        # 分隔线2
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Plain)
        separator2.setStyleSheet("background-color: #505050;")
        separator2.setFixedWidth(1)
        details_layout.addWidget(separator2)
        
        # 核心类型信息
        kernel_layout = QHBoxLayout()
        kernel_layout.setSpacing(6)
        
        # 核心图标
        kernel_icon = QLabel()
        kernel_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(kernel_icon, "ic_fluent_chip_24_regular", size=14)
            kernel_icon.setStyleSheet("color: #B0B0B0;")
        else:
            kernel_icon.setText("⚙️")
            kernel_icon.setStyleSheet("color: #B0B0B0; font-size: 14px;")
        kernel_layout.addWidget(kernel_icon)
        
        # 核心类型标签
        self.kernel_type_label = QLabel()
        self.kernel_type_label.setStyleSheet("color: #757575; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(self.kernel_type_label)
        
        # 获取核心全名（如果可用）
        kernel_display_name = self.kernel_type
        if hasattr(self, 'kernel_fullname'):
            # 只显示核心全名的前半部分，不包含"Kernel"字样
            kernel_display_name = self.kernel_fullname.split(" Kernel")[0]
        
        self.kernel_type_label.setText(f"核心: {kernel_display_name}")
        
        # 设置提示信息
        if hasattr(self, 'kernel_fullname'):
            self.kernel_type_label.setToolTip(f"{self.kernel_fullname} ({self.kernel_type})")
        else:
            self.kernel_type_label.setToolTip(f"下载核心: {self.kernel_type}")
            
        kernel_layout.addWidget(self.kernel_type_label)
        kernel_layout.addStretch()
        
        details_layout.addLayout(kernel_layout)
        details_layout.addStretch(1)
        
        progress_layout.addLayout(details_layout)
        self.content_layout.addWidget(progress_frame)
        
        # 分段信息按钮容器
        segment_header_frame = QFrame()
        segment_header_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        segment_header_layout = QHBoxLayout(segment_header_frame)
        segment_header_layout.setContentsMargins(20, 10, 20, 10)  # 增加左右边距
        segment_header_layout.setSpacing(10)
        
        # 分段信息图标
        segments_icon = QLabel()
        segments_icon.setFixedSize(16, 16)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_icon_font(segments_icon, "ic_fluent_data_histogram_24_regular", size=14)
            segments_icon.setStyleSheet("color: #B39DDB;")
        else:
            segments_icon.setStyleSheet("background-image: url(assets/icons/icon_segments.png); background-position: center; background-repeat: no-repeat;")
        segment_header_layout.addWidget(segments_icon)
        
        # 分段信息标题
        segments_title = QLabel("分段下载信息")
        segments_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(segments_title)
        segment_header_layout.addWidget(segments_title)
        
        segment_header_layout.addStretch(1)
        
        # 切换按钮 - 根据是否显示分段信息设置不同图标
        self.toggle_segments_button = QPushButton()
        self.toggle_segments_button.setFixedSize(24, 24)
        if hasattr(self, 'font_manager'):
            # 设置与展开/折叠状态匹配的图标
            if self.show_segments:
                # 展开状态 - 显示向上箭头表示可以折叠
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_up_24_regular", size=16)
            else:
                # 折叠状态 - 显示向下箭头表示可以展开
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_down_24_regular", size=16)
        else:
            # 文本备用方案
            self.toggle_segments_button.setText("分段信息 ▽" if self.show_segments else "分段信息 ▷")
            
        # 设置切换按钮样式
        self.toggle_segments_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #CCCCCC;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        
        self.toggle_segments_button.clicked.connect(self._toggle_segments_display)
        segment_header_layout.addWidget(self.toggle_segments_button)
        
        self.content_layout.addWidget(segment_header_frame)
        
        # 分段信息区域
        self.segments_frame = QFrame()
        self.segments_frame.setStyleSheet("background-color: #2A2A2A; border-radius: 8px;")
        self.segments_layout = QVBoxLayout(self.segments_frame)
        self.segments_layout.setContentsMargins(20, 15, 20, 15)  # 增加左右边距
        self.segments_layout.setSpacing(10)
        
        # 分段信息表头
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #323232; border-radius: 6px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(15)
        
        # 序号
        index_header = QLabel("#")
        index_header.setFixedWidth(30)
        index_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(index_header)
        header_layout.addWidget(index_header)
        
        # 状态
        status_header = QLabel("状态")
        status_header.setFixedWidth(100)
        status_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(status_header)
        header_layout.addWidget(status_header)
        
        # 已下载
        downloaded_header = QLabel("已下载")
        downloaded_header.setFixedWidth(100)
        downloaded_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(downloaded_header)
        header_layout.addWidget(downloaded_header)
        
        # 总大小
        total_header = QLabel("总大小")
        total_header.setFixedWidth(100)
        total_header.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(total_header)
        header_layout.addWidget(total_header)
        
        self.segments_layout.addWidget(header_frame)
        
        # 分段信息内容区域 - 使用滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 应用滚动条样式
        ScrollStyle.apply_to_widget(scroll_area, "dark")
        
        self.segments_scroll_area = QFrame()
        self.segments_scroll_layout = QVBoxLayout(self.segments_scroll_area)
        self.segments_scroll_layout.setContentsMargins(0, 3, 0, 3)  # 减小边距
        self.segments_scroll_layout.setSpacing(3)  # 减少间距
        
        scroll_area.setWidget(self.segments_scroll_area)
        scroll_area.setMinimumHeight(80)  # 减小最小高度
        scroll_area.setMaximumHeight(120)  # 减小最大高度
        self.segments_layout.addWidget(scroll_area)
        
        self.content_layout.addWidget(self.segments_frame)
        # 根据show_segments属性设置分段信息框的可见性（默认为False，即折叠状态）
        self.segments_frame.setVisible(self.show_segments)
        
        # 添加空白空间
        self.content_layout.addStretch(1)
        
        # 底部按钮
        self.button_layout.addStretch(1)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(110, 40)  # 增加按钮宽度
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_dismiss_24_regular")
            self.cancel_button.setIcon(icon)
            self.cancel_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            self.cancel_button.setText("  取消")
            self.font_manager.apply_font(self.cancel_button)
        
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
        """)
        self.cancel_button.clicked.connect(self._on_cancel_download)
        self.button_layout.addWidget(self.cancel_button)
        
        self.download_button = QPushButton("")
        self.download_button.setFixedSize(110, 40)  # 增加按钮宽度
        if hasattr(self, 'font_manager'):
            # 不使用布局，直接设置图标
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_pause_24_regular")  # 默认显示暂停图标
            self.download_button.setIcon(icon)
            self.download_button.setIconSize(QSize(16, 16))
            
            # 设置文本并添加前导空格以防止文本和图标重叠
            self.download_button.setText("  暂停")
            self.font_manager.apply_font(self.download_button)
        
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #8A7CEC;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #9E8FEF;
            }
            QPushButton:pressed {
                background-color: #7A6CD8;
            }
        """)
        self.download_button.clicked.connect(self._on_pause_resume)
        self.button_layout.addWidget(self.download_button)
        
        # 设置当前状态
        self.current_state = "downloading"
        self.is_paused = False
        
        # 保存任务ID
        self.task_id = task_data.get("task_id", "")
        
        # 初始化段列表
        self.segment_rows = []
        
        # 设置窗口自动调整大小
        QTimer.singleShot(0, lambda: self._auto_resize())
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _extract_filename_from_url(self, url):
        """从URL提取文件名"""
        try:
            # 解析URL
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # 从路径中获取文件名
            if path:
                filename = os.path.basename(path)
                # 处理查询参数
                if '?' in filename:
                    filename = filename.split('?')[0]
                # URL解码
                try:
                    filename = unquote(filename)
                except:
                    pass
                return filename
        except:
            pass
            
        return ""
    
    def _get_readable_size(self, size_bytes):
        """获取可读的文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
    
    def _get_readable_speed(self, speed_bytes):
        """获取可读的下载速度"""
        if speed_bytes < 1024:
            return f"{speed_bytes} B/s"
        elif speed_bytes < 1024 * 1024:
            return f"{speed_bytes/1024:.1f} KB/s"
        elif speed_bytes < 1024 * 1024 * 1024:
            return f"{speed_bytes/(1024*1024):.2f} MB/s"
        else:
            return f"{speed_bytes/(1024*1024*1024):.2f} GB/s"
    
    def _get_readable_time(self, seconds):
        """获取可读的时间格式"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}分{seconds:.0f}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}时{minutes:.0f}分"
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于窗口拖动"""
        try:
            if event.button() == Qt.LeftButton:
                # 检查鼠标是否在标题栏区域内
                title_bar = self.findChild(QFrame, "title_bar")
                if title_bar and title_bar.geometry().contains(event.pos()):
                    self.dragging = True
                    # 使用globalPosition()获取全局坐标，更准确
                    self.drag_position = event.globalPosition().toPoint() - self.pos()
                    
                    # 记录当前时间，用于计算拖动速度
                    self.last_move_time = time.time()
                    self.last_move_pos = event.globalPosition().toPoint()
                    
                    # 修改光标形状为移动状态
                    self.setCursor(Qt.ClosedHandCursor)
                    event.accept()
                    return
            
            # 如果不满足拖动条件，调用父类处理
            super().mousePressEvent(event)
        except Exception as e:
            logging.debug(f"鼠标按下事件异常: {e}")
            event.ignore()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 用于窗口拖动"""
        try:
            if event.buttons() & Qt.LeftButton and self.dragging:
                # 计算当前时间和位置
                current_time = time.time()
                current_pos = event.globalPosition().toPoint()
                
                # 计算移动速度（像素/秒）
                time_diff = current_time - getattr(self, 'last_move_time', current_time)
                if time_diff > 0:
                    last_pos = getattr(self, 'last_move_pos', current_pos)
                    dx = current_pos.x() - last_pos.x()
                    dy = current_pos.y() - last_pos.y()
                    distance = (dx**2 + dy**2)**0.5
                    speed = distance / time_diff
                    
                    # 更新最后移动时间和位置
                    self.last_move_time = current_time
                    self.last_move_pos = current_pos
                    
                    # 如果移动速度过快，适当降低响应频率以防止卡顿
                    if speed > 1500 and hasattr(self, 'last_update_time'):
                        if current_time - self.last_update_time < 0.016:  # 约60fps
                            event.accept()
                            return
                    
                    self.last_update_time = current_time
                
                # 计算精确的新位置
                new_pos = event.globalPosition().toPoint() - self.drag_position
                
                # 限制窗口不要移出屏幕
                screen = QApplication.primaryScreen().availableGeometry()
                new_pos.setX(max(0, min(new_pos.x(), screen.width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), screen.height() - self.height())))
                
                # 直接设置位置，避免使用move()可能导致的问题
                self.setGeometry(new_pos.x(), new_pos.y(), self.width(), self.height())
                
                # 强制立即更新窗口位置
                QApplication.processEvents()
                
                event.accept()
                return
            
            # 如果不满足拖动条件，调用父类处理
            super().mouseMoveEvent(event)
        except Exception as e:
            logging.debug(f"鼠标移动事件异常: {e}")
            event.ignore()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 用于窗口拖动"""
        try:
            if event.button() == Qt.LeftButton and self.dragging:
                self.dragging = False
                # 恢复默认光标
                self.setCursor(Qt.ArrowCursor)
                event.accept()
                return
                
            # 如果不满足拖动条件，调用父类处理
            super().mouseReleaseEvent(event)
        except Exception as e:
            logging.debug(f"鼠标释放事件异常: {e}")
            event.ignore()
    
    def _process_download_data(self, download_data):
        """处理下载数据，添加必要的信息
        
        参数:
            download_data (dict): 原始下载数据
            
        返回:
            dict: 处理后的任务数据
        """
        # 拷贝数据，避免修改原始对象
        task_data = dict(download_data)
        
        # 确保有ID
        if "task_id" not in task_data:
            task_data["task_id"] = f"popup_{int(time.time() * 1000)}"
        
        # 确保有requestId
        if "requestId" not in task_data:
            task_data["requestId"] = f"popup_{int(time.time() * 1000)}"
        
        # 确保有保存路径
        if "save_path" not in task_data:
            task_data["save_path"] = os.path.expanduser("~/Downloads")
            # 创建目录
            os.makedirs(task_data["save_path"], exist_ok=True)
        
        # 确保有标头
        if "headers" not in task_data:
            # 获取用户设置的UA
            user_agent = self.get_user_agent()
            task_data["headers"] = {
                "User-Agent": user_agent
            }
        
        # 处理文件名
        url = task_data.get("url", "")
        if not url:
            logging.error("下载数据缺少URL")
            return None
            
        if "file_name" not in task_data or not task_data["file_name"]:
            filename = self._extract_filename_from_url(url)
            task_data["file_name"] = filename
        
        # 添加开始时间
        task_data["start_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加多线程标志
        if "multi_thread" not in task_data:
            task_data["multi_thread"] = True
        
        return task_data
        
    def get_user_agent(self):
        """获取用户设置的User-Agent，查找上层窗口的配置管理器
        
        返回:
            str: 用户设置的User-Agent，如未设置则返回默认值
        """
        try:
            # 向上查找主窗口
            parent = self.parent()
            while parent:
                # 查找主窗口的get_user_agent方法
                if hasattr(parent, 'get_user_agent'):
                    return parent.get_user_agent()
                # 查找主窗口的配置管理器
                elif hasattr(parent, 'config_manager') and parent.config_manager:
                    # 尝试获取UA
                    if hasattr(parent.config_manager, 'get_user_agent'):
                        return parent.config_manager.get_user_agent()
                    else:
                        network_config = parent.config_manager.get("network", {})
                        user_agent = network_config.get("user_agent")
                        if user_agent:
                            return user_agent
                parent = parent.parent()
        except Exception as e:
            logging.warning(f"获取User-Agent失败: {e}")
        
        # 返回默认值
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    def _set_thread_priority_safely(self):
        """安全地设置线程优先级"""
        if not hasattr(self, 'download_engine') or self.download_engine is None:
            return
            
        try:
            # 检查线程是否在运行
            if self.download_engine.isRunning():
                # 设置为低优先级，使下载线程更容易被系统中断
                self.download_engine.setPriority(QThread.LowPriority)
                logging.debug("成功设置下载线程为低优先级")
            else:
                logging.debug("下载线程未运行，无法设置优先级")
        except Exception as e:
            # 忽略设置优先级可能的错误，不影响下载功能
            logging.debug(f"设置线程优先级失败: {e}")
    
    def _start_download(self, task_data):
        """开始下载任务
        
        参数:
            task_data (dict): 下载任务数据
        """
        try:
            # 获取必要参数
            url = task_data.get("url", "")
            headers = task_data.get("headers", {})
            save_path = task_data.get("save_path", os.path.expanduser("~/Downloads"))
            file_name = task_data.get("file_name", "")
            multi_thread = task_data.get("multi_thread", True)
            max_concurrent = 8 if multi_thread else 1
            
            # 从配置中获取默认分段数和是否启用智能线程管理
            default_segments = 8  # 默认值
            smart_threading = multi_thread  # 默认智能线程与多线程设置一致
            
            try:
                # 导入配置管理器
                from client.ui.client_interface.settings.config import config
                
                # 获取默认分段数
                default_segments = config.get_setting("download", "default_segments", 8)
                
                # 只有在多线程模式下才可能启用智能线程管理
                if multi_thread:
                    # 读取智能线程管理设置
                    smart_threading = config.get_setting("download", "dynamic_threads", True)
                    if not smart_threading:
                        logging.info(f"智能线程管理已关闭，将使用固定分段数: {default_segments}")
            except Exception as e:
                logging.warning(f"获取配置失败，使用默认值: {e}")
            
            # 使用AS内核自动选择最合适的下载内核
            with self.thread_lock:
                # 创建自动调度内核
                self.as_kernel = HanabiASKernel()
                
                # 初始化下载任务，这会自动选择最合适的内核
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success, error_msg = loop.run_until_complete(
                    self.as_kernel.initialize_download(
                        url=url,
                        headers=headers,
                        save_path=save_path,
                        file_name=file_name,
                        max_concurrent=max_concurrent,
                        smart_threading=smart_threading,
                        default_segments=default_segments
                    )
                )
                
                if not success:
                    raise Exception(f"初始化下载失败: {error_msg}")
                
                # 获取选择的内核类型
                kernel_type = self.as_kernel.current_kernel_type
                # 保存核心类型
                self.kernel_type = kernel_type
                
                # 获取核心全名（如果存在）
                if hasattr(self.as_kernel, 'current_kernel_fullname'):
                    self.kernel_fullname = self.as_kernel.current_kernel_fullname
                else:
                    # 如果AS内核没有提供全名，则使用默认映射
                    kernel_names = {
                        "NSF": "Nextgen Speed Force Kernel",
                        "NCT": "Nextgen Crystal Transfer Kernel"
                    }
                    self.kernel_fullname = kernel_names.get(kernel_type, kernel_type)
                
                # 如果是NSF内核，直接使用其实例
                if kernel_type == "NSF":
                    self.download_engine = self.as_kernel.nsf_kernel
                    
                    # 连接信号
                    self.download_engine.initialized.connect(self._on_download_initialized)
                    self.download_engine.block_progress_updated.connect(self._on_progress_updated)
                    self.download_engine.speed_updated.connect(self._on_speed_updated)
                    self.download_engine.download_completed.connect(self._on_download_completed)
                    self.download_engine.error_occurred.connect(self._on_download_error)
                    self.download_engine.file_name_changed.connect(self._on_filename_changed)
                    
                    # 启动下载线程
                    loop.run_until_complete(self.as_kernel.start_download())
                    
                    # 在线程启动后设置优先级
                    try:
                        # 等待极短时间确保线程已启动
                        QTimer.singleShot(10, lambda: self._set_thread_priority_safely())
                    except Exception as e:
                        # 忽略设置优先级可能的错误，不影响下载功能
                        logging.debug(f"设置线程优先级时出错: {e}")
                    
                elif kernel_type == "NCT":
                    # 如果是NCT内核，需要不同的处理
                    self.download_engine = None  # 清除引用
                    self.nct_kernel = self.as_kernel.nct_kernel
                    
                    # 初始化NCT下载相关状态
                    self.nct_download_started = True
                    self.nct_download_progress = 0
                    self.nct_download_speed = 0
                    self.nct_file_size = 0
                    self.nct_downloaded = 0
                    self.nct_last_update_time = time.time()
                    
                    # 创建NCT下载进度回调函数
                    def progress_callback(transferred, total):
                        try:
                            self.nct_file_size = total
                            self.nct_downloaded = transferred
                            
                            # 计算下载速度
                            current_time = time.time()
                            time_diff = current_time - self.nct_last_update_time
                            if time_diff > 0.1:  # 至少0.1秒更新一次速度
                                # 计算速度（字节/秒）
                                self.nct_download_speed = int((transferred - self.nct_download_progress) / time_diff)
                                self.nct_download_progress = transferred
                                self.nct_last_update_time = current_time
                                
                                # 更新UI上的速度显示
                                speed_str = self._get_readable_speed(self.nct_download_speed)
                                self.speed_label.setText(f"速度: {speed_str}")
                                
                                # 更新进度条
                                if total > 0:
                                    progress = (transferred / total) * 100
                                    self.update_progress(progress)
                                    
                                    # 更新剩余时间
                                    if self.nct_download_speed > 0:
                                        remaining = total - transferred
                                        seconds_left = remaining / self.nct_download_speed
                                        time_str = self._get_readable_time(seconds_left)
                                        self.time_label.setText(time_str)
                        except Exception as e:
                            logging.error(f"NCT进度回调处理错误: {e}")
                    
                    # 创建NCT下载完成回调函数
                    def download_complete_callback(success, error=None):
                        try:
                            if success:
                                # 下载成功
                                logging.info(f"NCT下载完成: {file_name}")
                                self.update_progress(100)
                                self._on_download_completed()
                            else:
                                # 下载失败
                                error_msg = error if error else "未知错误"
                                logging.error(f"NCT下载失败: {error_msg}")
                                self._on_download_error(error_msg)
                        except Exception as e:
                            logging.error(f"NCT完成回调处理错误: {e}")
                    
                    # 模拟初始化完成信号
                    QTimer.singleShot(100, lambda: self._on_download_initialized(True))
                    
                    # 启动NCT下载任务（异步）
                    async def start_nct_download():
                        try:
                            # 启动下载并等待完成
                            await self.as_kernel.download_file(
                                progress_callback=progress_callback,
                                complete_callback=download_complete_callback
                            )
                        except Exception as e:
                            logging.error(f"NCT下载任务启动失败: {e}")
                            self._on_download_error(str(e))
                    
                    # 创建新的事件循环来运行异步任务
                    def run_async_download():
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            new_loop.run_until_complete(start_nct_download())
                        except Exception as e:
                            logging.error(f"NCT下载线程执行错误: {e}")
                    
                    # 在单独的线程中启动异步下载任务
                    import threading
                    self.nct_download_thread = threading.Thread(target=run_async_download)
                    self.nct_download_thread.daemon = True
                    self.nct_download_thread.start()
                    
                    logging.info(f"使用NCT内核下载: {url}")
                else:
                    raise Exception(f"未知的内核类型: {kernel_type}")
                
                # 启动进度更新定时器
                self.progress_timer.start(500)  # 每500毫秒更新一次
                
                # 保存任务ID
                self.task_id = task_data.get("task_id", "")
                
                # 更新UI状态
                self.status_label.setText("初始化中...")
                
                # 如果已经创建了核心类型标签，更新其内容
                if hasattr(self, 'kernel_type_label'):
                    self.kernel_type_label.setText(f"核心: {self.kernel_type}")
                
                logging.info(f"弹窗已启动下载任务: {url}, 内核类型: {kernel_type}, 智能线程管理: {smart_threading}, 默认分段数: {default_segments}")
                
        except Exception as e:
            logging.error(f"启动下载任务失败: {e}")
            self._on_download_error(str(e))
    
    def _on_download_initialized(self, multi_thread_support):
        """下载初始化完成回调
        
        参数:
            multi_thread_support (bool): 是否支持多线程下载
        """
        with self.thread_lock:
            if not self.download_engine and not hasattr(self, 'nct_download_started'):
                return
                
            # 更新UI
            self.status_label.setText("下载中...")
            
            # 更新核心类型标签
            if hasattr(self, 'kernel_type_label'):
                # 获取核心全名
                kernel_fullname = ""
                if self.kernel_type == "NSF":
                    kernel_fullname = "Nextgen Speed Force"
                    self.kernel_type_label.setText(f"核心: {kernel_fullname}")
                    self.kernel_type_label.setStyleSheet("color: #8A7CEC; font-size: 13px;")  # 紫色
                elif self.kernel_type == "NCT":
                    kernel_fullname = "Nextgen Crystal Transfer"
                    self.kernel_type_label.setText(f"核心: {kernel_fullname}")
                    self.kernel_type_label.setStyleSheet("color: #4CAF50; font-size: 13px;")  # 绿色
                else:
                    self.kernel_type_label.setText(f"核心: {self.kernel_type}")
                    self.kernel_type_label.setStyleSheet("color: #757575; font-size: 13px;")  # 灰色
                
                # 添加提示工具提示
                if kernel_fullname:
                    self.kernel_type_label.setToolTip(f"{kernel_fullname} Kernel ({self.kernel_type})")
            
            # 更新文件大小
            if hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                size_str = self._get_readable_size(self.download_engine.file_size)
                self.size_label.setText(f"大小: {size_str}")
                
            # 显示分段下载状态
            if multi_thread_support:
                # 启用分段显示切换按钮
                if hasattr(self, 'toggle_segments_button'):
                    self.toggle_segments_button.setEnabled(True)
                    self.toggle_segments_button.setToolTip("点击显示/隐藏分段下载详情")
            else:
                # 禁用分段显示切换按钮
                if hasattr(self, 'toggle_segments_button'):
                    self.toggle_segments_button.setEnabled(False)
                    self.toggle_segments_button.setToolTip("当前下载不支持分段")
                    
            # 更新进度条状态
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setEnabled(True)
    
    def _on_progress_updated(self, progress_data):
        """进度更新回调
        
        参数:
            progress_data (list): 进度数据
        """
        try:
            # 导入time模块
            import time
            
            # 检查是否是NCT内核下载
            if hasattr(self, 'nct_download_started') and self.nct_download_started:
                # NCT内核的进度更新由progress_callback处理
                # 这里不需要额外处理
                return
                
            # 以下是NSF内核的进度处理
            # 计算总进度百分比
            total_downloaded = 0
            total_size = 0
            
            # 添加更详细的字段兼容处理
            processed_blocks = []
            
            # 状态稳定性处理 - 跟踪各段之前的状态
            if not hasattr(self, '_previous_block_statuses'):
                self._previous_block_statuses = {}  # 用于记录每个块的上一个状态
                self._status_stable_counter = {}   # 状态稳定计数器
                self._last_segments_update = 0     # 上次段信息更新时间
            
            # 确保_last_segments_update已初始化
            if not hasattr(self, '_last_segments_update'):
                self._last_segments_update = 0
                
            current_time = time.time()
            status_changed = False  # 跟踪是否有状态变更
            
            for i, block in enumerate(progress_data):
                if isinstance(block, dict):
                    # 支持多种字段名格式
                    start_pos = block.get('start_pos', block.get('start_position', block.get('startPos', 0)))
                    end_pos = block.get('end_pos', block.get('end_position', block.get('endPos', 0)))
                    current = block.get('progress', block.get('current_pos', block.get('current_position', block.get('currentPos', start_pos))))
                    status = block.get('status', "下载中")
                elif isinstance(block, (list, tuple)) and len(block) >= 3:
                    start_pos, current, end_pos = block[:3]
                    status = "下载中" if current < end_pos else "已完成"
                else:
                    continue
                
                # 确保值合法并转为整数
                try:
                    start_pos = max(0, int(start_pos))
                    end_pos = max(start_pos, int(end_pos)) 
                    current = max(start_pos, min(end_pos, int(current)))
                except (ValueError, TypeError):
                    # 如果转换失败，使用默认值
                    start_pos, current, end_pos = 0, 0, 0
                
                # 状态稳定性处理
                block_id = f"{start_pos}:{end_pos}"
                previous_status = self._previous_block_statuses.get(block_id, None)
                
                # 如果状态从"下载中"切换到"连接中"且短时间内发生，保持为"下载中"
                if status == "连接中" and previous_status == "下载中":
                    if block_id not in self._status_stable_counter:
                        self._status_stable_counter[block_id] = 0
                    
                    self._status_stable_counter[block_id] += 1
                    # 如果连续3次都想切换到"连接中"，才真正切换
                    if self._status_stable_counter[block_id] < 3:
                        status = "下载中"  # 保持为下载中
                    else:
                        # 确认切换到连接中
                        status_changed = True
                        self._status_stable_counter[block_id] = 0
                else:
                    # 其他状态变化立即接受
                    if previous_status != status:
                        status_changed = True
                    
                    # 重置计数器
                    self._status_stable_counter[block_id] = 0
                
                # 记录当前状态为下一次比较的基础
                self._previous_block_statuses[block_id] = status
                
                # 计算已下载量
                block_downloaded = current - start_pos
                block_size = end_pos - start_pos + 1
                
                # 累计总量
                total_downloaded += block_downloaded
                total_size += block_size
                
                # 创建统一格式的块信息
                processed_block = {
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'progress': current,
                    'status': status,
                    'downloaded': block_downloaded,
                    'size': block_size
                }
                processed_blocks.append(processed_block)
            
            # 计算百分比
            if total_size > 0:
                progress = (total_downloaded / total_size) * 100
                # 如果进度超过99.9%，视为完成
                if progress > 99.9:
                    progress = 100
                
                # 修复：添加安全检查，确保progress_bar对象存在
                if hasattr(self, 'progress_bar') and self.progress_bar is not None:
                    # 平滑进度变化
                    if not hasattr(self, 'last_progress'):
                        self.last_progress = 0
                        
                    # 防止进度回退
                    if self.last_progress > progress and self.last_progress < 99:
                        progress = self.last_progress  # 保持原进度
                    else:
                        # 进度前进时平滑变化
                        progress = min(100, self.last_progress * 0.7 + progress * 0.3)
                    
                    # 记录当前进度
                    self.last_progress = progress
                    
                    # 设置进度条值
                    self.progress_bar.setValue(int(progress))
                else:
                    logging.debug("进度条对象不存在，跳过进度更新")
                    return
            
            # 使用处理后的块信息更新分段信息
            # 限制更新频率，有状态变化或超过1秒才更新
            if processed_blocks and hasattr(self, 'segments_scroll_layout'):
                if status_changed or (current_time - self._last_segments_update) > 1.0:
                    self._update_segments_info(processed_blocks)
                    self._last_segments_update = current_time
            
        except Exception as e:
            logging.error(f"处理进度更新失败: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            
    def _on_speed_updated(self, speed_bytes):
        """速度更新回调
        
        参数:
            speed_bytes (int): 下载速度(字节/秒)
        """
        # 更新UI - 使用统一格式"速度: {speed_str}"
        speed_str = self._get_readable_speed(speed_bytes)
        self.speed_label.setText(f"速度: {speed_str}")
        
        # 估算剩余时间
        if hasattr(self, 'download_engine') and self.download_engine:
            try:
                if speed_bytes > 0 and hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                    # 计算已下载量
                    downloaded = self.download_engine.current_progress
                    remaining = self.download_engine.file_size - downloaded
                    
                    # 计算剩余时间
                    if remaining > 0:
                        seconds_left = remaining / speed_bytes
                        time_str = self._get_readable_time(seconds_left)
                        self.time_label.setText(time_str)
            except Exception as e:
                logging.error(f"计算剩余时间失败: {e}")
    
    def _on_download_completed(self, status=None):
        """下载完成回调"""
        logging.info("下载任务完成")
        
        # 停止定时器
        self.progress_timer.stop()
        
        # 如果已经关闭了窗口，不处理
        if not self.isVisible():
            return
        
        # 准备完成数据 - 从下载引擎获取信息
        file_name = ""
        file_size = 0
        save_path = ""
        
        with self.thread_lock:
            if self.download_engine:
                file_name = self.download_engine.file_name
                file_size = self.download_engine.file_size
                save_path = self.download_engine.save_path
                
                # 如果文件大小未知或为0，尝试从实际文件获取
                if file_size <= 0:
                    try:
                        file_path = Path(save_path) / file_name
                        if file_path.exists():
                            file_size = file_path.stat().st_size
                            logging.info(f"从实际文件获取大小: {file_size} 字节")
                    except Exception as e:
                        logging.error(f"获取实际文件大小失败: {e}")
        
        # 创建完成数据
        task_data = {
            "task_id": self.task_id,
            "file_name": file_name,
            "file_size": file_size,
            "save_path": save_path,
            "status": "已完成"
        }
        
        # 如果提供了status参数，使用其中的值覆盖
        if status and isinstance(status, dict):
            if "file_name" in status and status["file_name"]:
                task_data["file_name"] = status["file_name"]
            if "file_size" in status and status["file_size"]:
                task_data["file_size"] = status["file_size"]
            if "save_path" in status and status["save_path"]:
                task_data["save_path"] = status["save_path"]
            if "status" in status:
                task_data["status"] = status["status"]
        
        # 记录之前的窗口状态
        old_state = self.current_state
        
        # 彻底清除当前UI
        self._clear_content()
        
        # 使用QTimer延迟创建完成界面，确保前一个界面被完全清除
        QTimer.singleShot(50, lambda: self._create_completed_ui_delayed(task_data))
        
        # 发送下载完成信号
        self.downloadCompleted.emit(task_data)
        
    def _create_completed_ui_delayed(self, task_data):
        """延迟创建完成界面，确保UI刷新"""
        # 更新UI - 显示下载完成界面
        self._create_completed_ui(task_data)
        
        # 清理断点续传文件
        try:
            file_name = task_data.get("file_name", "")
            save_path = task_data.get("save_path", "")
            if file_name and save_path:
                from pathlib import Path
                file_path = Path(save_path) / file_name
                resume_file = file_path.with_suffix(file_path.suffix + '.resume')
                if resume_file.exists():
                    resume_file.unlink()
                    logging.info(f"完成界面创建后已删除断点续传文件: {resume_file}")
        except Exception as e:
            logging.warning(f"完成界面创建后删除断点续传文件失败: {e}")
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _on_download_error(self, error_msg):
        """下载错误回调
        
        参数:
            error_msg (str): 错误信息
        """
        logging.error(f"下载失败: {error_msg}")
        
        # 停止定时器
        self.progress_timer.stop()
        
        # 更新状态
        if hasattr(self, 'status_label'):
            self.status_label.setText("下载失败")
            self.status_label.setStyleSheet("color: #E53935; font-size: 12px;")
        
        # 更新按钮状态
        if hasattr(self, 'download_button'):
            self.download_button.setEnabled(False)
    
    def _on_filename_changed(self, new_filename):
        """文件名变更回调
        
        参数:
            new_filename (str): 新文件名
        """
        # 更新UI
        if hasattr(self, 'filename_label'):
            self.filename_label.setText(new_filename)
        
        # 获取文件扩展名，如果没有扩展名则显示"No"
        file_ext_raw = os.path.splitext(new_filename)[1]
        file_ext = file_ext_raw.lstrip('.') if file_ext_raw else "No"
        
        # 更新扩展名标签
        if hasattr(self, 'ext_label'):
            self.ext_label.setText(file_ext)
            
            # 更新扩展名标签的背景颜色
            if hasattr(self, 'file_icon_getter'):
                ext_bg_color = self.file_icon_getter.get_file_color(new_filename)
                self.ext_label.setStyleSheet(f"""
                    background-color: {ext_bg_color};
                    color: white;
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 12px;
                    font-weight: bold;
                """)
            
        # 尝试更新文件图标
        if hasattr(self, 'file_icon_getter') and hasattr(self, 'download_engine') and self.download_engine:
            try:
                # 优先使用扩展名安全获取图标
                icon = self.file_icon_getter.get_icon_by_ext_safe(file_ext)
                
                # 查找文件图标QLabel
                file_icon = None
                for child in self.findChildren(QLabel):
                    if child.objectName() == "file_icon":
                        file_icon = child
                        break
                
                # 如果找不到指定命名的控件，尝试在前缀内容区域查找符合尺寸的控件
                if file_icon is None:
                    content_frame = self.findChild(QFrame, "file_info_frame")
                    if content_frame:
                        for child in content_frame.findChildren(QLabel):
                            if child.size().width() == 36 and child.size().height() == 36:
                                file_icon = child
                                break
                
                # 如果找到了图标控件，更新图标
                if file_icon and icon and not icon.isNull():
                    pixmap = icon.pixmap(32, 32)
                    file_icon.setPixmap(pixmap)
                    file_icon.setScaledContents(True)
            except Exception as e:
                logging.debug(f"更新文件图标失败: {e}")
    
    def _update_download_info(self):
        """更新下载信息"""
        if self.current_state != "downloading":
            return
            
        # 修复：添加安全检查，确保progress_bar对象存在
        if not hasattr(self, 'progress_bar') or self.progress_bar is None:
            self.progress_timer.stop()
            logging.debug("进度条对象不存在，停止进度更新定时器")
            return
            
        with self.thread_lock:
            if not hasattr(self, 'download_engine') or not self.download_engine or not hasattr(self.download_engine, 'is_running'):
                return
                
            try:
                # 文件大小未知但已完成下载的情况
                file_size_unknown = hasattr(self.download_engine, 'file_size') and self.download_engine.file_size <= 0
                
                # 如果文件大小未知，尝试从实际文件获取
                if file_size_unknown:
                    try:
                        file_path = Path(self.download_engine.save_path) / self.download_engine.file_name
                        if file_path.exists():
                            actual_size = file_path.stat().st_size
                            # 检查文件是否已下载完毕（无活动块且文件大小已稳定）
                            all_inactive = True
                            for block in self.download_engine.blocks:
                                if hasattr(block, 'active') and block.active:
                                    all_inactive = False
                                    break
                                    
                            if all_inactive and actual_size > 0:
                                # 更新下载引擎中的文件大小
                                self.download_engine.file_size = actual_size
                                logging.info(f"从实际文件更新大小: {actual_size} 字节")
                    except Exception as e:
                        logging.debug(f"获取实际文件大小失败: {e}")
                
                # 获取当前进度和大小信息
                current_progress = 0
                current_downloaded = 0
                current_total_size = 0
                
                if hasattr(self.download_engine, 'current_progress'):
                    current_downloaded = self.download_engine.current_progress
                    
                if hasattr(self.download_engine, 'file_size') and self.download_engine.file_size > 0:
                    current_total_size = self.download_engine.file_size
                    current_progress = min(100, (current_downloaded / current_total_size) * 100)
                
                # 防止进度回退，使用平滑更新策略
                if current_progress > 0 and current_progress < self.last_progress and self.last_progress < 99.5:
                    # 如果进度回退但不是因为完成后重置，则保持上次进度
                    current_progress = self.last_progress
                elif current_progress > 0:
                    # 正常情况下，缓慢更新进度，避免跳动
                    if self.last_progress > 0 and abs(current_progress - self.last_progress) < 10:
                        # 小幅度变化时平滑过渡
                        current_progress = self.last_progress * 0.7 + current_progress * 0.3
                    
                    # 更新缓存的进度
                    self.last_progress = current_progress
                
                # 更新进度条 - 再次检查进度条对象是否存在
                if current_progress > 0:
                    if hasattr(self, 'progress_bar') and self.progress_bar is not None:
                        try:
                            self.progress_bar.setValue(int(current_progress))
                        except Exception as e:
                            logging.error(f"设置进度条值失败: {e}")
                            # 如果设置进度条失败，停止定时器
                            self.progress_timer.stop()
                            return
                            
                        # 更新状态文本 - 避免频繁更新
                        if hasattr(self, 'status_label') and self.status_label is not None:
                            new_status_text = f"{current_progress:.1f}%"
                            if new_status_text != self.last_status_text:
                                self.status_label.setText(new_status_text)
                                self.last_status_text = new_status_text
                        else:
                            # 进度条对象不存在，停止更新
                            logging.debug("进度条对象不存在，停止进度更新")
                            self.progress_timer.stop()
                            return
                    else:
                        # 进度条对象不存在，停止更新
                        logging.debug("进度条对象不存在，停止进度更新")
                        self.progress_timer.stop()
                        return
                else:
                    # 文件大小未知，显示下载中状态
                    if hasattr(self, 'status_label') and self.status_label is not None and self.last_status_text != "下载中...":
                        self.status_label.setText("下载中...")
                        self.last_status_text = "下载中..."
                    
                    # 对于未知大小的文件，显示已下载量
                    if current_downloaded > 0 and hasattr(self, 'size_label') and self.size_label is not None:
                        downloaded_str = self._get_readable_size(current_downloaded)
                        new_size_text = f"已下载: {downloaded_str}"
                        if new_size_text != self.last_size_text:
                            self.size_label.setText(new_size_text)
                            self.last_size_text = new_size_text
                
                # 更新速度 - 使用统一格式"速度: {speed_str}"
                if hasattr(self.download_engine, 'avg_speed') and hasattr(self, 'speed_label') and self.speed_label is not None:
                    speed = self.download_engine.avg_speed
                    speed_str = self._get_readable_speed(speed)
                    self.speed_label.setText(f"速度: {speed_str}")
                    
                    # 更新剩余时间 - 根据下载速度计算
                    if speed > 0 and hasattr(self.download_engine, 'file_size') and hasattr(self.download_engine, 'current_progress') and hasattr(self, 'time_label') and self.time_label is not None:
                        if self.download_engine.file_size > 0:
                            remaining_bytes = self.download_engine.file_size - self.download_engine.current_progress
                            if remaining_bytes > 0:
                                remaining_time = remaining_bytes / speed
                                time_str = self._get_readable_time(remaining_time)
                                self.time_label.setText(time_str)
                            else:
                                self.time_label.setText("即将完成")
                        else:
                            self.time_label.setText("计算中...")
                
                # 更新文件大小信息 - 避免频繁更新
                if current_total_size > 0 and current_downloaded > 0 and hasattr(self, 'size_label') and self.size_label is not None:
                    # 防止大小信息频繁变化
                    if (abs(current_downloaded - self.last_downloaded_size) > current_downloaded * 0.01 or 
                        abs(current_total_size - self.last_total_size) > current_total_size * 0.01):
                        # 只有当变化超过1%时才更新显示
                        total_size_str = self._get_readable_size(current_total_size)
                        downloaded_size_str = self._get_readable_size(current_downloaded)
                        new_size_text = f"大小: {downloaded_size_str} / {total_size_str}"
                        
                        if new_size_text != self.last_size_text:
                            self.size_label.setText(new_size_text)
                            self.last_size_text = new_size_text
                            
                        # 更新缓存的大小
                        self.last_downloaded_size = current_downloaded
                        self.last_total_size = current_total_size
                
                # 处理下载块信息 - 从blocks属性获取信息
                if hasattr(self.download_engine, 'blocks') and self.download_engine.blocks:
                    # 创建块信息列表
                    blocks_info = []
                    all_blocks_completed = True
                    any_block_active = False
                    
                    for i, block in enumerate(self.download_engine.blocks):
                        if isinstance(block, object) and hasattr(block, 'start_position'):
                            # 计算块统计数据
                            start_pos = block.start_position
                            current_pos = block.current_position
                            end_pos = block.end_position
                            downloaded = current_pos - start_pos
                            total_size = end_pos - start_pos + 1
                            status = getattr(block, 'status', "下载中")
                            
                            # 检查块是否活跃
                            if hasattr(block, 'active') and block.active:
                                any_block_active = True
                                
                            # 检查是否所有块都已完成
                            if current_pos < end_pos:
                                all_blocks_completed = False
                            
                            # 使用缓存的状态，避免状态频繁变化
                            block_key = f"block_{i}"
                            if block_key in self.last_segment_statuses:
                                # 如果状态是"下载中"且之前是"下载中"，保持"下载中"
                                if status == "下载中" and self.last_segment_statuses[block_key] == "下载中":
                                    status = "下载中"
                                # 如果状态变成了"已完成"，则更新
                                elif status == "已完成" or current_pos >= end_pos:
                                    status = "已完成"
                                    self.last_segment_statuses[block_key] = status
                                # 其他情况保持之前的状态，避免闪烁
                                else:
                                    status = self.last_segment_statuses[block_key]
                            else:
                                # 首次设置状态
                                self.last_segment_statuses[block_key] = status
                            
                            # 创建块信息字典
                            block_info = {
                                "index": i,
                                "status": status,
                                "downloaded": downloaded,
                                "size": total_size,
                                "start_pos": start_pos,
                                "progress": current_pos,
                                "end_pos": end_pos,
                                "speed": getattr(block, 'download_speed', 0),
                                "active": getattr(block, 'active', False)
                            }
                            blocks_info.append(block_info)
                    
                    # 检查是否下载已完成（所有块已完成且无活动块）
                    if all_blocks_completed and not any_block_active and not self.download_engine.is_paused:
                        # 触发下载完成信号
                        logging.info("检测到所有块已完成且无活动块，触发下载完成")
                        self.progress_timer.stop()
                        
                        # 设置为100%显示 - 添加安全检查
                        if hasattr(self, 'progress_bar') and self.progress_bar is not None:
                            self.progress_bar.setValue(100)
                        if hasattr(self, 'status_label') and self.status_label is not None:
                            self.status_label.setText("100%")
                        
                        # 可能的文件大小更新
                        if file_size_unknown:
                            try:
                                file_path = Path(self.download_engine.save_path) / self.download_engine.file_name
                                if file_path.exists() and hasattr(self, 'size_label') and self.size_label is not None:
                                    self.download_engine.file_size = file_path.stat().st_size
                                    total_size_str = self._get_readable_size(self.download_engine.file_size)
                                    downloaded_size_str = self._get_readable_size(self.download_engine.current_progress)
                                    self.size_label.setText(f"大小: {downloaded_size_str} / {total_size_str}")
                            except Exception:
                                pass
                        
                        # 调用下载完成方法
                        QTimer.singleShot(100, self._on_download_completed)
                    
                    # 如果是初始化阶段，创建分段信息UI
                    if hasattr(self, 'segment_rows') and not self.segment_rows and blocks_info:
                        try:
                            self._update_segments_info(blocks_info)
                        except Exception as e:
                            logging.error(f"更新分段信息失败: {e}")
                    # 否则更新现有分段信息
                    elif hasattr(self, 'segment_rows') and self.segment_rows and blocks_info:
                        for i, block_info in enumerate(blocks_info):
                            if i < len(self.segment_rows):
                                try:
                                    self._update_segment_row(
                                        i, 
                                        status=block_info.get("status"),
                                        start_pos=block_info.get("start_pos"),
                                        progress=block_info.get("progress"),
                                        end_pos=block_info.get("end_pos")
                                    )
                                except Exception as e:
                                    logging.debug(f"更新分段行 {i} 失败: {e}")
                
                # 如果下载已完成或已暂停，停止定时器
                if hasattr(self.download_engine, 'is_running') and (not self.download_engine.is_running or self.download_engine.is_paused):
                    self.progress_timer.stop()
                
            except Exception as e:
                logging.error(f"更新下载信息失败: {e}")
                import traceback
                logging.debug(traceback.format_exc())
                # 发生错误时停止定时器
                self.progress_timer.stop()
    
    def _on_cancel_download(self):
        """取消下载按钮点击处理"""
        # 设置取消标志
        self.cancelled = True
        
        # 检查下载引擎和AS内核是否存在
        has_download_engine = hasattr(self, 'download_engine') and self.download_engine is not None
        has_as_kernel = hasattr(self, 'as_kernel') and self.as_kernel is not None
        
        if not (has_download_engine or has_as_kernel):
            logging.warning("无法取消下载：下载引擎和AS内核均不存在")
            
            # 尝试关闭窗口
            try:
                self.close()
            except Exception as close_error:
                logging.error(f"关闭窗口失败: {close_error}")
            return
        
        # 获取当前任务ID
        task_id = getattr(self, 'task_id', "未知任务")
        
        try:
            # 首先停止进度更新定时器
            if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
                try:
                    self.progress_timer.stop()
                except Exception as timer_error:
                    logging.error(f"停止定时器出错: {timer_error}")
            
            # 发送取消信号
            if hasattr(self, 'downloadCancelled'):
                try:
                    self.downloadCancelled.emit(task_id)
                except Exception as signal_error:
                    logging.error(f"发送取消信号失败: {signal_error}")
            
            # 停止下载
            try:
                logging.info(f"停止下载任务: {task_id}")
                
                # 先处理AS内核（如果有）
                if has_as_kernel:
                    # 使用AS内核停止 - 需要处理异步调用
                    import asyncio
                    
                    # 创建一个用于处理异步调用的函数
                    async def async_stop():
                        try:
                            return await self.as_kernel.stop_download()
                        except Exception as e:
                            logging.error(f"异步停止下载出错: {e}")
                            return False
                    
                    # 在新的事件循环中运行异步函数
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        success = loop.run_until_complete(async_stop())
                        if not success:
                            logging.error("使用AS内核停止下载失败")
                            if has_download_engine:
                                # 回退到直接使用下载引擎
                                self.download_engine.stop()
                                
                                # === 修复：增加线程等待逻辑 ===
                                if hasattr(self.download_engine, 'wait') and callable(self.download_engine.wait):
                                    # 等待线程停止，最多等待3秒
                                    if not self.download_engine.wait(3000):
                                        logging.warning("下载引擎线程停止超时(3秒)，尝试额外方法停止线程")
                                        
                                        # 尝试使用quit优雅退出线程
                                        if hasattr(self.download_engine, 'quit') and callable(self.download_engine.quit):
                                            try:
                                                self.download_engine.quit()
                                                # 再等待2秒
                                                if not self.download_engine.wait(2000):
                                                    logging.warning("下载引擎线程quit后等待超时(2秒)，尝试强制终止")
                                                    
                                                    # 如果还在运行，尝试terminate强制终止（最后手段）
                                                    if hasattr(self.download_engine, 'terminate') and callable(self.download_engine.terminate):
                                                        try:
                                                            self.download_engine.terminate()
                                                            # 等待终止完成
                                                            self.download_engine.wait(1000)
                                                        except Exception as term_error:
                                                            logging.error(f"强制终止下载引擎线程出错: {term_error}")
                                            except Exception as quit_error:
                                                logging.error(f"退出下载引擎线程出错: {quit_error}")
                    finally:
                        loop.close()
                        
                        # === 修复：处理NSF内核特殊情况 ===
                        if has_as_kernel and hasattr(self.as_kernel, 'current_kernel_type') and self.as_kernel.current_kernel_type == "NSF":
                            if hasattr(self.as_kernel, 'nsf_kernel') and self.as_kernel.nsf_kernel:
                                # 再次确认NSF内核已停止
                                try:
                                    if hasattr(self.as_kernel.nsf_kernel, 'isRunning') and callable(self.as_kernel.nsf_kernel.isRunning):
                                        if self.as_kernel.nsf_kernel.isRunning():
                                            logging.warning("NSF内核仍在运行，尝试额外方法停止")
                                            
                                            # 尝试停止和等待
                                            if hasattr(self.as_kernel.nsf_kernel, 'stop') and callable(self.as_kernel.nsf_kernel.stop):
                                                self.as_kernel.nsf_kernel.stop()
                                                
                                                # 等待线程停止
                                                if hasattr(self.as_kernel.nsf_kernel, 'wait') and callable(self.as_kernel.nsf_kernel.wait):
                                                    # 等待3秒
                                                    if not self.as_kernel.nsf_kernel.wait(3000):
                                                        logging.warning("NSF内核线程额外停止尝试超时")
                                                        
                                                        # 尝试terminate作为最后手段
                                                        if hasattr(self.as_kernel.nsf_kernel, 'terminate') and callable(self.as_kernel.nsf_kernel.terminate):
                                                            try:
                                                                self.as_kernel.nsf_kernel.terminate()
                                                                self.as_kernel.nsf_kernel.wait(1000)
                                                            except Exception as term_error:
                                                                logging.error(f"终止NSF内核线程出错: {term_error}")
                                except Exception as nsf_error:
                                    logging.error(f"额外处理NSF内核停止时出错: {nsf_error}")
                elif has_download_engine:
                    # 直接使用下载引擎
                    self.download_engine.stop()
                    
                    # === 修复：增加等待逻辑 ===
                    if hasattr(self.download_engine, 'wait') and callable(self.download_engine.wait):
                        # 等待线程停止，最多等待3秒
                        if not self.download_engine.wait(3000):
                            logging.warning("下载引擎线程停止超时(3秒)，尝试额外方法停止线程")
                            
                            # 尝试使用quit优雅退出线程
                            if hasattr(self.download_engine, 'quit') and callable(self.download_engine.quit):
                                try:
                                    self.download_engine.quit()
                                    # 再等待2秒
                                    if not self.download_engine.wait(2000):
                                        logging.warning("下载引擎线程quit后等待超时(2秒)，尝试强制终止")
                                        
                                        # 如果还在运行，尝试terminate强制终止（最后手段）
                                        if hasattr(self.download_engine, 'terminate') and callable(self.download_engine.terminate):
                                            try:
                                                self.download_engine.terminate()
                                                # 等待终止完成
                                                self.download_engine.wait(1000)
                                            except Exception as term_error:
                                                logging.error(f"强制终止下载引擎线程出错: {term_error}")
                                except Exception as quit_error:
                                    logging.error(f"退出下载引擎线程出错: {quit_error}")
                
            except Exception as stop_error:
                logging.error(f"停止下载引擎出错: {stop_error}")
            
            # 清理下载引擎和相关资源
            try:
                # 解除信号连接
                if has_download_engine:
                    # 断开所有信号连接
                    try:
                        if (hasattr(self.download_engine, 'initialized') and 
                            hasattr(self.download_engine.initialized, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.initialized, 'receivers') and self.download_engine.initialized.receivers() > 0:
                                self.download_engine.initialized.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'block_progress_updated') and 
                            hasattr(self.download_engine.block_progress_updated, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.block_progress_updated, 'receivers') and self.download_engine.block_progress_updated.receivers() > 0:
                                self.download_engine.block_progress_updated.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'speed_updated') and 
                            hasattr(self.download_engine.speed_updated, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.speed_updated, 'receivers') and self.download_engine.speed_updated.receivers() > 0:
                                self.download_engine.speed_updated.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'download_completed') and 
                            hasattr(self.download_engine.download_completed, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.download_completed, 'receivers') and self.download_engine.download_completed.receivers() > 0:
                                self.download_engine.download_completed.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'error_occurred') and 
                            hasattr(self.download_engine.error_occurred, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.error_occurred, 'receivers') and self.download_engine.error_occurred.receivers() > 0:
                                self.download_engine.error_occurred.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'file_name_changed') and 
                            hasattr(self.download_engine.file_name_changed, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.file_name_changed, 'receivers') and self.download_engine.file_name_changed.receivers() > 0:
                                self.download_engine.file_name_changed.disconnect()
                    except Exception as signal_error:
                        logging.error(f"断开下载引擎信号时出错: {signal_error}")
                
                    # 清空引用
                    self.download_engine = None
                    self.as_kernel = None
                    
                    # 尝试手动触发垃圾回收
                    import gc
                    gc.collect()
                    
                    # === 修复：再次强制GC ===
                    # 短暂延时后再次执行垃圾回收
                    import time
                    time.sleep(0.1)  # 给100毫秒让系统处理资源
                    gc.collect()
            except Exception as cleanup_error:
                logging.error(f"清理下载资源出错: {cleanup_error}")
            
            # 通知用户已取消
            try:
                # 更新状态
                if hasattr(self, 'status_label'):
                    self.status_label.setText("已取消")
            except Exception as status_error:
                logging.error(f"更新状态出错: {status_error}")
            
            # 关闭窗口
            try:
                # 给UI一点时间更新
                import time
                time.sleep(0.1)
                
                def complete_destruction():
                    try:
                        # === 修复：执行最终垃圾回收 ===
                        import gc
                        gc.collect()
                        
                        self.deleteLater()
                    except:
                        pass
                
                # 在主线程中执行延迟销毁
                from PySide6.QtCore import QTimer
                # === 修复：增加延迟时间，给线程更多时间结束 ===
                QTimer.singleShot(500, complete_destruction)
                
                # 关闭窗口
                self.close()
                
            except Exception as close_error:
                logging.error(f"关闭窗口失败: {close_error}")
            
        except Exception as e:
            logging.error(f"取消下载过程中出错: {e}")
            import traceback
            logging.error(traceback.format_exc())
    def _toggle_segments_display(self):
        """切换分段信息显示状态"""
        self.show_segments = not self.show_segments
        self.segments_frame.setVisible(self.show_segments)
        
        # 更新按钮图标 - 根据折叠状态设置不同图标
        if hasattr(self, 'font_manager') and hasattr(self, 'toggle_segments_button'):
            if self.show_segments:
                # 展开状态 - 显示向上箭头表示可以折叠
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_up_24_regular", size=16)
            else:
                # 折叠状态 - 显示向下箭头表示可以展开
                self.font_manager.apply_icon_font(self.toggle_segments_button, "ic_fluent_chevron_down_24_regular", size=16)
        else:
            # 文本备用方案
            self.toggle_segments_button.setText("分段信息 ▽" if self.show_segments else "分段信息 ▷")
        
        # 调整窗口大小
        if self.isVisible():
            self._auto_resize()
    
    def _auto_resize(self):
        """自动调整窗口大小以适应内容
        
        根据当前内容自动计算并调整窗口大小，确保所有内容都能完整显示
        同时限制最大尺寸，避免窗口过大
        使用动画效果使调整过程更加平滑
        """
        # 先计算窗口内容的理想大小
        content_size = self.sizeHint()
        
        # 获取屏幕大小
        screen_size = QApplication.primaryScreen().availableSize()
        
        # 限制最大宽高为屏幕的75%
        max_width = int(screen_size.width() * 0.75)
        max_height = int(screen_size.height() * 0.75)
        
        # 确保窗口大小在合理范围内
        # 增加最小宽度，让界面左右更宽一些
        new_width = min(max(content_size.width(), 550), max_width)  # 最小宽度550，原来是450
        new_height = min(max(content_size.height(), 300), max_height)  # 最小高度300
        
        # 添加额外宽度，确保文本和控件显示更和谐
        new_width += 50  # 额外增加50像素宽度
        
        # 使用动画平滑调整窗口大小
        apply_resize_animation(self, new_width, new_height)
        
        # 强制布局更新
        self.layout().update()
        
        # 处理窗口位置以确保它在屏幕上可见
        self._ensure_visible_on_screen()
        
    def _ensure_visible_on_screen(self):
        """确保窗口在屏幕上完全可见，使用动画效果平滑移动窗口"""
        # 获取当前窗口几何信息
        window_geometry = self.frameGeometry()
        
        # 获取当前屏幕
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # 当前位置
        current_x = self.x()
        current_y = self.y()
        
        # 新位置（默认为当前位置）
        new_x = current_x
        new_y = current_y
        
        # 检查窗口是否超出屏幕边界，并计算新位置
        if window_geometry.right() > screen_geometry.right():
            # 右边超出屏幕，向左移动
            new_x = screen_geometry.right() - window_geometry.width()
            
        if window_geometry.bottom() > screen_geometry.bottom():
            # 底部超出屏幕，向上移动
            new_y = screen_geometry.bottom() - window_geometry.height()
            
        if window_geometry.left() < screen_geometry.left():
            # 左边超出屏幕，向右移动
            new_x = screen_geometry.left()
            
        if window_geometry.top() < screen_geometry.top():
            # 顶部超出屏幕，向下移动
            new_y = screen_geometry.top()
        
        # 如果位置有变化，使用动画移动窗口
        if new_x != current_x or new_y != current_y:
            # 创建位置动画
            pos_animation = QPropertyAnimation(self, b"pos")
            pos_animation.setDuration(200)  # 200毫秒
            pos_animation.setStartValue(self.pos())
            pos_animation.setEndValue(QPoint(new_x, new_y))
            pos_animation.setEasingCurve(QEasingCurve.OutCubic)
            pos_animation.start(QPropertyAnimation.DeleteWhenStopped)  # 动画结束后自动删除
            
    def _update_segment_row(self, index, status=None, downloaded=None, total=None, start_pos=None, progress=None, end_pos=None):
        """更新分段下载信息行
        
        参数:
            index (int): 行索引
            status (str): 状态文本
            downloaded (int): 已下载字节数
            total (int): 总字节数
            start_pos (int): 起始位置
            progress (int): 当前进度位置
            end_pos (int): 结束位置
        """
        # 检查索引是否有效
        if not hasattr(self, 'segment_rows') or index < 0 or index >= len(self.segment_rows):
            return
            
        row = self.segment_rows[index]
        
        # 更新状态 - 只在状态真正改变时更新UI
        if status is not None and 'status' in row:
            # 检查状态是否真正改变，避免不必要的UI更新
            current_status = row['status'].text()
            if current_status != status:
                # 标准化状态文本，确保统一的状态文本格式
                # 根据状态设置颜色
                status_color = "#B39DDB"  # 默认紫色
                
                # 使用精确匹配而非模糊匹配
                if status == "已完成" or status == "完成":
                    status_color = "#4CAF50"  # 完成 - 绿色
                    status = "已完成"  # 标准化状态文本
                elif status == "下载失败" or status == "失败" or status == "错误":
                    status_color = "#F44336"  # 错误 - 红色
                    status = "下载失败"  # 标准化状态文本
                elif status == "已暂停" or status == "暂停":
                    status_color = "#FF9800"  # 暂停 - 橙色
                    status = "已暂停"  # 标准化状态文本
                elif status == "等待中" or status == "等待":
                    status_color = "#FFC107"  # 等待 - 黄色
                    status = "等待中"  # 标准化状态文本
                elif status == "下载中":
                    status_color = "#2196F3"  # 活跃 - 蓝色
                elif status == "连接中":
                    status_color = "#2196F3"  # 活跃 - 蓝色
                
                # 设置文本和颜色
                row['status'].setText(status)
                row['status'].setStyleSheet(f"color: {status_color}; font-size: 13px;")
        
        # 更新已下载大小 - 优先使用直接提供的downloaded参数
        if downloaded is not None and 'downloaded' in row:
            downloaded_str = self._get_readable_size(downloaded)
            row['downloaded'].setText(downloaded_str)
        # 如果提供了start_pos和progress，计算downloaded
        elif start_pos is not None and progress is not None and 'downloaded' in row:
            downloaded = progress - start_pos if progress > start_pos else 0
            downloaded_str = self._get_readable_size(downloaded)
            row['downloaded'].setText(downloaded_str)
        
        # 更新总大小 - 优先使用直接提供的total参数
        if total is not None and 'total' in row:
            total_str = self._get_readable_size(total)
            row['total'].setText(total_str)
        # 如果提供了start_pos和end_pos，计算total
        elif start_pos is not None and end_pos is not None and 'total' in row:
            total_size = end_pos - start_pos + 1 if end_pos >= start_pos else 0
            total_str = self._get_readable_size(total_size)
            row['total'].setText(total_str)
    
    def _update_segments_info(self, blocks_info):
        """更新分段下载信息
        
        参数:
            blocks_info (list): 下载块信息列表
        """
        import time
        
        if not hasattr(self, 'segments_scroll_layout'):
            return
            
        # 状态转换平滑处理
        if not hasattr(self, '_segment_status_history'):
            self._segment_status_history = {}  # 存储每个段的状态历史
            self._status_transition_count = {}  # 存储状态转换计数
            self._status_last_change_time = {}  # 存储状态最后变化时间
            
        # 确保所有需要的属性都已初始化
        if not hasattr(self, '_status_last_change_time'):
            self._status_last_change_time = {}
            
        if not hasattr(self, '_last_resize_time'):
            self._last_resize_time = 0
        
        # 如果没有块信息，清空现有段并显示提示
        if not blocks_info:
            # 清空现有段信息
            for i in reversed(range(self.segments_scroll_layout.count())):
                widget = self.segments_scroll_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            
            # 清空段行引用
            self.segment_rows = []
            
            # 显示提示
            empty_label = QLabel("没有分段信息")
            empty_label.setStyleSheet("color: #B0B0B0; font-size: 13px; background-color: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            if hasattr(self, 'font_manager'):
                self.font_manager.apply_font(empty_label)
            self.segments_scroll_layout.addWidget(empty_label)
            return
        
        # 检查是否需要重建UI
        need_rebuild = len(blocks_info) != len(self.segment_rows) if hasattr(self, 'segment_rows') else True
        
        # 如果需要重建整个UI
        if need_rebuild:
            # 清空现有段信息
            for i in reversed(range(self.segments_scroll_layout.count())):
                widget = self.segments_scroll_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            
            # 清空段行引用
            self.segment_rows = []
            
            # 添加每个段的信息
            for i, block in enumerate(blocks_info):
                segment_frame = QFrame()
                segment_frame.setStyleSheet("background-color: #323232; border-radius: 5px;")  # 减小圆角
                segment_layout = QHBoxLayout(segment_frame)
                segment_layout.setContentsMargins(8, 6, 8, 6)  # 减小内边距
                segment_layout.setSpacing(10)  # 减少间距
                
                # 序号
                index_label = QLabel(f"{i+1}")
                index_label.setFixedWidth(25)  # 减少宽度
                index_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
                if hasattr(self, 'font_manager'):
                    self.font_manager.apply_font(index_label)
                segment_layout.addWidget(index_label)
                
                # 状态 - 获取状态
                block_id = f"{block.get('start_pos', 0)}:{block.get('end_pos', 0)}"
                raw_status = block.get("status", "未知")
                
                # 应用状态平滑处理
                status_text = self._get_stable_status(block_id, raw_status)
                
                # 根据状态设置颜色
                status_color = self._get_status_color(status_text)
                
                status_label = QLabel(status_text)
                status_label.setFixedWidth(90)  # 减少宽度
                status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")  # 减小字体
                if hasattr(self, 'font_manager'):
                    self.font_manager.apply_font(status_label)
                segment_layout.addWidget(status_label)
                
                # 已下载 - 从processed_blocks计算
                downloaded = block.get("downloaded", 0)
                if downloaded == 0:
                    # 尝试从进度和起始位置计算
                    start_pos = block.get("start_pos", 0)
                    progress = block.get("progress", start_pos)
                    downloaded = progress - start_pos if progress > start_pos else 0
                
                downloaded_str = self._get_readable_size(downloaded)
                downloaded_label = QLabel(downloaded_str)
                downloaded_label.setFixedWidth(90)  # 减少宽度
                downloaded_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
                if hasattr(self, 'font_manager'):
                    self.font_manager.apply_font(downloaded_label)
                segment_layout.addWidget(downloaded_label)
                
                # 总大小 - 从processed_blocks计算
                total_size = block.get("size", 0)
                if total_size == 0:
                    # 尝试从起始位置和结束位置计算
                    start_pos = block.get("start_pos", 0) 
                    end_pos = block.get("end_pos", 0)
                    total_size = end_pos - start_pos + 1 if end_pos >= start_pos else 0
                
                total_str = self._get_readable_size(total_size)
                total_label = QLabel(total_str)
                total_label.setFixedWidth(90)  # 减少宽度
                total_label.setStyleSheet("color: #E0E0E0; font-size: 12px;")  # 减小字体
                if hasattr(self, 'font_manager'):
                    self.font_manager.apply_font(total_label)
                segment_layout.addWidget(total_label)
                
                self.segments_scroll_layout.addWidget(segment_frame)
                
                # 保存行引用，用于更新
                self.segment_rows.append({
                    "frame": segment_frame,
                    "status": status_label,
                    "downloaded": downloaded_label,
                    "total": total_label,
                    "block_id": block_id
                })
        else:
            # 仅更新现有行的内容
            for i, (block, row) in enumerate(zip(blocks_info, self.segment_rows)):
                if i >= len(self.segment_rows):
                    break
                    
                # 获取块ID
                block_id = f"{block.get('start_pos', 0)}:{block.get('end_pos', 0)}"
                if "block_id" in row:
                    row["block_id"] = block_id
                
                # 更新状态
                raw_status = block.get("status", "未知")
                status_text = self._get_stable_status(block_id, raw_status)
                status_color = self._get_status_color(status_text)
                
                if 'status' in row:
                    row['status'].setText(status_text)
                    row['status'].setStyleSheet(f"color: {status_color}; font-size: 12px;")
                
                # 更新已下载
                downloaded = block.get("downloaded", 0)
                if downloaded == 0:
                    start_pos = block.get("start_pos", 0)
                    progress = block.get("progress", start_pos)
                    downloaded = progress - start_pos if progress > start_pos else 0
                
                if 'downloaded' in row:
                    row['downloaded'].setText(self._get_readable_size(downloaded))
                
                # 更新总大小
                total_size = block.get("size", 0)
                if total_size == 0:
                    start_pos = block.get("start_pos", 0) 
                    end_pos = block.get("end_pos", 0)
                    total_size = end_pos - start_pos + 1 if end_pos >= start_pos else 0
                
                if 'total' in row:
                    row['total'].setText(self._get_readable_size(total_size))
        
        # 更新后延迟自动调整窗口大小，避免频繁调整
        if self.isVisible() and self.current_state == "downloading":
            # 限制窗口大小调整频率
            if not hasattr(self, '_last_resize_time'):
                self._last_resize_time = 0
            
            current_time = time.time()
            if (current_time - self._last_resize_time) > 1.0:  # 至少1秒钟才调整一次
                QTimer.singleShot(100, lambda: self._auto_resize())
                self._last_resize_time = current_time
    
    def _get_stable_status(self, block_id, current_status):
        """获取稳定的状态显示（防止状态频繁切换）
        
        参数:
            block_id (str): 块ID
            current_status (str): 当前状态
            
        返回:
            str: 稳定处理后的状态
        """
        import time
        
        # 初始化状态历史和转换计数器
        if not hasattr(self, '_segment_status_history'):
            self._segment_status_history = {}
            self._status_transition_count = {}
            self._status_last_change_time = {}
        
        # 确保_status_last_change_time已初始化
        if not hasattr(self, '_status_last_change_time'):
            self._status_last_change_time = {}
            
        # 获取历史状态
        if block_id not in self._segment_status_history:
            self._segment_status_history[block_id] = current_status
            self._status_transition_count[block_id] = 0
            self._status_last_change_time[block_id] = time.time()
            return current_status
            
        previous_status = self._segment_status_history[block_id]
        
        # 如果状态没变，直接返回并重置计数器
        if current_status == previous_status:
            self._status_transition_count[block_id] = 0
            return current_status
        
        # 如果状态是从"连接中"变为"下载中"，立即接受变化
        if previous_status == "连接中" and current_status == "下载中":
            self._segment_status_history[block_id] = current_status
            self._status_transition_count[block_id] = 0
            self._status_last_change_time[block_id] = time.time()
            return current_status
            
        # 如果状态是从"下载中"变为"连接中"，需要稳定性检查
        if previous_status == "下载中" and current_status == "连接中":
            # 增加过渡计数
            if block_id not in self._status_transition_count:
                self._status_transition_count[block_id] = 0
            self._status_transition_count[block_id] += 1
            
            # 只有连续5次都是"连接中"才真正切换状态
            if self._status_transition_count[block_id] >= 5:
                self._segment_status_history[block_id] = current_status
                self._status_transition_count[block_id] = 0
                self._status_last_change_time[block_id] = time.time()
                return current_status
            else:
                # 否则保持原状态
                return previous_status
                
        # 获取上次状态变化的时间
        last_change = self._status_last_change_time.get(block_id, 0)
        current_time = time.time()
        
        # 如果距离上次变化不到0.5秒，且不是变为"已完成"状态，则保持原状态
        if (current_time - last_change) < 0.5 and current_status != "已完成":
            if block_id not in self._status_transition_count:
                self._status_transition_count[block_id] = 0
            self._status_transition_count[block_id] += 1
            return previous_status
            
        # 其他状态变化，更新历史并接受
        self._segment_status_history[block_id] = current_status
        self._status_transition_count[block_id] = 0
        self._status_last_change_time[block_id] = current_time
        return current_status
    
    def _get_status_color(self, status):
        """根据状态获取对应的颜色
        
        参数:
            status (str): 状态文本
            
        返回:
            str: 颜色代码
        """
        if status == "已完成" or status == "完成":
            return "#4CAF50"  # 完成 - 绿色
        elif status == "下载失败" or status == "失败" or status == "错误":
            return "#F44336"  # 错误 - 红色
        elif status == "已暂停" or status == "暂停":
            return "#FF9800"  # 暂停 - 橙色
        elif status == "等待中" or status == "等待":
            return "#FFC107"  # 等待 - 黄色
        elif status == "下载中":
            return "#2196F3"  # 活跃 - 蓝色
        elif status == "连接中":
            return "#2196F3"  # 活跃 - 蓝色
        else:
            return "#B39DDB"  # 默认紫色
    
    def _clear_content(self):
        """清空内容区域"""
        # 停止所有可能运行的定时器
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
        if hasattr(self, 'auto_close_timer') and self.auto_close_timer.isActive():
            self.auto_close_timer.stop()
            
        # 清理内容布局
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                
        # 清理按钮布局
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                
        # 确保内存中的引用也被清除
        if hasattr(self, 'filename_label'):
            self.filename_label = None
        if hasattr(self, 'size_label'):
            self.size_label = None
        if hasattr(self, 'status_label'):
            self.status_label = None
        if hasattr(self, 'speed_label'):
            self.speed_label = None
        if hasattr(self, 'time_label'):
            self.time_label = None
        if hasattr(self, 'progress_bar'):
            self.progress_bar = None
        if hasattr(self, 'segments_frame'):
            self.segments_frame = None
        if hasattr(self, 'segment_rows'):
            self.segment_rows = []
        if hasattr(self, 'segments_scroll_area'):
            self.segments_scroll_area = None
        if hasattr(self, 'toggle_segments_button'):
            self.toggle_segments_button = None
        if hasattr(self, 'url_input'):
            self.url_input = None
        if hasattr(self, 'filename_input'):
            self.filename_input = None
        if hasattr(self, 'save_path_input'):
            self.save_path_input = None
        if hasattr(self, 'multi_thread_checkbox'):
            self.multi_thread_checkbox = None
        if hasattr(self, 'cancel_button'):
            self.cancel_button = None
        if hasattr(self, 'download_button'):
            self.download_button = None
            
        # 强制清理
        self.content_widget.update()
        self.button_widget.update()
        
        # 强制重新处理事件和重绘
        QApplication.processEvents()
            
        # 重置UI状态
        self.update()
    
    def _clear_layout(self, layout):
        """清空布局中的所有部件"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)  # 断开父子关系
                widget.deleteLater()    # 安排删除
            elif item.layout():
                self._clear_layout(item.layout())
                layout.removeItem(item) # 从布局中移除子布局
    
    def _on_browse(self):
        """浏览保存位置"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path_input.text())
        if folder_path:
            self.save_path_input.setText(folder_path)
            
    def _on_download(self):
        """开始下载按钮点击处理"""
        # 在下载按钮被点击时，先获取并保存所有需要的数据
        try:
            # 构建任务数据
            task_data = {}
            
            # 如果有待处理的任务数据，优先使用它
            if self.pending_task_data and isinstance(self.pending_task_data, dict):
                task_data = dict(self.pending_task_data)  # 创建副本避免修改原始数据
                
                # 更新用户可能修改的字段，使用安全方式访问UI控件
                try:
                    if hasattr(self, 'url_input') and self.url_input and not self._is_destroyed(self.url_input):
                        task_data["url"] = self.url_input.text().strip()
                except (RuntimeError, AttributeError, Exception) as e:
                    # 控件可能已被删除，保留原值
                    logging.debug(f"访问url_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'filename_input') and self.filename_input and not self._is_destroyed(self.filename_input):
                        task_data["file_name"] = self.filename_input.text().strip()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问filename_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'save_path_input') and self.save_path_input and not self._is_destroyed(self.save_path_input):
                        task_data["save_path"] = self.save_path_input.text()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问save_path_input时出错: {e}")
                    
                try:
                    if hasattr(self, 'multi_thread_checkbox') and self.multi_thread_checkbox and not self._is_destroyed(self.multi_thread_checkbox):
                        task_data["multi_thread"] = self.multi_thread_checkbox.isChecked()
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.debug(f"访问multi_thread_checkbox时出错: {e}")
            else:
                # 如果没有待处理数据，从UI控件获取数据
                try:
                    url = ""
                    if hasattr(self, 'url_input') and self.url_input and not self._is_destroyed(self.url_input):
                        url = self.url_input.text().strip()
                    if not url:
                        logging.warning("下载失败: URL为空")
                        return
                        
                    # 获取文件名
                    filename = ""
                    if hasattr(self, 'filename_input') and self.filename_input and not self._is_destroyed(self.filename_input):
                        filename = self.filename_input.text().strip()
                    
                    # 如果没有输入文件名，尝试从URL中提取
                    if not filename:
                        filename = self._extract_filename_from_url(url)
                    
                    # 保存路径
                    save_path = ""
                    if hasattr(self, 'save_path_input') and self.save_path_input and not self._is_destroyed(self.save_path_input):
                        save_path = self.save_path_input.text()
                    
                    # 多线程选项
                    multi_thread = True
                    if hasattr(self, 'multi_thread_checkbox') and self.multi_thread_checkbox and not self._is_destroyed(self.multi_thread_checkbox):
                        multi_thread = self.multi_thread_checkbox.isChecked()
                    
                    # 创建下载任务数据
                    task_data = {
                        "url": url,
                        "file_name": filename,
                        "save_path": save_path,
                        "multi_thread": multi_thread,
                        "source": "browser_extension",
                        "request_id": f"popup_{int(time.time() * 1000)}"
                    }
                except (RuntimeError, AttributeError, Exception) as e:
                    logging.error(f"从UI获取下载信息时出错: {e}")
                    return
            
            # 验证URL
            url = task_data.get("url", "")
            if not url:
                logging.error("下载失败: URL为空")
                return
                
            # 添加保存以供发送
            task_data_copy = dict(task_data)
                
            # 先保存副本，防止信号触发后窗口关闭导致访问已删除对象
            try:
                # 发送下载请求信号
                if hasattr(self, 'downloadRequested'):
                    self.downloadRequested.emit(task_data_copy)
                    
                # 不立即关闭窗口，我们应该在这里切换到下载中界面
                # 先彻底清除当前UI
                self._clear_content()
                
                # 用延时确保前一界面完全清除
                QTimer.singleShot(100, lambda: self._switch_to_downloading_ui(task_data_copy))
                
                # 使用延时器而不是直接调用close()，防止线程在UI更新前被销毁
                # 确保在主线程中保持足够长的时间
                QApplication.processEvents()
                
            except Exception as e:
                logging.error(f"发送下载请求时出错: {e}")
        except Exception as e:
            logging.error(f"处理下载请求时出错: {e}")
    
    def _switch_to_downloading_ui(self, task_data):
        """切换到下载中界面并开始下载"""
        try:
            # 检查对话框是否仍然有效
            if not self.isVisible() or not self.isActiveWindow():
                logging.warning("窗口已不可见或非活跃，取消UI切换")
                return
                
            # 继续显示下载界面并开始下载
            self._create_downloading_ui(task_data)
            
            # 强制更新UI以确保界面已完全更新
            self.repaint()
            QApplication.processEvents()
            
            # 在UI更新后开始下载
            QTimer.singleShot(50, lambda: self._start_download_delayed(task_data))
            
        except Exception as e:
            logging.error(f"切换到下载中界面失败: {e}")
            
    def _start_download_delayed(self, task_data):
        """延迟启动下载，确保UI已经更新"""
        try:
            # 检查对话框是否仍然有效
            if not self.isVisible():
                logging.warning("窗口已不可见，取消下载启动")
                return
                
            # 开始下载
            self._start_download(task_data)
            
            # 强制更新UI
            self.repaint()
            QApplication.processEvents()
            
        except Exception as e:
            logging.error(f"延迟启动下载失败: {e}")
    
    def _on_pause_resume(self):
        """暂停/继续按钮点击处理"""
        # 检查下载引擎和AS内核是否存在
        has_download_engine = hasattr(self, 'download_engine') and self.download_engine is not None
        has_as_kernel = hasattr(self, 'as_kernel') and self.as_kernel is not None
        
        if not (has_download_engine or has_as_kernel):
            logging.error("无法暂停/继续下载：下载引擎和AS内核均不存在")
            return
        
        try:
            if self.is_paused:
                # 恢复下载
                self.download_button.setText("  暂停")
                # 更新按钮图标为暂停图标（两条竖线）
                if hasattr(self, 'font_manager'):
                    icon = QIcon()
                    self.font_manager.apply_icon_to_icon(icon, "ic_fluent_pause_24_regular")
                    self.download_button.setIcon(icon)
                    self.download_button.setIconSize(QSize(16, 16))
                
                self.download_button.setStyleSheet("""
                    QPushButton {
                        background-color: #8A7CEC;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 8px;
                        padding: 4px 12px;
                        font-size: 14px;
                        font-weight: bold;
                        text-align: center;
                    }
                    QPushButton:hover {
                        background-color: #9E8FEF;
                    }
                    QPushButton:pressed {
                        background-color: #7A6CD8;
                    }
                """)
                # 断开之前的连接再重新连接，避免多次连接
                try:
                    self.download_button.clicked.disconnect()
                except:
                    pass
                self.download_button.clicked.connect(self._on_pause_resume)
                self.is_paused = False
                
                # 恢复下载
                logging.info("恢复下载任务")
                if has_as_kernel:
                    # 使用AS内核恢复 - 直接调用同步方法
                    success = self.as_kernel.resume_download()
                    if not success:
                        logging.error("使用AS内核恢复下载失败")
                        if has_download_engine:
                            # 回退到直接使用下载引擎
                            self.download_engine.resume()
                elif has_download_engine:
                    # 直接使用下载引擎
                    self.download_engine.resume()
                
                # 更新状态提示
                self.status_label.setText("下载中...")
            else:
                # 暂停下载
                self.download_button.setText("  继续")
                # 更新按钮图标为播放图标（三角形）
                if hasattr(self, 'font_manager'):
                    icon = QIcon()
                    self.font_manager.apply_icon_to_icon(icon, "ic_fluent_play_24_regular")
                    self.download_button.setIcon(icon)
                    self.download_button.setIconSize(QSize(16, 16))
                
                self.download_button.setStyleSheet("""
                    QPushButton {
                        background-color: #8A7CEC;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 8px;
                        padding: 4px 12px;
                        font-size: 14px;
                        font-weight: bold;
                        text-align: center;
                    }
                    QPushButton:hover {
                        background-color: #9E8FEF;
                    }
                    QPushButton:pressed {
                        background-color: #7A6CD8;
                    }
                """)
                # 断开之前的连接再重新连接，避免多次连接
                try:
                    self.download_button.clicked.disconnect()
                except:
                    pass
                self.download_button.clicked.connect(self._on_pause_resume)
                self.is_paused = True
                
                # 暂停下载
                logging.info("暂停下载任务")
                if has_as_kernel:
                    # 使用AS内核暂停 - 直接调用同步方法
                    success = self.as_kernel.pause_download()
                    if not success:
                        logging.error("使用AS内核暂停下载失败")
                        if has_download_engine:
                            # 回退到直接使用下载引擎
                            self.download_engine.pause()
                elif has_download_engine:
                    # 直接使用下载引擎
                    self.download_engine.pause()
                
                # 更新状态提示
                self.status_label.setText("已暂停")
                
        except Exception as e:
            logging.error(f"暂停/恢复下载时出错: {e}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _on_url_changed(self, url):
        """URL输入变化处理"""
        if not url:
            return
            
        # 尝试从URL提取文件名
        if not self.filename_input.text():
            filename = self._extract_filename_from_url(url)
            if filename:
                self.filename_input.setText(filename)
                
    def update_progress(self, progress_percent, speed_bytes=0, time_left="计算中..."):
        """更新下载进度"""
        # 检查当前状态
        if self.current_state != "downloading":
            return
            
        try:
            # 修复：添加安全检查，确保progress_bar对象存在
            if hasattr(self, 'progress_bar') and self.progress_bar is not None:
                self.progress_bar.setValue(int(progress_percent))
            else:
                return
            
            # 更新状态文本
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"{progress_percent:.1f}%")
            
            # 更新速度
            if speed_bytes > 0 and hasattr(self, 'speed_label') and self.speed_label is not None:
                speed_str = self._get_readable_speed(speed_bytes)
                self.speed_label.setText(f"速度: {speed_str}")
            
            # 更新剩余时间
            if hasattr(self, 'time_label') and self.time_label is not None:
                self.time_label.setText(f"剩余时间: {time_left}")
        except Exception as e:
            logging.error(f"更新进度失败: {e}")
            
    def _create_completed_ui(self, task_data):
        """创建下载完成UI
        
        参数:
            task_data (dict): 任务数据
        """
        # 确保先前的UI完全清除
        self._clear_content()
        
        # 停止进度更新定时器
        if hasattr(self, 'progress_timer') and self.progress_timer.isActive():
            self.progress_timer.stop()
            
        # 设置标题
        self.title_label.setText("下载完成")
        
        # 获取文件信息
        filename = task_data.get("file_name", "未知文件")
        save_path = task_data.get("save_path", "")
        file_path = os.path.join(save_path, filename) if save_path and filename else ""
        file_ext_raw = os.path.splitext(filename)[1]
        file_ext = file_ext_raw.lstrip('.') if file_ext_raw else "No"
        
        # 获取文件大小
        file_size = task_data.get("file_size", 0)
        if file_size <= 0:
            # 如果文件大小仍未知，尝试再次从文件获取
            try:
                if save_path and filename:
                    file_path_obj = Path(save_path) / filename
                    if file_path_obj.exists():
                        file_size = file_path_obj.stat().st_size
                        logging.info(f"完成UI - 从实际文件获取大小: {file_size} 字节")
            except Exception as e:
                logging.error(f"完成UI - 获取实际文件大小失败: {e}")
        
        size_str = self._get_readable_size(file_size) if file_size > 0 else "未知大小"
        
        # 获取下载耗时
        download_duration = task_data.get("download_duration", 0)
        duration_str = self._get_readable_time(download_duration) if download_duration > 0 else "未知时间"
        
        # 设置窗口最小大小
        self.setMinimumSize(722, 337)
        
        # 主题颜色 - 微软Fluent设计风格
        accent_color = "#B088FF"  # 微软蓝
        text_color = "#323130"    # 深灰色文本
        secondary_text = "#605E5C" # 次要文本颜色
        background_color = "#F5F5F5" # 背景色
        
        # 设置窗口背景色
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {background_color};
                border-radius: 8px;
            }}
        """)
        
        # 创建主容器
        main_container = QWidget()
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(24, 10, 24, 24)
        main_layout.setSpacing(20)
        
        # ===== 顶部文件信息区域 =====
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(18)
        
        # 文件名和图标区域
        file_header = QHBoxLayout()
        file_header.setSpacing(12)
        
        # 文件图标
        file_icon_label = QLabel()
        file_icon_label.setFixedSize(48, 48)
        if hasattr(self, 'font_manager'):
            # 导入FileFluentIcon类
            from client.ui.client_interface.utils.file_fluent_icon import FileFluentIcon
            
            # 创建FileFluentIcon实例
            file_icon_getter = FileFluentIcon()
            
            # 获取文件图标
            icon = file_icon_getter.get_large_icon_for_file(file_ext=file_ext)
            
            # 设置图标
            pixmap = icon.pixmap(48, 48)
            file_icon_label.setPixmap(pixmap)
        file_header.addWidget(file_icon_label)
        
        # 文件名和大小
        file_info = QVBoxLayout()
        file_info.setSpacing(4)
        
        file_name_label = QLabel(filename)
        file_name_label.setStyleSheet(f"color: {text_color}; font-size: 16px; font-weight: bold;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(file_name_label)
        file_info.addWidget(file_name_label)
        
        file_size_label = QLabel(size_str)
        file_size_label.setStyleSheet(f"color: {secondary_text}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(file_size_label)
        file_info.addWidget(file_size_label)
        
        file_header.addLayout(file_info, 1)
        
        # FK标记
        fk_container = QWidget()
        fk_container.setFixedWidth(40)
        fk_layout = QVBoxLayout(fk_container)
        fk_layout.setContentsMargins(0, 0, 0, 0)
        fk_layout.setSpacing(0)
        # 不知道写什么
        f_label = QLabel("")
        f_label.setStyleSheet(f"color: {accent_color}; font-size: 20px; font-weight: bold;")
        f_label.setAlignment(Qt.AlignRight)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(f_label)
        fk_layout.addWidget(f_label)
        # 预留空位
        k_label = QLabel("")
        k_label.setStyleSheet(f"color: {accent_color}; font-size: 20px; font-weight: bold;")
        k_label.setAlignment(Qt.AlignRight)
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(k_label)
        fk_layout.addWidget(k_label)
        
        file_header.addWidget(fk_container)
        
        info_layout.addLayout(file_header)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #E1E1E1; border: none; height: 1px;")
        info_layout.addWidget(separator)
        
        # 详细信息网格
        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(30)
        details_grid.setVerticalSpacing(12)
        
        # 下载耗时
        time_icon = QLabel()
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_clock_16_regular")
            pixmap = icon.pixmap(16, 16)
            time_icon.setPixmap(pixmap)
        details_grid.addWidget(time_icon, 0, 0)
        
        time_label = QLabel("下载耗时:")
        time_label.setStyleSheet(f"color: {secondary_text}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(time_label)
        details_grid.addWidget(time_label, 0, 1)
        
        time_value = QLabel(duration_str)
        time_value.setStyleSheet(f"color: {text_color}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(time_value)
        details_grid.addWidget(time_value, 0, 2)
        
        # 保存位置
        location_icon = QLabel()
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_folder_16_regular")
            pixmap = icon.pixmap(16, 16)
            location_icon.setPixmap(pixmap)
        details_grid.addWidget(location_icon, 1, 0)
        
        location_label = QLabel("保存位置:")
        location_label.setStyleSheet(f"color: {secondary_text}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(location_label)
        details_grid.addWidget(location_label, 1, 1)
        
        location_value = QLabel(save_path)
        location_value.setStyleSheet(f"color: {text_color}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(location_value)
        details_grid.addWidget(location_value, 1, 2)
        
        # 文件类型
        type_icon = QLabel()
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_document_16_regular")
            pixmap = icon.pixmap(16, 16)
            type_icon.setPixmap(pixmap)
        details_grid.addWidget(type_icon, 2, 0)
        
        type_label = QLabel("文件类型:")
        type_label.setStyleSheet(f"color: {secondary_text}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(type_label)
        details_grid.addWidget(type_label, 2, 1)
        
        file_type = f"Windows 可执行文件 (.{file_ext.lower()})" if file_ext.lower() == 'exe' else f"{file_ext.upper()} 文件"
        type_value = QLabel(file_type)
        type_value.setStyleSheet(f"color: {text_color}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(type_value)
        details_grid.addWidget(type_value, 2, 2)
        
        # 设置列宽度
        details_grid.setColumnStretch(0, 0)  # 图标列
        details_grid.setColumnStretch(1, 1)  # 标签列
        details_grid.setColumnStretch(2, 3)  # 值列
        
        info_layout.addLayout(details_grid)
        
        main_layout.addWidget(info_container)
        
        # ===== 内核信息 =====
        kernel_container = QWidget()
        kernel_layout = QHBoxLayout(kernel_container)
        kernel_layout.setContentsMargins(0, 0, 0, 0)
        
        kernel_icon = QLabel()
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_rocket_16_regular")
            pixmap = icon.pixmap(16, 16)
            kernel_icon.setPixmap(pixmap)
        kernel_layout.addWidget(kernel_icon)
        
        kernel_fullname = task_data.get("kernel_fullname", "Hanabi Nextgen Speed Force Kernel")
        kernel_label = QLabel(kernel_fullname)
        kernel_label.setStyleSheet(f"color: {accent_color}; font-size: 13px;")
        if hasattr(self, 'font_manager'):
            self.font_manager.apply_font(kernel_label)
        kernel_layout.addWidget(kernel_label)
        
        kernel_layout.addStretch(1)
        
        main_layout.addWidget(kernel_container)
        
        # 添加弹性空间
        main_layout.addStretch(1)
        
        # ===== 底部按钮区域 =====
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(12)
        
        # 按钮样式
        primary_button_style = f"""
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #F0BBFF;
            }}
            QPushButton:pressed {{
                background-color: #FFB3FF;
            }}
        """
        
        secondary_button_style = f"""
            QPushButton {{
                background-color: #CCBBFF;
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #D1BBFF;
            }}
            QPushButton:pressed {{
                background-color: #D1BBFF;
            }}
        """
        
        # 打开文件按钮 (主要按钮)
        open_file_button = QPushButton("打开文件")
        open_file_button.setStyleSheet(primary_button_style)
        open_file_button.setFixedHeight(36)
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_document_24_regular",color="#000000")
            open_file_button.setIcon(icon)
            open_file_button.setIconSize(QSize(16, 16))
            self.font_manager.apply_font(open_file_button)
        open_file_button.clicked.connect(lambda: self._on_open_file_and_close(file_path))
        buttons_layout.addWidget(open_file_button)
        
        # 打开文件夹按钮 (次要按钮)
        open_folder_button = QPushButton("打开文件夹")
        open_folder_button.setStyleSheet(secondary_button_style)
        open_folder_button.setFixedHeight(36)
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_folder_open_24_regular",color="#000000")
            open_folder_button.setIcon(icon)
            open_folder_button.setIconSize(QSize(16, 16))
            self.font_manager.apply_font(open_folder_button)
        open_folder_button.clicked.connect(lambda: self._on_open_folder_and_close(save_path))
        buttons_layout.addWidget(open_folder_button)
        
        # 关闭按钮 (次要按钮)
        close_button = QPushButton("关闭")
        close_button.setStyleSheet(secondary_button_style)
        close_button.setFixedHeight(36)
        if hasattr(self, 'font_manager'):
            icon = QIcon()
            self.font_manager.apply_icon_to_icon(icon, "ic_fluent_dismiss_24_regular",color="#000000")
            close_button.setIcon(icon)
            close_button.setIconSize(QSize(16, 16))
            self.font_manager.apply_font(close_button)
        close_button.clicked.connect(self.close)
        buttons_layout.addWidget(close_button)
        
        main_layout.addWidget(buttons_container)
        
        # 添加到主布局
        self.content_layout.addWidget(main_container)
        
        # 调整窗口大小
        QTimer.singleShot(0, lambda: self._auto_resize())
        
        # 强制更新UI
        self.repaint()
        QApplication.processEvents()
    
    def _on_open_folder(self, folder_path):
        """打开文件夹
        
        参数:
            folder_path (str): 文件夹路径
        """
        if not folder_path:
            return
            
        # 获取文件名，用于选中文件
        file_name = ""
        if hasattr(self, 'download_engine') and self.download_engine:
            if hasattr(self.download_engine, 'file_name'):
                file_name = self.download_engine.file_name
                
        # 发送信号
        self.folderOpened.emit(folder_path)
        
        # 尝试使用系统默认方式打开文件夹
        try:
            import subprocess
            import os
            import platform
            
            if platform.system() == "Windows":
                if file_name:
                    # 使用/select参数打开文件夹并选中文件
                    full_path = os.path.join(folder_path, file_name)
                    subprocess.run(['explorer', '/select,', full_path])
                else:
                    # 仅打开文件夹
                    os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                if file_name:
                    # 在macOS上选中文件
                    full_path = os.path.join(folder_path, file_name)
                    subprocess.call(["open", "-R", full_path])
                else:
                    subprocess.call(["open", folder_path])
            else:  # Linux
                if file_name:
                    # 尝试在Linux上选中文件（不同文件管理器命令不同）
                    try:
                        full_path = os.path.join(folder_path, file_name)
                        # 尝试使用nautilus（GNOME）
                        subprocess.call(["nautilus", "--select", full_path])
                    except:
                        # 如果失败，只打开文件夹
                        subprocess.call(["xdg-open", folder_path])
                else:
                    subprocess.call(["xdg-open", folder_path])
                
        except Exception as e:
            logging.error(f"打开文件夹失败: {e}")
    
    # 已移除自动关闭选项改变处理方法
    
    def __del__(self):
        """析构函数，确保资源释放"""
        try:
            # 首先标记取消状态
            try:
                self.cancelled = True
            except:
                pass
                
            # 停止所有定时器 - 使用更安全的方式检查
            try:
                if hasattr(self, 'auto_close_timer') and self.auto_close_timer is not None:
                    # 使用hasattr检查是否存在stop方法，确保对象没有被销毁
                    if hasattr(self.auto_close_timer, 'stop') and callable(self.auto_close_timer.stop):
                        self.auto_close_timer.stop()
            except (RuntimeError, ReferenceError, TypeError) as e:
                # 忽略QTimer已被删除的错误
                pass
                
            try:
                if hasattr(self, 'progress_timer') and self.progress_timer is not None:
                    # 使用hasattr检查是否存在stop方法，确保对象没有被销毁
                    if hasattr(self.progress_timer, 'stop') and callable(self.progress_timer.stop):
                        self.progress_timer.stop()
            except (RuntimeError, ReferenceError, TypeError) as e:
                # 忽略QTimer已被删除的错误
                pass
                
            # 安全处理AS内核
            if hasattr(self, 'as_kernel') and self.as_kernel is not None:
                try:
                    # 如果是NSF内核，先确保线程停止
                    if hasattr(self.as_kernel, 'current_kernel_type') and self.as_kernel.current_kernel_type == "NSF":
                        if hasattr(self.as_kernel, 'nsf_kernel') and self.as_kernel.nsf_kernel is not None:
                            # 安全调用stop方法
                            if hasattr(self.as_kernel.nsf_kernel, 'stop') and callable(self.as_kernel.nsf_kernel.stop):
                                try:
                                    self.as_kernel.nsf_kernel.stop()
                                except:
                                    pass
                
                    # 清除引用
                    self.as_kernel = None
                except:
                    pass
                
            # 安全停止下载引擎
            if hasattr(self, 'download_engine') and self.download_engine is not None:
                try:
                    # 断开下载引擎的信号 - 使用更安全的方式检查
                    try:
                        if (hasattr(self.download_engine, 'initialized') and 
                            hasattr(self.download_engine.initialized, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.initialized, 'receivers') and self.download_engine.initialized.receivers() > 0:
                                self.download_engine.initialized.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'block_progress_updated') and 
                            hasattr(self.download_engine.block_progress_updated, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.block_progress_updated, 'receivers') and self.download_engine.block_progress_updated.receivers() > 0:
                                self.download_engine.block_progress_updated.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'speed_updated') and 
                            hasattr(self.download_engine.speed_updated, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.speed_updated, 'receivers') and self.download_engine.speed_updated.receivers() > 0:
                                self.download_engine.speed_updated.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'download_completed') and 
                            hasattr(self.download_engine.download_completed, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.download_completed, 'receivers') and self.download_engine.download_completed.receivers() > 0:
                                self.download_engine.download_completed.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'error_occurred') and 
                            hasattr(self.download_engine.error_occurred, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.error_occurred, 'receivers') and self.download_engine.error_occurred.receivers() > 0:
                                self.download_engine.error_occurred.disconnect()
                    except:
                        pass
                        
                    try:
                        if (hasattr(self.download_engine, 'file_name_changed') and 
                            hasattr(self.download_engine.file_name_changed, 'disconnect')):
                            # 检查信号是否有接收者
                            if hasattr(self.download_engine.file_name_changed, 'receivers') and self.download_engine.file_name_changed.receivers() > 0:
                                self.download_engine.file_name_changed.disconnect()
                    except Exception as signal_error:
                        logging.error(f"断开下载引擎信号时出错: {signal_error}")
                    
                    # 检查stop方法是否存在
                    if hasattr(self.download_engine, 'stop') and callable(self.download_engine.stop):
                        try:
                            # 安全调用stop，确保不会引发异常
                            self.download_engine.stop()
                        except:
                            pass
                    
                    # 检查线程是否仍在运行
                    if (hasattr(self.download_engine, 'isRunning') and 
                        callable(self.download_engine.isRunning)):
                        try:
                            if self.download_engine.isRunning():
                                # 尝试使用更安全的quit方法而不是terminate
                                if hasattr(self.download_engine, 'quit') and callable(self.download_engine.quit):
                                    try:
                                        self.download_engine.quit()
                                        # 等待极短时间
                                        if hasattr(self.download_engine, 'wait') and callable(self.download_engine.wait):
                                            self.download_engine.wait(100)  # 最多等待100毫秒
                                    except:
                                        pass
                        except:
                            pass
                    
                    # 清除引用，帮助垃圾回收
                    self.download_engine = None
                except Exception as e:
                    # 忽略析构中的错误
                    pass
                
            # 处理NCT下载线程
            if hasattr(self, 'nct_download_thread') and self.nct_download_thread is not None:
                try:
                    # 只需清除引用
                    self.nct_download_thread = None
                except:
                    pass
                
            # 强制垃圾回收
            try:
                import gc
                gc.collect()
            except:
                pass
        except Exception as e:
            # 完全忽略析构中的任何错误
            pass
    
    def showEvent(self, event):
        """窗口显示事件处理"""
        super().showEvent(event)
        
        # 确保窗口显示时总是在最上层，但不要频繁调用raise和activate
        # 这些方法可能导致窗口抽搐
        self.raise_()
        
        # 只在首次显示时激活窗口，避免反复激活导致的抽搐
        if not hasattr(self, '_first_show_done'):
            self.activateWindow()
            self._first_show_done = True
        
        # 如果设置了延迟移除置顶标志，则启动定时器
        # 延长时间到10秒，减少状态变化频率
        if hasattr(self, 'remove_top_hint') and self.remove_top_hint:
            # 10秒后移除置顶标志，让窗口可以被其他窗口覆盖
            QTimer.singleShot(10000, self._remove_always_on_top)
    
    def _ensure_window_active(self):
        """确保窗口处于活跃状态"""
        if not self._is_destroyed(self):
            try:
                # 只提升窗口层级，不要频繁激活窗口
                self.raise_()
                
                # 避免使用会导致窗口状态频繁变化的方法
                # 不再使用setWindowState方法，它可能导致窗口抽搐
            except Exception as e:
                logging.error(f"确保窗口活跃时出错: {str(e)}")
    
    def _remove_always_on_top(self):
        """移除窗口的置顶标志，允许被其他窗口覆盖"""
        if not self._is_destroyed(self) and hasattr(self, 'remove_top_hint') and self.remove_top_hint:
            try:
                # 获取当前窗口标志
                flags = self.windowFlags()
                
                # 移除置顶标志
                if flags & Qt.WindowStaysOnTopHint:
                    # 保存当前位置和大小
                    current_geometry = self.geometry()
                    
                    # 移除置顶标志
                    self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
                    
                    # 重新显示窗口（设置窗口标志后窗口会隐藏）
                    # 恢复到原来的位置和大小
                    self.setGeometry(current_geometry)
                    self.show()
                    
                    # 标记已移除置顶标志
                    self.remove_top_hint = False
            except Exception as e:
                logging.error(f"移除窗口置顶标志时出错: {str(e)}")
    
    def focusOutEvent(self, event):
        """窗口失去焦点事件处理"""
        super().focusOutEvent(event)
        
        # 失去焦点时不要做任何可能导致窗口状态变化的操作
        # 移除任何可能导致窗口重新获取焦点的代码
    
    def _on_open_file_and_close(self, file_path):
        """打开文件并关闭窗口
        
        参数:
            file_path (str): 文件路径
        """
        if not file_path:
            return
            
        # 发送打开文件信号
        if hasattr(self, 'fileOpened'):
            self.fileOpened.emit(file_path)
        
        # 尝试使用系统默认方式打开文件
        try:
            import subprocess
            import os
            import platform
            
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", file_path])
            else:  # Linux
                subprocess.call(["xdg-open", file_path])
                
            # 等待100毫秒后关闭窗口，给系统一些时间启动程序
            QTimer.singleShot(100, self.close)
                
        except Exception as e:
            logging.error(f"打开文件失败: {e}")
            
            # 即使打开失败也关闭窗口
            QTimer.singleShot(500, self.close)
    
    def _on_open_folder_and_close(self, folder_path):
        """打开文件夹并关闭窗口
        
        参数:
            folder_path (str): 文件夹路径
        """
        if not folder_path:
            return
            
        # 发送信号
        if hasattr(self, 'folderOpened'):
            self.folderOpened.emit(folder_path)
        
        # 获取文件名，用于选中文件
        file_name = ""
        if hasattr(self, 'download_engine') and self.download_engine:
            if hasattr(self.download_engine, 'file_name'):
                file_name = self.download_engine.file_name
                
        # 尝试使用系统默认方式打开文件夹
        try:
            import subprocess
            import os
            import platform
            
            if platform.system() == "Windows":
                if file_name:
                    # 使用/select参数打开文件夹并选中文件
                    full_path = os.path.join(folder_path, file_name)
                    subprocess.run(['explorer', '/select,', full_path])
                else:
                    # 仅打开文件夹
                    os.startfile(folder_path)
            elif platform.system() == "Darwin":  # macOS
                if file_name:
                    # 在macOS上选中文件
                    full_path = os.path.join(folder_path, file_name)
                    subprocess.call(["open", "-R", full_path])
                else:
                    subprocess.call(["open", folder_path])
            else:  # Linux
                if file_name:
                    # 尝试在Linux上选中文件（不同文件管理器命令不同）
                    try:
                        full_path = os.path.join(folder_path, file_name)
                        # 尝试使用nautilus（GNOME）
                        subprocess.call(["nautilus", "--select", full_path])
                    except:
                        # 如果失败，只打开文件夹
                        subprocess.call(["xdg-open", folder_path])
                else:
                    subprocess.call(["xdg-open", folder_path])
            
            # 等待100毫秒后关闭窗口，给系统一些时间启动程序
            QTimer.singleShot(100, self.close)
                
        except Exception as e:
            logging.error(f"打开文件夹失败: {e}")
            
            # 即使打开失败也关闭窗口
            QTimer.singleShot(500, self.close)