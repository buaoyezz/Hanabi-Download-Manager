#!/usr/bin/env python
"""
花火下载管理器 - Tkinter轻量级崩溃对话框

提供无需PySide6的备用崩溃报告界面，使用标准库Tkinter实现。
优点是启动极快，资源占用少，无外部依赖。
"""

import os
import sys
import threading
import webbrowser
import subprocess
import tempfile
from datetime import datetime

# Tkinter导入方式兼容Python 2和3
try:
    # Python 3
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
    from tkinter import font as tkfont
except ImportError:
    # Python 2
    import Tkinter as tk
    import ttk
    import tkMessageBox as messagebox
    import tkFont as tkfont

# 全局变量
DEFAULT_GITHUB_URL = "https://github.com/buaoyezz/Hanabi-Download-Manager/issues"
DEFAULT_ICON_PATH = None

def create_warning_icon(canvas, x, y, size=48, color="#FFCC00"):
    """在Canvas上绘制警告图标
    
    Args:
        canvas: Tkinter Canvas对象
        x, y: 图标中心坐标
        size: 图标大小
        color: 警告三角形颜色
    """
    # 计算坐标
    half_size = size / 2
    # 绘制三角形
    canvas.create_polygon(
        x, y - half_size,             # 顶部
        x - half_size, y + half_size, # 左下
        x + half_size, y + half_size, # 右下
        fill=color, outline="black", width=2
    )
    
    # 绘制感叹号
    exclamation_height = size * 0.4
    dot_y_offset = size * 0.1
    
    # 感叹号竖线
    canvas.create_line(
        x, y - exclamation_height/2,
        x, y + exclamation_height/2,
        fill="black", width=3
    )
    
    # 感叹号点
    canvas.create_oval(
        x - 2, y + exclamation_height/2 + dot_y_offset,
        x + 2, y + exclamation_height/2 + dot_y_offset + 4,
        fill="black", outline="black"
    )

def save_crash_info(crash_info):
    """保存崩溃信息到临时文件
    
    Args:
        crash_info: 崩溃详细信息字符串
        
    Returns:
        str: 保存的文件路径
    """
    try:
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="hanabi_crash_")
        os.close(fd)
        
        # 添加时间戳和基本信息
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"花火下载管理器崩溃报告\n时间: {timestamp}\n\n"
        
        # 写入崩溃信息
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(header + crash_info)
            
        return temp_path
    except Exception as e:
        print(f"保存崩溃信息失败: {e}", file=sys.stderr)
        return None

def restart_application():
    """重启应用程序"""
    # 获取执行路径和命令行参数
    executable = sys.executable
    args = sys.argv[:]
    
    # 如果是作为脚本运行的Python程序，保持相同命令行参数
    if executable.endswith('pythonw.exe') or executable.endswith('python.exe') or executable.endswith('python'):
        args = [executable] + args
    
    # 如果运行的是已编译的可执行文件，直接使用当前进程的路径
    elif getattr(sys, 'frozen', False):
        executable = sys.executable
        args = [executable] + args[1:]  # 排除可执行文件本身的参数
    
    try:
        # 启动新实例
        if sys.platform == 'win32':
            from subprocess import CREATE_NEW_PROCESS_GROUP, DETACHED_PROCESS
            subprocess.Popen(
                args, 
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Linux/Mac
            subprocess.Popen(args)
        
        # 退出当前实例
        sys.exit(0)
    except Exception as e:
        print(f"重启应用程序失败: {e}", file=sys.stderr)

class TkCrashDialog:
    """基于Tkinter的崩溃对话框"""
    
    def __init__(self, master=None, reason="程序意外终止", details="", github_url=DEFAULT_GITHUB_URL):
        """初始化崩溃对话框
        
        Args:
            master: 父窗口
            reason: 崩溃原因
            details: 崩溃详情
            github_url: GitHub Issues URL
        """
        self.reason = reason
        self.details = details
        self.github_url = github_url
        self.dump_path = None
        
        # 保存崩溃信息到文件
        self.dump_path = save_crash_info(reason + "\n\n" + details)
        
        # 创建主窗口
        self.root = tk.Toplevel(master) if master else tk.Tk()
        self.root.title("程序异常")
        
        # 窗口大小和位置
        self.root.minsize(600, 400)
        self.root.geometry("600x500")
        self.center_window()
        
        # 设置图标
        self.set_icon()
        
        # 创建界面
        self.create_widgets()
        
        # 设置模态窗口
        if master:
            self.root.transient(master)
            self.root.grab_set()
        
        # 设置关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.geometry(f"+{x}+{y}")
        
    def set_icon(self):
        """设置窗口图标"""
        if DEFAULT_ICON_PATH and os.path.exists(DEFAULT_ICON_PATH):
            try:
                # 尝试加载图标
                if sys.platform == 'win32':
                    self.root.iconbitmap(DEFAULT_ICON_PATH)
                else:
                    # Linux/Mac需要使用PhotoImage
                    icon = tk.PhotoImage(file=DEFAULT_ICON_PATH)
                    self.root.tk.call('wm', 'iconphoto', self.root._w, icon)
            except Exception:
                pass
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部区域：图标和标题
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 创建Canvas用于绘制警告图标
        icon_size = 48
        icon_canvas = tk.Canvas(top_frame, width=icon_size, height=icon_size, 
                              highlightthickness=0, bd=0)
        icon_canvas.pack(side=tk.LEFT, padx=(0, 10))
        
        # 绘制警告图标
        create_warning_icon(icon_canvas, icon_size//2, icon_size//2, icon_size)
        
        # 标题文本
        title_font = tkfont.Font(family="Arial", size=14, weight="bold")
        title_label = ttk.Label(top_frame, text="程序意外终止", font=title_font)
        title_label.pack(side=tk.LEFT, fill=tk.X)
        
        # 说明文本
        description = ttk.Label(main_frame, text="程序遇到了一个未处理的错误，需要重新启动。"
                               "请查看以下错误信息，并考虑向开发者报告此问题。",
                               wraplength=560)
        description.pack(fill=tk.X, pady=(0, 10))
        
        # 错误信息文本框
        self.error_text = tk.Text(main_frame, wrap=tk.WORD, height=15)
        self.error_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.error_text, command=self.error_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.error_text.config(yscrollcommand=scrollbar.set)
        
        # 填充错误信息
        error_message = ""
        if self.reason:
            error_message += f"崩溃原因: {self.reason}\n\n"
        if self.details:
            error_message += self.details
        if self.dump_path:
            error_message += f"\n\n崩溃信息已保存到: {self.dump_path}"
            
        self.error_text.insert(tk.END, error_message)
        self.error_text.config(state=tk.DISABLED)  # 设为只读
        
        # 底部区域
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 重启选项
        self.restart_var = tk.BooleanVar(value=True)
        restart_check = ttk.Checkbutton(bottom_frame, text="重启程序", 
                                      variable=self.restart_var)
        restart_check.pack(side=tk.LEFT)
        
        # 按钮区域在底部右侧
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(side=tk.RIGHT)
        
        # 复制按钮
        copy_button = ttk.Button(button_frame, text="复制错误信息", 
                               command=self.copy_error_info)
        copy_button.pack(side=tk.LEFT, padx=5)
        
        # GitHub按钮
        github_button = ttk.Button(button_frame, text="打开GitHub Issues", 
                                 command=self.open_github_issues)
        github_button.pack(side=tk.LEFT, padx=5)
        
        # 关闭按钮
        close_button = ttk.Button(button_frame, text="关闭",
                                command=self.on_close)
        close_button.pack(side=tk.LEFT, padx=5)
    
    def copy_error_info(self):
        """复制错误信息到剪贴板"""
        text = self.error_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        
        messagebox.showinfo("复制成功", "错误信息已复制到剪贴板")
    
    def open_github_issues(self):
        """打开GitHub Issues页面"""
        try:
            webbrowser.open(self.github_url)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开GitHub Issues页面: {e}")
    
    def on_close(self):
        """处理窗口关闭事件"""
        # 检查是否需要重启
        if self.restart_var.get():
            # 在独立线程中重启应用程序，避免阻塞
            threading.Thread(target=restart_application, daemon=True).start()
        
        # 关闭对话框
        self.root.destroy()
        
    def show(self):
        """显示对话框并阻塞直到关闭"""
        # 在显示之前再次居中
        self.center_window()
        
        if not isinstance(self.root, tk.Toplevel):
            self.root.mainloop()
        else:
            # 等待窗口关闭
            self.root.wait_window(self.root)

def show_crash_dialog(reason="程序意外终止", details="", github_url=None):
    """显示崩溃对话框
    
    Args:
        reason: 崩溃原因
        details: 崩溃详情
        github_url: GitHub Issues URL
    """
    # 设置默认GitHub URL
    if not github_url:
        github_url = DEFAULT_GITHUB_URL
        
    try:
        # 为确保线程安全，在主线程中创建和显示对话框
        if threading.current_thread() is threading.main_thread():
            # 直接在当前线程显示
            dialog = TkCrashDialog(reason=reason, details=details, github_url=github_url)
            dialog.show()
        else:
            # 如果是在子线程中调用，则将对话框显示延迟到主线程
            print("警告：在非主线程中调用show_crash_dialog，对话框可能无法正确显示", file=sys.stderr)
            dialog = TkCrashDialog(reason=reason, details=details, github_url=github_url)
            dialog.show()
    except Exception as e:
        # 确保即使对话框失败也能看到错误信息
        print(f"崩溃对话框显示失败: {e}", file=sys.stderr)
        print(f"崩溃原因: {reason}", file=sys.stderr)
        print(details, file=sys.stderr)

def set_app_icon(icon_path):
    """设置应用图标路径
    
    Args:
        icon_path: 图标文件路径
    """
    global DEFAULT_ICON_PATH
    if os.path.exists(icon_path):
        DEFAULT_ICON_PATH = icon_path

# 测试代码
if __name__ == "__main__":
    # 测试崩溃对话框
    exception_info = {
        "type": "RuntimeError",
        "message": "这是一个测试异常",
        "traceback": "Traceback (most recent call last):\n"
                     "  File \"test.py\", line 10, in <module>\n"
                     "    raise RuntimeError(\"这是一个测试异常\")\n"
                     "RuntimeError: 这是一个测试异常"
    }
    
    # 尝试查找并设置图标
    icon_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "logo.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "logo.png")
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            set_app_icon(path)
            break
    
    # 显示测试对话框
    show_crash_dialog(
        reason=f"{exception_info['type']}: {exception_info['message']}",
        details=exception_info['traceback'],
        github_url="https://github.com/buaoyezz/Hanabi-Download-Manager/issues"
    ) 