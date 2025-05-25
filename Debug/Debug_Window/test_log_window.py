#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试日志窗口的脚本

功能测试指南:
1. 日志显示功能 - 观察不同颜色的日志级别显示
2. 过滤功能 - 尝试使用顶部的过滤选项（日志级别选择、搜索框）
3. 自动滚动 - 勾选/取消"自动滚动"选项，观察行为变化
4. 清空日志 - 点击"清空日志"按钮测试清空功能
5. 导出日志 - 点击"导出日志"按钮测试导出功能
6. 复制功能 - 选择部分日志文本，点击复制按钮测试复制功能
7. 退出测试:
   - 点击"关闭日志窗口"按钮 - 仅关闭日志窗口，主程序继续运行
   - 点击"退出整个应用程序"按钮 - 会弹出确认对话框，确认后将关闭所有窗口和进程
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from core.log.log_window import LogWindow
from core.log.log_manager import log

def main():
    """主函数，测试日志窗口"""
    app = QApplication(sys.argv)
    
    # 创建并显示日志窗口
    log_window = LogWindow()
    log_window.show()
    
    # 生成一些测试日志
    log.debug("这是一条调试日志消息 - 用于开发调试")
    log.info("这是一条信息日志消息 - 系统正常运行信息")
    log.warning("这是一条警告日志消息 - 表示可能的问题")
    log.error("这是一条错误日志消息 - 表示发生了错误")
    log.critical("这是一条严重错误日志消息 - 表示系统可能无法继续运行")
    
    # 模拟更多日志
    for i in range(5):
        log.info(f"测试日志消息 #{i+1}: 这是一条自动生成的信息")
        time.sleep(0.3)  # 间隔0.3秒产生一条日志
    
    # 演示不同日志级别
    log.debug("调试信息: 正在初始化下载模块...")
    log.info("用户已请求下载文件: example.zip")
    log.warning("下载速度较慢: 仅有 50KB/s")
    log.error("下载失败: 连接超时")
    log.critical("系统崩溃: 内存不足")
    
    # 特别说明，用于提示用户测试退出按钮
    log.info("-" * 30)
    log.info("测试指南：")
    log.info("1. 点击标题栏右侧的'关闭日志窗口'按钮仅关闭此窗口")
    log.info("2. 点击标题栏右侧的红色'退出整个应用程序'按钮将关闭所有窗口和进程")
    log.info("-" * 30)
    
    # 启动事件循环
    return app.exec() # 使用新的exec方法

if __name__ == "__main__":
    sys.exit(main()) 