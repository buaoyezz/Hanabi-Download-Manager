#!/usr/bin/env python
"""
花火下载管理器 - 调试页面模块

提供用于开发和测试的调试功能页面，包括崩溃测试、日志查看和系统监控等。
"""

import os
import sys
import platform
import traceback
import threading
import time
import psutil
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QTabWidget, QTextEdit, QGridLayout, 
    QGroupBox, QComboBox, QSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QScrollArea, QSizePolicy,
    QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QFont, QColor

from core.log.log_manager import log

# 定义通用样式
CARD_STYLE = """
    background-color: #2C2C2C;
    border-radius: 10px;
    border: 1px solid #3C3C3C;
    padding: 15px;
    margin: 5px;
"""

TITLE_STYLE = """
    color: #FFFFFF;
    font-size: 14pt;
    font-weight: bold;
    margin-bottom: 10px;
"""

BUTTON_STYLE = """
    QPushButton {
        background-color: #7E57C2;
        color: #FFFFFF;
        border-radius: 5px;
        padding: 8px 15px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #9575CD;
    }
    QPushButton:pressed {
        background-color: #673AB7;
    }
    QPushButton:disabled {
        background-color: #555555;
        color: #AAAAAA;
    }
"""

TEXT_STYLE = """
    color: #FFFFFF;
    background-color: #383838;
    border-radius: 5px;
    border: 1px solid #555555;
    padding: 10px;
"""

COMBOBOX_STYLE = """
    QComboBox {
        color: #FFFFFF;
        background-color: #383838;
        border: 1px solid #555555;
        border-radius: 5px;
        padding: 5px 10px;
        min-width: 100px;
    }
    QComboBox QAbstractItemView {
        color: #FFFFFF;
        background-color: #383838;
        border: 1px solid #555555;
        selection-background-color: #7E57C2;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
"""

class SystemInfoWidget(QWidget):
    """系统信息显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.update_system_info()
    
    def setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建卡片容器
        card = QWidget()
        card.setStyleSheet(CARD_STYLE)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        
        # 系统信息标题
        title = QLabel("系统信息")
        title.setStyleSheet(TITLE_STYLE)
        card_layout.addWidget(title)
        
        # 创建滚动区域以适应不同屏幕大小
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2A2A2A;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 信息显示容器
        info_container = QWidget()
        info_container_layout = QVBoxLayout(info_container)
        
        # 信息显示区域
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.info_text.setStyleSheet(TEXT_STYLE)
        info_container_layout.addWidget(self.info_text)
        
        scroll_area.setWidget(info_container)
        card_layout.addWidget(scroll_area, 1)  # 给滚动区域分配伸缩空间
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新系统信息")
        refresh_btn.setStyleSheet(BUTTON_STYLE)
        refresh_btn.clicked.connect(self.update_system_info)
        
        # 添加按钮容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.addStretch(1)
        button_layout.addWidget(refresh_btn)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        card_layout.addWidget(button_container)
        main_layout.addWidget(card)
    
    def update_system_info(self):
        """更新系统信息"""
        try:
            info = []
            
            # 系统基本信息
            info.append(f"操作系统: {platform.system()} {platform.release()} {platform.version()}")
            info.append(f"架构: {platform.machine()}")
            info.append(f"处理器: {platform.processor()}")
            
            # Python信息
            info.append(f"Python版本: {sys.version}")
            info.append(f"Python路径: {sys.executable}")
            
            # 内存信息
            memory = psutil.virtual_memory()
            info.append(f"总内存: {memory.total / (1024**3):.2f} GB")
            info.append(f"可用内存: {memory.available / (1024**3):.2f} GB")
            info.append(f"内存占用率: {memory.percent}%")
            
            # 磁盘信息
            for disk in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    info.append(f"磁盘 {disk.device} ({disk.mountpoint}):")
                    info.append(f"  总空间: {usage.total / (1024**3):.2f} GB")
                    info.append(f"  已用空间: {usage.used / (1024**3):.2f} GB")
                    info.append(f"  剩余空间: {usage.free / (1024**3):.2f} GB")
                    info.append(f"  使用率: {usage.percent}%")
                except PermissionError:
                    pass
                    
            # 进程信息
            current_process = psutil.Process(os.getpid())
            info.append(f"进程ID: {current_process.pid}")
            info.append(f"进程内存使用: {current_process.memory_info().rss / (1024**2):.2f} MB")
            info.append(f"CPU使用率: {current_process.cpu_percent()}%")
            info.append(f"线程数: {current_process.num_threads()}")
            
            # 更新文本显示
            self.info_text.setText("\n".join(info))
            
        except Exception as e:
            self.info_text.setText(f"获取系统信息出错: {e}\n{traceback.format_exc()}")

class LogViewerWidget(QWidget):
    """日志查看组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_file_path = None
        self.watching = False
        self.watch_timer = None
        self.setup_ui()
    
    def setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建主卡片
        main_card = QWidget()
        main_card.setStyleSheet(CARD_STYLE)
        main_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout = QVBoxLayout(main_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(15)
        
        # 标题
        title = QLabel("日志查看器")
        title.setStyleSheet(TITLE_STYLE)
        card_layout.addWidget(title)
        
        # 控制面板卡片
        control_card = QWidget()
        control_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 12px;
        """)
        control_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        control_layout = QVBoxLayout(control_card)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setSpacing(15)
        
        # 顶部控件行
        top_control_layout = QHBoxLayout()
        top_control_layout.setSpacing(15)
        
        # 日志级别选择
        filter_group = QWidget()
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(10)
        
        level_label = QLabel("日志级别:")
        level_label.setStyleSheet("color: #FFFFFF;")
        filter_layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText("WARNING")  # 默认显示警告级别
        self.level_combo.setStyleSheet(COMBOBOX_STYLE)
        self.level_combo.currentTextChanged.connect(self.filter_log_level)
        filter_layout.addWidget(self.level_combo)
        top_control_layout.addWidget(filter_group)
        
        # 关键词搜索
        search_group = QWidget()
        search_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        search_layout = QHBoxLayout(search_group)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        search_label = QLabel("关键词搜索:")
        search_label.setStyleSheet("color: #FFFFFF;")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_input.setStyleSheet("""
            QLineEdit {
                color: #FFFFFF;
                background-color: #2A2A2A;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 6px 10px;
                selection-background-color: #7E57C2;
            }
        """)
        self.search_input.setPlaceholderText("输入搜索内容")
        self.search_input.textChanged.connect(self.search_log)
        search_layout.addWidget(self.search_input)
        
        search_btn = QPushButton("搜索")
        search_btn.setStyleSheet(BUTTON_STYLE)
        search_btn.clicked.connect(lambda: self.search_log(self.search_input.text()))
        search_layout.addWidget(search_btn)
        
        top_control_layout.addWidget(search_group, 1)  # 使搜索区域可伸缩
        
        control_layout.addLayout(top_control_layout)
        
        # 第二行控件
        bottom_control_layout = QHBoxLayout()
        bottom_control_layout.setSpacing(15)
        
        # 自动刷新选项
        refresh_group = QWidget()
        refresh_group.setStyleSheet("""
            background-color: #2A2A2A;
            border-radius: 5px;
            padding: 5px;
        """)
        refresh_layout = QHBoxLayout(refresh_group)
        refresh_layout.setContentsMargins(10, 5, 10, 5)
        refresh_layout.setSpacing(10)
        
        self.auto_refresh = QCheckBox("自动刷新")
        self.auto_refresh.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555555;
                background: #2A2A2A;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #7E57C2;
                background: #7E57C2;
                border-radius: 3px;
            }
        """)
        self.auto_refresh.setChecked(False)
        self.auto_refresh.stateChanged.connect(self.toggle_watch)
        refresh_layout.addWidget(self.auto_refresh)
        
        interval_label = QLabel("刷新间隔:")
        interval_label.setStyleSheet("color: #FFFFFF;")
        refresh_layout.addWidget(interval_label)
        
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(1, 60)
        self.refresh_interval.setValue(5)
        self.refresh_interval.setSuffix(" 秒")
        self.refresh_interval.setStyleSheet("""
            QSpinBox {
                color: #FFFFFF;
                background-color: #2A2A2A;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 2px 5px;
                min-width: 70px;
            }
        """)
        refresh_layout.addWidget(self.refresh_interval)
        
        bottom_control_layout.addWidget(refresh_group)
        
        # 按钮组
        button_group = QWidget()
        button_layout = QHBoxLayout(button_group)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        # 打开日志按钮
        self.open_btn = QPushButton("打开日志文件")
        self.open_btn.setStyleSheet(BUTTON_STYLE)
        self.open_btn.clicked.connect(self.open_log_file)
        button_layout.addWidget(self.open_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet(BUTTON_STYLE)
        self.refresh_btn.clicked.connect(self.load_log_content)
        button_layout.addWidget(self.refresh_btn)
        
        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setStyleSheet(BUTTON_STYLE.replace("#7E57C2", "#E57373").replace("#9575CD", "#EF9A9A").replace("#673AB7", "#D32F2F"))
        self.clear_btn.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_btn)
        
        bottom_control_layout.addWidget(button_group)
        bottom_control_layout.addStretch(1)  # 添加弹性空间
        
        control_layout.addLayout(bottom_control_layout)
        card_layout.addWidget(control_card)
        
        # 日志显示卡片
        log_display_card = QWidget()
        log_display_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 10px;
        """)
        
        log_display_layout = QVBoxLayout(log_display_card)
        log_display_layout.setContentsMargins(10, 10, 10, 10)
        log_display_layout.setSpacing(10)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        font = QFont("Consolas, Courier New, Monospace", 9)
        self.log_text.setFont(font)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_text.setStyleSheet("""
            color: #FFFFFF;
            background-color: #262626;
            border: 1px solid #3C3C3C;
            border-radius: 5px;
            padding: 8px;
        """)
        log_display_layout.addWidget(self.log_text)
        
        # 状态栏
        status_bar = QWidget()
        status_bar.setStyleSheet("""
            background-color: #2A2A2A;
            border-radius: 5px;
            padding: 2px;
        """)
        
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_label = QLabel("未加载日志文件")
        self.status_label.setStyleSheet("""
            color: #BBBBBB;
            font-size: 11px;
        """)
        status_layout.addWidget(self.status_label)
        
        # 添加日志行数显示
        self.lines_count_label = QLabel("0 行")
        self.lines_count_label.setStyleSheet("""
            color: #BBBBBB;
            font-size: 11px;
        """)
        status_layout.addWidget(self.lines_count_label, 0, Qt.AlignRight)
        
        log_display_layout.addWidget(status_bar)
        card_layout.addWidget(log_display_card, 1)  # 让日志区域可伸缩
        
        main_layout.addWidget(main_card)
        
        # 尝试加载当前日志
        self.log_file_path = log.get_log_file_path()
        if self.log_file_path:
            self.load_log_content()
    
    def open_log_file(self):
        """打开日志文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择日志文件", "", "日志文件 (*.log);;所有文件 (*.*)"
        )
        
        if file_path:
            self.log_file_path = file_path
            self.load_log_content()
    
    def load_log_content(self):
        """加载日志文件内容"""
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            self.status_label.setText("日志文件不存在")
            return
        
        try:
            with open(self.log_file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            # 应用日志级别过滤
            self.log_text.setText(content)
            self.filter_log_level(self.level_combo.currentText())
            
            # 更新状态
            file_size = os.path.getsize(self.log_file_path) / 1024
            self.status_label.setText(
                f"已加载: {self.log_file_path} ({file_size:.2f} KB) - {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # 更新行数显示
            line_count = content.count('\n') + 1
            self.lines_count_label.setText(f"{line_count} 行")
            
            # 滚动到底部
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
            
            # 如果搜索框有内容，应用搜索
            if hasattr(self, 'search_input') and self.search_input.text():
                self.search_log(self.search_input.text())
            
        except Exception as e:
            self.status_label.setText(f"加载日志失败: {e}")
    
    def filter_log_level(self, level):
        """根据日志级别过滤内容"""
        if not self.log_text.toPlainText():
            return
        
        # 如果是ALL级别，显示所有内容
        if level == "ALL":
            self.load_log_content()
            return
        
        try:
            with open(self.log_file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            filtered_lines = []
            for line in lines:
                if f"│ {level}" in line:
                    filtered_lines.append(line)
                # 特别处理警告类日志，使其显示出来
                elif level == "WARNING" and ("WARNING" in line or "timed out" in line or "timeout" in line):
                    filtered_lines.append(line)
            
            self.log_text.setText("".join(filtered_lines))
            
            # 更新行数显示
            line_count = len(filtered_lines)
            self.lines_count_label.setText(f"{line_count} 行")
            
        except Exception as e:
            self.status_label.setText(f"过滤日志失败: {e}")
    
    def search_log(self, text):
        """搜索日志内容"""
        if not text or not self.log_text.toPlainText():
            return
        
        current_text = self.log_text.toPlainText()
        lines = current_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            if text.lower() in line.lower():
                filtered_lines.append(line)
        
        if filtered_lines:
            self.log_text.setText('\n'.join(filtered_lines))
            
            # 更新行数显示
            self.lines_count_label.setText(f"{len(filtered_lines)} 行")
        else:
            # 如果没找到，显示提示并恢复原始过滤
            self.status_label.setText(f"未找到匹配内容: {text}")
            self.filter_log_level(self.level_combo.currentText())
    
    def clear_log(self):
        """清空日志显示区域"""
        self.log_text.clear()
        self.status_label.setText("日志显示已清空")
        self.lines_count_label.setText("0 行")
    
    def toggle_watch(self, state):
        """切换日志自动刷新"""
        if state == Qt.Checked:
            # 启动定时器
            if not self.watch_timer:
                self.watch_timer = QTimer(self)
                self.watch_timer.timeout.connect(self.load_log_content)
            
            interval = self.refresh_interval.value() * 1000
            self.watch_timer.start(interval)
            self.watching = True
            self.status_label.setText(f"自动刷新已启动，间隔: {self.refresh_interval.value()} 秒")
            
        else:
            # 停止定时器
            if self.watch_timer:
                self.watch_timer.stop()
            self.watching = False
            self.status_label.setText("自动刷新已停止")

class PerformanceMonitor(QThread):
    """性能监控线程"""
    update_signal = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        """运行监控线程"""
        while self.running:
            try:
                stats = {}
                
                # 获取CPU和内存使用情况
                process = psutil.Process(os.getpid())
                stats['cpu'] = process.cpu_percent(interval=1)
                stats['memory'] = process.memory_info().rss / (1024 * 1024)
                stats['threads'] = process.num_threads()
                
                # 系统内存
                vm = psutil.virtual_memory()
                stats['system_memory_percent'] = vm.percent
                stats['system_memory_available'] = vm.available / (1024 * 1024)
                
                # 发送更新信号
                self.update_signal.emit(stats)
                
            except Exception:
                pass
            
            # 休眠一秒
            time.sleep(1)
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.wait()

class PerformanceWidget(QWidget):
    """性能监控组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.monitor = None
        self.setup_ui()
        self.start_monitoring()
    
    def setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建主卡片
        main_card = QWidget()
        main_card.setStyleSheet(CARD_STYLE)
        main_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout = QVBoxLayout(main_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(15)
        
        # 标题
        title = QLabel("性能监控")
        title.setStyleSheet(TITLE_STYLE)
        card_layout.addWidget(title)
        
        # 性能指标卡片
        stats_card = QWidget()
        stats_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 15px;
        """)
        stats_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        stats_layout = QGridLayout(stats_card)
        stats_layout.setVerticalSpacing(15)
        stats_layout.setHorizontalSpacing(25)
        stats_layout.setContentsMargins(15, 15, 15, 15)
        
        # 为网格中所有标签设置统一样式
        label_style = """
            color: #FFFFFF;
            font-size: 12px;
        """
        
        value_style = """
            color: #FFFFFF;
            font-size: 14px;
            font-weight: bold;
        """
        
        # CPU使用率
        cpu_title = QLabel("CPU使用率:")
        cpu_title.setStyleSheet(label_style)
        stats_layout.addWidget(cpu_title, 0, 0)
        self.cpu_label = QLabel("0%")
        self.cpu_label.setStyleSheet(value_style)
        stats_layout.addWidget(self.cpu_label, 0, 1)
        
        # 内存使用
        mem_title = QLabel("内存使用:")
        mem_title.setStyleSheet(label_style)
        stats_layout.addWidget(mem_title, 1, 0)
        self.memory_label = QLabel("0 MB")
        self.memory_label.setStyleSheet(value_style)
        stats_layout.addWidget(self.memory_label, 1, 1)
        
        # 线程数
        thread_title = QLabel("线程数:")
        thread_title.setStyleSheet(label_style)
        stats_layout.addWidget(thread_title, 2, 0)
        self.threads_label = QLabel("0")
        self.threads_label.setStyleSheet(value_style)
        stats_layout.addWidget(self.threads_label, 2, 1)
        
        # 系统内存使用率
        sys_mem_title = QLabel("系统内存使用率:")
        sys_mem_title.setStyleSheet(label_style)
        stats_layout.addWidget(sys_mem_title, 0, 2)
        self.system_memory_percent_label = QLabel("0%")
        self.system_memory_percent_label.setStyleSheet(value_style)
        stats_layout.addWidget(self.system_memory_percent_label, 0, 3)
        
        # 系统可用内存
        sys_avail_title = QLabel("系统可用内存:")
        sys_avail_title.setStyleSheet(label_style)
        stats_layout.addWidget(sys_avail_title, 1, 2)
        self.system_memory_available_label = QLabel("0 MB")
        self.system_memory_available_label.setStyleSheet(value_style)
        stats_layout.addWidget(self.system_memory_available_label, 1, 3)
        
        card_layout.addWidget(stats_card)
        
        # 控制按钮卡片
        control_card = QWidget()
        control_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 10px;
        """)
        
        button_layout = QHBoxLayout(control_card)
        button_layout.setContentsMargins(10, 10, 10, 10)
        button_layout.setSpacing(15)
        
        self.start_button = QPushButton("开始监控")
        self.start_button.setStyleSheet(BUTTON_STYLE)
        self.start_button.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止监控")
        self.stop_button.setStyleSheet(BUTTON_STYLE)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        button_layout.addStretch(1)
        
        card_layout.addWidget(control_card)
        card_layout.addStretch(1)
        
        main_layout.addWidget(main_card)
    
    def start_monitoring(self):
        """开始监控"""
        if not self.monitor:
            self.monitor = PerformanceMonitor()
            self.monitor.update_signal.connect(self.update_stats)
        
        self.monitor.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
    
    def stop_monitoring(self):
        """停止监控"""
        if self.monitor:
            self.monitor.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    @Slot(dict)
    def update_stats(self, stats):
        """更新统计数据显示"""
        self.cpu_label.setText(f"{stats['cpu']:.1f}%")
        self.memory_label.setText(f"{stats['memory']:.1f} MB")
        self.threads_label.setText(f"{stats['threads']}")
        self.system_memory_percent_label.setText(f"{stats['system_memory_percent']:.1f}%")
        self.system_memory_available_label.setText(f"{stats['system_memory_available']:.1f} MB")
        
        # 根据使用率设置颜色
        if stats['cpu'] > 80:
            self.cpu_label.setStyleSheet("color: #FF5252; font-size: 14px; font-weight: bold;")
        elif stats['cpu'] > 50:
            self.cpu_label.setStyleSheet("color: #FFB74D; font-size: 14px; font-weight: bold;")
        else:
            self.cpu_label.setStyleSheet("color: #81C784; font-size: 14px; font-weight: bold;")
        
        if stats['system_memory_percent'] > 90:
            self.system_memory_percent_label.setStyleSheet("color: #FF5252; font-size: 14px; font-weight: bold;")
        elif stats['system_memory_percent'] > 70:
            self.system_memory_percent_label.setStyleSheet("color: #FFB74D; font-size: 14px; font-weight: bold;")
        else:
            self.system_memory_percent_label.setStyleSheet("color: #81C784; font-size: 14px; font-weight: bold;")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.monitor:
            self.monitor.stop()
        super().closeEvent(event)

class CrashTestWidget(QWidget):
    """崩溃测试组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 创建滚动区域以适应不同屏幕大小
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2A2A2A;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建主卡片作为滚动区域的内容
        main_card = QWidget()
        main_card.setStyleSheet(CARD_STYLE)
        main_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        card_layout = QVBoxLayout(main_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(15)
        
        # 标题
        title = QLabel("崩溃测试")
        title.setStyleSheet(TITLE_STYLE)
        card_layout.addWidget(title)
        
        # 警告卡片
        warning_card = QWidget()
        warning_card.setStyleSheet("""
            background-color: #B71C1C;
            border-radius: 8px;
            padding: 15px;
        """)
        warning_layout = QVBoxLayout(warning_card)
        warning_layout.setContentsMargins(15, 15, 15, 15)
        
        warning = QLabel("警告：这些选项将导致程序崩溃，用于测试崩溃处理机制。")
        warning.setStyleSheet("color: white; font-weight: bold;")
        warning_layout.addWidget(warning)
        
        card_layout.addWidget(warning_card)
        
        # 崩溃按钮卡片
        buttons_card = QWidget()
        buttons_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 15px;
        """)
        buttons_layout = QVBoxLayout(buttons_card)
        buttons_layout.setContentsMargins(15, 15, 15, 15)
        buttons_layout.setSpacing(15)
        
        # 子标题
        subtitle = QLabel("选择崩溃方式")
        subtitle.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
        buttons_layout.addWidget(subtitle)
        
        # 崩溃按钮样式
        crash_button_style = """
            QPushButton {
                background-color: #C75450;
                color: #FFFFFF;
                border-radius: 5px;
                padding: 10px 15px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #D76D6B;
            }
            QPushButton:pressed {
                background-color: #B74440;
            }
        """
        
        # 零除错误
        zero_div_btn = QPushButton("零除错误")
        zero_div_btn.setStyleSheet(crash_button_style)
        zero_div_btn.clicked.connect(self.crash_zero_division)
        buttons_layout.addWidget(zero_div_btn)
        
        # 空指针
        null_ptr_btn = QPushButton("空指针引用")
        null_ptr_btn.setStyleSheet(crash_button_style)
        null_ptr_btn.clicked.connect(self.crash_null_pointer)
        buttons_layout.addWidget(null_ptr_btn)
        
        # 索引越界
        index_btn = QPushButton("索引越界")
        index_btn.setStyleSheet(crash_button_style)
        index_btn.clicked.connect(self.crash_index_error)
        buttons_layout.addWidget(index_btn)
        
        # 线程崩溃
        thread_btn = QPushButton("线程崩溃")
        thread_btn.setStyleSheet(crash_button_style)
        thread_btn.clicked.connect(self.crash_thread)
        buttons_layout.addWidget(thread_btn)
        
        # 自定义异常
        custom_btn = QPushButton("自定义异常")
        custom_btn.setStyleSheet(crash_button_style)
        custom_btn.clicked.connect(self.crash_custom)
        buttons_layout.addWidget(custom_btn)
        
        card_layout.addWidget(buttons_card)
        
        # 说明卡片
        note_card = QWidget()
        note_card.setStyleSheet("""
            background-color: #383838;
            border-radius: 8px;
            padding: 15px;
        """)
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(15, 15, 15, 15)
        
        note = QLabel("说明：崩溃后，系统应该显示崩溃报告对话框，用于收集和分析错误信息。")
        note.setStyleSheet("color: #BBBBBB;")
        note.setWordWrap(True)
        note_layout.addWidget(note)
        
        card_layout.addWidget(note_card)
        
        # 添加弹性空间
        card_layout.addStretch(1)
        main_layout.addWidget(scroll_area)
    
    def crash_zero_division(self):
        """触发零除错误"""
        if QMessageBox.warning(
            self, 
            "确认操作", 
            "这将导致程序崩溃，确定继续吗？", 
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            # 故意触发零除错误
            result = 1 / 0
            print(f"这行代码不会执行: {result}")
    
    def crash_null_pointer(self):
        """触发空指针引用"""
        if QMessageBox.warning(
            self, 
            "确认操作", 
            "这将导致程序崩溃，确定继续吗？", 
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            # 故意触发空引用
            none_obj = None
            none_obj.some_method()
    
    def crash_index_error(self):
        """触发索引越界错误"""
        if QMessageBox.warning(
            self, 
            "确认操作", 
            "这将导致程序崩溃，确定继续吗？", 
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            # 故意触发索引越界
            empty_list = []
            item = empty_list[10]
            print(f"这行代码不会执行: {item}")
    
    def crash_thread(self):
        """在线程中触发崩溃"""
        if QMessageBox.warning(
            self, 
            "确认操作", 
            "这将导致程序崩溃，确定继续吗？", 
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            # 创建一个会崩溃的线程
            def crash_func():
                time.sleep(1)  # 延迟一秒
                # 故意触发错误
                raise RuntimeError("线程崩溃测试")
            
            thread = threading.Thread(target=crash_func)
            thread.daemon = True
            thread.start()
    
    def crash_custom(self):
        """触发自定义异常"""
        if QMessageBox.warning(
            self, 
            "确认操作", 
            "这将导致程序崩溃，确定继续吗？", 
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            # 故意触发自定义异常
            raise Exception("这是一个自定义测试异常，用于测试崩溃报告系统")

class DebugPagesWidget(QWidget):
    """调试页面主组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 标题卡片
        title_card = QWidget()
        title_card.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #673AB7, stop:1 #9C27B0);
            border-radius: 12px;
            color: white;
        """)
        title_card.setMaximumHeight(90)
        title_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        title_layout = QHBoxLayout(title_card)
        title_layout.setContentsMargins(25, 15, 25, 15)
        
        # 左侧标题区域
        title_area = QWidget()
        title_area_layout = QVBoxLayout(title_area)
        title_area_layout.setContentsMargins(0, 0, 0, 0)
        title_area_layout.setSpacing(5)
        
        # 标题
        title = QLabel("调试与开发工具")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #FFFFFF;")
        title_area_layout.addWidget(title)
        
        # 副标题
        subtitle = QLabel("用于开发和测试的工具集")
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        title_area_layout.addWidget(subtitle)
        
        title_layout.addWidget(title_area)
        
        # 右侧说明
        description = QLabel("这些工具用于开发和测试，请谨慎使用")
        description.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        title_layout.addWidget(description, 0, Qt.AlignRight | Qt.AlignVCenter)
        
        main_layout.addWidget(title_card)
        
        # 创建内容卡片
        content_card = QWidget()
        content_card.setStyleSheet("""
            background-color: #262626;
            border-radius: 12px;
        """)
        content_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建选项卡组件
        tab_widget = QTabWidget()
        tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            
            QTabBar::tab {
                background-color: #3C3C3C;
                color: #FFFFFF;
                padding: 12px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 120px;
                font-size: 12px;
            }
            
            QTabBar::tab:selected {
                background-color: #7E57C2;
                color: #FFFFFF;
                font-weight: bold;
            }
            
            QTabBar::tab:!selected {
                background-color: #323232;
                color: #CCCCCC;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #4C4C4C;
            }
        """)
        
        # 调整选项卡顺序，将日志查看放在最前面
        tab_widget.addTab(LogViewerWidget(), "日志查看")
        tab_widget.addTab(SystemInfoWidget(), "系统信息")
        tab_widget.addTab(PerformanceWidget(), "性能监控")
        tab_widget.addTab(CrashTestWidget(), "崩溃测试")
        
        content_layout.addWidget(tab_widget)
        main_layout.addWidget(content_card, 1)
        
        # 添加底部卡片
        footer_card = QWidget()
        footer_card.setStyleSheet("""
            background-color: #2A2A2A;
            border-radius: 8px;
        """)
        footer_card.setMaximumHeight(40)
        footer_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(15, 5, 15, 5)
        
        # 添加底部状态信息
        status = QLabel(f"花火下载管理器 - 调试模式 - {datetime.now().strftime('%Y-%m-%d')}")
        status.setStyleSheet("color: #999999; font-size: 11px;")
        footer_layout.addWidget(status)
        
        main_layout.addWidget(footer_card)

# 测试代码
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = DebugPagesWidget()
    window.show()
    sys.exit(app.exec())
