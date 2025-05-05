from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QSizePolicy, QFrame, QScrollArea, QLineEdit, QFileDialog,
                              QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap

import os
import datetime
import logging
import time
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from core.font.font_manager import FontManager
from client.ui.components.progressBar import ProgressBar
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.client_interface.task_window import TaskWindow, RoundedTaskFrame

class DownloadWindow(QWidget):
    """下载管理窗口，负责显示下载任务和控制下载操作"""
    
    # 定义信号
    downloadAdded = Signal(dict)  # 添加下载任务
    saveFolderChanged = Signal(str)  # 保存文件夹改变
    downloadRequested = Signal(str)  # 请求下载信号，参数为URL
    taskPaused = Signal(int)  # 任务暂停信号
    taskResumed = Signal(int)  # 任务恢复信号
    taskCancelled = Signal(int)  # 任务取消信号
    
    def __init__(self, font_manager=None, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = font_manager if font_manager else FontManager()
        
        # 默认保存路径
        self.save_path = os.path.expanduser("~/Downloads")
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        
        # 创建URL输入区域
        self._create_url_input_section()
        
        # 创建任务列表区域
        self._create_tasks_area()
        
    def _create_url_input_section(self):
        """创建URL输入和按钮区域"""
        top_card = RoundedTaskFrame()
        top_card.setMinimumHeight(150)
        top_card_layout = QVBoxLayout(top_card)
        top_card_layout.setContentsMargins(20, 20, 20, 20)
        top_card_layout.setSpacing(15)
        
        # URL输入框标题
        url_title = QLabel("添加下载")
        url_title.setAlignment(Qt.AlignCenter)
        url_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(url_title)
        top_card_layout.addWidget(url_title)
        
        # URL输入框和按钮区域
        url_input_layout = QHBoxLayout()
        url_input_layout.setSpacing(10)
        
        # URL输入框
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入下载链接...")
        self.url_input.setMinimumHeight(45)
        self.font_manager.apply_font(self.url_input)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 15px;
            }
            QLineEdit:focus {
                border: 1px solid #B39DDB;
            }
        """)
        # 添加回车键触发下载功能
        self.url_input.returnPressed.connect(self._on_download_clicked)
        url_input_layout.addWidget(self.url_input, 5)
        
        # 创建下载和路径按钮
        self._create_action_buttons(url_input_layout)
        
        top_card_layout.addLayout(url_input_layout)
        
        # 显示保存路径
        self.save_path_label = QLabel(f"当前保存位置: {self.save_path}")
        self.save_path_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.save_path_label.setAlignment(Qt.AlignCenter)
        top_card_layout.addWidget(self.save_path_label)
        
        # 添加到下载页面
        self.main_layout.addWidget(top_card)
    
    def _create_action_buttons(self, parent_layout):
        """创建下载和选择路径按钮"""
        # 下载按钮
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setMinimumWidth(100)
        self.download_btn.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #1FB15F;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 5px 15px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #17A452;
            }
            QPushButton:pressed {
                background-color: #149048;
            }
        """)
        
        download_btn_layout = QHBoxLayout(self.download_btn)
        download_btn_layout.setContentsMargins(10, 0, 10, 0)
        download_btn_layout.setSpacing(8)
        
        # 添加图标
        icon_label = self.font_manager.create_icon_label(
            self.download_btn, 
            "ic_fluent_arrow_download_24_regular", 
            size=14,
            color="#FFFFFF"
        )
        download_btn_layout.addWidget(icon_label)
        
        # 添加文本
        text_label = QLabel("开始下载")
        text_label.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
        self.font_manager.apply_font(text_label)
        download_btn_layout.addWidget(text_label)
        
        # 连接点击事件
        self.download_btn.clicked.connect(self._on_download_clicked)
        parent_layout.addWidget(self.download_btn, 1)
        
        # 选择保存路径按钮
        self.path_btn = QPushButton()
        self.path_btn.setMinimumHeight(45)
        self.path_btn.setMinimumWidth(150)
        self.path_btn.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.path_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 8px;
                padding: 5px 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """)
        
        path_btn_layout = QHBoxLayout(self.path_btn)
        path_btn_layout.setContentsMargins(10, 0, 10, 0)
        path_btn_layout.setSpacing(5)
        
        # 创建图标
        folder_icon = self.font_manager.create_icon_label(
            self.path_btn,
            "ic_fluent_folder_24_regular",
            size=14,
            color="#FFFFFF"
        )
        path_btn_layout.addWidget(folder_icon)
        
        # 创建文本
        path_text = QLabel("保存位置")
        path_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_text.setMinimumWidth(70)
        path_text.setAlignment(Qt.AlignCenter)
        path_btn_layout.addWidget(path_text)
        
        # 连接事件
        self.path_btn.clicked.connect(self._on_select_path_clicked)
        parent_layout.addWidget(self.path_btn, 2)
        
    def _on_download_clicked(self):
        """下载按钮点击事件处理"""
        url = self.url_input.text().strip()
        if url:
            # 创建任务数据
            task_data = {
                "url": url,
                "save_path": self.save_path,
                "multi_thread": True
            }
            
            # 显示下载弹窗
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            dialog = DownloadPopDialog.create_and_show(task_data, self)
            
            # 连接信号
            dialog.downloadRequested.connect(self._on_dialog_download_requested)
            dialog.downloadCompleted.connect(self._on_dialog_download_completed)
            
            # 清空输入框
            self.url_input.clear()
    
    def _on_dialog_download_requested(self, task_data):
        """处理弹窗发出的下载请求"""
        # 将弹窗的下载请求转发给应用程序
        self.downloadAdded.emit(task_data)
    
    def _on_dialog_download_completed(self, task_data):
        """处理弹窗发出的下载完成信号"""
        # 在任务窗口添加已完成的任务
        task_data["status"] = "已完成"
        task_data["progress"] = 100
        self.add_download_task(task_data)
    
    def _on_select_path_clicked(self):
        """选择保存路径按钮点击事件处理"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.set_save_path(folder_path)
        
    def _create_tasks_area(self):
        """创建下载任务列表区域"""
        # 创建任务窗口
        self.task_frame = RoundedTaskFrame()
        self.task_frame.setMinimumHeight(300)
        task_layout = QVBoxLayout(self.task_frame)
        task_layout.setContentsMargins(5, 5, 5, 5)
        
        # 初始化任务窗口
        self.task_window = TaskWindow(self.font_manager, self)
        
        # 连接任务窗口信号
        self._connect_task_signals()
        
        # 添加任务窗口到布局
        task_layout.addWidget(self.task_window, 1)
        
        # 添加到主布局
        self.main_layout.addWidget(self.task_frame, 1)
    
    def _connect_task_signals(self):
        """连接任务窗口信号"""
        if hasattr(self, 'task_window') and self.task_window:
            # 连接暂停/恢复/取消信号
            self.task_window.taskPaused.connect(self._on_task_paused)
            self.task_window.taskResumed.connect(self._on_task_resumed)
            self.task_window.taskCancelled.connect(self._on_task_cancelled)
            
            # 连接文件操作信号
            if hasattr(self.task_window, 'fileOpened'):
                self.task_window.fileOpened.connect(self._on_file_opened)
            
            if hasattr(self.task_window, 'folderOpened'):
                self.task_window.folderOpened.connect(self._on_folder_opened)
    
    def add_download_task(self, task_data):
        """添加下载任务
        
        参数:
            task_data (dict): 任务数据，包含url, file_name等信息
        """
        try:
            if not hasattr(self, 'task_window') or not self.task_window:
                logging.error("任务窗口未初始化")
                return -1
                
            # 确保任务数据包含必要字段
            if not task_data.get("url"):
                logging.error("任务数据缺少URL")
                return -1
                
            # 为任务添加ID和时间戳
            if "id" not in task_data:
                task_data["id"] = f"task_{int(time.time() * 1000)}"
                
            if "start_time" not in task_data:
                task_data["start_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            # 设置保存路径
            if "save_path" not in task_data:
                task_data["save_path"] = self.save_path
                
            # 处理文件名，去除不合法字符
            if "file_name" in task_data:
                task_data["file_name"] = self._sanitize_filename(task_data["file_name"])
            else:
                # 从URL推断文件名
                url = task_data.get("url", "")
                filename = self._extract_filename_from_url(url)
                task_data["file_name"] = filename
                
            # 添加到任务窗口
            row = self.task_window.add_task(task_data)
            
            if row >= 0:
                # 发送添加下载任务信号
                self.downloadAdded.emit(task_data)
                logging.info(f"已添加下载任务: {task_data.get('url')}")
                
            return row
        except Exception as e:
            logging.error(f"添加下载任务失败: {e}")
            import traceback
            traceback.print_exc()
            return -1
    
    def _extract_filename_from_url(self, url):
        """从URL中提取文件名
        
        参数:
            url (str): 下载链接
            
        返回:
            str: 提取的文件名，如果无法提取则返回一个基于时间戳的默认文件名
        """
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
        """清理文件名，移除不合法字符
        
        参数:
            filename (str): 原始文件名
            
        返回:
            str: 处理后的合法文件名
        """
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
    
    def process_browser_extension_download(self, download_data):
        """处理来自浏览器扩展的下载请求
        
        参数:
            download_data (dict): 下载数据
            
        返回:
            dict: 处理后的任务数据
        """
        try:
            # 从下载数据中提取必要信息
            url = download_data.get("url", "")
            if not url:
                raise ValueError("下载数据缺少URL")
                
            # 获取文件名 - 优先使用提供的文件名，否则从URL提取
            filename = download_data.get("filename", "")
            if not filename:
                filename = self._extract_filename_from_url(url)
            
            # 创建任务数据
            request_id = download_data.get("requestId", f"ext_{int(time.time() * 1000)}")
            
            task_data = {
                "url": url,
                "file_name": filename,
                "total_size": download_data.get("size", "获取中..."),
                "progress": 0,
                "status": "初始化中",
                "speed": "0 B/s",
                "save_path": self.save_path,
                "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "browser",  # 标记为浏览器来源
                "request_id": request_id,
                "headers": download_data.get("headers", {})
            }
            
            # 添加Referer支持
            if "referrer" in download_data and "headers" in task_data:
                if "Referer" not in task_data["headers"]:
                    task_data["headers"]["Referer"] = download_data["referrer"]
            
            return task_data
            
        except Exception as e:
            logging.error(f"处理浏览器扩展下载失败: {e}")
            raise
    
    def update_task_progress(self, row, progress_data, file_size=0):
        """更新任务进度
        
        参数:
            row (int): 任务行号
            progress_data (list): 进度数据
            file_size (int): 文件大小
        """
        if hasattr(self, 'task_window') and self.task_window:
            self.task_window.update_progress(row, progress_data, file_size)
    
    def update_task_speed(self, row, speed_bytes):
        """更新任务速度
        
        参数:
            row (int): 任务行号
            speed_bytes (int): 下载速度(字节/秒)
        """
        if hasattr(self, 'task_window') and self.task_window:
            self.task_window.update_speed(row, speed_bytes)
    
    def update_task_status(self, row, status_text, is_complete=False, error_info=None):
        """更新任务状态
        
        参数:
            row (int): 任务行号
            status_text (str): 状态文本
            is_complete (bool): 是否完成
            error_info (str): 错误信息
        """
        if hasattr(self, 'task_window') and self.task_window:
            self.task_window.update_status(row, status_text, is_complete, error_info)
    
    def update_task_file_info(self, row, filename=None, size=None):
        """更新任务文件信息
        
        参数:
            row (int): 任务行号
            filename (str): 文件名
            size (int): 文件大小
        """
        if hasattr(self, 'task_window') and self.task_window:
            # 清理文件名，确保合法
            if filename:
                filename = self._sanitize_filename(filename)
            self.task_window.update_file_info(row, filename, size)
    
    def _on_task_paused(self, row):
        """任务暂停事件处理"""
        self.taskPaused.emit(row)
        logging.info(f"暂停任务: {row}")
        
    def _on_task_resumed(self, row):
        """任务恢复事件处理"""
        self.taskResumed.emit(row)
        logging.info(f"恢复任务: {row}")
        
    def _on_task_cancelled(self, row):
        """任务取消事件处理"""
        self.taskCancelled.emit(row)
        logging.info(f"取消任务: {row}")
        
    def _on_file_opened(self, file_path):
        """打开文件事件处理"""
        self._open_file(file_path)
        
    def _on_folder_opened(self, folder_path):
        """打开文件夹事件处理"""
        self._open_folder(folder_path)
    
    def _open_file(self, file_path):
        """打开文件"""
        try:
            import os
            import subprocess
            
            if os.path.exists(file_path):
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:  # Linux
                    subprocess.call(['xdg-open', file_path])
                logging.info(f"已打开文件: {file_path}")
            else:
                logging.warning(f"尝试打开不存在的文件: {file_path}")
                QMessageBox.warning(self, "文件不存在", f"无法找到文件:\n{file_path}")
        except Exception as e:
            logging.error(f"打开文件失败: {e}")
            QMessageBox.critical(self, "打开失败", f"无法打开文件: {e}")
    
    def _open_folder(self, folder_path):
        """打开文件夹"""
        try:
            import os
            import subprocess
            
            if os.path.exists(folder_path):
                if os.name == 'nt':  # Windows
                    subprocess.call(['explorer', folder_path])
                elif os.name == 'darwin':  # macOS
                    subprocess.call(['open', folder_path])
                else:  # Linux
                    subprocess.call(['xdg-open', folder_path])
                logging.info(f"已打开文件夹: {folder_path}")
            else:
                logging.warning(f"尝试打开不存在的文件夹: {folder_path}")
                QMessageBox.warning(self, "文件夹不存在", f"无法找到文件夹:\n{folder_path}")
        except Exception as e:
            logging.error(f"打开文件夹失败: {e}")
            QMessageBox.critical(self, "打开失败", f"无法打开文件夹: {e}")
        
    def set_save_path(self, path):
        """设置保存路径
        
        参数:
            path (str): 新的保存路径
        """
        if path and os.path.isdir(path):
            self.save_path = path
            if hasattr(self, 'save_path_label'):
                self.save_path_label.setText(f"当前保存位置: {self.save_path}")
            self.saveFolderChanged.emit(path)
            return True
        return False
        
    def redownload_from_history(self, history_record):
        """从历史记录重新下载文件
        
        参数:
            history_record (dict): 历史记录数据
            
        返回:
            int: 任务行号，-1表示失败
        """
        try:
            if not history_record or "url" not in history_record:
                logging.error("历史记录数据缺少URL")
                return -1
                
            # 创建任务数据
            task_data = {
                "url": history_record.get("url", ""),
                "file_name": history_record.get("filename", self._extract_filename_from_url(history_record.get("url", ""))),
                "save_path": self.save_path,
                "multi_thread": True,
                "source": "history",
                "request_id": f"history_{int(time.time() * 1000)}"
            }
            
            # 显示下载弹窗
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            dialog = DownloadPopDialog.create_and_show(task_data, self)
            
            # 连接信号
            dialog.downloadRequested.connect(self._on_dialog_download_requested)
            dialog.downloadCompleted.connect(self._on_dialog_download_completed)
            
            return 0  # 返回成功
            
        except Exception as e:
            logging.error(f"从历史记录重新下载失败: {e}")
            return -1
            
    def clear_tasks(self):
        """清空所有任务"""
        if hasattr(self, 'task_window') and self.task_window:
            self.task_window.clear_all_tasks()
            
    def get_task_count(self):
        """获取任务数量
        
        返回:
            int: 任务数量
        """
        if hasattr(self, 'task_window') and self.task_window:
            return self.task_window.tableWidget.rowCount()
        return 0

    def handle_browser_download_request(self, download_data):
        """处理浏览器下载请求
        
        参数:
            download_data (dict): 浏览器下载数据
            
        返回:
            bool: 成功返回True，失败返回False
        """
        try:
            # 从下载数据中提取必要信息
            url = download_data.get("url", "")
            if not url:
                raise ValueError("下载数据缺少URL")
                
            # 获取文件名 - 优先使用提供的文件名，否则从URL提取
            filename = download_data.get("filename", "")
            if not filename:
                filename = self._extract_filename_from_url(url)
            
            # 创建任务数据
            request_id = download_data.get("requestId", f"ext_{int(time.time() * 1000)}")
            
            task_data = {
                "url": url,
                "file_name": filename,
                "save_path": self.save_path,
                "multi_thread": True,
                "source": "browser",  # 标记为浏览器来源
                "request_id": request_id,
                "headers": download_data.get("headers", {})
            }
            
            # 添加Referer支持
            if "referrer" in download_data and "headers" in task_data:
                if "Referer" not in task_data["headers"]:
                    task_data["headers"]["Referer"] = download_data["referrer"]
            
            # 显示下载弹窗
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            dialog = DownloadPopDialog.create_and_show(task_data, self, auto_start=True)  # 自动开始下载
            
            # 连接信号
            dialog.downloadRequested.connect(self._on_dialog_download_requested)
            dialog.downloadCompleted.connect(self._on_dialog_download_completed)
            
            return True
            
        except Exception as e:
            logging.error(f"处理浏览器下载请求失败: {e}")
            return False
