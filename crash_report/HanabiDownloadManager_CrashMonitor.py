#!/usr/bin/env python
"""
花火下载管理器 - 轻量级崩溃监控程序

用于监控花火下载管理器的运行状态，发现崩溃时自动启动报告程序。
设计为低资源占用，快速启动。
"""

import os
import sys
import time
import argparse
import subprocess
import threading
import glob
import tempfile
from datetime import datetime
from pathlib import Path

# 全局变量
MAIN_PROCESS_NAME = "python.exe" if sys.platform == "win32" else "python"
MAIN_SCRIPT_NAME = "main.py"
CHECK_INTERVAL = 2.0  # 检查间隔(秒)
MAX_LOG_SIZE = 1024 * 1024  # 最大日志大小(字节)
LOG_FILE = os.path.join(tempfile.gettempdir(), "hanabi_crash_monitor.log")

# 全局标志
running = True
silent_mode = False

# 延迟导入UI相关模块
_UI_IMPORTED = False
_TKINTER_IMPORTED = False

def log(message):
    """记录日志
    
    Args:
        message: 日志消息
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    try:
        # 检查日志文件大小
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            # 备份旧日志
            backup_file = LOG_FILE + ".bak"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            os.rename(LOG_FILE, backup_file)
        
        # 写入日志
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"写入日志失败: {e}", file=sys.stderr)
    
    # 控制台输出(非静默模式)
    if not silent_mode:
        print(log_entry.strip())

def find_main_script():
    """查找主程序脚本
    
    Returns:
        str: 主程序脚本路径，未找到则返回None
    """
    # 获取当前脚本目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # 查找可能的路径
    possible_paths = [
        os.path.join(parent_dir, MAIN_SCRIPT_NAME),
        os.path.join(current_dir, "..", MAIN_SCRIPT_NAME),
        os.path.join(current_dir, "..", "..", MAIN_SCRIPT_NAME)
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    
    return None

def find_log_files():
    """查找日志文件
    
    Returns:
        list: 日志文件路径列表
    """
    # 可能的日志目录
    log_dirs = []
    
    # 获取当前脚本目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # 添加可能的日志目录
    log_dirs.extend([
        os.path.join(parent_dir, "logs"),
        os.path.join(parent_dir, "log"),
        os.path.join(os.path.expanduser("~"), ".hanabi"),
        os.path.join(os.path.expanduser("~"), ".hanabi", "logs"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Hanabi", "logs") if sys.platform == "win32" else None
    ])
    
    # 过滤None值
    log_dirs = [d for d in log_dirs if d is not None]
    
    # 查找日志文件
    log_files = []
    for log_dir in log_dirs:
        if os.path.exists(log_dir):
            # 查找常见日志文件
            for pattern in ["*.log", "hanabi*.txt", "error*.log"]:
                log_files.extend(glob.glob(os.path.join(log_dir, pattern)))
    
    return log_files

def get_latest_log():
    """获取最新的日志文件内容
    
    Returns:
        tuple: (文件路径, 文件内容)，未找到则返回(None, None)
    """
    # 查找所有日志文件
    log_files = find_log_files()
    
    if not log_files:
        return None, None
    
    # 按修改时间排序，获取最新的
    latest_log = max(log_files, key=os.path.getmtime, default=None)
    
    if not latest_log:
        return None, None
    
    try:
        # 读取日志内容
        with open(latest_log, "r", encoding="utf-8", errors="replace") as f:
            # 读取最后100行
            lines = f.readlines()[-100:]
            return latest_log, "".join(lines)
    except Exception as e:
        log(f"读取日志文件失败: {e}")
        return latest_log, None

def is_main_process_running():
    """检查主进程是否运行
    
    Returns:
        bool: 主进程是否运行
    """
    # 使用更轻量级的方法检查主进程
    try:
        main_script = find_main_script()
        if not main_script:
            log("未找到主程序脚本")
            return False
        
        if sys.platform == "win32":
            # Windows - 使用tasklist和findstr
            cmd = f'tasklist /FI "IMAGENAME eq {MAIN_PROCESS_NAME}" /NH'
            output = subprocess.check_output(cmd, shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 如果找到进程，检查其命令行参数
            if MAIN_PROCESS_NAME in output:
                # 查找运行了main.py的进程
                main_script_name = os.path.basename(main_script)
                from psutil import process_iter
                from psutil import NoSuchProcess, AccessDenied

                for proc in process_iter():
                    try:
                        cmdline = proc.cmdline()
                        for idx, item in enumerate(cmdline):
                            if item.endswith(MAIN_PROCESS_NAME) and idx + 1 < len(cmdline) and main_script_name in cmdline[idx + 1]:
                                return True
                    except (NoSuchProcess, AccessDenied):
                        continue
            
            return False
        else:
            # Linux/Mac - 使用pgrep
            main_script_name = os.path.basename(main_script)
            try:
                result = subprocess.run(["pgrep", "-f", main_script_name], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return result.returncode == 0
            except subprocess.SubprocessError:
                return False
    except Exception as e:
        log(f"检查主进程时出错: {e}")
        return False

def show_crash_notification():
    """显示崩溃通知"""
    global _UI_IMPORTED, _TKINTER_IMPORTED
    
    log("正在显示崩溃通知...")
    
    # 获取日志内容
    log_path, log_content = get_latest_log()
    
    # 尝试使用Tkinter显示崩溃对话框
    if not _TKINTER_IMPORTED:
        try:
            # 延迟导入，减小启动内存占用
            # 使用相对导入尝试获取崩溃对话框
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.append(current_dir)
            
            # 尝试导入Tkinter崩溃对话框
            import tkinter_dialog
            _TKINTER_IMPORTED = True
            
            # 设置对话框内容
            reason = "花火下载管理器已崩溃"
            details = "程序异常终止。\n\n"
            
            if log_path:
                details += f"日志文件: {log_path}\n\n"
            
            if log_content:
                details += "最近日志内容:\n" + log_content
            
            # 显示对话框
            tkinter_dialog.show_crash_dialog(
                reason=reason, 
                details=details,
                github_url="https://github.com/buaoyezz/Hanabi-Download-Manager/issues"
            )
            return
        except ImportError:
            log("Tkinter崩溃对话框导入失败")
        except Exception as e:
            log(f"显示Tkinter崩溃对话框失败: {e}")
    
    # 如果Tkinter失败，使用简单的控制台输出
    print("\n" + "="*60)
    print("花火下载管理器已崩溃！")
    print("="*60)
    
    if log_path:
        print(f"日志文件: {log_path}")
    
    if log_content:
        print("\n最近日志内容:\n")
        print(log_content)
    
    print("\n请考虑向开发者报告此问题:")
    print("https://github.com/buaoyezz/Hanabi-Download-Manager/issues")
    print("="*60)
    
    # 等待用户按任意键继续
    if not silent_mode:
        try:
            input("\n按回车键退出...")
        except:
            pass

def restart_main_program():
    """重启主程序"""
    # 查找主程序脚本
    main_script = find_main_script()
    if not main_script:
        log("未找到主程序脚本，无法重启")
        return False
    
    try:
        # 启动主程序
        if sys.platform == 'win32':
            subprocess.Popen([sys.executable, main_script])
        else:
            subprocess.Popen([sys.executable, main_script])
        
        log(f"已重启主程序: {main_script}")
        return True
    except Exception as e:
        log(f"重启主程序失败: {e}")
        return False

def monitor_thread_func():
    """监控线程函数"""
    global running
    
    log("监控线程已启动")
    
    # 启动时等待一段时间，避免误报
    time.sleep(CHECK_INTERVAL * 2)
    
    crash_detected = False
    
    while running:
        try:
            # 检查主进程
            if not is_main_process_running():
                # 再次检查以确认
                time.sleep(1)
                if not is_main_process_running():
                    log("检测到主进程已终止")
                    crash_detected = True
                    break
            
            # 间隔一段时间再次检查
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log("收到中断信号，停止监控")
            break
        except Exception as e:
            log(f"监控线程出错: {e}")
            time.sleep(CHECK_INTERVAL)
    
    if crash_detected and running:
        log("处理崩溃事件")
        # 显示崩溃通知
        show_crash_notification()

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="花火下载管理器崩溃监控程序")
    parser.add_argument("--silent", action="store_true", help="静默模式，不显示控制台输出")
    parser.add_argument("--no-restart", action="store_true", help="崩溃后不自动重启")
    return parser.parse_args()

def main():
    """主函数"""
    global running, silent_mode
    
    # 解析命令行参数
    args = parse_arguments()
    silent_mode = args.silent
    
    # 记录启动信息
    log("崩溃监控程序已启动")
    log(f"Python版本: {sys.version}")
    log(f"平台: {sys.platform}")
    
    try:
        # 检查是否已有实例在运行
        # 简单方法：尝试创建/写入一个锁文件
        lock_file = os.path.join(tempfile.gettempdir(), "hanabi_crash_monitor.lock")
        
        if os.path.exists(lock_file):
            # 检查文件是否过期(超过1小时)
            file_time = os.path.getmtime(lock_file)
            if time.time() - file_time > 3600:
                os.remove(lock_file)
            else:
                log(f"崩溃监控程序已在运行，退出")
                return 1
        
        # 创建锁文件
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_thread_func)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        try:
            # 主线程等待
            while running:
                time.sleep(1)
        except KeyboardInterrupt:
            log("收到中断信号，停止监控")
            running = False
        
        # 等待监控线程结束
        monitor_thread.join(timeout=5.0)
        
        # 删除锁文件
        if os.path.exists(lock_file):
            os.remove(lock_file)
            
        return 0
    except Exception as e:
        log(f"崩溃监控程序出错: {e}")
        import traceback
        log(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 