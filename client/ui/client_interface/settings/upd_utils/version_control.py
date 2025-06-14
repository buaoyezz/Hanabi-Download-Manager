"""
版本控制工具模块

此模块提供了版本号管理的各种实用工具函数，用于比较、解析和规范化版本号。
支持标准的语义化版本号格式，并能处理特殊的后缀格式。
"""

import re
import logging


class VersionControl:
    """版本控制工具类"""

    @staticmethod
    def compare_versions(version1, version2):
        """
        比较两个版本号的大小，支持标准化的语义化版本号格式
        
        支持以下格式:
        - 标准版本号 (1.0.0, 1.0.10, 1.1.11)
        - 带hotfix/remake后缀 (1.0.0-1 hotfix, 1.0.0 remake)
        - 四段式版本号 (1.0.0.1000)
        - 混合模式 (1.1.1.9033 hotfix)
        
        Args:
            version1 (str): 第一个版本号
            version2 (str): 第二个版本号
        
        Returns:
            int:
            - 1: version1 更新
            - 0: 版本相同
            - -1: version2 更新
        """
        # 定义优先级字典，值越大优先级越高
        suffix_priority = {
            "": 0,
            "hotfix": 1,  # hotfix优先级低于普通版本
            "remake": 2   # remake优先级高于普通版本
        }
        
        # 解析版本1
        v1_main, v1_build, v1_suffix, v1_suffix_num = VersionControl._parse_version(version1)
        
        # 解析版本2
        v2_main, v2_build, v2_suffix, v2_suffix_num = VersionControl._parse_version(version2)
        
        # 首先比较主版本号
        for i in range(max(len(v1_main), len(v2_main))):
            v1_comp = v1_main[i] if i < len(v1_main) else 0
            v2_comp = v2_main[i] if i < len(v2_main) else 0
            
            if v1_comp > v2_comp:
                return 1  # version1 更新
            elif v1_comp < v2_comp:
                return -1  # version2 更新
        
        # 如果主版本号相同，比较构建版本号
        if v1_build > v2_build:
            return 1
        elif v1_build < v2_build:
            return -1
            
        # 如果主版本号和构建版本号都相同，比较后缀优先级
        if suffix_priority.get(v1_suffix, 0) > suffix_priority.get(v2_suffix, 0):
            return 1
        elif suffix_priority.get(v1_suffix, 0) < suffix_priority.get(v2_suffix, 0):
            return -1
            
        # 如果后缀类型相同，比较后缀数字（仅hotfix有）
        if v1_suffix == v2_suffix == "hotfix":
            if v1_suffix_num > v2_suffix_num:
                return 1
            elif v1_suffix_num < v2_suffix_num:
                return -1
        
        # 完全相同
        return 0
    
    @staticmethod
    def _parse_version(version_str):
        """解析版本号字符串
        
        Args:
            version_str (str): 要解析的版本号字符串
        
        Returns:
            tuple: (主版本号列表, 构建版本号, 后缀类型, 后缀编号)
        """
        # 默认值
        main_version = []
        build_number = 0
        suffix_type = ""
        suffix_number = 0
        
        # 处理特殊情况：空字符串或None
        if not version_str:
            return ([0, 0, 0], 0, "", 0)
            
        # 处理后缀
        version_parts = version_str.lower().split()
        version_base = version_parts[0]  # 基本版本部分
        
        # 检查是否有后缀类型
        if len(version_parts) > 1:
            if "hotfix" in version_parts:
                suffix_type = "hotfix"
            elif "remake" in version_parts:
                suffix_type = "remake"
        
        # 处理带有-的hotfix格式（例如1.0.0-1）
        if "-" in version_base and not suffix_type:
            version_base, suffix_part = version_base.split("-", 1)
            # 检查后缀部分是否为纯数字
            if suffix_part.isdigit():
                suffix_type = "hotfix"
                try:
                    suffix_number = int(suffix_part)
                except ValueError:
                    suffix_number = 0
        
        # 分割版本号
        version_segments = version_base.split(".")
        
        # 解析主版本号（前三段）
        main_segments = min(3, len(version_segments))
        for i in range(main_segments):
            try:
                main_version.append(int(version_segments[i]))
            except ValueError:
                main_version.append(0)
        
        # 补齐主版本号到3段
        while len(main_version) < 3:
            main_version.append(0)
        
        # 如果有第四段，作为构建版本号，支持超大数字
        if len(version_segments) > 3:
            try:
                build_number = int(version_segments[3])
            except ValueError:
                build_number = 0
                logging.warning(f"无效的构建号格式: {version_segments[3]}")
        
        return (main_version, build_number, suffix_type, suffix_number)
    
    @staticmethod
    def normalize_version(version_str):
        """
        规范化版本号格式
        
        Args:
            version_str (str): 输入的版本号字符串
            
        Returns:
            str: 规范化后的版本号
        """
        # 解析版本号
        main_version, build, suffix_type, suffix_num = VersionControl._parse_version(version_str)
        
        # 构建基本版本号
        base_version = ".".join(map(str, main_version))
        
        # 添加构建号（如果有）
        if build > 0:
            base_version += f".{build}"
        
        # 添加后缀（如果有）
        if suffix_type == "hotfix":
            if suffix_num > 0:
                base_version += f"-{suffix_num} hotfix"
            else:
                base_version += " hotfix"
        elif suffix_type == "remake":
            base_version += " remake"
        
        return base_version
    
    @staticmethod
    def increment_version(version_str, increment_type="patch"):
        """
        递增版本号
        
        Args:
            version_str (str): 当前版本号
            increment_type (str): 递增类型，可以是 'major', 'minor', 'patch', 'build'
            
        Returns:
            str: 递增后的版本号
        """
        # 解析版本号
        main_version, build, suffix_type, suffix_num = VersionControl._parse_version(version_str)
        
        # 根据类型递增
        if increment_type == "major":
            main_version[0] += 1
            main_version[1] = 0
            main_version[2] = 0
            build = 0
            suffix_type = ""
            suffix_num = 0
        elif increment_type == "minor":
            main_version[1] += 1
            main_version[2] = 0
            build = 0
            suffix_type = ""
            suffix_num = 0
        elif increment_type == "patch":
            main_version[2] += 1
            build = 0
            suffix_type = ""
            suffix_num = 0
        elif increment_type == "build":
            build += 1
        elif increment_type == "hotfix":
            if suffix_type == "hotfix":
                suffix_num += 1
            else:
                suffix_type = "hotfix"
                suffix_num = 1
        
        # 构建新版本号
        new_version = ".".join(map(str, main_version))
        
        # 添加构建号（如果有）
        if build > 0:
            new_version += f".{build}"
        
        # 添加后缀（如果有）
        if suffix_type == "hotfix":
            if suffix_num > 0:
                new_version += f"-{suffix_num} hotfix"
            else:
                new_version += " hotfix"
        elif suffix_type == "remake":
            new_version += " remake"
        
        return new_version
    
    @staticmethod
    def is_valid_version(version_str):
        """
        验证版本号格式是否有效
        
        Args:
            version_str (str): 要验证的版本号
            
        Returns:
            bool: 是否为有效版本号
        """
        # 简单验证：检查是否有至少一个点号，并且点号分隔的部分都是数字
        if not version_str:
            return False
            
        # 处理可能的后缀
        base_version = version_str.split()[0]
        
        # 处理可能的hotfix格式 (1.0.0-1)
        if "-" in base_version:
            base_parts = base_version.split("-")
            if len(base_parts) != 2:
                return False
            base_version = base_parts[0]
            hotfix_num = base_parts[1]
            if not hotfix_num.isdigit():
                return False
        
        # 检查主版本号格式
        version_parts = base_version.split(".")
        if len(version_parts) < 2:
            return False
            
        # 验证每个部分是否为数字
        for part in version_parts:
            if not part.isdigit():
                return False
        
        return True

def compare_versions(version1, version2):
    """向后兼容的版本比较函数"""
    return VersionControl.compare_versions(version1, version2)

def normalize_version(version_str):
    """向后兼容的版本标准化函数"""
    return VersionControl.normalize_version(version_str)

def increment_version(version_str, increment_type="patch"):
    """向后兼容的版本递增函数"""
    return VersionControl.increment_version(version_str, increment_type)

def is_valid_version(version_str):
    """向后兼容的版本验证函数"""
    return VersionControl.is_valid_version(version_str)
