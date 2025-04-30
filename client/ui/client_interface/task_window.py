from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QLabel, QSizePolicy, QFrame, QScrollArea)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap

import os

from client.ui.components.progressBar import ProgressBar
from core.font.font_manager import FontManager
from client.ui.components.download_log_dialog import DownloadLogDialog

class RoundedTaskFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("roundedTaskFrame")
        self.setStyleSheet("""
            #roundedTaskFrame {
                background-color: #171717;
                border-radius: 15px;
                padding: 10px;
            }
        """)

class TaskItemWidget(QFrame):
    """单个下载任务项组件"""
    def __init__(self, parent=None, row_index=0, font_manager=None):
        super().__init__(parent)
        self.row_index = row_index
        self.font_manager = font_manager
        
        # 设置基本样式
        self.setStyleSheet("""
            TaskItemWidget {
                background-color: #1A1A1A;
                border-radius: 5px;
                margin: 3px 0px;
            }
        """)
        
        # 创建布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 图标区域
        self.icon_label = QLabel()
        self.icon_label.setFixedWidth(60)
        icon_font = self.font_manager.create_icon_font(32)  # 进一步增大图标尺寸
        self.icon_label.setFont(icon_font)
        self.icon_label.setStyleSheet("color: #4285F4;")  # 使用蓝色以更好区分
        self.icon_label.setText("\ue24d")  # insert_drive_file的Unicode码点
        self.icon_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.icon_label)
        
        # 文件信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        
        # 文件名
        self.filename_label = QLabel("准备中...")
        self.filename_label.setStyleSheet("color: #FFFFFF; font-size: 14px;")
        info_layout.addWidget(self.filename_label)
        
        # 文件大小和下载速度
        size_speed_layout = QHBoxLayout()
        size_speed_layout.setSpacing(15)
        
        # 文件大小标签 - 添加图标
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(5)
        
        # 文件大小图标
        size_icon = QLabel()
        icon_font = self.font_manager.create_icon_font(14)
        size_icon.setFont(icon_font)
        size_icon.setText("\ue1af")  # data_usage的Unicode码点
        size_icon.setStyleSheet("color: #9E9E9E;")
        size_layout.addWidget(size_icon)
        
        # 文件大小文字
        self.size_label = QLabel("文件大小:")
        self.size_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        size_layout.addWidget(self.size_label)
        
        size_speed_layout.addWidget(size_widget)
        
        # 下载速度标签 - 添加图标
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(5)
        
        # 下载速度图标
        speed_icon = QLabel()
        speed_icon.setFont(icon_font)
        speed_icon.setText("\ue2c4")  # download的Unicode码点
        speed_icon.setStyleSheet("color: #9E9E9E;")
        speed_layout.addWidget(speed_icon)
        
        # 下载速度文字
        self.speed_label = QLabel("下载速度: N/A")
        self.speed_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        speed_layout.addWidget(self.speed_label)
        
        size_speed_layout.addWidget(speed_widget)
        
        size_speed_layout.addStretch()
        info_layout.addLayout(size_speed_layout)
        
        # 进度条区域
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(3)
        
        # 进度标签和总进度百分比在同一行
        progress_header_layout = QHBoxLayout()
        progress_header_layout.setSpacing(5)
        
        # 使用Material Icons作为进度标签
        self.progress_label = QLabel()
        # 使用混合字体样式，可以同时显示图标和文字
        self.progress_label.setStyleSheet("color: #9E9E9E; font-size: 12px;")
        self.progress_label.setMinimumWidth(120)  # 设置最小宽度以适应"下载完成"文字
        
        # 为progress_label设置图标字体
        icon_font = self.font_manager.create_icon_font(16)
        self.progress_label.setFont(icon_font)
        self.progress_label.setText("\ue2c6")  # download_for_offline的Unicode码点
        
        progress_header_layout.addWidget(self.progress_label)
        
        progress_header_layout.addStretch()
        
        # 总进度百分比标签
        self.total_progress_label = QLabel("进度")
        self.total_progress_label.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        self.total_progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_header_layout.addWidget(self.total_progress_label)
        
        # 添加进度头部布局
        progress_layout.addLayout(progress_header_layout)
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.font_manager.apply_font(self.progress_bar)
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setIdmStyle(True)
        self.progress_bar.setShowSegments(True)
        self.progress_bar.setProgress(0)
        progress_layout.addWidget(self.progress_bar)
        
        info_layout.addLayout(progress_layout)
        main_layout.addLayout(info_layout, 1)
        
        # 操作按钮区域
        self.action_widget = QWidget()
        self.action_layout = QHBoxLayout(self.action_widget)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(5)
        self.action_layout.addStretch()  # 确保按钮靠右对齐
        
        # 添加操作区域
        main_layout.addWidget(self.action_widget)
    
    def update_filename(self, filename):
        """更新文件名"""
        if filename:
            self.filename_label.setText(filename)
    
    def update_size(self, size):
        """更新文件大小"""
        if isinstance(size, (int, float)):
            size_text = self.get_readable_size(size)
            self.size_label.setText(f"文件大小: {size_text}")
        elif isinstance(size, str):
            self.size_label.setText(f"文件大小: {size}")
    
    def update_speed(self, speed_bytes):
        """更新下载速度"""
        speed_text = self.get_readable_size(speed_bytes) + "/s"
        self.speed_label.setText(f"下载速度: {speed_text}")
    
    def update_progress(self, progress_data, file_size=0):
        """更新进度条"""
        if not progress_data and isinstance(file_size, (int, float)) and file_size > 0:
            # 可能是进度百分比
            percentage = int((file_size / 100) * 100)
            self.progress_bar.setProgress(percentage)
            self.progress_bar.setSegments([(0, percentage, "#1FB15F")])
            self.progress_bar.setShowSegments(True)
            self.total_progress_label.setText(f"总进度: {percentage}%")
            return
            
        if file_size > 0 and progress_data:
            # 使用分段功能
            self.progress_bar.updateFromDownloadSegments(progress_data, file_size)
            
            # 计算总进度
            total_progress = 0
            if isinstance(progress_data[0], dict):
                total_size = sum([segment.get('endPos', 0) - segment.get('startPos', 0) for segment in progress_data])
                current_progress = sum([segment.get('progress', 0) - segment.get('startPos', 0) for segment in progress_data])
                if total_size > 0:
                    total_progress = int((current_progress / total_size) * 100)
            elif isinstance(progress_data[0], (list, tuple)) and len(progress_data[0]) >= 3:
                total_size = sum([segment[2] - segment[0] for segment in progress_data])
                current_progress = sum([segment[1] - segment[0] for segment in progress_data])
                if total_size > 0:
                    total_progress = int((current_progress / total_size) * 100)
            
            self.total_progress_label.setText(f"进度: {total_progress}%")
    
    def update_status(self, status_text, is_complete=False):
        """更新任务状态"""
        if "下载中" in status_text and "%" in status_text:
            try:
                percent = int(status_text.split(":")[1].strip().replace("%", ""))
                self.total_progress_label.setText(f"进度: {percent}%")
                # 设置下载中图标为蓝色
                self.progress_label.setStyleSheet("color: #3478F6; font-size: 12px;")
                self.progress_label.setText("\ue2c0")  # downloading的Unicode码点
            except:
                self.total_progress_label.setText(status_text)
        elif is_complete:
            self.total_progress_label.setText("进度: 100%")
            # 创建完成图标+文字的混合显示
            try:
                # 先尝试设置字体以显示图标
                icon_font = self.font_manager.create_icon_font(16)
                self.progress_label.setFont(icon_font)
                
                # 设置图标和文字，直接使用Unicode码点
                self.progress_label.setText("\ue86c 下载完成")  # check_circle的Unicode码点
                self.progress_label.setStyleSheet("color: #1FB15F; font-size: 12px;")
            except Exception as e:
                print(f"设置完成图标出错: {e}")
                # 如果出错，至少显示文字
                self.progress_label.setText("下载完成")
                self.progress_label.setStyleSheet("color: #1FB15F; font-size: 12px;")
                
            self.progress_bar.setProgress(100)
            self.progress_bar.setSegments([(0, 100, "#1FB15F")])
            self.add_completed_actions()
        elif "暂停" in status_text:
            # 设置暂停图标为黄色
            self.progress_label.setText("\ue034")  # pause_circle的Unicode码点
            self.progress_label.setStyleSheet("color: #FFC107; font-size: 12px;")
        elif "取消" in status_text or "错误" in status_text:
            # 设置错误图标为红色
            self.progress_label.setText("\ue001")  # error_outline的Unicode码点
            self.progress_label.setStyleSheet("color: #FF3B30; font-size: 12px;")
    
    def add_completed_actions(self):
        """添加完成后的操作按钮"""
        # 清空现有布局
        for i in reversed(range(self.action_layout.count())): 
            item = self.action_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # 更新进度标签为"已完成"图标+文字
        try:
            # 先尝试设置字体以显示图标
            icon_font = self.font_manager.create_icon_font(16)
            self.progress_label.setFont(icon_font)
            
            # 设置图标和文字，直接使用Unicode码点
            self.progress_label.setText("\ue86c 下载完成")  # check_circle的Unicode码点
            self.progress_label.setStyleSheet("color: #1FB15F; font-size: 12px;")
        except Exception as e:
            print(f"设置完成图标出错: {e}")
            # 如果出错，至少显示文字
            self.progress_label.setText("下载完成")
            self.progress_label.setStyleSheet("color: #1FB15F; font-size: 12px;")
            
        self.total_progress_label.setText("进度: 100%")
        
        # 创建操作按钮的通用样式
        btn_style = """
            QPushButton {
                background-color: #333333;
                border: none;
                border-radius: 3px;
                padding: 5px;
                min-width: 32px;
                min-height: 32px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """
        
        # 资源路径
        resources_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "resources")
        
        # 创建按钮
        # 打开文件按钮
        open_btn = QPushButton()
        open_icon = QIcon(os.path.join(resources_path, "file_open.svg"))
        open_btn.setIcon(open_icon)
        open_btn.setIconSize(QSize(22, 22))
        open_btn.setStyleSheet(btn_style)
        open_btn.setToolTip("打开文件")
        open_btn.setProperty("row", self.row_index)
        self.open_btn = open_btn
        
        # 删除按钮
        delete_btn = QPushButton()
        delete_icon = QIcon(os.path.join(resources_path, "delete.svg"))
        delete_btn.setIcon(delete_icon)
        delete_btn.setIconSize(QSize(22, 22))
        delete_btn.setStyleSheet(btn_style)
        delete_btn.setToolTip("删除")
        delete_btn.setProperty("row", self.row_index)
        self.delete_btn = delete_btn
        
        # 打开文件夹按钮
        folder_btn = QPushButton()
        folder_icon = QIcon(os.path.join(resources_path, "folder.svg"))
        folder_btn.setIcon(folder_icon)
        folder_btn.setIconSize(QSize(22, 22))
        folder_btn.setStyleSheet(btn_style)
        folder_btn.setToolTip("打开文件夹")
        folder_btn.setProperty("row", self.row_index)
        self.folder_btn = folder_btn
        
        # 添加按钮到布局
        self.action_layout.addWidget(open_btn)
        self.action_layout.addWidget(delete_btn)
        self.action_layout.addWidget(folder_btn)
    
    @staticmethod
    def get_readable_size(size_in_bytes):
        """将字节数转换为可读的大小表示"""
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        if isinstance(size_in_bytes, (int, float)):
            while size_in_bytes >= 1024 and i < len(size_names) - 1:
                size_in_bytes /= 1024
                i += 1
            return f"{size_in_bytes:.2f} {size_names[i]}"
        return size_in_bytes  # 如果不是数字，返回原值

class TaskWindow(QWidget):
    taskPaused = Signal(int)  # 任务暂停信号
    taskResumed = Signal(int)  # 任务恢复信号
    taskCancelled = Signal(int)  # 任务取消信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)
        
        # 标题和控制按钮
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(20, 10, 20, 10)
        self.header_layout.setSpacing(10)
        
        # 标题
        self.title_label = QLabel("下载任务")
        self.title_label.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold;")
        self.font_manager.apply_font(self.title_label)
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch(1)
        
        # 控制按钮
        control_button_style = """
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 5px;
                padding: 5px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """
        
        # 创建带图标按钮的辅助函数
        def create_control_button(text, icon_filename):
            btn = QPushButton()
            btn.setStyleSheet(control_button_style)
            
            # 使用布局方式设置图标和文本
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(8, 0, 8, 0)
            btn_layout.setSpacing(5)
            
            # 资源路径
            resources_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "resources")
            
            # 创建图标标签
            icon_label = QLabel()
            # 加载SVG图标
            icon_pixmap = QPixmap(os.path.join(resources_path, icon_filename))
            icon_label.setPixmap(icon_pixmap.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            icon_label.setStyleSheet("background-color: transparent;")
            btn_layout.addWidget(icon_label)
            
            # 创建文本标签
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            btn_layout.addWidget(text_label)
            
            return btn
        
        # 暂停按钮 - 使用SVG图标
        self.pause_btn = create_control_button("暂停", "pause.svg")
        self.pause_btn.clicked.connect(self.pause_selected_tasks)
        
        # 恢复按钮 - 使用SVG图标
        self.resume_btn = create_control_button("恢复", "play.svg")
        self.resume_btn.clicked.connect(self.resume_selected_tasks)
        
        # 取消按钮 - 使用SVG图标
        self.cancel_btn = create_control_button("取消", "cancel.svg")
        self.cancel_btn.clicked.connect(self.cancel_selected_tasks)
        
        # 添加按钮到布局
        self.header_layout.addWidget(self.pause_btn)
        self.header_layout.addWidget(self.resume_btn)
        self.header_layout.addWidget(self.cancel_btn)
        
        self.main_layout.addLayout(self.header_layout)
        
        # 下载任务列表区域
        self.tasks_frame = RoundedTaskFrame()
        self.tasks_layout = QVBoxLayout(self.tasks_frame)
        self.tasks_layout.setContentsMargins(15, 15, 15, 15)
        self.tasks_layout.setSpacing(8)
        
        # 使用滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建一个容器widget来包含所有下载项
        self.tasks_container = QWidget()
        self.tasks_container.setStyleSheet("background-color: transparent;")
        self.tasks_container_layout = QVBoxLayout(self.tasks_container)
        self.tasks_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_container_layout.setSpacing(8)
        self.tasks_container_layout.addStretch()  # 添加弹性空间让任务项靠上显示
        
        self.scroll_area.setWidget(self.tasks_container)
        self.tasks_layout.addWidget(self.scroll_area)
        
        self.main_layout.addWidget(self.tasks_frame)
        
        # 保存下载任务项的引用
        self.task_items = {}
        
    def add_download_task(self, filename="准备中...", size="获取中..."):
        """添加一个新的下载任务到任务列表中"""
        # 获取当前行数作为新任务的索引
        row_position = len(self.task_items)
        
        # 创建新的任务项组件
        task_item = TaskItemWidget(parent=self.tasks_container, row_index=row_position, font_manager=self.font_manager)
        task_item.update_filename(filename)
        task_item.update_size(size)
        
        # 添加到容器布局的顶部
        self.tasks_container_layout.insertWidget(0, task_item)
        
        # 保存任务项引用
        self.task_items[row_position] = task_item
        
        # 连接按钮信号
        # 当按钮被创建时会连接
        
        return row_position
    
    def update_file_info(self, row, filename=None, size=None):
        """更新文件信息"""
        if row not in self.task_items:
            return
        
        task_item = self.task_items[row]
        if filename is not None:
            task_item.update_filename(filename)
            
        if size is not None:
            task_item.update_size(size)
    
    def update_progress(self, row, progress_data, file_size=0):
        """更新进度条显示"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.update_progress(progress_data, file_size)
    
    def update_speed(self, row, speed_bytes):
        """更新下载速度显示"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.update_speed(speed_bytes)
    
    def update_status(self, row, status_text, is_complete=False):
        """更新任务状态"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.update_status(status_text, is_complete)
        
        # 如果完成，连接操作按钮
        if is_complete:
            self._connect_completed_actions(row)
    
    def _connect_completed_actions(self, row):
        """连接完成后的操作按钮信号"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        
        if hasattr(task_item, 'open_btn'):
            task_item.open_btn.clicked.connect(self.open_file)
        
        if hasattr(task_item, 'delete_btn'):
            task_item.delete_btn.clicked.connect(self.delete_file)
        
        if hasattr(task_item, 'folder_btn'):
            task_item.folder_btn.clicked.connect(self.open_folder)
    
    def _add_completed_actions(self, row):
        """为已完成的下载任务添加操作按钮"""
        if row not in self.task_items:
            return
            
        task_item = self.task_items[row]
        task_item.add_completed_actions()
        self._connect_completed_actions(row)
    
    def open_file(self):
        """打开下载的文件"""
        sender = self.sender()
        if sender and hasattr(sender, 'property'):
            row = sender.property("row")
            if row is not None:
                # 发射信号给主窗口处理
                print(f"打开文件：行 {row}")
    
    def delete_file(self):
        """删除下载的文件"""
        sender = self.sender()
        if sender and hasattr(sender, 'property'):
            row = sender.property("row")
            if row is not None:
                # 发射信号给主窗口处理
                print(f"删除文件：行 {row}")
    
    def open_folder(self):
        """打开文件所在文件夹"""
        sender = self.sender()
        if sender and hasattr(sender, 'property'):
            row = sender.property("row")
            if row is not None:
                # 发射信号给主窗口处理
                print(f"打开文件夹：行 {row}")
    
    def get_selected_rows(self):
        """获取当前选中的行索引"""
        # 这个实现需要修改，因为没有了表格
        # 这里简单返回一个空列表
        return []
    
    def pause_selected_tasks(self):
        """暂停选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskPaused.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已暂停")
    
    def resume_selected_tasks(self):
        """恢复选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskResumed.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已恢复")
    
    def cancel_selected_tasks(self):
        """取消选中的任务"""
        selected_rows = self.get_selected_rows()
        for row in selected_rows:
            self.taskCancelled.emit(row)
            if row in self.task_items:
                self.task_items[row].update_status("已取消")
    
    def show_download_log(self):
        """显示下载日志对话框"""
        # 获取发送信号的按钮
        sender = self.sender()
        if not sender or not hasattr(sender, 'property'):
            return
            
        # 获取行号
        row = sender.property("row")
        if row is None:
            return
            
        # 发送信号给主窗口处理
        self.show_log_for_row(row)
    
    def show_log_for_row(self, row):
        """显示特定行的下载日志的回调函数，由主窗口连接"""
        pass  # 由主窗口连接实现
