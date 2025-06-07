import sys
import argparse
from typing import Optional, List

# 静默启动参数名
SILENT_ARG = "--silent"

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="花火下载器启动参数")
    parser.add_argument(SILENT_ARG, action="store_true", 
                        help="静默启动模式，启动时最小化到系统托盘")
    
    # 确保不解析的参数不会导致错误
    return parser.parse_known_args(args)[0]

def is_silent_mode(args: Optional[List[str]] = None) -> bool:
    parsed_args = parse_args(args)
    return getattr(parsed_args, SILENT_ARG.lstrip('-'), False)

# 测试代码
if __name__ == "__main__":
    # 测试不同的参数
    test_args1 = []
    test_args2 = ["--silent"]
    test_args3 = ["--other-arg", "--silent", "--another-arg"]
    test_args4 = ["--debug"]
    print(f"空参数: {is_silent_mode(test_args1)}")
    print(f"Silent参数: {is_silent_mode(test_args2)}")
    print(f"Mixed参数: {is_silent_mode(test_args3)}")
    print(f"Debug参数: {is_silent_mode(test_args4)}")
