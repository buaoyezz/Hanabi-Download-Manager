from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLineEdit, QTableWidget, 
                              QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
                              QSplitter, QFrame, QLabel, QSizePolicy, QStackedWidget, QScrollArea, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPainterPath, QBrush, QMouseEvent, QFontDatabase

from client.ui.components.progressBar import ProgressBar
from client.ui.title_styles.titleStyles import TitleBar
from core.download_core.download_kernel import TransferManager
from core.font.font_manager import FontManager
from client.ui.client_interface.about_window import AboutWindow
from client.ui.client_interface.settings.settings_page import SettingsPage
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.components.download_log_dialog import DownloadLogDialog
from client.ui.components.update_log_dialog import UpdateLogDialog
from core.update.update_log_manager import UpdateLogManager
from client.ui.pages_manager import PagesManager, CategoryButton
from client.ui.client_interface.task_window import TaskWindow, RoundedTaskFrame

import os
import sys
import threading
import types

# 字体管理器已经在font_manager.py中自行加载，此处不需要重复加载
# def load_material_icons():
#     font_id = QFontDatabase.addApplicationFont("core/font/font/MaterialIcons-Regular.ttf")
#     if font_id != -1:
#         font_families = QFontDatabase.applicationFontFamilies(font_id)
#         if font_families:
#             return True
#     return False

class RoundedWidget(QWidget):
    def __init__(self, parent=None, radius=10, bg_color="#2C2C2C", corners="all"):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.corners = corners  # 可以是 "all", "left", "right", "top", "bottom", "top-left", "bottom-left" 
        self.setAttribute(Qt.WA_TranslucentBackground)  # 确保背景透明
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        
        # 根据不同的角落设置不同的圆角
        if self.corners == "all":
            path.addRoundedRect(rect, self.radius, self.radius)
        elif self.corners == "left":
            # 左侧两个角落圆角，右侧直角
            path = QPainterPath()
            path.moveTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left() + self.radius, rect.bottom())
            path.arcTo(rect.left(), rect.bottom() - 2 * self.radius, 
                      2 * self.radius, 2 * self.radius, 270, 90)
            path.lineTo(rect.left(), rect.top() + self.radius)
            path.arcTo(rect.left(), rect.top(), 
                      2 * self.radius, 2 * self.radius, 180, 90)
            path.lineTo(rect.right(), rect.top())
        elif self.corners == "bottom-left":
            # 只有左下角是圆角
            path = QPainterPath()
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left() + self.radius, rect.bottom())
            path.arcTo(rect.left(), rect.bottom() - 2 * self.radius, 
                      2 * self.radius, 2 * self.radius, 270, 90)
            path.lineTo(rect.left(), rect.top())
        else:
            # 默认全圆角
            path.addRoundedRect(rect, self.radius, self.radius)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)
        
class DownloadManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化更新日志管理器
        self.update_log_manager = UpdateLogManager()
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 初始化配置管理器
        from client.ui.client_interface.settings.config import config
        self.config_manager = config
        
        # 设置窗口基本属性
        self.setWindowTitle("Hanabi Download Manager")
        self.resize(1050, 650)
        
        # 设置应用图标
        self.icon_path = self.get_resource_path("resources/logo.png")
        
        # 确保图标存在
        if os.path.exists(self.icon_path):
            self.app_icon = QIcon(self.icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            print(f"警告: 图标文件不存在: {self.icon_path}")
            self.app_icon = None
        
        # 属性
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置应用深色主题 - 注意这里不要设置主窗口背景色，由paintEvent处理
        self.setStyleSheet("""
            QWidget {
                color: #FFFFFF;
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
            }
            QLabel, QPushButton, QLineEdit, QTableWidget, QHeaderView {
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
            }
            QTableWidget::item {
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei"; 
            }
        """)
        
        # 初始化下载任务列表
        self.download_tasks = []
        
        # 设置中心部件 - 中心部件需要透明背景
        self.central_widget = QWidget()
        self.central_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(self.central_widget)
        
        # 创建布局
        self.setup_ui()
        
        # 启动时检查一次更新日志
        self.check_update_logs()
    
    def paintEvent(self, event):
        # 使用高质量抗锯齿
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        # 创建圆角路径
        path = QPainterPath()
        rect = self.rect()
        
        # 增大圆角半径
        cornerRadius = 30
        path.addRoundedRect(rect, cornerRadius, cornerRadius)
        
        # 设置无边框和背景色
        painter.setPen(Qt.NoPen)  # 确保不画任何边框
        painter.setBrush(QColor("#1E1E1E"))
        
        # 使用路径裁剪和绘制
        painter.setClipPath(path)
        painter.drawPath(path)  # 使用drawPath替代drawRect，确保完全按照路径绘制
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.title_bar.underMouse():
                super().mousePressEvent(event)
                
    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(12, 0, 12, 12)  # 左右下添加边距，顶部为0让标题栏紧贴窗口
        main_layout.setSpacing(0)  # 去掉间距完全消除白线
        
        # 自定义标题栏
        self.title_bar = TitleBar(self)
        self.title_bar.setAttribute(Qt.WA_TranslucentBackground)  # 确保标题栏背景透明
        # 连接托盘信号
        self.title_bar.minimizeToTray.connect(self.on_minimize_to_tray)
        main_layout.addWidget(self.title_bar)
        
        # 内容区布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)  # 去掉顶部间距
        content_layout.setSpacing(12)  # 增加侧边栏和内容区之间的间距
        
        # 创建左侧导航栏 - 使用普通Widget而非RoundedWidget，移除圆角效果
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("background-color: #1E1E1E;")  # 保持背景色一致
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 25)
        sidebar_layout.setSpacing(20)
        
        # 品牌和应用信息区域
        brand_container = QWidget()
        brand_container.setStyleSheet("background-color: transparent;")
        brand_layout = QVBoxLayout(brand_container)
        brand_layout.setContentsMargins(10, 0, 10, 0)
        brand_layout.setSpacing(8)
        
        # 应用名称
        app_title = QLabel()
        app_title.setText("<span style='font-size: 28px;'>Hanabi</span><br><span style='font-size: 14px;'>Download Manager</span>")
        app_title.setStyleSheet("color: #B39DDB; font-weight: bold; background-color: transparent;")
        app_title.setTextFormat(Qt.RichText)
        self.font_manager.apply_font(app_title)
        brand_layout.addWidget(app_title)
        
        # 应用口号
        slogan_label = QLabel("Dev By ZZBuAoYe")
        slogan_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.font_manager.apply_font(slogan_label)
        brand_layout.addWidget(slogan_label)
        
        # 下方装饰线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333; margin-top: 8px;")
        separator.setFixedHeight(1)
        brand_layout.addWidget(separator)
        
        sidebar_layout.addWidget(brand_container)
        
        # 右侧内容区域
        self.content_area = RoundedWidget(radius=20, bg_color="#1E1E1E", corners="all")
                
        # 创建设置页面和关于页面
        self.settings_page = SettingsPage(self.config_manager, self)
        # 连接设置页面消息信号
        self.settings_page.settingsMessage.connect(self.handle_settings_message)
        
        # 关于页面
        self.about_page = AboutWindow()
        
        # 使用PagesManager进行页面管理并传入主窗口引用
        self.pages_manager = PagesManager(self.sidebar, self.content_area, self)
        
        # 注册所有常用页面
        pages = self.pages_manager.register_common_pages()
        
        # 获取下载页面的引用
        self.download_page = pages["downloads"]
        self.download_content = self.download_page.content_widget
        self.download_page_layout = self.download_page.content_layout
        
        # 获取已完成页面的引用
        self.finished_page = pages["finished"]
        
        # 创建任务窗口实例
        self.task_window = TaskWindow()
        self.task_window.taskPaused.connect(self.pause_download_task)
        self.task_window.taskResumed.connect(self.resume_download_task)
        self.task_window.taskCancelled.connect(self.cancel_download_task)
        
        # 连接文件操作信号
        self.connect_file_operations()
        
        # 创建卡片式布局
        self.setup_card_layout()
        
        # 添加下载任务窗口到下载页面
        task_card = RoundedTaskFrame()
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_layout.addWidget(self.task_window)
        
        self.download_page_layout.addWidget(task_card)
        
        # 保留空间占位区域
        spacer_widget = QWidget()
        spacer_widget.setFixedHeight(100)  # 设置适当的高度以匹配之前的过滤器区域
        spacer_widget.setStyleSheet("background-color: transparent;")
        sidebar_layout.addWidget(spacer_widget)
        
        # 添加左侧导航栏到内容布局
        content_layout.addWidget(self.sidebar)
        
        # 添加内容区到内容布局
        content_layout.addWidget(self.content_area, 1)
        
        # 添加内容布局到主布局
        main_layout.addLayout(content_layout, 1)
    
    def setup_card_layout(self):
        # 顶部URL输入和按钮区域
        top_card = RoundedWidget(radius=15)
        top_card_layout = QVBoxLayout(top_card)
        top_card_layout.setContentsMargins(20, 20, 20, 20)
        top_card_layout.setSpacing(15)
        
        # URL输入框标题 - 居中
        url_title = QLabel("添加下载")
        url_title.setAlignment(Qt.AlignCenter)
        url_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(url_title)
        top_card_layout.addWidget(url_title)
        
        # URL输入框和按钮
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
        url_input_layout.addWidget(self.url_input, 5)  # 保持输入框占较大比例
        
        # 开始下载按钮
        download_button_style = """
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
        """
        
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(45)
        self.download_btn.setMinimumWidth(100)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.download_btn.setSizePolicy(size_policy)
        self.download_btn.setStyleSheet(download_button_style)
        
        # 创建水平布局用于图标和文本
        download_btn_layout = QHBoxLayout(self.download_btn)
        download_btn_layout.setContentsMargins(10, 0, 10, 0)
        download_btn_layout.setSpacing(8)
        
        # 添加图标
        icon_label = QLabel()
        self.font_manager.apply_icon_font(icon_label, 16)
        icon_label.setText(self.font_manager.get_icon_text("download"))
        icon_label.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        download_btn_layout.addWidget(icon_label)
        
        # 添加文本
        text_label = QLabel("开始下载")
        text_label.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
        self.font_manager.apply_font(text_label)
        download_btn_layout.addWidget(text_label)
        
        # 连接点击事件
        self.download_btn.clicked.connect(self.start_download)
        url_input_layout.addWidget(self.download_btn, 1)  # 保持按钮占较小比例
        
        # 选择保存路径按钮
        self.path_btn = QPushButton()
        self.path_btn.setMinimumHeight(45)
        self.path_btn.setMinimumWidth(150)
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.path_btn.setSizePolicy(size_policy)
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
        
        # 使用布局方式设置图标和文本
        path_btn_layout = QHBoxLayout(self.path_btn)
        path_btn_layout.setContentsMargins(10, 0, 10, 0)
        path_btn_layout.setSpacing(5)
        
        # 创建图标标签
        folder_icon = QLabel()
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(16)
        folder_icon.setFont(icon_font)
        
        # 设置文件夹图标
        folder_icon.setText(self.font_manager.get_icon_text("folder"))
        folder_icon.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_btn_layout.addWidget(folder_icon)
        
        # 创建文本标签
        path_text = QLabel("保存位置")
        path_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        path_text.setMinimumWidth(70)
        path_text.setAlignment(Qt.AlignCenter)
        path_btn_layout.addWidget(path_text)
        
        self.path_btn.clicked.connect(self.select_save_path)
        url_input_layout.addWidget(self.path_btn, 2) # 稍微调整比例
        
        top_card_layout.addLayout(url_input_layout)
        
        # 当前保存路径
        self.save_path = os.path.expanduser("~/Downloads")
        
        # 添加顶部区域到内容布局
        self.download_page_layout.addWidget(top_card)
    
    def select_save_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择保存位置", self.save_path)
        if folder_path:
            self.save_path = folder_path
            QMessageBox.information(self, "保存位置", f"已选择保存位置: {self.save_path}")
    
    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            # 对于测试，如果没有输入URL，使用默认测试URL
            url = "https://speed.hetzner.de/100MB.bin"
            self.url_input.setText(url)
            
        # 从配置管理器获取线程数和最大线程数
        thread_count = self.config_manager.get_download_thread_count()
        if thread_count <= 0:
            thread_count = 4  # 默认使用4个线程
            
        dynamic_threads = self.config_manager.get_dynamic_threads()
        
        # 打印调试信息
        print(f"[DEBUG] 开始下载 - 从配置获取 线程数: {thread_count}, 动态线程: {dynamic_threads}")
        
        # 创建新的下载任务行
        row_position = self.task_window.add_download_task()
        
        # 创建下载线程
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        
        # 创建下载管理器
        transfer_manager = TransferManager(
            url=url,
            headers=headers,
            maxThreads=thread_count,
            savePath=self.save_path,
            filename=None,  # 初始化不指定文件名
            dynamicThreads=dynamic_threads
        )
        
        # 连接信号
        transfer_manager.initComplete.connect(lambda supports_multi_threading: 
                                             self.update_file_size(row_position, transfer_manager.fileSize))
        transfer_manager.segmentProgressChanged.connect(lambda progress: self.update_progress(row_position, progress))
        transfer_manager.transferSpeedChanged.connect(lambda speed: self.update_speed(row_position, speed))
        transfer_manager.downloadComplete.connect(lambda: self.download_completed(row_position))
        transfer_manager.errorOccurred.connect(lambda error: self.download_error(row_position, error))
        
        # 保存下载管理器对象
        download_task = {
            'manager': transfer_manager,
            'row': row_position,
            'status': 'running'
        }
        self.download_tasks.append(download_task)
        
        print(f"[DEBUG] 启动下载任务: {url}")
        # 启动下载
        transfer_manager.start()
    
    def update_file_size(self, row, size):
        # 更新任务窗口中的文件大小
        for task in self.download_tasks:
            if task['row'] == row:
                # 更新文件名
                self.task_window.update_file_info(row, filename=task['manager'].filename, size=size)
                break
    
    def update_progress(self, row, progress_data):
        # 查找对应任务获取文件大小
        file_size = 0
        for task in self.download_tasks:
            if task['row'] == row:
                file_size = task['manager'].fileSize
                break
                
        # 打印进度数据用于调试
        print(f"[DEBUG] 更新进度: 行={row}, 文件大小={file_size}, 进度数据={progress_data}")
                
        # 更新任务窗口中的进度条
        self.task_window.update_progress(row, progress_data, file_size)
        
        # 计算总进度百分比
        total_progress = 0
        total_downloaded = 0
        total_size = 0
        
        try:
            if progress_data and isinstance(progress_data[0], dict):
                for segment in progress_data:
                    # 字段名可能是 start 或 startPos，需要兼容处理
                    start_pos = segment.get('start', segment.get('startPos', 0))
                    end_pos = segment.get('end', segment.get('endPos', 0))
                    current = segment.get('progress', start_pos)
                    
                    # 直接对比数值，避免计算错误
                    current_downloaded = max(0, current - start_pos)
                    segment_size = max(1, end_pos - start_pos + 1)
                    
                    # 累加已下载和总大小
                    total_downloaded += current_downloaded
                    total_size += segment_size
            
            if total_size > 0:
                # 使用浮点数计算避免整数除法导致0
                total_progress = int((float(total_downloaded) / float(total_size)) * 100.0)
                total_progress = max(1, min(100, total_progress))  # 确保在1-100之间
                
                print(f"[DEBUG] 计算主窗口进度: {total_progress}%, 已下载={total_downloaded}, 总大小={total_size}")
                
                # 如果计算出总进度，更新状态文本
                self.task_window.update_status(row, f"下载中: {total_progress}%")
            
            # 检查是否已全部下载完成
            if total_progress >= 100 or self._is_download_complete(progress_data):
                self.download_completed(row)
                
        except Exception as e:
            import traceback
            print(f"[ERROR] 主窗口计算进度出错: {e}")
            traceback.print_exc()
    
    def _is_download_complete(self, progress_data):
        """检查下载是否已完成"""
        if not progress_data:
            return False
            
        try:
            # 检查是否所有分段都已下载完成
            for segment in progress_data:
                if isinstance(segment, dict):
                    start = segment.get('start', segment.get('startPos', 0))
                    end = segment.get('end', segment.get('endPos', 0))
                    progress = segment.get('progress', 0)
                    
                    if progress < end:
                        return False
                elif isinstance(segment, (list, tuple)) and len(segment) >= 3:
                    if segment[1] < segment[2]:
                        return False
            
            return True
        except:
            return False
    
    def update_speed(self, row, speed_bytes):
        # 更新任务窗口中的下载速度
        self.task_window.update_speed(row, speed_bytes)
    
    def download_completed(self, row):
        # 更新任务窗口中的状态为已完成
        self.task_window.update_status(row, "已完成", True)
        
        # 更新任务状态
        for task in self.download_tasks:
            if task['row'] == row:
                task['status'] = 'completed'
                break
    
    def download_error(self, row, error):
        # 更新任务窗口中的状态为错误
        self.task_window.update_status(row, f"错误: {error}")
        
        # 更新任务状态
        for task in self.download_tasks:
            if task['row'] == row:
                task['status'] = 'error'
                break
    
    def pause_download_task(self, row):
        for task in self.download_tasks:
            if task['row'] == row and task['status'] == 'running':
                task['manager'].stop()
                task['status'] = 'paused'
    
    def resume_download_task(self, row):
        for task in self.download_tasks:
            if task['row'] == row and task['status'] == 'paused':
                # 需要重新创建下载任务，TransferManager不支持恢复
                # 这里只是界面示例，实际功能需要在下载核心支持恢复功能
                task['status'] = 'running'
    
    def cancel_download_task(self, row):
        for task in self.download_tasks:
            if task['row'] == row:
                task['manager'].stop()
                task['status'] = 'canceled'
    
    def show_download_log(self, download_info):
        # 创建并显示日志对话框
        log_dialog = DownloadLogDialog(self, download_info)
        log_dialog.exec()
        
    def add_download_from_extension(self, download_data):
        url = download_data.get('url')
        if not url:
            return
            
        # 创建新的下载任务行
        row_position = self.task_window.add_download_task(
            filename=download_data.get('filename', "准备中...")
        )
        
        # 从请求中提取HTTP头信息
        headers = download_data.get('headers', {})
        if not headers:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            
        # 创建下载管理器
        transfer_manager = TransferManager(
            url=url,
            headers=headers,
            maxThreads=self.config_manager.get_download_thread_count(),
            savePath=self.save_path,
            filename=download_data.get('filename'),
            dynamicThreads=self.config_manager.get_dynamic_threads()
        )
        
        # 连接信号
        transfer_manager.initComplete.connect(lambda supports_multi_threading: 
                                             self.update_file_size(row_position, transfer_manager.fileSize))
        transfer_manager.segmentProgressChanged.connect(lambda progress: self.update_progress(row_position, progress))
        transfer_manager.transferSpeedChanged.connect(lambda speed: self.update_speed(row_position, speed))
        transfer_manager.downloadComplete.connect(lambda: self.download_completed(row_position))
        transfer_manager.errorOccurred.connect(lambda error: self.download_error(row_position, error))
        
        # 保存下载管理器对象
        download_task = {
            'manager': transfer_manager,
            'row': row_position,
            'status': 'running'
        }
        self.download_tasks.append(download_task)
        
        # 启动下载
        transfer_manager.start()

    def switch_page(self, index):
        # 将索引转换为页面ID
        page_id = None
        if index == 0:
            page_id = "downloads"
        elif index == 1:
            page_id = "finished"
        elif index == 2:
            page_id = "settings"
        elif index == 3:
            page_id = "about"
        
        # 切换到指定页面
        if page_id:
            self.pages_manager.switch_page(page_id)
    
    def open_settings(self):
        self.pages_manager.switch_page("settings")

    def handle_settings_message(self, success, message):
        if success:
            QMessageBox.information(self, "设置", message)
        else:
            QMessageBox.warning(self, "设置错误", message)
        
    def closeEvent(self, event):
        # 在这里添加关闭事件的处理逻辑
        super().closeEvent(event)
        
    def check_update_logs(self):
        latest = self.update_log_manager.get_latest_version_log()
        if latest:
            version, log_data = latest
            dialog = UpdateLogDialog(
                version=version,
                content=log_data["content"],
                update_time=log_data["update_time"],
                parent=self
            )
            if dialog.exec() == QDialog.Accepted:
                self.update_log_manager.mark_as_read(version)
                # 清理旧的更新日志
                self.update_log_manager.clean_old_logs()
        
    def connect_file_operations(self):
        """连接文件操作功能"""
        def open_file_method(self, row):
            """打开下载的文件"""
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件路径
                        filename = task.get('manager').filename
                        if not filename:
                            continue
                        
                        filepath = os.path.join(self.save_path, filename)
                        if not os.path.exists(filepath):
                            QMessageBox.warning(self, "错误", f"文件不存在: {filepath}")
                            return
                        
                        # 使用系统默认程序打开文件
                        import subprocess
                        import sys
                        
                        if sys.platform == 'win32':
                            os.startfile(filepath)
                        elif sys.platform == 'darwin':  # macOS
                            subprocess.call(['open', filepath])
                        else:  # Linux
                            subprocess.call(['xdg-open', filepath])
                            
                        print(f"打开文件: {filepath}")
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法打开文件: {str(e)}")
                    break
        
        def delete_file_method(self, row):
            """删除下载的文件"""
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件路径
                        filename = task.get('manager').filename
                        if not filename:
                            continue
                        
                        filepath = os.path.join(self.save_path, filename)
                        if not os.path.exists(filepath):
                            QMessageBox.warning(self, "错误", f"文件不存在: {filepath}")
                            return
                        
                        # 确认删除
                        confirm = QMessageBox.question(self, "确认删除", 
                                                     f"确定要删除文件 {filename} 吗？",
                                                     QMessageBox.Yes | QMessageBox.No)
                        if confirm == QMessageBox.Yes:
                            os.remove(filepath)
                            QMessageBox.information(self, "成功", f"文件已删除: {filename}")
                            print(f"删除文件: {filepath}")
                            
                            # 也可以从任务列表中移除该任务
                            # self.download_tasks.remove(task)
                            # self.task_window.download_table.removeRow(row)
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法删除文件: {str(e)}")
                    break
        
        def open_folder_method(self, row):
            """打开文件所在文件夹"""
            for task in self.download_tasks:
                if task['row'] == row:
                    try:
                        # 获取文件夹路径
                        folder_path = self.save_path
                        if not os.path.exists(folder_path):
                            QMessageBox.warning(self, "错误", f"文件夹不存在: {folder_path}")
                            return
                        
                        # 使用系统默认文件管理器打开文件夹
                        import subprocess
                        import sys
                        
                        if sys.platform == 'win32':
                            os.startfile(folder_path)
                        elif sys.platform == 'darwin':  # macOS
                            subprocess.call(['open', folder_path])
                        else:  # Linux
                            subprocess.call(['xdg-open', folder_path])
                            
                        print(f"打开文件夹: {folder_path}")
                    except Exception as e:
                        QMessageBox.warning(self, "错误", f"无法打开文件夹: {str(e)}")
                    break
        
        # 动态绑定方法到任务窗口
        self.task_window.open_file = types.MethodType(open_file_method, self)
        self.task_window.delete_file = types.MethodType(delete_file_method, self)
        self.task_window.open_folder = types.MethodType(open_folder_method, self)
        
    def on_minimize_to_tray(self):
        """处理最小化到托盘的逻辑"""
        # 检查是否有活跃的下载任务
        active_downloads = False
        for task in self.download_tasks:
            if task['status'] == 'running':
                active_downloads = True
                break
                
        # 显示通知
        tray_icon = self.title_bar.tray_icon
        if tray_icon.isSystemTrayAvailable() and tray_icon.supportsMessages():
            # 获取图标实例
            notification_icon = self.app_icon
            
            if active_downloads:
                tray_icon.showMessage(
                    "Hanabi Download Manager",
                    "应用程序将在后台继续下载，双击托盘图标可以恢复窗口。",
                    notification_icon,
                    3000  # 显示3秒
                )
            else:
                tray_icon.showMessage(
                    "Hanabi Download Manager",
                    "应用程序已最小化到系统托盘，双击托盘图标可以恢复窗口。",
                    notification_icon,
                    3000  # 显示3秒
                )
                
        # 记录状态
        self.is_minimized_to_tray = True
        
        # 检查是否有活跃下载任务，只有存在活跃任务时才保存状态
        if active_downloads:
            self.save_application_state()
    
    def save_application_state(self):
        """保存应用状态"""
        try:
            # 保存活跃下载任务状态等
            active_tasks = []
            for task in self.download_tasks:
                if task['status'] in ['running', 'paused']:
                    active_tasks.append({
                        'url': task['manager'].url,
                        'filename': task['manager'].filename,
                        'status': task['status'],
                        'progress': task['manager'].get_progress()
                    })
            
            # 如果有需要，可以将状态写入临时文件
            # import tempfile
            # import json
            # with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            #     json.dump(active_tasks, f)
            #     self.state_file = f.name
            
            print(f"[DEBUG] 已保存{len(active_tasks)}个活跃任务的状态")
        except Exception as e:
            print(f"[ERROR] 保存应用状态失败: {str(e)}")
        
    @staticmethod
    def get_resource_path(relative_path):
        """获取资源文件的绝对路径，适用于开发环境和打包环境"""
        import os
        import sys
        
        # 统一处理路径分隔符
        relative_path = relative_path.replace('/', os.sep)
        
        if getattr(sys, 'frozen', False):
            # 如果是打包环境
            base_path = os.path.dirname(sys.executable)
            # 获取应用安装目录 (HanabiDownloadManager)
            app_dir = os.path.basename(base_path)
            if app_dir != "HanabiDownloadManager":
                # 检查是否在上级目录
                parent_dir = os.path.dirname(base_path)
                if os.path.basename(parent_dir) == "HanabiDownloadManager":
                    base_path = parent_dir
                    
            # 直接构建资源路径
            resource_path = os.path.join(base_path, "resources", os.path.basename(relative_path))
            
            # 调试信息
            print(f"应用基础路径: {base_path}")
            print(f"尝试加载资源: {resource_path}")
            
            if os.path.exists(resource_path):
                return resource_path
                
            # 向上一级查找
            parent_resource_path = os.path.join(os.path.dirname(base_path), "resources", os.path.basename(relative_path))
            if os.path.exists(parent_resource_path):
                return parent_resource_path
                
            # 在当前目录查找
            direct_resource = os.path.join(base_path, os.path.basename(relative_path))
            if os.path.exists(direct_resource):
                return direct_resource
                
            # 搜索logo.png
            if os.path.basename(relative_path) == "logo.png":
                print("正在搜索logo.png文件...")
                for root, dirs, files in os.walk(base_path, topdown=True):
                    if "logo.png" in files:
                        logo_path = os.path.join(root, "logo.png")
                        print(f"找到logo文件: {logo_path}")
                        return logo_path
            
            # 查看基础目录内容
            print(f"目录 {base_path} 内容:")
            try:
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path):
                        print(f"- 目录: {item}")
                        # 检查resources目录
                        if item == "resources":
                            resources_dir = item_path
                            print(f"  Resources目录内容:")
                            for res_item in os.listdir(resources_dir):
                                print(f"  - {res_item}")
                    else:
                        print(f"- 文件: {item}")
            except Exception as e:
                print(f"列出目录内容出错: {str(e)}")
                
            # 返回硬编码的正确路径
            hardcoded_path = "E:\\HanabiDownloadManager\\resources\\" + os.path.basename(relative_path)
            if os.path.exists(hardcoded_path):
                print(f"使用硬编码路径: {hardcoded_path}")
                return hardcoded_path
                
            return resource_path
        else:
            # 如果是开发环境
            base_path = os.path.dirname(os.path.abspath(__file__))
            # 转到项目根目录
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(base_path))))
            return os.path.join(base_path, relative_path)
        