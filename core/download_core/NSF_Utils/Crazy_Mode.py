#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Crazy_Mode.py - Utils
# NSF的Crazy模式
# Author: ZZBuAoYe

"""
疯狂模式处理模块
支持64-128线程的高并发下载
警告：疯狂模式可能导致下载文件损坏、服务器拒绝连接或系统资源耗尽！
"""

import logging
import threading
import time
import os
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 疯狂模式配置
CRAZY_MODE_MIN_THREADS = 64
CRAZY_MODE_MAX_THREADS = 128
CRAZY_MODE_MIN_BLOCK_SIZE = 512 * 1024  # 512KB最小块大小
CRAZY_MODE_BUFFER_SIZE = 256 * 1024  # 256KB缓冲区大小

# 工具函数
def getReadableSize(size_bytes):
    """将字节大小转换为人类可读的格式"""
    if size_bytes < 0:
        return "未知"
    elif size_bytes == 0:
        return "0B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

class CrazyModeManager:
    """疯狂模式管理器 - 处理高线程数下载"""
    
    def __init__(self):
        self.enabled = False
        self.thread_count = 0
        self.original_thread_count = 0
        self.download_engine = None
        self.executor = None
        self.blocks = []
        self.active_blocks = 0
        self.lock = threading.RLock()
        self.monitoring = False
        self.monitor_thread = None
        self.last_calculated_boundaries = []  # 存储最后一次计算的分块结果
    
    def enable(self, thread_count: int, download_engine=None) -> bool:
        """启用疯狂模式
        
        Args:
            thread_count: 线程数量
            download_engine: 下载引擎实例
            
        Returns:
            bool: 是否成功启用
        """
        with self.lock:
            # 验证线程数是否在疯狂模式范围内
            if thread_count < CRAZY_MODE_MIN_THREADS:
                logging.warning(f"线程数 {thread_count} 小于疯狂模式最小值 {CRAZY_MODE_MIN_THREADS}，不启用疯狂模式")
                return False
            
            if thread_count > CRAZY_MODE_MAX_THREADS:
                logging.warning(f"线程数 {thread_count} 超过疯狂模式最大值 {CRAZY_MODE_MAX_THREADS}，将限制为 {CRAZY_MODE_MAX_THREADS}")
                thread_count = CRAZY_MODE_MAX_THREADS
            
            self.enabled = True
            self.original_thread_count = thread_count
            self.thread_count = thread_count
            self.download_engine = download_engine
            
            logging.warning(f"疯狂模式已启用！线程数: {thread_count}")
            
            if download_engine:
                self._log_debug(f"疯狂模式已启用，线程数: {thread_count}")
            
            return True
    
    def disable(self) -> None:
        """禁用疯狂模式"""
        with self.lock:
            self.enabled = False
            self.thread_count = 0
            self.stop_monitoring()
            
            if self.download_engine:
                self._log_debug("疯狂模式已禁用")
    
    def _log_debug(self, message: str) -> None:
        """记录调试信息"""
        if self.download_engine and hasattr(self.download_engine, '_log_download_debug'):
            self.download_engine._log_download_debug(f"[疯狂模式] {message}")
        else:
            logging.debug(f"[疯狂模式] {message}")
    
    def create_executor(self) -> ThreadPoolExecutor:
        """创建适用于疯狂模式的线程池
        
        Returns:
            ThreadPoolExecutor: 线程池实例
        """
        if not self.enabled:
            return None
        
        # 创建自定义线程池
        self.executor = ThreadPoolExecutor(
            max_workers=self.thread_count,
            thread_name_prefix="crazy_mode_worker"
        )
        
        self._log_debug(f"创建疯狂模式线程池，工作线程数: {self.thread_count}")
        return self.executor
    
    def patch_download_engine(self) -> bool:
        """修补下载引擎以支持疯狂模式
        
        Returns:
            bool: 是否成功修补
        """
        if not self.enabled or not self.download_engine:
            return False
        
        try:
            # 保存原始方法
            original_execute = self.download_engine._execute_download
            original_calculate = self.download_engine._calculate_blocks
            
            # 修补_execute_download方法
            def patched_execute_download(self_engine):
                if not hasattr(self_engine, 'crazy_mode') or not self_engine.crazy_mode:
                    # 如果不是疯狂模式，使用原始方法
                    return original_execute()
                
                # 疯狂模式处理
                self._log_debug("使用疯狂模式执行下载")
                
                # 使用疯狂模式的线程池
                crazy_executor = self.create_executor()
                if crazy_executor:
                    # 临时替换引擎的executor
                    original_executor = self_engine.executor
                    self_engine.executor = crazy_executor
                    
                    # 调用原始方法
                    result = original_execute()
                    
                    # 恢复原始executor
                    if not self_engine.executor._shutdown:
                        self_engine.executor = original_executor
                    
                    return result
                else:
                    return original_execute()
            
            # 修补_calculate_blocks方法
            def patched_calculate_blocks(self_engine):
                if not hasattr(self_engine, 'crazy_mode') or not self_engine.crazy_mode:
                    # 如果不是疯狂模式，使用原始方法
                    return original_calculate()
                
                # 疯狂模式下的分块计算
                self._log_debug("使用疯狂模式计算下载块")
                
                # 确保文件大小有效
                if self_engine.known_file_size <= 0:
                    self._log_debug(f"文件大小无效 ({self_engine.known_file_size})，无法计算分块")
                    return []
                
                # 计算分块
                file_size = self_engine.known_file_size
                file_size_gb = file_size / (1024 * 1024 * 1024)
                
                # 根据文件大小确定分段数
                if file_size_gb < 0.5:  # 小于500MB
                    segment_count = min(64, self.thread_count)
                    reason = f"疯狂模式-文件小于500MB，使用{segment_count}个分段"
                elif file_size_gb < 2:  # 小于2GB
                    segment_count = min(96, self.thread_count)
                    reason = f"疯狂模式-文件在500MB-2GB范围，使用{segment_count}个分段"
                else:  # 大于2GB
                    segment_count = self.thread_count
                    reason = f"疯狂模式-文件大于2GB，使用全部{segment_count}个分段"
                
                self._log_debug(f"疯狂模式分段计算: {reason}, 文件大小={getReadableSize(self_engine.known_file_size)}")
                logging.warning(f"疯狂模式分段计算: {reason}")
                
                # 计算每块的大小
                basic_block_size = max(CRAZY_MODE_MIN_BLOCK_SIZE, file_size // segment_count)
                
                # 创建块边界
                boundaries = []
                start_pos = 0
                
                for i in range(segment_count):
                    # 最后一个块获取所有剩余大小
                    if i == segment_count - 1:
                        boundaries.append([start_pos, file_size - 1])
                        break
                    
                    # 计算当前块的结束位置
                    end_pos = min(start_pos + basic_block_size - 1, file_size - 1)
                    
                    # 确保块至少有1字节
                    if end_pos <= start_pos:
                        end_pos = start_pos + 1
                    
                    boundaries.append([start_pos, end_pos])
                    start_pos = end_pos + 1
                    
                    # 如果已经没有更多内容，跳出循环
                    if start_pos >= file_size:
                        break
                
                # 记录块边界信息
                self._log_debug(f"疯狂模式分块计算完成: 共{len(boundaries)}个块")
                for i, (start, end) in enumerate(boundaries):
                    block_size = end - start + 1
                    self._log_debug(f"块 #{i}: 起始={start}, 结束={end}, 大小={getReadableSize(block_size)}, "
                                   f"占比={block_size/file_size*100:.2f}%")
                
                # 保存计算结果以便直接获取
                self.last_calculated_boundaries = boundaries
                
                return boundaries
            
            # 应用补丁
            # 注意：这里使用的是Python的方法绑定技巧
            import types
            self.download_engine._original_execute_download = original_execute
            self.download_engine._execute_download = types.MethodType(
                lambda self_engine: patched_execute_download(self_engine), 
                self.download_engine
            )
            
            self.download_engine._original_calculate_blocks = original_calculate
            self.download_engine._calculate_blocks = types.MethodType(
                lambda self_engine: patched_calculate_blocks(self_engine), 
                self.download_engine
            )
            
            self._log_debug("下载引擎已成功修补以支持疯狂模式")
            
            # 启动监控
            self.start_monitoring()
            
            return True
            
        except Exception as e:
            logging.error(f"修补下载引擎失败: {e}")
            self._log_debug(f"修补下载引擎失败: {e}")
            return False
    
    def restore_download_engine(self) -> bool:
        """恢复下载引擎的原始方法
        
        Returns:
            bool: 是否成功恢复
        """
        if not self.download_engine:
            return False
        
        try:
            # 恢复原始方法
            if hasattr(self.download_engine, '_original_execute_download'):
                self.download_engine._execute_download = self.download_engine._original_execute_download
                delattr(self.download_engine, '_original_execute_download')
            
            if hasattr(self.download_engine, '_original_calculate_blocks'):
                self.download_engine._calculate_blocks = self.download_engine._original_calculate_blocks
                delattr(self.download_engine, '_original_calculate_blocks')
            
            self._log_debug("下载引擎已恢复原始方法")
            return True
            
        except Exception as e:
            logging.error(f"恢复下载引擎失败: {e}")
            return False
    
    def start_monitoring(self) -> None:
        """启动疯狂模式监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        self._log_debug("疯狂模式监控已启动")
    
    def stop_monitoring(self) -> None:
        """停止疯狂模式监控"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(1.0)
        self.monitor_thread = None
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        last_log_time = time.time()
        
        while self.monitoring and self.download_engine:
            try:
                # 每3秒检查一次
                time.sleep(3.0)
                
                # 获取当前活跃块数
                active_count = 0
                if hasattr(self.download_engine, 'blocks'):
                    for block in self.download_engine.blocks:
                        if hasattr(block, 'active') and block.active:
                            active_count += 1
                
                self.active_blocks = active_count
                
                # 每30秒记录一次状态
                now = time.time()
                if now - last_log_time >= 30:
                    self._log_debug(f"疯狂模式状态: 活跃块: {active_count}/{len(self.download_engine.blocks) if hasattr(self.download_engine, 'blocks') else 0}")
                    last_log_time = now
                
                # 检查系统资源
                self._check_system_resources()
                
            except Exception as e:
                logging.error(f"疯狂模式监控错误: {e}")
                time.sleep(5.0)  # 出错后暂停较长时间
    
    def _check_system_resources(self) -> None:
        """检查系统资源使用情况"""
        try:
            import psutil
            
            # 获取CPU和内存使用率
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory_percent = psutil.virtual_memory().percent
            
            # 如果资源使用率过高，发出警告
            if cpu_percent > 90 or memory_percent > 90:
                self._log_debug(f"系统资源使用率过高! CPU: {cpu_percent}%, 内存: {memory_percent}%")
                
                # 如果资源严重不足，可以考虑自动减少线程数
                if cpu_percent > 95 or memory_percent > 95:
                    self._reduce_threads()
            
        except ImportError:
            # psutil不可用，跳过资源检查
            pass
        except Exception as e:
            logging.error(f"检查系统资源失败: {e}")
    
    def _reduce_threads(self) -> None:
        """减少线程数以缓解系统压力"""
        with self.lock:
            if self.thread_count <= CRAZY_MODE_MIN_THREADS:
                return
            
            # 减少25%的线程数
            new_thread_count = max(CRAZY_MODE_MIN_THREADS, int(self.thread_count * 0.75))
            if new_thread_count != self.thread_count:
                self._log_debug(f"系统资源不足，自动减少线程数: {self.thread_count} -> {new_thread_count}")
                self.thread_count = new_thread_count

    def get_calculated_boundaries(self) -> List[List[int]]:
        """获取最后计算的分块边界
        
        Returns:
            List[List[int]]: 分块边界列表 [[起始位置, 结束位置], ...]
        """
        with self.lock:
            return self.last_calculated_boundaries.copy() if self.last_calculated_boundaries else []

    def calculate_boundaries(self, file_size: int) -> List[List[int]]:
        """直接计算分块边界，不需要修补下载引擎
        
        Args:
            file_size: 文件大小(字节)
            
        Returns:
            List[List[int]]: 分块边界列表 [[起始位置, 结束位置], ...]
        """
        if not self.enabled or file_size <= 0:
            return []
            
        # 计算分块
        file_size_gb = file_size / (1024 * 1024 * 1024)
        
        # 根据文件大小确定分段数
        if file_size_gb < 0.5:  # 小于500MB
            segment_count = min(64, self.thread_count)
            reason = f"疯狂模式-文件小于500MB，使用{segment_count}个分段"
        elif file_size_gb < 2:  # 小于2GB
            segment_count = min(96, self.thread_count)
            reason = f"疯狂模式-文件在500MB-2GB范围，使用{segment_count}个分段"
        else:  # 大于2GB
            segment_count = self.thread_count
            reason = f"疯狂模式-文件大于2GB，使用全部{segment_count}个分段"
        
        self._log_debug(f"疯狂模式分段计算: {reason}, 文件大小={getReadableSize(file_size)}")
        
        # 计算每块的大小
        basic_block_size = max(CRAZY_MODE_MIN_BLOCK_SIZE, file_size // segment_count)
        
        # 创建块边界
        boundaries = []
        start_pos = 0
        
        for i in range(segment_count):
            # 最后一个块获取所有剩余大小
            if i == segment_count - 1:
                boundaries.append([start_pos, file_size - 1])
                break
            
            # 计算当前块的结束位置
            end_pos = min(start_pos + basic_block_size - 1, file_size - 1)
            
            # 确保块至少有1字节
            if end_pos <= start_pos:
                end_pos = start_pos + 1
            
            boundaries.append([start_pos, end_pos])
            start_pos = end_pos + 1
            
            # 如果已经没有更多内容，跳出循环
            if start_pos >= file_size:
                break
        
        # 记录块边界信息
        self._log_debug(f"疯狂模式分块计算完成: 共{len(boundaries)}个块")
        
        # 保存计算结果
        self.last_calculated_boundaries = boundaries
        
        return boundaries


# 全局疯狂模式管理器实例
crazy_mode_manager = CrazyModeManager()

def enable_crazy_mode(thread_count: int, download_engine=None) -> bool:
    """启用疯狂模式
    
    Args:
        thread_count: 线程数量
        download_engine: 下载引擎实例
        
    Returns:
        bool: 是否成功启用
    """
    return crazy_mode_manager.enable(thread_count, download_engine)

def disable_crazy_mode() -> None:
    """禁用疯狂模式"""
    crazy_mode_manager.disable()

def patch_download_engine() -> bool:
    """修补下载引擎以支持疯狂模式
    
    Returns:
        bool: 是否成功修补
    """
    return crazy_mode_manager.patch_download_engine()

def restore_download_engine() -> bool:
    """恢复下载引擎的原始方法
    
    Returns:
        bool: 是否成功恢复
    """
    return crazy_mode_manager.restore_download_engine()

def get_crazy_mode_status() -> Dict[str, Any]:
    """获取疯狂模式状态
    
    Returns:
        Dict[str, Any]: 状态信息
    """
    return {
        'enabled': crazy_mode_manager.enabled,
        'thread_count': crazy_mode_manager.thread_count,
        'original_thread_count': crazy_mode_manager.original_thread_count,
        'active_blocks': crazy_mode_manager.active_blocks,
        'monitoring': crazy_mode_manager.monitoring
    }

def get_calculated_boundaries() -> List[List[int]]:
    """获取最后计算的分块边界
    
    Returns:
        List[List[int]]: 分块边界列表 [[起始位置, 结束位置], ...]
    """
    return crazy_mode_manager.get_calculated_boundaries()

def calculate_boundaries(file_size: int) -> List[List[int]]:
    """直接计算分块边界，不需要修补下载引擎
    
    Args:
        file_size: 文件大小(字节)
        
    Returns:
        List[List[int]]: 分块边界列表 [[起始位置, 结束位置], ...]
    """
    return crazy_mode_manager.calculate_boundaries(file_size)

# 使用示例
"""
# 在下载引擎初始化时:
from core.download_core.NSF_Utils.Crazy_Mode import enable_crazy_mode, patch_download_engine

class DownloadEngine(QThread):
    def __init__(self, url, headers=None, max_concurrent=32, ...):
        # ...现有代码...
        
        # 检查是否启用疯狂模式
        self.crazy_mode = max_concurrent > 32
        if self.crazy_mode:
            # 启用疯狂模式
            enable_crazy_mode(max_concurrent, self)
            # 记录日志
            logging.warning(f"NSF内核启用疯狂模式! 线程数: {max_concurrent}")
            self._log_download_debug(f"疯狂模式已启用，线程数: {max_concurrent}")
        
        # ...其余初始化代码...
    
    def run(self):
        # ...现有代码...
        
        # 如果是疯狂模式，修补下载引擎
        if self.crazy_mode:
            from core.download_core.NSF_Utils.Crazy_Mode import patch_download_engine
            patch_download_engine()
        
        # ...继续执行下载...
        
    def stop(self):
        # ...现有代码...
        
        # 如果是疯狂模式，恢复下载引擎
        if self.crazy_mode:
            from core.download_core.NSF_Utils.Crazy_Mode import restore_download_engine
            restore_download_engine()
        
        # ...其余清理代码...
"""
