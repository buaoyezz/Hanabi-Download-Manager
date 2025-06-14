#!/usr/bin/env python
"""
花火下载管理器 - 崩溃报告系统

提供全局异常处理和崩溃报告功能，支持多种显示方式。

快速启动：
```python
from crash_report import install_crash_handler

# 安装崩溃处理程序
install_crash_handler(app)
```
"""

from .crash_handler import (
    install, 
    configure as configure_crash_handler,
    add_crash_handler,
    test_crash,
    uninstall as uninstall_crash_handler
)

# 简化API入口点
def install_crash_handler(app=None, silent_mode=False):
    """安装崩溃处理程序
    
    Args:
        app: QApplication实例(可选)
        silent_mode: 是否静默模式
        
    Returns:
        bool: 安装是否成功
    """
    return install(app, silent_mode)

# 尝试预加载tkinter_dialog以确保其可用性
try:
    from . import tkinter_dialog
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False

# 预加载crash_dialog以确保其可用性
try:
    from . import crash_dialog
    _HAS_CRASH_DIALOG = True
except ImportError:
    _HAS_CRASH_DIALOG = False

# 输出加载信息
import logging
if _HAS_CRASH_DIALOG:
    logging.debug("已加载PySide6崩溃对话框")
if _HAS_TKINTER:
    logging.debug("已加载Tkinter备用崩溃对话框")

__all__ = [
    'install_crash_handler', 
    'configure_crash_handler',
    'add_crash_handler',
    'test_crash',
    'uninstall_crash_handler'
]

# 版本
__version__ = '1.0.0' 