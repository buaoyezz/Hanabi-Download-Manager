#!/usr/bin/env python
"""
花火下载管理器 - 智能启动器

启动主程序并监控其运行状态，提供崩溃报告功能。
优先使用Python版监控器以减少资源占用。
"""

import os
import sys
import time
import subprocess
import threading

# 主程序启动延迟（秒）
STARTUP_DELAY = 0.5

def find_script_path(script_name):
    """查找脚本路径
    
    Args:
        script_name: 脚本文件名
        
    Returns:
        str: 脚本完整路径
    """
    # 获取当前脚本目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # 可能的路径列表
    possible_paths = [
        os.path.join(current_dir, script_name),
        os.path.join(parent_dir, script_name),
        os.path.join(parent_dir, 'scripts', script_name)
    ]
    
    # 查找脚本
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def start_crash_monitor():
    """启动崩溃监控程序"""
    # 查找监控程序
    monitor_path = find_script_path("HanabiDownloadManager_CrashMonitor.py")
    if not monitor_path:
        print("未找到崩溃监控程序")
        return None
    
    # 创建无控制台窗口的进程
    try:
        if sys.platform == 'win32':
            from subprocess import CREATE_NO_WINDOW
            process = subprocess.Popen(
                [sys.executable, monitor_path],
                creationflags=CREATE_NO_WINDOW
            )
        else:
            # Linux/Mac
            process = subprocess.Popen(
                [sys.executable, monitor_path],
                start_new_session=True
            )
        return process
    except Exception as e:
        print(f"启动监控程序失败: {e}")
        return None

def start_main_program(args=None):
    """启动主程序
    
    Args:
        args: 命令行参数
        
    Returns:
        subprocess.Popen: 主程序进程对象
    """
    # 寻找主程序
    main_path = find_script_path("main.py")
    if not main_path:
        print("未找到主程序")
        return None
    
    # 构建命令行参数
    cmd = [sys.executable, main_path]
    
    # 添加自定义参数
    if args:
        cmd.extend(args)
    
    # 启动主程序
    try:
        process = subprocess.Popen(cmd)
        return process
    except Exception as e:
        print(f"启动主程序失败: {e}")
        return None

def main():
    """主函数"""
    # 获取传递给启动器的参数（排除脚本本身名称）
    args = sys.argv[1:]
    
    # 启动监控程序
    monitor_process = start_crash_monitor()
    
    # 添加一点延迟，确保监控程序正常启动
    time.sleep(STARTUP_DELAY)
    
    # 启动主程序
    main_process = start_main_program(args)
    
    if main_process:
        # 输出进程ID信息
        print(f"主程序已启动，PID: {main_process.pid}")
        
        # 等待主程序结束
        exit_code = main_process.wait()
        
        if exit_code != 0:
            print(f"主程序异常退出，退出代码: {exit_code}")
        else:
            print("主程序正常结束")
            
            # 主程序正常结束时，结束监控程序
            if monitor_process:
                try:
                    monitor_process.terminate()
                except Exception:
                    pass
    else:
        print("主程序启动失败")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 