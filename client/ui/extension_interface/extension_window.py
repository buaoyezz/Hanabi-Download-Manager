from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QSizePolicy, QFrame, QMessageBox, QFileDialog, QSpacerItem)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPoint, Property
from PySide6.QtGui import QFont, QIcon, QColor, QPainter, QPainterPath, QBrush, QCursor

import os
import logging
import datetime
import time
import re
import threading
import webbrowser
from urllib.parse import unquote, urlparse
from pathlib import Path

from core.font.font_manager import FontManager
from client.ui.components.progressBar import ProgressBar
from connect.fallback_connector import FallbackConnector
from client.ui.extension_interface.pop_dialog import DownloadPopDialog

class RoundedFrame(QFrame):
    """圆角边框容器"""
    def __init__(self, parent=None, radius=10, bg_color="#252526"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.setStyleSheet("background:transparent;")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect, self.radius, self.radius)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)
        
    # 添加属性访问器，用于QPropertyAnimation
    def get_background_color(self):
        return QColor(self.bg_color)
        
    def set_background_color(self, color):
        if isinstance(color, QColor):
            self.bg_color = color.name()
        else:
            self.bg_color = color
        self.update()
        
    # 属性定义
    background_color = Property(QColor, get_background_color, set_background_color)

class ExtensionWindow(QWidget):
    """浏览器扩展下载窗口，接收和处理来自浏览器扩展的下载请求"""
    
    # 定义信号
    extensionDownloadReceived = Signal(dict)  # 收到浏览器扩展下载请求
    downloadStarted = Signal(dict)  # 下载开始
    downloadCompleted = Signal(dict)  # 下载完成
    connectionStatusChanged = Signal(bool, str)  # 连接状态变化(连接状态, 服务器类型)
    
    def __init__(self, parent=None, font_manager=None, config_manager=None):
        super().__init__(parent)
        self.setWindowTitle("浏览器扩展")
        
        # 初始化
        self.font_manager = font_manager if font_manager else FontManager()
        self.config_manager = config_manager
        self.save_path = os.path.expanduser("~/Downloads")
        
        # 当前下载任务列表
        self.extension_tasks = []
        self.thread_lock = threading.Lock()
        
        # 创建UI
        self._setup_ui()
        
        # 初始化连接器
        self._init_connector()
        
        # 启动定时检查
        self._start_health_check_timer()
        
    def _setup_ui(self):
        """设置用户界面"""
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)
        
        # 状态框
        self._create_status_panel()
        
        # 创建插件卡片
        self._create_extension_card()
        
        # 添加伸缩项使内容靠上对齐
        self.main_layout.addStretch(1)
    
    def _create_status_panel(self):
        """创建状态面板，显示连接状态"""
        status_frame = RoundedFrame(radius=8, bg_color="#2C2C2C")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(15, 10, 15, 10)
        
        # 状态图标
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(16, 16)
        self.status_icon.setStyleSheet("background-color: #E53935; border-radius: 8px;")
        status_layout.addWidget(self.status_icon)
        
        # 状态文本
        self.status_text = QLabel("等待连接浏览器扩展...")
        self.status_text.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        self.font_manager.apply_font(self.status_text)
        status_layout.addWidget(self.status_text)
        
        # 服务器类型
        self.server_type_label = QLabel("服务器类型: 未知")
        self.server_type_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.font_manager.apply_font(self.server_type_label)
        status_layout.addWidget(self.server_type_label, 0, Qt.AlignRight)
        
        self.main_layout.addWidget(status_frame)

    def _create_extension_card(self):
        """创建扩展插件卡片"""
        # 扩展插件卡片容器
        extension_frame = RoundedFrame(radius=8, bg_color="#2D2D2D")
        extension_layout = QVBoxLayout(extension_frame)
        extension_layout.setContentsMargins(15, 15, 15, 15)
        extension_layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("浏览器扩展")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(title_label)
        extension_layout.addWidget(title_label)
        
        # 描述
        desc_label = QLabel("使用浏览器扩展可以直接从网页拦截并管理下载。")
        desc_label.setStyleSheet("color: #CCCCCC; font-size: 13px;")
        desc_label.setWordWrap(True)
        self.font_manager.apply_font(desc_label)
        extension_layout.addWidget(desc_label)
        
        # 卡片按钮 - 点击跳转到Edge扩展商店
        extension_button = self._create_clickable_card(
            "安装 Edge 浏览器扩展",
            "点击跳转到 Microsoft Edge 扩展商店安装 Hanabi Download Manager Extension",
            "https://microsoftedge.microsoft.com/addons/detail/hanabi-download-manager-e/nifalaonnaeobogcnhfoeaklpihcaeia"
        )
        extension_layout.addWidget(extension_button)
        
        # 添加源码跳转卡片
        source_code_button = self._create_clickable_card(
            "查看项目源码",
            "点击跳转到 GitHub 查看 Hanabi Download Manager 的开源代码",
            "https://github.com/buaoyezz/Hanabi-Download-Manager"
        )
        extension_layout.addWidget(source_code_button)

        friend_link_button = self._create_clickable_card(
            "XiaoY API",
            "感谢XiaoY提供API和云计算服务",
            "https://apiv2.xiaoy.asia"
        )
        extension_layout.addWidget(friend_link_button)
        
        # 声明卡片
        declaration_frame = RoundedFrame(radius=6, bg_color="#363636")
        declaration_layout = QVBoxLayout(declaration_frame)
        declaration_layout.setContentsMargins(10, 10, 10, 10)
        
        declaration_label = QLabel("> 感谢使用HDM，本扩展 Dev By ZZBUAOYE 由ZZBuAoYe维护和更新")
        declaration_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        declaration_label.setWordWrap(True)
        self.font_manager.apply_font(declaration_label)
        declaration_layout.addWidget(declaration_label)
        
        extension_layout.addWidget(declaration_frame)
        
        # 添加到主布局
        self.main_layout.addWidget(extension_frame)
    
    def _create_clickable_card(self, title, description, url):
        """创建可点击的卡片按钮"""
        card = RoundedFrame(radius=6, bg_color="#363636")
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setMinimumHeight(80)
        
        # 添加点击事件
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton:
                webbrowser.open(url)
        
        # 鼠标悬停效果
        def enterEvent(event):
            card.bg_color = "#404040"
            card.update()
        
        def leaveEvent(event):
            card.bg_color = "#363636"
            card.update()
        
        # 绑定事件处理方法
        card.mousePressEvent = mousePressEvent
        card.enterEvent = enterEvent
        card.leaveEvent = leaveEvent
        
        # 卡片内容布局
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        self.font_manager.apply_font(title_label)
        layout.addWidget(title_label)
        
        # 描述
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        desc_label.setWordWrap(True)
        self.font_manager.apply_font(desc_label)
        layout.addWidget(desc_label)
        
        return card

    def _init_connector(self):
        """初始化浏览器连接器"""
        try:
            logging.info("开始初始化浏览器扩展连接器")
            
            # 创建连接器并设置处理函数
            self.connector = FallbackConnector()
            self.connector.downloadRequestReceived.connect(self._handle_browser_download)
            
            # 启动连接器
            self.connector.start()
            
            # 更新状态
            QTimer.singleShot(1000, self._update_connection_status)
            
            logging.info("浏览器扩展连接器初始化完成")
        except Exception as e:
            logging.error(f"初始化浏览器扩展连接器失败: {e}")
            # 更新连接状态为断开
            self._set_disconnected_status("初始化失败")
    
    def _start_health_check_timer(self):
        """启动健康检查定时器"""
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._check_connector_health)
        self.health_timer.start(10000)  # 每10秒检查一次
    
    def _check_connector_health(self):
        """检查连接器健康状态"""
        if hasattr(self, 'connector') and self.connector:
            is_running = self.connector.is_running()
            if not is_running:
                logging.warning("连接器不在运行中，正在重新初始化")
                self._reinitialize_connector()
            else:
                self._update_connection_status()
        else:
            logging.warning("连接器不存在，正在重新初始化")
            self._reinitialize_connector()
    
    def _update_connection_status(self):
        """更新连接状态"""
        if hasattr(self, 'connector') and self.connector:
            is_running = self.connector.is_running()
            
            if is_running:
                self._set_connected_status()
            else:
                self._set_disconnected_status("连接断开")
        else:
            self._set_disconnected_status("未初始化")
    
    def _set_connected_status(self):
        """设置为已连接状态"""
        self.status_icon.setStyleSheet("background-color: #4CAF50; border-radius: 8px;")
        self.status_text.setText("本地端口已启动")
        
        # 获取服务器类型
        server_type = "WebSocket"
        if hasattr(self, 'connector') and self.connector:
            if hasattr(self.connector, 'server') and self.connector.server:
                if hasattr(self.connector.server, 'server_type'):
                    server_type = self.connector.server.server_type
                elif "WebSocketServer" in str(type(self.connector.server)):
                    server_type = "WebSocket"
                elif "TCPServer" in str(type(self.connector.server)):
                    server_type = "TCP"
        
        self.server_type_label.setText(f"服务器类型: {server_type}")
        
        # 发送状态变化信号
        self.connectionStatusChanged.emit(True, server_type)
    
    def _set_disconnected_status(self, message="连接断开"):
        """设置为断开连接状态"""
        self.status_icon.setStyleSheet("background-color: #E53935; border-radius: 8px;")
        self.status_text.setText(f"浏览器扩展{message}")
        self.server_type_label.setText("服务器类型: 未连接")
        
        # 发送状态变化信号
        self.connectionStatusChanged.emit(False, "未连接")
    
    def _reinitialize_connector(self):
        """重新初始化连接器"""
        try:
            # 先停止现有连接器
            if hasattr(self, 'connector') and self.connector:
                try:
                    self.connector.stop()
                except:
                    pass
            
            # 创建新连接器
            self.connector = FallbackConnector()
            self.connector.downloadRequestReceived.connect(self._handle_browser_download)
            
            # 启动连接器
            self.connector.start()
            
            # 更新状态
            QTimer.singleShot(1000, self._update_connection_status)
            
            logging.info("浏览器扩展连接器已重新初始化")
        except Exception as e:
            logging.error(f"重新初始化浏览器扩展连接器失败: {e}")
            # 更新连接状态为断开
            self._set_disconnected_status("初始化失败")
    
    @Slot(dict)
    def _handle_browser_download(self, download_data):
        """处理浏览器下载请求"""
        try:
            # 记录请求
            request_id = download_data.get("requestId", f"ext_{int(time.time() * 1000)}")
            logging.info(f"[extension_window.py] 收到浏览器扩展下载请求 [ID: {request_id}]: {download_data.get('url', '未知URL')}")
            
            # 处理下载数据
            processed_data = self._process_download_data(download_data)
            
            # 添加到预览区
            self._add_download_preview_item(download_data)
            
            # 为保证弹窗只创建一次，直接在本地处理，不发送信号给主窗口
            # 添加一个标记防止重复处理
            processed_data["download_source"] = "client/ui/extension_interface/extension_window.py:_handle_browser_download"
            processed_data["handled_by_extension"] = True
            
            # 直接调用处理方法
            self.start_download_from_extension(processed_data)
            
            # 返回处理结果
            return True
        except Exception as e:
            logging.error(f"处理浏览器下载请求失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_download_data(self, download_data):
        """处理下载数据，添加必要的信息"""
        # 拷贝数据，避免修改原始对象
        processed_data = dict(download_data)
        
        # 确保有ID
        if "requestId" not in processed_data:
            processed_data["requestId"] = f"ext_{int(time.time() * 1000)}"
        
        # 确保有保存路径
        processed_data["save_path"] = self.save_path
        
        # 确保有标头
        if "headers" not in processed_data:
            # 获取用户设置的UA
            user_agent = self.get_user_agent()
            processed_data["headers"] = {
                "User-Agent": user_agent
            }
        
        # 处理文件名
        if "filename" not in processed_data or not processed_data["filename"]:
            url = processed_data.get("url", "")
            filename = self._extract_filename_from_url(url)
            processed_data["filename"] = filename
        else:
            # 清理文件名
            processed_data["filename"] = self._sanitize_filename(processed_data["filename"])
        
        # 添加开始时间
        processed_data["start_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加来源标记
        processed_data["source"] = "browser_extension"
        
        return processed_data
    
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
    
    def _extract_filename_from_url(self, url):
        """从URL中提取文件名"""
        try:
            if not url:
                return f"download_{int(time.time())}.bin"
                
            # 解析URL
            parsed_url = urlparse(url)
            path = parsed_url.path
            
            # 从路径中提取文件名
            if path:
                filename = os.path.basename(path)
                if filename:
                    # 去除查询参数
                    if '?' in filename:
                        filename = filename.split('?')[0]
                        
                    # URL解码
                    try:
                        decoded_filename = unquote(filename)
                        if decoded_filename != filename:
                            filename = decoded_filename
                    except:
                        pass
                        
                    # 确保文件有扩展名
                    if '.' in filename:
                        return filename
            
            # 如果无法提取有效文件名，创建默认名称
            timestamp = int(time.time())
            return f"download_{timestamp}.bin"
            
        except Exception as e:
            logging.warning(f"从URL提取文件名失败: {e}")
            timestamp = int(time.time())
            return f"download_{timestamp}.bin"
    
    def _sanitize_filename(self, filename):
        """清理文件名，移除不合法字符"""
        try:
            if not filename:
                return "未命名文件"
                
            # 处理URL编码
            try:
                decoded = unquote(filename)
                if decoded != filename:
                    filename = decoded
            except Exception as e:
                logging.warning(f"URL解码文件名失败: {e}")
                
            # 处理Windows非法字符
            if os.name == 'nt':  # Windows
                filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
                
            # 截断过长文件名
            if len(filename) > 200:
                name, ext = os.path.splitext(filename)
                name = name[:195 - len(ext)]
                filename = name + ext
                
            return filename
        except Exception as e:
            logging.error(f"处理文件名失败: {e}")
            return "未命名文件"
    
    def start_download_from_extension(self, download_data):
        """启动从浏览器扩展接收的下载任务"""
        try:
            # 确保数据有效
            if not download_data or "url" not in download_data:
                logging.error("下载数据无效或缺少URL")
                return False
            
            # 记录请求ID并进行日志记录
            request_id = download_data.get("requestId", f"ext_{int(time.time() * 1000)}")
            download_source = download_data.get("download_source", "未知来源")
            logging.info(f"[extension_window.py] 启动浏览器扩展下载任务 [ID: {request_id}] [来源: {download_source}]")
            
            # 只有在特定情况下才创建下载弹窗
            if download_data.get("handled_by_extension", False):
                # 创建下载弹窗时添加来源信息
                download_data["download_source"] = "client/ui/extension_interface/extension_window.py:start_download_from_extension"
                from client.ui.extension_interface.pop_dialog import DownloadPopDialog
                dialog = DownloadPopDialog.create_and_show(download_data, self, auto_start=True)
                logging.info(f"[extension_window.py] 已为下载请求 [ID: {request_id}] 创建弹窗")
            
            # 添加下载预览项
            self._add_download_preview_item(download_data)
            
            # 创建下载管理器 (保留这部分来确保下载进度可以追踪)
            connector = FallbackConnector()
            download_manager = connector.create_download_task(download_data)
            
            # 设置保存路径
            download_manager.save_path = download_data.get("save_path", self.save_path)
            
            # 生成任务ID
            task_id = f"task_{int(time.time() * 1000)}"
            
            # 保存任务信息
            with self.thread_lock:
                self.extension_tasks.append({
                    "task_id": task_id,
                    "manager": download_manager,
                    "url": download_data.get("url", ""),
                    "filename": download_data.get("filename", "未知文件"),
                    "save_path": download_data.get("save_path", self.save_path),
                    "status": "下载中",
                    "start_time": datetime.datetime.now(),
                    "request_id": download_data.get("requestId", "")
                })
            
            # 连接信号
            download_manager.initialized.connect(lambda _: self._on_download_initialized(task_id, download_manager))
            download_manager.block_progress_updated.connect(lambda progress_data: self._on_progress_updated(task_id, progress_data))
            download_manager.speed_updated.connect(lambda speed: self._on_speed_updated(task_id, speed))
            download_manager.download_completed.connect(lambda: self._on_download_completed(task_id))
            download_manager.error_occurred.connect(lambda error: self._on_download_error(task_id, error))
            
            # 启动下载
            download_manager.start()
            
            # 发送下载开始信号
            self.downloadStarted.emit(download_data)
            
            logging.info(f"[extension_window.py] 已开始浏览器扩展下载任务 [ID: {task_id}]: {download_data.get('filename', '未知文件')}")
            return True
        except Exception as e:
            logging.error(f"启动浏览器扩展下载任务失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _on_download_initialized(self, task_id, manager):
        """下载初始化完成回调"""
        try:
            logging.info(f"浏览器扩展下载任务初始化完成 [ID: {task_id}]")
            
            # 更新任务信息
            with self.thread_lock:
                for task in self.extension_tasks:
                    if task["task_id"] == task_id:
                        task["file_name"] = manager.file_name
                        task["file_size"] = manager.file_size
                        break
        except Exception as e:
            logging.error(f"处理下载初始化失败: {e}")
    
    def _on_progress_updated(self, task_id, progress_data):
        """进度更新回调"""
        try:
            # 查找任务
            task = None
            with self.thread_lock:
                for t in self.extension_tasks:
                    if t["task_id"] == task_id:
                        task = t
                        break
            
            if not task:
                return
            
            # 计算总进度
            progress_percent = self._calculate_progress_percent(progress_data)
            
            # 更新任务状态
            with self.thread_lock:
                task["progress"] = progress_percent
            
            # 检查下载完成 - 如果进度超过99.9%，标记为完成
            if progress_percent >= 99.9 and task["status"] != "已完成":
                with self.thread_lock:
                    task["status"] = "已完成"
                    task["end_time"] = datetime.datetime.now()
                
                # 添加到历史记录
                self._add_to_history(task)
        except Exception as e:
            logging.error(f"处理进度更新失败: {e}")
    
    def _calculate_progress_percent(self, progress_data):
        """计算下载进度百分比"""
        if not progress_data:
            return 0
            
        try:
            total_downloaded = 0
            total_size = 0
            
            for block in progress_data:
                if isinstance(block, dict):
                    # 支持新旧格式
                    start_pos = block.get('start_position', block.get('startPos', 0))
                    end_pos = block.get('end_position', block.get('endPos', 0))
                    current = block.get('current_position', block.get('progress', start_pos))
                elif isinstance(block, (list, tuple)) and len(block) >= 3:
                    start_pos, current, end_pos = block[:3]
                else:
                    continue
                
                # 确保值合法
                start_pos = max(0, int(start_pos))
                end_pos = max(start_pos, int(end_pos))
                current = max(start_pos, min(end_pos, int(current)))
                
                # 计算已下载量
                block_downloaded = current - start_pos
                block_size = end_pos - start_pos + 1
                
                # 累计总量
                total_downloaded += block_downloaded
                total_size += block_size
            
            # 计算百分比
            if total_size > 0:
                progress = (total_downloaded / total_size) * 100
                # 如果进度超过99.9%，视为完成
                if progress > 99.9:
                    return 100
                return min(round(progress, 1), 100)  # 确保不超过100%
            
            return 0
        except Exception as e:
            logging.error(f"计算进度出错: {e}")
            return 0
    
    def _on_speed_updated(self, task_id, speed_bytes):
        """速度更新回调"""
        try:
            # 查找任务
            with self.thread_lock:
                for task in self.extension_tasks:
                    if task["task_id"] == task_id:
                        task["speed"] = speed_bytes
                        break
        except Exception as e:
            logging.error(f"处理速度更新失败: {e}")
    
    def _on_download_completed(self, task_id):
        """下载完成回调"""
        try:
            # 查找任务
            task = None
            with self.thread_lock:
                for t in self.extension_tasks:
                    if t["task_id"] == task_id:
                        task = t
                        break
            
            if not task:
                return
            
            # 如果任务已经标记为完成，不再处理
            if task.get("status") == "已完成":
                return
            
            # 标记任务为完成
            with self.thread_lock:
                task["status"] = "已完成"
                task["end_time"] = datetime.datetime.now()
            
            # 添加到历史记录
            self._add_to_history(task)
            
            # 发送下载完成信号
            complete_data = {
                "task_id": task_id,
                "url": task.get("url", ""),
                "filename": task.get("file_name", task.get("filename", "未知文件")),
                "save_path": task.get("save_path", ""),
                "file_size": task.get("file_size", 0),
                "status": "已完成",
                "source": "browser_extension",
                "end_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.downloadCompleted.emit(complete_data)
            
            logging.info(f"浏览器扩展下载任务完成 [ID: {task_id}]: {task.get('file_name', task.get('filename', '未知文件'))}")
            
        except Exception as e:
            logging.error(f"处理下载完成失败: {e}")
    
    def _on_download_error(self, task_id, error):
        """下载错误回调"""
        try:
            # 查找任务
            with self.thread_lock:
                for task in self.extension_tasks:
                    if task["task_id"] == task_id:
                        task["status"] = "下载失败"
                        task["error"] = str(error)
                        break
            
            logging.error(f"浏览器扩展下载任务出错 [ID: {task_id}]: {error}")
        except Exception as e:
            logging.error(f"处理下载错误失败: {e}")
    
    def _add_to_history(self, task):
        """添加任务到历史记录"""
        try:
            # 获取下载管理器
            manager = task.get("manager")
            if not manager:
                return
            
            # 创建历史记录条目
            from core.history.history_manager import HistoryManager
            
            history_item = {
                'filename': getattr(manager, 'file_name', task.get('filename', '未知文件')),
                'url': getattr(manager, 'url', task.get('url', '')),
                'save_path': os.path.join(task.get('save_path', ''), getattr(manager, 'file_name', task.get('filename', '未知文件'))),
                'file_size': getattr(manager, 'file_size', 0),
                'download_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'completed'
            }
            
            # 添加记录
            history_manager = HistoryManager()
            history_manager.add_record(history_item)
            
            logging.info(f"已将浏览器扩展下载任务添加到历史记录: {history_item['filename']}")
        except Exception as e:
            logging.error(f"添加历史记录失败: {e}")

    def _add_download_preview_item(self, download_data):
        """添加下载预览项"""
        # 修改方法为空实现，保留API兼容性
        pass

    def _create_extension_detector(self):
        """创建浏览器插件检测面板"""
        # 删除整个方法内容
        pass
    
    def _start_extension_detector(self):
        """启动插件检测定时器"""
        # 删除整个方法内容
        pass
    
    def _check_extension_installed(self):
        """检查浏览器插件是否已安装"""
        # 删除整个方法内容
        pass
    
    def _on_download_extension(self):
        """打开浏览器下载插件"""
        # 删除整个方法内容
        pass
    
    def _create_settings_panel(self):
        """创建设置面板，包含保存路径设置"""
        # 删除整个方法内容
        pass
    
    def _on_change_path(self):
        """更改保存路径"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.save_path = folder_path
            
            # 保存到配置
            if self.config_manager:
                self.config_manager.set_save_path(folder_path)
            
            logging.info(f"浏览器扩展下载保存路径已更新: {folder_path}")
