import sys
import argparse
import os
from typing import Optional, List

# 静默启动参数名 (确保格式一致)
SILENT_ARG = "--silent"

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """解析命令行参数
    
    Args:
        args: 命令行参数列表，默认为None表示使用sys.argv
        
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(description="花火下载器启动参数")
    parser.add_argument(SILENT_ARG, action="store_true", 
                        help="静默启动模式，启动时最小化到系统托盘")
    
    # 确保不解析的参数不会导致错误
    return parser.parse_known_args(args)[0]

def is_silent_mode(args: Optional[List[str]] = None) -> bool:
    """检查是否处于静默模式
    
    Args:
        args: 命令行参数列表，默认为None表示使用sys.argv
        
    Returns:
        是否为静默模式
    """
    # 如果未提供参数，使用系统参数
    if args is None:
        args = sys.argv[1:]
    
    # 方法1: 直接检查原始参数列表中是否包含静默参数
    # 这是最直接的方法，可以避免argparse可能的解析问题
    if SILENT_ARG in args:
        print(f"[静默模式] 通过直接参数匹配检测到{SILENT_ARG}参数")
        return True
    
    # 方法2: 尝试使用argparse进行解析
    try:
        parsed_args = parse_args(args)
        silent_attr = SILENT_ARG.lstrip('-').replace('-', '_')
        is_silent = getattr(parsed_args, silent_attr, False)
        if is_silent:
            print(f"[静默模式] 通过argparse检测到{SILENT_ARG}参数")
            return True
    except Exception as e:
        print(f"[静默模式] 参数解析出错: {e}")
    
    # 方法3: 检查命令行中是否有包含silent的参数(不区分大小写，更宽松的匹配)
    for arg in args:
        if 'silent' in arg.lower():
            print(f"[静默模式] 通过宽松匹配检测到含silent的参数: {arg}")
            return True
    
    # 所有方法都未检测到静默模式
    print(f"[静默模式] 未检测到静默模式参数，原始参数: {args}")
    return False

# 测试代码
if __name__ == "__main__":
    # 测试不同的参数
    test_args1 = []
    test_args2 = ["--silent"]
    test_args3 = ["--other-arg", "--silent", "--another-arg"]
    test_args4 = ["--debug"]
    test_args5 = ["/silent"]  # Windows风格参数
    test_args6 = ["-silent"]  # 单横线参数
    
    print(f"空参数: {is_silent_mode(test_args1)}")
    print(f"Silent参数: {is_silent_mode(test_args2)}")
    print(f"Mixed参数: {is_silent_mode(test_args3)}")
    print(f"Debug参数: {is_silent_mode(test_args4)}")
    print(f"Windows风格参数: {is_silent_mode(test_args5)}")
    print(f"单横线参数: {is_silent_mode(test_args6)}")
    
    # 测试当前系统参数
    print(f"当前系统参数: {sys.argv}")
    print(f"当前是否静默模式: {is_silent_mode()}")

    # 保存测试参数到本地文件
    # def save_test_args():
    #     test_args = {
    #         "empty": [],
    #         "silent": ["--silent"],
    #         "mixed": ["--other-arg", "--silent", "--another-arg"],
    #         "debug": ["--debug"],
    #         "windows_style": ["/silent"],
    #         "single_dash": ["-silent"]
    #     }
        
    #     import json
    #     import os
        
    #     # 确保测试数据目录存在
    #     test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
    #     os.makedirs(test_data_dir, exist_ok=True)
        
    #     # 保存测试参数到JSON文件
    #     test_args_file = os.path.join(test_data_dir, "silent_mode_test_args.json")
    #     with open(test_args_file, "w", encoding="utf-8") as f:
    #         json.dump(test_args, f, ensure_ascii=False, indent=4)
        
    #     print(f"测试参数已保存到: {test_args_file}")
    
    # # 调用保存函数
    # save_test_args()
