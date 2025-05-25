#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志窗口模块 - 用于显示程序运行时的日志信息
"""

import os
import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLabel, QPushButton, QComboBox,
    QCheckBox, QLineEdit, QSplitter, QToolBar,
    QStatusBar, QFileDialog, QFrame, QToolButton, 
    QTabWidget, QSpacerItem, QSizePolicy, QMessageBox,
    QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QTextCursor, QIcon, QColor, QTextCharFormat, QPainter, QPainterPath, QBrush

# 导入日志管理器
from core.log.log_manager import log
from core.font.font_manager import FontManager

# 日志观察者 - 用于接收日志并通过信号转发
class LogObserver(QObject):
    """日志观察者，接收日志并通过信号发送到UI线程"""
    # 定义信号：日志级别, 时间戳, 发送者, 消息
    log_received = Signal(str, float, str, str)
    
    def __init__(self):
        super().__init__()
        # 注册到日志管理器
        log.add_observer(self)
        log.info("日志观察者已初始化")
    
    def on_log(self, level, timestamp, sender, message):
        """接收日志的回调方法，由LogManager调用
        
        Args:
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            timestamp: 日志时间戳
            sender: 发送者 (通常是文件名)
            message: 日志消息
        """
        try:
            # 发送信号，将日志信息传递给UI线程
            self.log_received.emit(level, timestamp, sender, message)
        except Exception as e:
            print(f"处理日志时出错: {str(e)}")
    
    def __del__(self):
        """析构时取消注册"""
        try:
            log.remove_observer(self)
        except:
            pass

class RoundedWidget(QWidget):
    """圆角背景组件"""
    def __init__(self, parent=None, radius=10, bg_color="#2C2C2C", border_color=None):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = bg_color
        self.border_color = border_color
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect, self.radius, self.radius)
        
        # 绘制背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.drawPath(path)
        
        # 绘制边框
        if self.border_color:
            painter.setPen(QColor(self.border_color))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

class IconButton(QToolButton):
    """图标按钮"""
    def __init__(self, icon_name, tooltip, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        
        # 设置图标
        if not icon_name.startswith("ic_fluent_"):
            icon_name = f"ic_fluent_{icon_name}"
        icon_text = self.font_manager.get_icon_text(icon_name)
        
        self.setText(icon_text)
        self.setFont(QFont("FluentSystemIcons-Regular", 16))
        self.setFixedSize(36, 36)
        
        # 设置样式
        self.setStyleSheet("""
            QToolButton {
                color: #AAAAAA;
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
            }
        """)

class LogFilterBar(QWidget):
    """日志过滤工具栏"""
    filter_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        self.setObjectName("logFilterBar")
        
        # 获取图标
        self.icon_down_arrow = self.font_manager.get_icon_text("ic_fluent_chevron_down_20_filled")
        self.icon_checkmark = self.font_manager.get_icon_text("ic_fluent_checkmark_16_filled")
        
        # 创建布局
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 8, 12, 8)
        self.layout.setSpacing(10)
        
        # 日志级别过滤
        self.level_label = QLabel("日志级别:")
        self.font_manager.apply_font(self.level_label)
        self.level_label.setStyleSheet("color: #DDDDDD;")
        
        self.level_combo = QComboBox()
        self.level_combo.addItem("全部", "ALL")
        self.level_combo.addItem("调试", "DEBUG")
        self.level_combo.addItem("信息", "INFO")
        self.level_combo.addItem("警告", "WARNING")
        self.level_combo.addItem("错误", "ERROR")
        self.level_combo.addItem("严重错误", "CRITICAL")
        self.level_combo.setCurrentIndex(0)  # 默认选择全部
        self.font_manager.apply_font(self.level_combo)
        self.level_combo.currentIndexChanged.connect(self.on_filter_changed)
        
        # 搜索框
        self.search_label = QLabel("搜索:")
        self.font_manager.apply_font(self.search_label)
        self.search_label.setStyleSheet("color: #DDDDDD;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setMinimumWidth(200)
        self.font_manager.apply_font(self.search_input)
        self.search_input.textChanged.connect(self.on_filter_changed)
        
        # 自动滚动选项
        self.auto_scroll_checkbox = QCheckBox("自动滚动")
        self.auto_scroll_checkbox.setChecked(True)
        self.font_manager.apply_font(self.auto_scroll_checkbox)
        self.auto_scroll_checkbox.setStyleSheet("color: #DDDDDD;")
        
        # 清空按钮
        self.clear_button = QPushButton("清空日志")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.font_manager.apply_font(self.clear_button)
        
        # 导出按钮
        self.export_button = QPushButton("导出日志")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.font_manager.apply_font(self.export_button)
        
        # 添加组件到布局
        self.layout.addWidget(self.level_label)
        self.layout.addWidget(self.level_combo)
        self.layout.addWidget(self.search_label)
        self.layout.addWidget(self.search_input)
        self.layout.addWidget(self.auto_scroll_checkbox)
        self.layout.addStretch()
        self.layout.addWidget(self.clear_button)
        self.layout.addWidget(self.export_button)
        
        # 设置样式
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 100px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                font-family: "FluentSystemIcons-Regular";
                font-size: 12px;
                color: #FFFFFF;
                text-align: center;
            }}
            QComboBox QAbstractItemView {{
                background-color: #252526;
                color: #FFFFFF;
                border: 1px solid #444444;
                selection-background-color: #0E639C;
            }}
            QLineEdit {{
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 10px;
                selection-background-color: #0E639C;
            }}
            QPushButton {{
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #444444;
                border: 1px solid #555555;
            }}
            QPushButton:pressed {{
                background-color: #222222;
            }}
            QCheckBox {{
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid #444444;
                border-radius: 3px;
                background-color: #333333;
            }}
            QCheckBox::indicator:checked {{
                background-color: #0E639C;
                border: 1px solid #0E639C;
                font-family: "FluentSystemIcons-Regular";
                color: #FFFFFF;
                font-size: 10px;
                text-align: center;
            }}
        """)
    
    def on_filter_changed(self):
        self.filter_changed.emit()
    
    def get_level_filter(self):
        return self.level_combo.currentData()
    
    def get_search_text(self):
        return self.search_input.text().lower()
    
    def is_auto_scroll(self):
        return self.auto_scroll_checkbox.isChecked()

class LogTextDisplay(QTextEdit):
    """日志文本显示区域"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setLineWrapMode(QTextEdit.NoWrap)  # 不自动换行
        
        # 使用等宽字体
        monospace_font = QFont("Consolas", 10)
        monospace_font.setStyleHint(QFont.Monospace)
        self.setFont(monospace_font)
        
        # 设置样式
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #2D2D2D;
                border-radius: 6px;
                selection-background-color: #264F78;
                selection-color: #FFFFFF;
                padding: 10px;
            }
            QScrollBar:vertical {
                background: #252526;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #252526;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #424242;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #505050;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

class LogWindow(QMainWindow):
    """日志窗口，用于显示和过滤程序日志"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
        
        # 日志缓冲区，暂存要显示的日志
        self.log_buffer = []
        self.max_buffer_size = 1000  # 最大缓冲日志数量
        
        # 获取Fluent图标字符
        self.icon_down_arrow = self.font_manager.get_icon_text("ic_fluent_chevron_down_20_filled")
        self.icon_checkmark = self.font_manager.get_icon_text("ic_fluent_checkmark_16_filled")
        
        # 创建日志观察者，确保在缓冲区初始化之后
        self.log_observer = LogObserver()
        
        # 窗口设置
        self.setWindowTitle("Hanabi Download Manager - Debug Mode")
        self.setMinimumSize(900, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 创建UI
        self._setup_ui()
        
        # 连接日志观察者的信号
        self.log_observer.log_received.connect(self.add_log)
        
        # 启动自动刷新计时器
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.update_log_display)
        self.auto_refresh_timer.start(100)  # 每100ms刷新一次
        
        # 初始日志
        log.info("日志窗口已启动")
        
        # 应用暗色主题
        self._apply_theme()
        
        # 尝试设置窗口图标
        self._setup_window_icon()
    
    def _setup_ui(self):
        """设置UI组件"""
        # 中心部件
        central_widget = RoundedWidget(radius=10, bg_color="#252526")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 标题区域
        title_layout = QHBoxLayout()
        
        # 标题标签
        title_label = QLabel("Debug Mode")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #FFFFFF;
        """)
        self.font_manager.apply_font(title_label)
        
        # 标题右侧操作按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # 复制按钮
        self.copy_button = IconButton("copy_24_regular", "复制选中日志")
        self.copy_button.clicked.connect(self.copy_selected_logs)
        
        # 刷新按钮
        self.refresh_button = IconButton("arrow_sync_24_regular", "刷新日志")
        self.refresh_button.clicked.connect(self.update_log_display)
        
        # 关闭窗口按钮
        self.close_window_button = IconButton("dismiss_24_regular", "关闭日志窗口")
        self.close_window_button.clicked.connect(self.close)
        
        # 退出进程按钮
        self.exit_app_button = IconButton("power_24_regular", "退出整个应用程序")
        self.exit_app_button.clicked.connect(self.exit_application)
        self.exit_app_button.setStyleSheet("""
            QToolButton {
                color: #FF5252;
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: rgba(255, 82, 82, 0.2);
                color: #FF5252;
            }
            QToolButton:pressed {
                background-color: rgba(255, 82, 82, 0.1);
                color: #FF5252;
            }
        """)
        
        # 添加按钮到布局
        buttons_layout.addWidget(self.copy_button)
        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addWidget(self.close_window_button)
        buttons_layout.addWidget(self.exit_app_button)
        
        # 添加组件到标题布局
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addLayout(buttons_layout)
        
        # 添加标题布局
        main_layout.addLayout(title_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333; max-height: 1px;")
        main_layout.addWidget(separator)
        
        # 过滤工具栏
        self.filter_bar = LogFilterBar()
        self.filter_bar.filter_changed.connect(self.update_log_display)
        self.filter_bar.clear_button.clicked.connect(self.clear_logs)
        self.filter_bar.export_button.clicked.connect(self.export_logs)
        main_layout.addWidget(self.filter_bar)
        
        # 日志显示区域
        self.log_text = LogTextDisplay()
        main_layout.addWidget(self.log_text)
        
        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.log_count_label = QLabel("日志数量: 0")
        self.font_manager.apply_font(self.log_count_label)
        self.statusBar.addWidget(self.log_count_label)
    
    def _apply_theme(self):
        """应用应用程序主题"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QStatusBar {
                background-color: #007ACC;
                color: #FFFFFF;
                font-weight: bold;
            }
            QStatusBar QLabel {
                margin: 2px 5px;
                color: #FFFFFF;
            }
        """)
    
    def _setup_window_icon(self):
        """设置窗口图标"""
        try:
            # 尝试获取应用程序图标路径
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                    "resources", "logo.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            log.warning(f"设置窗口图标失败: {e}")
    
    @Slot(str, float, str, str)
    def add_log(self, level, timestamp, sender, message):
        """添加一条日志到缓冲区"""
        # 格式化时间戳
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        
        # 创建日志项
        log_entry = {
            "level": level,
            "timestamp": timestamp,
            "time_str": time_str,
            "sender": sender,
            "message": message
        }
        
        # 添加到缓冲区
        self.log_buffer.append(log_entry)
        
        # 限制缓冲区大小
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
    
    def update_log_display(self):
        """更新日志显示"""
        if not self.log_buffer:
            return
        
        # 保存当前滚动位置
        scrollbar = self.log_text.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
        
        # 获取过滤条件
        level_filter = self.filter_bar.get_level_filter()
        search_text = self.filter_bar.get_search_text()
        
        # 准备新的日志文本
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # 文本格式
        normal_format = QTextCharFormat()
        normal_format.setForeground(QColor("#FFFFFF"))
        
        debug_format = QTextCharFormat()
        debug_format.setForeground(QColor("#9CDCFE"))  # 浅蓝色
        
        info_format = QTextCharFormat()
        info_format.setForeground(QColor("#6A9955"))  # 绿色
        
        warning_format = QTextCharFormat()
        warning_format.setForeground(QColor("#DCDCAA"))  # 黄色
        
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#F14C4C"))  # 红色
        
        critical_format = QTextCharFormat()
        critical_format.setForeground(QColor("#FF0000"))  # 深红色
        critical_format.setFontWeight(QFont.Bold)
        
        # 清空文本框
        self.log_text.clear()
        
        # 显示过滤后的日志
        displayed_count = 0
        for entry in self.log_buffer:
            # 应用级别过滤
            if level_filter != "ALL" and entry["level"] != level_filter:
                continue
            
            # 应用搜索过滤
            if search_text and search_text not in entry["message"].lower() and search_text not in entry["sender"].lower():
                continue
            
            # 格式化日志行
            log_line = f"[{entry['time_str']}] [{entry['level']}] [{entry['sender']}] {entry['message']}\n"
            
            # 根据日志级别选择格式
            if entry["level"] == "DEBUG":
                cursor.insertText(log_line, debug_format)
            elif entry["level"] == "INFO":
                cursor.insertText(log_line, info_format)
            elif entry["level"] == "WARNING":
                cursor.insertText(log_line, warning_format)
            elif entry["level"] == "ERROR":
                cursor.insertText(log_line, error_format)
            elif entry["level"] == "CRITICAL":
                cursor.insertText(log_line, critical_format)
            else:
                cursor.insertText(log_line, normal_format)
            
            displayed_count += 1
        
        # 如果启用了自动滚动且之前在底部，则滚动到底部
        if self.filter_bar.is_auto_scroll() and was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        
        # 更新状态栏
        self.log_count_label.setText(f"日志数量: {displayed_count}/{len(self.log_buffer)}")
    
    def clear_logs(self):
        """清空日志"""
        self.log_buffer.clear()
        self.log_text.clear()
        self.log_count_label.setText("日志数量: 0/0")
        log.info("日志已清空")
    
    def copy_selected_logs(self):
        """复制选中的日志文本"""
        selected_text = self.log_text.textCursor().selectedText()
        if selected_text:
            clipboard = self.log_text.QApplication.clipboard()
            clipboard.setText(selected_text)
            self.statusBar.showMessage("已复制选中的日志内容", 3000)
    
    def export_logs(self):
        """导出日志到文件"""
        try:
            # 获取时间戳作为默认文件名
            default_filename = f"log_export_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出日志", 
                os.path.join(os.path.expanduser("~/Documents"), default_filename),
                "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if not file_path:
                return
            
            # 写入日志
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入头部信息
                f.write("="*80 + "\n")
                f.write(f"花火下载管理器日志导出\n")
                f.write(f"导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"日志条数: {len(self.log_buffer)}\n")
                f.write("="*80 + "\n\n")
                
                # 写入日志内容
                for entry in self.log_buffer:
                    f.write(f"[{entry['time_str']}] [{entry['level']}] [{entry['sender']}] {entry['message']}\n")
            
            log.info(f"日志已导出到: {file_path}")
            self.statusBar.showMessage(f"日志已导出到: {file_path}", 5000)
        except Exception as e:
            log.error(f"导出日志失败: {str(e)}")
            self.statusBar.showMessage(f"导出失败: {str(e)}", 5000)
    
    def exit_application(self):
        """退出整个应用程序"""
        # 确认对话框
        result = QMessageBox.question(
            self, 
            "确认退出", 
            "确定要退出整个应用程序吗？\n这将关闭所有窗口和进程。",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            log.info("用户通过日志窗口请求退出整个应用程序")
            QApplication.quit()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止计时器
        self.auto_refresh_timer.stop()
        # 取消注册日志观察者
        log.remove_observer(self.log_observer)
        log.info("日志窗口已关闭")
        event.accept()

# 测试代码
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    log_window = LogWindow()
    log_window.show()
    
    # 生成一些测试日志
    log.debug("这是一条调试日志")
    log.info("这是一条信息日志")
    log.warning("这是一条警告日志")
    log.error("这是一条错误日志")
    log.critical("这是一条严重错误日志")
    
    sys.exit(app.exec())
