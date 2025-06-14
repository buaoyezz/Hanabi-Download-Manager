# -*- coding: utf-8 -*-
import os
import sys
import winreg

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

# 现在使用绝对导入
from core.autoboot.silent_mode import SILENT_ARG

def test_startup_command(startup_command):
    """测试启动命令是否有效
    
    Args:
        startup_command: 要测试的启动命令
        
    Returns:
        bool: 命令是否有效
    """
    import subprocess
    
    print(f"正在测试启动命令: {startup_command}")
    
    try:
        # 移除静默参数以便测试时可以看到窗口
        test_cmd = startup_command.replace(SILENT_ARG, "--help")
        
        # 使用subprocess启动进程，但设置超时以避免实际运行程序
        # 我们只是想验证命令格式是否正确
        process = subprocess.Popen(
            test_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NO_WINDOW
        )
        
        # 等待进程启动，但设置超时
        try:
            process.wait(timeout=1.0)
            print("进程已启动并退出")
        except subprocess.TimeoutExpired:
            print("进程已启动但未退出，这是预期行为")
            # 超时表示进程正在运行，这是好的
            process.kill()  # 终止进程
        
        # 检查进程是否成功启动
        if process.poll() is None or process.returncode == 0:
            print("✓ 启动命令测试成功")
            return True
        else:
            print(f"✗ 启动命令测试失败，返回码: {process.returncode}")
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            stdout = process.stdout.read().decode('utf-8', errors='ignore')
            if stderr:
                print(f"错误输出: {stderr}")
            if stdout:
                print(f"标准输出: {stdout}")
            return False
    except Exception as e:
        print(f"✗ 测试启动命令时出错: {e}")
        return False

def create_startup_shortcut(use_silent_mode=True):
    """创建启动文件夹中的快捷方式作为备用自启动方法
    
    Args:
        use_silent_mode (bool): 是否使用静默启动模式，默认为True
        
    Returns:
        bool: 是否成功创建快捷方式
    """
    try:
        import win32com.client
        import winshell
        
        # 获取启动文件夹路径
        startup_folder = winshell.startup()
        shortcut_path = os.path.join(startup_folder, "HanabiDownloadManager.lnk")
        
        # 获取可执行文件路径
        if getattr(sys, 'frozen', False):
            # PyInstaller打包的可执行文件
            target_path = sys.executable
        else:
            # 开发环境下，使用脚本路径
            target_path = os.path.abspath(sys.argv[0])
            
        # 创建快捷方式
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_path
        
        # 设置启动参数
        if use_silent_mode:
            shortcut.Arguments = SILENT_ARG
            
        # 设置工作目录
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        
        # 设置快捷方式图标
        icon_path = os.path.join(os.path.dirname(target_path), "resources", "logo.ico")
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
            
        # 保存快捷方式
        shortcut.save()
        
        print(f"已成功创建启动快捷方式: {shortcut_path}")
        print(f"目标路径: {target_path}")
        print(f"启动参数: {shortcut.Arguments}")
        
        return True
    except ImportError:
        print("无法创建快捷方式: 缺少必要的模块 (win32com, winshell)")
        print("请使用pip安装: pip install pywin32 winshell")
        return False
    except Exception as e:
        print(f"创建快捷方式失败: {e}")
        return False

def add_to_startup(use_silent_mode=True):
    """添加程序到Windows启动项
    
    Args:
        use_silent_mode (bool): 是否使用静默启动模式，默认为True
        
    Returns:
        bool: 是否成功添加到启动项
    """
    # 获取可执行文件的绝对路径
    if getattr(sys, 'frozen', False):
        # PyInstaller打包的可执行文件
        exe_path = sys.executable
        # 崩溃监控程序路径
        crash_monitor_path = os.path.join(os.path.dirname(exe_path), "crash_report", "start_monitor.bat")
        if os.path.exists(crash_monitor_path):
            # 如果存在崩溃监控程序，则使用它
            exe_path = crash_monitor_path
            print(f"使用崩溃监控启动脚本: {crash_monitor_path}")
    else:
        # 开发环境下，使用脚本路径
        exe_path = os.path.abspath(sys.argv[0])
        # 在开发环境中，确保使用pythonw.exe运行脚本
        if exe_path.endswith('.py'):
            python_exe = sys.executable
            if 'python.exe' in python_exe.lower():
                # 将python.exe替换为pythonw.exe以避免显示控制台窗口
                pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')
                if os.path.exists(pythonw_exe):
                    startup_command = f'"{pythonw_exe}" "{exe_path}"'
                else:
                    startup_command = f'"{python_exe}" "{exe_path}"'
            else:
                startup_command = f'"{python_exe}" "{exe_path}"'
        else:
            startup_command = f'"{exe_path}"'
    
    # 确保路径使用双引号包裹，避免空格问题
    if 'startup_command' not in locals():
        # 如果是打包后的可执行文件
        exe_path = exe_path.replace('"', '')
        startup_command = f'"{exe_path}"'
    
    # 添加静默参数
    if use_silent_mode:
        # 确保在路径和参数之间有空格，且参数格式正确
        startup_command += f' {SILENT_ARG}'
    
    print(f"添加到启动项: {startup_command}")
    
    # 进行测试输出
    print(f"解析后启动命令: {startup_command}")
    
    # 测试启动命令是否有效
    is_valid = test_startup_command(startup_command)
    if not is_valid:
        print("警告: 启动命令测试失败，可能无法正常自启动")
    
    # 写入注册表
    registry_success = False
    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
            winreg.SetValueEx(reg_key, "HanabiDownloadManager", 0, winreg.REG_SZ, startup_command)
        print("启动项已成功添加到注册表")
        
        # 检查注册表项是否写入成功
        check_value = get_current_startup_command()
        print(f"写入后检查: {check_value}")
        if check_value == startup_command:
            print("启动项写入注册表验证成功")
            registry_success = True
        else:
            print(f"警告: 启动项写入后检查不一致，期望: {startup_command}, 实际: {check_value}")
    except Exception as e:
        print(f"写入注册表时出错: {str(e)}")
        registry_success = False
    
    # 如果注册表方法失败，尝试使用快捷方式方法
    if not registry_success:
        print("注册表方法失败，尝试使用快捷方式方法...")
        shortcut_success = create_startup_shortcut(use_silent_mode)
        return shortcut_success
    
    return registry_success

def remove_from_startup():
    """从Windows启动项中移除程序"""
    success = True
    
    # 移除注册表项
    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_ALL_ACCESS) as reg_key:
            try:
                winreg.DeleteValue(reg_key, "HanabiDownloadManager")
                print("已从注册表启动项移除")
            except FileNotFoundError:
                # 启动项不存在，忽略错误
                print("注册表中未找到启动项")
                success = success and True  # 不影响成功状态
    except Exception as e:
        print(f"移除注册表启动项时出错: {e}")
        success = False
    
    # 移除启动文件夹中的快捷方式
    try:
        import winshell
        startup_folder = winshell.startup()
        shortcut_path = os.path.join(startup_folder, "HanabiDownloadManager.lnk")
        
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
            print(f"已从启动文件夹移除快捷方式: {shortcut_path}")
        else:
            print("启动文件夹中未找到快捷方式")
    except ImportError:
        print("无法移除快捷方式: 缺少必要的模块 (winshell)")
        # 不影响总体成功状态，因为这只是备用方法
    except Exception as e:
        print(f"移除启动快捷方式时出错: {e}")
        # 不影响总体成功状态，因为这只是备用方法
    
    return success

# 获取当前注册表中的启动命令（用于调试）
def get_current_startup_command():
    """获取当前注册表中的启动命令（用于调试）"""
    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        try:
            # 尝试以只读方式打开
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_READ) as reg_key:
                try:
                    value, _ = winreg.QueryValueEx(reg_key, "HanabiDownloadManager")
                    return value
                except FileNotFoundError:
                    print("注册表中找不到HanabiDownloadManager项")
                    return "未找到启动项"
        except Exception as e:
            print(f"注册表访问错误: {e}")
            
            # 备用方法：使用os.system运行reg query命令
            import subprocess
            try:
                print("尝试使用reg命令查询注册表...")
                cmd = 'reg query "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v HanabiDownloadManager'
                
                # 使用subprocess执行命令并捕获输出
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # 命令成功执行
                    output = result.stdout.strip()
                    print(f"Reg命令输出: {output}")
                    
                    # 解析输出以获取命令
                    if "REG_SZ" in output:
                        # 格式通常是: "HanabiDownloadManager    REG_SZ    命令内容"
                        parts = output.split("REG_SZ", 1)
                        if len(parts) > 1:
                            return parts[1].strip()
                
                return "使用reg命令无法获取启动项"
            except Exception as reg_e:
                print(f"使用reg命令查询失败: {reg_e}")
                return "查询注册表失败"
    except Exception as e:
        return f"未找到启动项或出错: {str(e)}"

# 测试和验证功能
def test_startup_integration(test_write=False):
    """测试启动集成功能
    
    Args:
        test_write (bool): 是否测试写入操作，默认为False以避免权限问题
    """
    print("=== 测试自启动集成功能 ===")
    
    # 测试获取当前启动命令
    current_cmd = get_current_startup_command()
    print(f"当前注册表中的启动命令: {current_cmd}")
    
    # 分析当前命令是否包含静默参数
    if current_cmd and SILENT_ARG in current_cmd:
        print(f"✓ 当前启动命令已包含静默参数: {current_cmd}")
    elif current_cmd:
        print(f"✗ 当前启动命令不包含静默参数: {current_cmd}")
    
    # 检查命令格式
    if current_cmd and '"' in current_cmd:
        print(f"✓ 命令正确使用引号包裹路径")
    elif current_cmd:
        print(f"✗ 命令未正确使用引号包裹路径: {current_cmd}")
    
    # 检查是否使用崩溃监控程序
    if current_cmd and "crash_report" in current_cmd:
        print(f"✓ 命令已集成崩溃监控程序")
    elif current_cmd:
        print(f"✗ 命令未集成崩溃监控程序: {current_cmd}")
    
    # 检查快捷方式是否存在
    try:
        import winshell
        startup_folder = winshell.startup()
        shortcut_path = os.path.join(startup_folder, "HanabiDownloadManager.lnk")
        
        if os.path.exists(shortcut_path):
            print(f"✓ 在启动文件夹中找到快捷方式: {shortcut_path}")
            
            # 尝试读取快捷方式信息
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                
                print(f"  - 目标路径: {shortcut.TargetPath}")
                print(f"  - 启动参数: {shortcut.Arguments}")
                print(f"  - 工作目录: {shortcut.WorkingDirectory}")
                
                # 检查参数是否包含静默模式
                if SILENT_ARG in shortcut.Arguments:
                    print(f"✓ 快捷方式包含静默参数")
                else:
                    print(f"✗ 快捷方式不包含静默参数")
            except Exception as e:
                print(f"✗ 无法读取快捷方式信息: {e}")
        else:
            print(f"✗ 未在启动文件夹中找到快捷方式")
    except ImportError:
        print("✗ 无法检查快捷方式: 缺少必要的模块 (winshell)")
    except Exception as e:
        print(f"✗ 检查快捷方式时出错: {e}")
        
    # 如果不测试写入，则结束测试
    if not test_write:
        print("\n跳过写入测试以避免权限问题")
        print("=== 测试完成 ===")
        return
    
    # 以下是写入测试，需要管理员权限
    try:
        # 测试添加自启动 (带静默参数)
        print("\n测试添加自启动 (带静默参数):")
        success = add_to_startup(True)
        
        if success:
            print("✓ 添加自启动成功")
        else:
            print("✗ 添加自启动失败")
        
        # 再次检查启动命令
        current_cmd = get_current_startup_command()
        print(f"添加后注册表中的启动命令: {current_cmd}")
        
        # 检查静默参数是否正确添加
        if SILENT_ARG in current_cmd:
            print(f"✓ 静默参数已正确添加")
        else:
            print(f"✗ 静默参数未正确添加: {current_cmd}")
        
        # 测试不带静默参数的自启动
        print("\n测试添加自启动 (不带静默参数):")
        success = add_to_startup(False)
        
        if success:
            print("✓ 添加自启动成功")
        else:
            print("✗ 添加自启动失败")
        
        # 再次检查启动命令
        current_cmd = get_current_startup_command()
        print(f"添加后注册表中的启动命令: {current_cmd}")
        
        # 检查静默参数是否未添加
        if SILENT_ARG not in current_cmd:
            print(f"✓ 命令中不包含静默参数，符合预期")
        else:
            print(f"✗ 命令中不应包含静默参数，但发现: {current_cmd}")
        
        # 测试移除自启动
        print("\n测试移除自启动:")
        success = remove_from_startup()
        
        if success:
            print("✓ 移除自启动成功")
        else:
            print("✗ 移除自启动失败")
            
        # 检查是否成功移除
        current_cmd = get_current_startup_command()
        if current_cmd == "未找到启动项":
            print("✓ 已成功从注册表移除")
        else:
            print(f"✗ 未能从注册表移除: {current_cmd}")
            
        # 检查快捷方式是否已移除
        try:
            import winshell
            startup_folder = winshell.startup()
            shortcut_path = os.path.join(startup_folder, "HanabiDownloadManager.lnk")
            
            if not os.path.exists(shortcut_path):
                print("✓ 已成功从启动文件夹移除快捷方式")
            else:
                print("✗ 未能从启动文件夹移除快捷方式")
        except ImportError:
            print("✗ 无法检查快捷方式: 缺少必要的模块 (winshell)")
        except Exception as e:
            print(f"✗ 检查快捷方式时出错: {e}")
    except PermissionError:
        print("\n⚠️ 权限错误: 需要管理员权限才能修改注册表")
    except Exception as e:
        print(f"\n⚠️ 测试过程中出错: {str(e)}")
    
    print("=== 测试完成 ===")

if __name__ == "__main__":
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="自启动管理工具")
    parser.add_argument("--test-write", action="store_true", help="测试写入操作")
    parser.add_argument("--add", action="store_true", help="添加到启动项")
    parser.add_argument("--remove", action="store_true", help="从启动项移除")
    parser.add_argument("--no-silent", action="store_true", help="不使用静默模式")
    args = parser.parse_args()
    
    # 执行相应操作
    if args.add:
        print("正在添加到启动项...")
        success = add_to_startup(not args.no_silent)
        print(f"添加{'成功' if success else '失败'}")
    elif args.remove:
        print("正在从启动项移除...")
        success = remove_from_startup()
        print(f"移除{'成功' if success else '失败'}")
    else:
        # 默认运行测试
        test_startup_integration(test_write=args.test_write)