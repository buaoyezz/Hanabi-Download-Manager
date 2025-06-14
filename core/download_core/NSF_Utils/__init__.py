#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NSF_Utils 包初始化文件
# 提供统一的功能导入接口
# 作为Hanabi NSF内核组件
# 开发者: ZZBuAoYe

"""
Hanabi NSF内核工具集
提供DNS优化、CDN加速、自动调整等高级功能
"""

import logging
import importlib
import sys
import os

# 版本信息
__version__ = "1.0.0"

# 功能模块列表
__all__ = [
    "DNS_CDN_Check",
    "Auto_adjust",
    "Crazy_Mode",
    "NSFEnhancer"
]

# 模块导入状态
_module_status = {
    "DNS_CDN_Check": {"loaded": False, "available": False, "error": None},
    "Auto_adjust": {"loaded": False, "available": False, "error": None},
    "Crazy_Mode": {"loaded": False, "available": False, "error": None},
}

# 尝试导入模块
def _try_import(module_name):
    """尝试导入模块，并记录状态"""
    try:
        module = importlib.import_module(f"core.download_core.NSF_Utils.{module_name}")
        _module_status[module_name]["loaded"] = True
        _module_status[module_name]["available"] = True
        return module
    except ImportError as e:
        _module_status[module_name]["error"] = str(e)
        logging.warning(f"无法导入NSF工具模块 {module_name}: {e}")
        return None
    except Exception as e:
        _module_status[module_name]["error"] = str(e)
        logging.error(f"导入NSF工具模块 {module_name} 时发生错误: {e}")
        return None

# 懒加载模块
DNS_CDN_Check = None
Auto_adjust = None
Crazy_Mode = None

def load_modules(modules=None):
    """加载指定模块或所有模块
    
    Args:
        modules: 要加载的模块列表，如果为None则加载所有模块
        
    Returns:
        已加载的模块字典
    """
    global DNS_CDN_Check, Auto_adjust, Crazy_Mode
    
    if modules is None:
        modules = ["DNS_CDN_Check", "Auto_adjust", "Crazy_Mode"]
    
    loaded_modules = {}
    
    for module_name in modules:
        if module_name == "DNS_CDN_Check" and DNS_CDN_Check is None:
            DNS_CDN_Check = _try_import("DNS_CDN_Check")
            loaded_modules["DNS_CDN_Check"] = DNS_CDN_Check
            
        elif module_name == "Auto_adjust" and Auto_adjust is None:
            Auto_adjust = _try_import("Auto_adjust")
            loaded_modules["Auto_adjust"] = Auto_adjust
            
        elif module_name == "Crazy_Mode" and Crazy_Mode is None:
            Crazy_Mode = _try_import("Crazy_Mode")
            loaded_modules["Crazy_Mode"] = Crazy_Mode
    
    return loaded_modules

def get_module_status():
    """获取模块加载状态
    
    Returns:
        模块状态字典
    """
    return _module_status

class NSFEnhancer:
    """NSF增强器 - 集成所有外部功能的统一接口"""
    
    def __init__(self, enable_dns_cdn=True, enable_auto_adjust=True, enable_crazy_mode=True):
        """初始化NSF增强器
        
        Args:
            enable_dns_cdn: 是否启用DNS和CDN优化
            enable_auto_adjust: 是否启用自动调整
            enable_crazy_mode: 是否启用疯狂模式
        """
        self.modules = load_modules()
        self.dns_cdn_enabled = enable_dns_cdn and self.modules.get("DNS_CDN_Check") is not None
        self.auto_adjust_enabled = enable_auto_adjust and self.modules.get("Auto_adjust") is not None
        self.crazy_mode_enabled = enable_crazy_mode and self.modules.get("Crazy_Mode") is not None
        
        # 初始化组件
        self.cdn_optimizer = None
        self.download_optimizer = None
        
        if self.dns_cdn_enabled:
            try:
                self.cdn_optimizer = self.modules["DNS_CDN_Check"].CDNOptimizer()
                logging.info("NSF增强器: DNS和CDN优化已启用")
            except Exception as e:
                logging.error(f"初始化CDN优化器失败: {e}")
                self.dns_cdn_enabled = False
        
        if self.auto_adjust_enabled:
            try:
                self.download_optimizer = self.modules["Auto_adjust"].DownloadOptimizer()
                logging.info("NSF增强器: 下载自动调整已启用")
            except Exception as e:
                logging.error(f"初始化下载优化器失败: {e}")
                self.auto_adjust_enabled = False
    
    def optimize_url(self, url, headers=None):
        """优化URL连接
        
        Args:
            url: 下载URL
            headers: 请求头
            
        Returns:
            dict: 包含优化后的URL和请求头
        """
        if not self.dns_cdn_enabled or not self.cdn_optimizer:
            return {"url": url, "headers": headers or {}, "best_ip": None}
        
        try:
            result = self.modules["DNS_CDN_Check"].optimize_url_connection(url, headers)
            return result
        except Exception as e:
            logging.error(f"优化URL失败: {e}")
            return {"url": url, "headers": headers or {}, "best_ip": None}
    
    def setup_download_optimizer(self, download_engine, optimization_level=2):
        """设置下载优化器
        
        Args:
            download_engine: 下载引擎实例
            optimization_level: 优化级别(1-3)
            
        Returns:
            bool: 是否设置成功
        """
        if not self.auto_adjust_enabled or not self.download_optimizer:
            return False
        
        try:
            # 设置优化级别
            self.download_optimizer.set_optimization_level(optimization_level)
            
            # 设置处理函数
            self.download_optimizer.set_download_handlers(
                reset_block_fn=lambda block_id: self._reset_block(download_engine, block_id),
                split_block_fn=lambda block_id, split_point: self._split_block(download_engine, block_id, split_point),
                log_fn=lambda msg: download_engine._log_download_debug(f"[优化器] {msg}")
            )
            
            return True
        except Exception as e:
            logging.error(f"设置下载优化器失败: {e}")
            return False
    
    def _reset_block(self, engine, block_id):
        """重置下载块
        
        Args:
            engine: 下载引擎
            block_id: 块ID
        """
        try:
            if 0 <= block_id < len(engine.blocks):
                block = engine.blocks[block_id]
                # 重置块处理逻辑
                if block.active and block.current_position < block.end_position:
                    block.active = False
                    engine._log_download_debug(f"[优化器] 重置块 #{block_id}")
                    # 重新提交块到线程池
                    if engine.executor and not engine.executor._shutdown:
                        engine.executor.submit(engine._process_block, block)
        except Exception as e:
            logging.error(f"重置块失败: {e}")
    
    def _split_block(self, engine, block_id, split_point):
        """分割下载块
        
        Args:
            engine: 下载引擎
            block_id: 块ID
            split_point: 分割点
            
        Returns:
            int: 新块ID，失败返回None
        """
        try:
            if 0 <= block_id < len(engine.blocks):
                block = engine.blocks[block_id]
                # 确保分割点在有效范围内
                if block.current_position < split_point < block.end_position:
                    # 创建新块
                    new_block = type(block)(
                        split_point, split_point, block.end_position,
                        engine.client_manager.create_client(engine.headers)
                    )
                    # 更新原块结束位置
                    block.end_position = split_point - 1
                    # 添加新块到列表
                    engine.blocks.append(new_block)
                    new_block_id = len(engine.blocks) - 1
                    engine._log_download_debug(f"[优化器] 分割块 #{block_id} 在位置 {split_point}，生成新块 #{new_block_id}")
                    # 提交新块到线程池
                    if engine.executor and not engine.executor._shutdown:
                        engine.executor.submit(engine._process_block, new_block)
                    return new_block_id
        except Exception as e:
            logging.error(f"分割块失败: {e}")
        return None
    
    def start_optimization(self):
        """启动优化
        
        Returns:
            bool: 是否成功启动
        """
        if self.auto_adjust_enabled and self.download_optimizer:
            return self.download_optimizer.start_optimization()
        return False
    
    def stop_optimization(self):
        """停止优化
        
        Returns:
            bool: 是否成功停止
        """
        if self.auto_adjust_enabled and self.download_optimizer:
            return self.download_optimizer.stop_optimization()
        return False
    
    def update_block_status(self, block_id, current_pos, start_pos, end_pos, active=True):
        """更新块状态
        
        Args:
            block_id: 块ID
            current_pos: 当前位置
            start_pos: 起始位置
            end_pos: 结束位置
            active: 是否激活
        """
        if self.auto_adjust_enabled and self.download_optimizer:
            self.download_optimizer.update_block_status(
                block_id, current_pos, start_pos, end_pos, active
            )
    
    def optimize_thread_count(self, file_size=-1, connection_speed=-1):
        """优化线程数
        
        Args:
            file_size: 文件大小(字节)
            connection_speed: 连接速度(字节/秒)
            
        Returns:
            int: 推荐的线程数
        """
        if self.auto_adjust_enabled and self.download_optimizer:
            return self.download_optimizer.optimize_thread_count(file_size, connection_speed)
        
        # 默认优化算法
        if file_size <= 0:
            return 16
        
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb < 10:
            return 4
        elif file_size_mb < 100:
            return 8
        elif file_size_mb < 1024:
            return 16
        else:
            return 32
    
    def get_optimization_stats(self):
        """获取优化统计信息
        
        Returns:
            dict: 优化统计信息
        """
        if self.auto_adjust_enabled and self.download_optimizer:
            return self.download_optimizer.get_optimization_stats()
        return {
            "dns_cdn_enabled": self.dns_cdn_enabled,
            "auto_adjust_enabled": self.auto_adjust_enabled
        } 