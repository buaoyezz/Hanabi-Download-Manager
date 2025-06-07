# -*- coding: utf-8 -*-
import os
import sys
import winreg
from .silent_mode import SILENT_ARG
<<<<<<< HEAD
=======
# 自启动功能实现
>>>>>>> 28724b36bd6128e814ac7cd634005f5e35da5122
executable_path = sys.argv[0]
current_path = os.path.dirname(os.path.abspath(executable_path))

# print("当前路径:", current_path)
# print("可执行文件路径:", executable_path)

<<<<<<< HEAD
def add_to_startup(use_silent_mode=True):
    #use_silent_mode (bool): 是否使用静默启动模式，默认为True
    
    exe_path = os.path.abspath(executable_path)
    # silent bool
    startup_command = f'"{exe_path}"'
    if use_silent_mode:
        startup_command += f' {SILENT_ARG}'
    
=======
def add_to_startup():
    exe_path = os.path.abspath(executable_path)
    # 添加静默启动参数
    startup_command = f'"{exe_path}" {SILENT_ARG}'
>>>>>>> 28724b36bd6128e814ac7cd634005f5e35da5122
    print("startup_command:", startup_command)
    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
        winreg.SetValueEx(reg_key, "HanabiDownloadManager", 0, winreg.REG_SZ, startup_command)
    
def remove_from_startup():
    key = winreg.HKEY_CURRENT_USER
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
        winreg.DeleteValue(reg_key, "HanabiDownloadManager")

if __name__ == "__main__":
    add_to_startup()