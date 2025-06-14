#!/usr/bin/env python
"""
花火下载管理器崩溃处理测试脚本

用于测试崩溃处理系统的各种功能。
"""

import os
import sys
import time
import threading
import argparse
from pathlib import Path

# 添加项目根目录到Python路径，确保能导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
    from PySide6.QtCore import Qt
    HAS_QT = True
except ImportError:
    print("PySide6未安装，仅支持控制台测试模式")
    HAS_QT = False

def test_simple_crash():
    """测试简单的崩溃场景"""
    from crash_report import install_crash_handler, test_crash
    
    print("正在测试简单崩溃场景...")
    install_crash_handler(silent_mode=False)
    
    # 触发一个测试崩溃
    test_crash()

def test_thread_crash():
    """测试线程崩溃场景"""
    from crash_report import install_crash_handler
    
    print("正在测试线程崩溃场景...")
    install_crash_handler(silent_mode=False)
    
    # 创建一个会崩溃的线程
    def crash_thread():
        time.sleep(1)  # 等待一秒
        print("线程即将崩溃...")
        raise RuntimeError("这是一个测试线程崩溃")
    
    # 启动线程
    thread = threading.Thread(target=crash_thread, name="CrashTestThread")
    thread.daemon = True
    thread.start()
    
    # 等待线程崩溃
    thread.join()

def test_silent_crash():
    """测试静默崩溃场景"""
    from crash_report import install_crash_handler, test_crash
    
    print("正在测试静默崩溃场景...")
    install_crash_handler(silent_mode=True)
    
    # 触发一个测试崩溃
    try:
        test_crash()
    except Exception as e:
        print(f"捕获到崩溃 (静默模式): {e}")

def test_gui_crash():
    """测试GUI应用崩溃场景"""
    if not HAS_QT:
        print("PySide6未安装，跳过GUI崩溃测试")
        return
    
    from crash_report import install_crash_handler
    
    app = QApplication(sys.argv)
    
    # 安装崩溃处理器
    install_crash_handler(app=app, silent_mode=False)
    
    # 创建主窗口
    main_window = QMainWindow()
    main_window.setWindowTitle("崩溃测试")
    main_window.resize(400, 300)
    
    # 创建中央部件
    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    
    # 创建布局
    layout = QVBoxLayout(central_widget)
    
    # 添加标签
    label = QLabel("点击按钮测试不同类型的崩溃")
    layout.addWidget(label)
    
    # 添加崩溃按钮
    crash_button = QPushButton("触发崩溃")
    crash_button.clicked.connect(lambda: 1/0)  # 除零错误
    layout.addWidget(crash_button)
    
    # 添加线程崩溃按钮
    thread_crash_button = QPushButton("触发线程崩溃")
    def start_crash_thread():
        def crash_thread_func():
            time.sleep(0.5)  # 等待半秒
            raise RuntimeError("这是UI线程崩溃测试")
        
        thread = threading.Thread(target=crash_thread_func)
        thread.daemon = True
        thread.start()
    
    thread_crash_button.clicked.connect(start_crash_thread)
    layout.addWidget(thread_crash_button)
    
    # 显示窗口
    main_window.show()
    
    # 运行应用
    sys.exit(app.exec())

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="花火下载管理器崩溃测试工具")
    parser.add_argument("--mode", choices=["simple", "thread", "silent", "gui"], 
                      default="simple", help="崩溃测试模式")
    
    args = parser.parse_args()
    
    try:
        if args.mode == "simple":
            test_simple_crash()
        elif args.mode == "thread":
            test_thread_crash()
        elif args.mode == "silent":
            test_silent_crash()
        elif args.mode == "gui":
            test_gui_crash()
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 