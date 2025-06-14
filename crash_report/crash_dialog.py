#!/usr/bin/env python
"""
花火下载管理器 - PySide6崩溃对话框模块

提供基于PySide6的崩溃报告对话框，用于显示崩溃信息并允许用户重启程序。
"""

import sys
import os
import threading
import webbrowser
import subprocess
import time
import logging
from datetime import datetime

try:
    from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QPushButton, QTextEdit, QCheckBox)
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath
    
    # 检查是否支持WindowContextHelpButtonHint
    HAS_CONTEXT_HELP_HINT = hasattr(Qt, 'WindowContextHelpButtonHint')
    
    class CrashDialog(QDialog):
        """崩溃报告对话框"""
        
        def __init__(self, reason="程序意外终止", details="", github_url=None):
            """初始化崩溃对话框
            
            Args:
                reason: 崩溃原因
                details: 崩溃详情
                github_url: GitHub Issues页面URL
            """
            super().__init__()
            
            self.reason = reason
            self.details = details
            self.github_url = github_url or "https://github.com/buaoyezz/Hanabi-Download-Manager/issues"
            
            # 窗口设置
            self.setWindowTitle("程序异常")
            self.setMinimumSize(600, 400)
            
            # 设置窗口标志 - 兼容性处理
            if HAS_CONTEXT_HELP_HINT:
                self.setWindowFlags(Qt.WindowCloseButtonHint)
            else:
                # 在较旧版本中使用Dialog标志
                self.setWindowFlags(Qt.Dialog)
            
            # 查找图标
            self.set_app_icon()
            
            # 创建UI
            self.setup_ui()
        
        def set_app_icon(self):
            """设置应用图标"""
            # 查找可能的图标路径
            icon_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "logo.png"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "logo.png")
            ]
            
            for path in icon_paths:
                if os.path.exists(path):
                    self.setWindowIcon(QIcon(path))
                    break
        
        def setup_ui(self):
            """设置UI界面"""
            # 主布局
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(15)
            
            # 标题区域
            title_layout = QHBoxLayout()
            
            # 添加警告图标
            warning_icon = QLabel()
            warning_pixmap = self.create_warning_icon(48)
            if warning_pixmap:
                warning_icon.setPixmap(warning_pixmap)
            title_layout.addWidget(warning_icon)
            
            # 标题文本
            title_label = QLabel("程序意外终止")
            title_font = QFont()
            title_font.setPointSize(14)
            title_font.setBold(True)
            title_label.setFont(title_font)
            title_layout.addWidget(title_label, 1)
            title_layout.addStretch()
            
            main_layout.addLayout(title_layout)
            
            # 说明文本
            description = QLabel("程序遇到了一个未处理的错误，需要重新启动。请查看以下错误信息，并考虑向开发者报告此问题。")
            description.setWordWrap(True)
            main_layout.addWidget(description)
            
            # 错误信息文本框
            self.error_text = QTextEdit()
            self.error_text.setReadOnly(True)
            
            # 填充错误信息
            error_message = ""
            if self.reason:
                error_message += f"崩溃原因: {self.reason}\n\n"
            if self.details:
                error_message += self.details
            
            self.error_text.setPlainText(error_message)
            
            main_layout.addWidget(self.error_text)
            
            # 底部操作区域
            bottom_layout = QHBoxLayout()
            
            # 添加重启选项
            self.restart_checkbox = QCheckBox("重启程序")
            self.restart_checkbox.setChecked(True)
            bottom_layout.addWidget(self.restart_checkbox)
            
            bottom_layout.addStretch()
            
            # 按钮区域
            self.copy_button = QPushButton("复制错误信息")
            self.copy_button.clicked.connect(self.copy_error_info)
            bottom_layout.addWidget(self.copy_button)
            
            self.issue_button = QPushButton("打开GitHub Issues")
            self.issue_button.clicked.connect(self.open_github_issues)
            bottom_layout.addWidget(self.issue_button)
            
            self.cancel_button = QPushButton("关闭")
            self.cancel_button.clicked.connect(self.close)
            bottom_layout.addWidget(self.cancel_button)
            
            main_layout.addLayout(bottom_layout)
        
        def create_warning_icon(self, size=48):
            """创建警告图标
            
            Args:
                size: 图标大小
                
            Returns:
                QPixmap: 警告图标
            """
            # 创建透明背景的图片
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            # 创建画笔
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 设置三角形的大小，略小于图标尺寸
            triangle_size = int(size * 0.8)
            # 计算左上角坐标，使三角形居中
            x_offset = (size - triangle_size) // 2
            y_offset = x_offset
            
            # 绘制黄色三角形
            path = QPainterPath()
            path.moveTo(x_offset + triangle_size // 2, y_offset)
            path.lineTo(x_offset, y_offset + triangle_size)
            path.lineTo(x_offset + triangle_size, y_offset + triangle_size)
            path.lineTo(x_offset + triangle_size // 2, y_offset)
            
            # 填充黄色
            painter.setBrush(QBrush(QColor(255, 200, 0)))
            # 设置黑色边框
            painter.setPen(QPen(Qt.black, 2))
            painter.drawPath(path)
            
            # 绘制感叹号
            painter.setPen(QPen(Qt.black, 3))
            # 感叹号竖线
            exclamation_height = int(triangle_size * 0.4)
            center_x = size // 2
            base_y = y_offset + int(triangle_size * 0.4)
            painter.drawLine(center_x, base_y, center_x, base_y + exclamation_height)
            
            # 感叹号点
            dot_y = base_y + exclamation_height + int(triangle_size * 0.1)
            painter.setBrush(QBrush(Qt.black))
            painter.drawEllipse(center_x - 2, dot_y - 2, 4, 4)
            
            painter.end()
            return pixmap
        
        def copy_error_info(self):
            """复制错误信息到剪贴板"""
            QApplication.clipboard().setText(self.error_text.toPlainText())
        
        def open_github_issues(self):
            """打开GitHub Issues页面"""
            webbrowser.open(self.github_url)
        
        def closeEvent(self, event):
            """关闭事件处理"""
            # 如果选择了重启，启动新进程
            if self.restart_checkbox.isChecked():
                threading.Thread(target=_restart_application, daemon=True).start()
            
            event.accept()
    
except ImportError as e:
    # 记录导入错误
    logging.error(f"无法导入PySide6模块: {e}")
    CrashDialog = None

def _restart_application():
    """重启应用程序"""
    # 获取程序路径和启动参数
    app_path = sys.executable
    args = sys.argv[:]
    
    # 确保不进入静默模式重启
    if '--silent' in args:
        args.remove('--silent')
        
    # 要在新进程中启动程序，在父进程退出后
    try:
        # 在Windows上，使用startupinfo隐藏控制台窗口
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
        # 启动新进程
        subprocess.Popen([app_path] + args[1:], startupinfo=startupinfo)
        
        # 延迟一秒后退出，确保新进程有时间启动
        time.sleep(1)
        sys.exit(0)
    except Exception as e:
        logging.error(f"重启应用程序失败: {e}")

def show_crash_dialog(reason="程序意外终止", details="", github_url=None):
    """显示崩溃对话框
    
    Args:
        reason: 崩溃原因
        details: 崩溃详情
        github_url: GitHub Issues URL
    """
    # 检查是否在主线程中
    if threading.current_thread() is not threading.main_thread():
        logging.error("子线程崩溃，无法显示对话框")
        print(f"崩溃原因: {reason}", file=sys.stderr)
        print(details, file=sys.stderr)
        return
    
    # 检查是否已导入PySide6
    if CrashDialog is None:
        logging.error("未导入PySide6模块，无法显示崩溃对话框")
        print(f"崩溃原因: {reason}", file=sys.stderr)
        print(details, file=sys.stderr)
        return
    
    try:
        # 确保有QApplication实例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建并显示对话框
        dialog = CrashDialog(reason, details, github_url)
        dialog.exec()
        
    except Exception as e:
        logging.error(f"Qt崩溃对话框失败: {e}")
        # 导入失败时，可以尝试使用其他方式显示
        print(f"崩溃原因: {reason}", file=sys.stderr)
        print(details, file=sys.stderr)

# 测试代码
if __name__ == "__main__":
    # 模拟一个崩溃
    show_crash_dialog(
        reason="测试崩溃",
        details="这是一个测试崩溃，用于验证崩溃对话框功能。\n\n" + 
                "Traceback (most recent call last):\n" + 
                "  File \"test.py\", line 10, in <module>\n" + 
                "    raise RuntimeError(\"测试崩溃\")\n" + 
                "RuntimeError: 测试崩溃"
    ) 