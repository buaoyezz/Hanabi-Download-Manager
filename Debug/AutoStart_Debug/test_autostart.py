#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试开机自启动配置是否有效的脚本
"""

import os
import sys
import subprocess

def test_windows_autostart():
    """测试Windows下的开机自启动配置"""
    print("正在检查Windows开机自启动配置...")
    
    try:
        import winreg
        # 打开注册表项
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        
        try:
            # 尝试获取自启动项的值
            value, regtype = winreg.QueryValueEx(key, "HanabiDownloadManager")
            print(f"✅ 已找到开机自启动注册表项")
            print(f"启动命令: {value}")
            
            # 检查命令是否包含正确的可执行文件
            if getattr(sys, 'frozen', False):
                # 打包环境，应包含.exe文件路径
                if sys.executable.lower() in value.lower():
                    print("✅ 启动命令正确包含了应用程序路径")
                else:
                    print("❌ 启动命令似乎没有包含正确的应用程序路径")
                    print(f"预期路径: {sys.executable}")
            else:
                # 开发环境，应包含python和main.py
                python_path = sys.executable
                main_script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'main.py'))
                if python_path.lower() in value.lower() and 'main.py' in value.lower():
                    print("✅ 启动命令正确包含了Python解释器和main.py")
                else:
                    print("❌ 启动命令似乎没有包含正确的Python解释器或main.py")
                    print(f"预期Python路径: {python_path}")
                    print(f"预期脚本路径: {main_script}")
            
            return True
        except WindowsError:
            print("❌ 未找到HanabiDownloadManager的开机自启动项")
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        print(f"❌ 检查开机自启动配置时出错: {str(e)}")
        return False

def test_macos_autostart():
    """测试macOS下的开机自启动配置"""
    print("正在检查macOS开机自启动配置...")
    
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.hanabi.downloadmanager.plist")
    if os.path.exists(plist_path):
        print(f"✅ 已找到启动配置文件: {plist_path}")
        
        # 读取并显示plist内容
        try:
            with open(plist_path, 'r') as f:
                plist_content = f.read()
                print("启动配置文件内容:")
                print("-" * 40)
                print(plist_content)
                print("-" * 40)
            
            # 检查plist文件是否已加载
            result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
            if "com.hanabi.downloadmanager" in result.stdout:
                print("✅ 启动项已在launchctl中加载")
            else:
                print("❌ 启动项未在launchctl中加载")
            
            return True
        except Exception as e:
            print(f"❌ 读取plist文件时出错: {str(e)}")
            return False
    else:
        print(f"❌ 未找到启动配置文件: {plist_path}")
        return False

def test_linux_autostart():
    """测试Linux下的开机自启动配置"""
    print("正在检查Linux开机自启动配置...")
    
    desktop_path = os.path.expanduser("~/.config/autostart/hanabidownloadmanager.desktop")
    if os.path.exists(desktop_path):
        print(f"✅ 已找到启动配置文件: {desktop_path}")
        
        # 读取并显示desktop内容
        try:
            with open(desktop_path, 'r') as f:
                desktop_content = f.read()
                print("启动配置文件内容:")
                print("-" * 40)
                print(desktop_content)
                print("-" * 40)
            
            # 检查文件权限
            mode = oct(os.stat(desktop_path).st_mode)[-3:]
            if int(mode) >= 755:
                print(f"✅ 文件权限正确: {mode}")
            else:
                print(f"⚠️ 文件权限可能不足: {mode}，建议设置为755")
            
            return True
        except Exception as e:
            print(f"❌ 读取desktop文件时出错: {str(e)}")
            return False
    else:
        print(f"❌ 未找到启动配置文件: {desktop_path}")
        return False

def get_app_path_args():
    """获取应用程序可执行文件及其参数列表"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包的环境
        return [sys.executable]
    else:
        # 开发环境
        python_path = sys.executable
        # 假设main.py在当前目录
        main_script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'main.py'))
        return [python_path, main_script_path]

def main():
    """主函数"""
    print("=" * 50)
    print("开机自启动配置测试工具")
    print("=" * 50)
    print(f"操作系统: {sys.platform}")
    
    # 获取并显示应用程序路径
    app_args = get_app_path_args()
    print(f"应用程序启动参数: {app_args}")
    command_line = subprocess.list2cmdline(app_args)
    print(f"命令行形式: {command_line}")
    print("-" * 50)
    
    # 根据操作系统运行相应的测试
    result = False
    if sys.platform == 'win32':  # Windows
        result = test_windows_autostart()
    elif sys.platform == 'darwin':  # macOS
        result = test_macos_autostart()
    elif sys.platform.startswith('linux'):  # Linux
        result = test_linux_autostart()
    else:
        print(f"❌ 不支持的操作系统: {sys.platform}")
    
    print("-" * 50)
    if result:
        print("✅ 开机自启动配置测试完成，配置文件已存在")
        print("请注意: 此测试只验证了配置文件是否存在，并不保证系统启动时一定会运行程序")
        print("建议重启系统进行完整测试")
    else:
        print("❌ 开机自启动配置测试失败，未找到有效配置")
        print("可能的解决方案:")
        print("1. 确保已在应用程序设置中启用了开机自启动")
        print("2. 确保应用程序有足够的权限创建自启动配置")
        print("3. 手动运行 general_control.py 中的 _setup_autostart() 方法")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 