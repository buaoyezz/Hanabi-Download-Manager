#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Auto_adjust.py - 自动调整模块
# 作为Hanabi NSF内核组件
# 开发者: ZZBuAoYe

"""
自动调整模块
提供智能下载块调整功能，监控和处理慢速块
"""

import logging
import threading
import time
from typing import Dict, List, Any, Optional, Callable

class DownloadOptimizer:
    """下载优化器 - 动态调整下载块和线程"""
    
    def __init__(self, optimization_level: int = 2):
        """初始化下载优化器
        
        Args:
            optimization_level: 优化级别(1-3)，数值越大优化越激进
        """
        self.optimization_level = max(1, min(3, optimization_level))
        self.running = False
        self.monitor_thread = None
        self.lock = threading.RLock()
        
        # 块状态跟踪
        self.block_status = {}  # 块ID -> 状态字典
        self.slow_blocks = set()  # 慢速块ID集合
        self.stalled_blocks = set()  # 停滞块ID集合
        
        # 回调函数
        self.reset_block_fn = None
        self.split_block_fn = None
        self.log_fn = None
        
        # 优化统计
        self.stats = {
            "resets": 0,
            "splits": 0,
            "optimizations": 0,
            "slow_blocks_detected": 0,
            "stalled_blocks_detected": 0
        }
        
        # 配置参数
        self._configure()
    
    def _configure(self):
        """根据优化级别配置参数"""
        # 基础配置
        self.check_interval = 2.0  # 检查间隔(秒)
        
        # 根据优化级别调整参数
        if self.optimization_level == 1:  # 保守模式
            self.slow_threshold = 0.3  # 慢速阈值(相对平均速度的比例)
            self.stall_threshold = 5.0  # 停滞阈值(秒)
            self.reset_threshold = 3  # 重置阈值(检测次数)
            self.split_threshold = 5  # 分割阈值(检测次数)
        elif self.optimization_level == 2:  # 平衡模式
            self.slow_threshold = 0.5
            self.stall_threshold = 3.0
            self.reset_threshold = 2
            self.split_threshold = 4
        else:  # 激进模式
            self.slow_threshold = 0.7
            self.stall_threshold = 2.0
            self.reset_threshold = 1
            self.split_threshold = 3
    
    def set_optimization_level(self, level: int) -> None:
        """设置优化级别
        
        Args:
            level: 优化级别(1-3)
        """
        if 1 <= level <= 3 and level != self.optimization_level:
            self.optimization_level = level
            self._configure()
            self._log(f"优化级别已设置为 {level}")
    
    def set_download_handlers(self, reset_block_fn: Callable = None, 
                             split_block_fn: Callable = None,
                             log_fn: Callable = None) -> None:
        """设置下载处理函数
        
        Args:
            reset_block_fn: 重置块的回调函数
            split_block_fn: 分割块的回调函数
            log_fn: 日志记录函数
        """
        self.reset_block_fn = reset_block_fn
        self.split_block_fn = split_block_fn
        self.log_fn = log_fn
    
    def _log(self, message: str) -> None:
        """记录日志
        
        Args:
            message: 日志消息
        """
        if self.log_fn:
            self.log_fn(message)
        else:
            logging.debug(f"[下载优化器] {message}")
    
    def start_optimization(self) -> bool:
        """启动优化
        
        Returns:
            bool: 是否成功启动
        """
        with self.lock:
            if self.running:
                return False
            
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._optimization_loop,
                daemon=True
            )
            self.monitor_thread.start()
            self._log("下载优化已启动")
            return True
    
    def stop_optimization(self) -> bool:
        """停止优化
        
        Returns:
            bool: 是否成功停止
        """
        with self.lock:
            if not self.running:
                return False
            
            self.running = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(1.0)
            
            self.monitor_thread = None
            self._log("下载优化已停止")
            return True
    
    def update_block_status(self, block_id: int, current_pos: int, 
                           start_pos: int, end_pos: int, active: bool = True) -> None:
        """更新块状态
        
        Args:
            block_id: 块ID
            current_pos: 当前位置
            start_pos: 起始位置
            end_pos: 结束位置
            active: 是否激活
        """
        with self.lock:
            # 获取现有状态或创建新状态
            if block_id not in self.block_status:
                self.block_status[block_id] = {
                    "start_pos": start_pos,
                    "current_pos": current_pos,
                    "end_pos": end_pos,
                    "active": active,
                    "last_pos": current_pos,
                    "last_update": time.time(),
                    "speed": 0,
                    "slow_count": 0,
                    "stall_count": 0
                }
                return
            
            # 更新现有状态
            status = self.block_status[block_id]
            
            # 计算速度
            now = time.time()
            time_diff = now - status["last_update"]
            if time_diff >= 0.5:  # 至少0.5秒才计算速度
                pos_diff = current_pos - status["last_pos"]
                if pos_diff > 0:
                    status["speed"] = pos_diff / time_diff
                status["last_update"] = now
                status["last_pos"] = current_pos
            
            # 更新位置和状态
            status["current_pos"] = current_pos
            status["active"] = active
            
            # 如果块已完成，清除慢速和停滞标记
            if current_pos >= end_pos:
                if block_id in self.slow_blocks:
                    self.slow_blocks.remove(block_id)
                if block_id in self.stalled_blocks:
                    self.stalled_blocks.remove(block_id)
    
    def _optimization_loop(self) -> None:
        """优化循环"""
        while self.running:
            try:
                # 检查间隔
                time.sleep(self.check_interval)
                
                # 执行优化
                self._optimize_blocks()
                
            except Exception as e:
                self._log(f"优化循环出错: {e}")
                time.sleep(5.0)  # 出错后暂停较长时间
    
    def _optimize_blocks(self) -> None:
        """优化下载块"""
        with self.lock:
            # 如果没有块，直接返回
            if not self.block_status:
                return
            
            # 计算平均速度
            active_blocks = [b for b in self.block_status.values() 
                            if b["active"] and b["current_pos"] < b["end_pos"]]
            
            if not active_blocks:
                return
            
            # 计算平均速度
            avg_speed = sum(b["speed"] for b in active_blocks) / len(active_blocks) if active_blocks else 0
            
            # 如果平均速度太低，不执行优化
            if avg_speed < 1024:  # 小于1KB/s
                return
            
            # 检查每个活跃块
            for block_id, status in self.block_status.items():
                # 跳过非活跃或已完成的块
                if not status["active"] or status["current_pos"] >= status["end_pos"]:
                    continue
                
                # 计算块的剩余大小
                remaining = status["end_pos"] - status["current_pos"]
                
                # 检查慢速块
                if status["speed"] > 0 and status["speed"] < avg_speed * self.slow_threshold:
                    status["slow_count"] += 1
                    
                    # 如果连续多次检测到慢速，标记为慢速块
                    if status["slow_count"] >= self.reset_threshold:
                        if block_id not in self.slow_blocks:
                            self.slow_blocks.add(block_id)
                            self.stats["slow_blocks_detected"] += 1
                            self._log(f"检测到慢速块 #{block_id}: {status['speed']:.2f} B/s (平均: {avg_speed:.2f} B/s)")
                        
                        # 尝试重置块
                        if self.reset_block_fn and status["slow_count"] >= self.reset_threshold:
                            self.reset_block_fn(block_id)
                            status["slow_count"] = 0
                            self.stats["resets"] += 1
                            self._log(f"重置慢速块 #{block_id}")
                else:
                    # 重置慢速计数
                    status["slow_count"] = 0
                
                # 检查停滞块
                now = time.time()
                if status["last_update"] < now - self.stall_threshold and status["current_pos"] == status["last_pos"]:
                    status["stall_count"] += 1
                    
                    # 如果连续多次检测到停滞，标记为停滞块
                    if status["stall_count"] >= self.reset_threshold:
                        if block_id not in self.stalled_blocks:
                            self.stalled_blocks.add(block_id)
                            self.stats["stalled_blocks_detected"] += 1
                            self._log(f"检测到停滞块 #{block_id}: {now - status['last_update']:.1f}秒未更新")
                        
                        # 尝试重置块
                        if self.reset_block_fn:
                            self.reset_block_fn(block_id)
                            status["stall_count"] = 0
                            self.stats["resets"] += 1
                            self._log(f"重置停滞块 #{block_id}")
                else:
                    # 重置停滞计数
                    status["stall_count"] = 0
                
                # 处理大块分割
                # 只有在块很大且下载很慢的情况下才分割
                if (self.split_block_fn and 
                    remaining > 1024 * 1024 and  # 至少1MB
                    (block_id in self.slow_blocks or block_id in self.stalled_blocks) and
                    status["slow_count"] >= self.split_threshold):
                    
                    # 计算分割点 - 在当前位置和结束位置之间的中点
                    split_point = status["current_pos"] + remaining // 2
                    
                    # 确保分割点至少比当前位置大1KB
                    if split_point > status["current_pos"] + 1024:
                        new_block_id = self.split_block_fn(block_id, split_point)
                        if new_block_id is not None:
                            self.stats["splits"] += 1
                            self._log(f"分割块 #{block_id} 在位置 {split_point}，生成新块 #{new_block_id}")
                            
                            # 重置慢速和停滞计数
                            status["slow_count"] = 0
                            status["stall_count"] = 0
            
            # 更新优化统计
            self.stats["optimizations"] += 1
    
    def optimize_thread_count(self, file_size: int = -1, connection_speed: int = -1) -> int:
        """优化线程数
        
        Args:
            file_size: 文件大小(字节)
            connection_speed: 连接速度(字节/秒)
            
        Returns:
            int: 推荐的线程数
        """
        # 如果文件大小或连接速度未知，使用默认值
        if file_size <= 0 or connection_speed <= 0:
            return 0  # 表示使用默认线程数
        
        # 基于文件大小的基础线程数
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb < 10:  # 小于10MB
            base_threads = 4
        elif file_size_mb < 50:  # 小于50MB
            base_threads = 8
        elif file_size_mb < 200:  # 小于200MB
            base_threads = 16
        elif file_size_mb < 1024:  # 小于1GB
            base_threads = 24
        else:  # 大于1GB
            base_threads = 32
        
        # 基于连接速度的调整因子
        speed_mbps = connection_speed / (1024 * 1024 / 8)  # 转换为Mbps
        
        if speed_mbps < 1:  # 低于1Mbps
            speed_factor = 0.5
        elif speed_mbps < 5:  # 低于5Mbps
            speed_factor = 0.75
        elif speed_mbps < 20:  # 低于20Mbps
            speed_factor = 1.0
        elif speed_mbps < 50:  # 低于50Mbps
            speed_factor = 1.25
        elif speed_mbps < 100:  # 低于100Mbps
            speed_factor = 1.5
        else:  # 高于100Mbps
            speed_factor = 2.0
        
        # 根据优化级别调整
        level_factor = 0.8 + (self.optimization_level * 0.2)
        
        # 计算最终线程数
        thread_count = int(base_threads * speed_factor * level_factor)
        
        # 限制在合理范围内
        thread_count = max(4, min(32, thread_count))
        
        return thread_count
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计信息
        
        Returns:
            dict: 优化统计信息
        """
        with self.lock:
            stats = self.stats.copy()
            stats.update({
                "slow_blocks": len(self.slow_blocks),
                "stalled_blocks": len(self.stalled_blocks),
                "active_blocks": len([b for b in self.block_status.values() if b["active"]]),
                "total_blocks": len(self.block_status),
                "optimization_level": self.optimization_level,
                "running": self.running
            })
            return stats


def optimize_url_connection(url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
    """优化URL连接（占位函数，实际由DNS_CDN_Check模块实现）
    
    Args:
        url: 下载URL
        headers: 请求头
        
    Returns:
        dict: 包含优化后的URL和请求头
    """
    # 这个函数是一个占位符，实际功能由DNS_CDN_Check模块实现
    return {"url": url, "headers": headers or {}, "best_ip": None}

# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    optimizer = DownloadOptimizer(optimization_level=2)
    
    # 模拟块状态更新
    for i in range(5):
        optimizer.update_block_status(i, 1000, 0, 10000, True)
    
    # 启动优化
    optimizer.start_optimization()
    
    # 模拟运行
    try:
        for _ in range(10):
            time.sleep(1)
            # 更新块状态
            for i in range(5):
                # 模拟不同的下载速度
                if i == 2:  # 慢速块
                    optimizer.update_block_status(i, 1100, 0, 10000, True)
                elif i == 3:  # 停滞块
                    optimizer.update_block_status(i, 1000, 0, 10000, True)
                else:  # 正常块
                    optimizer.update_block_status(i, 5000, 0, 10000, True)
    finally:
        # 停止优化
        optimizer.stop_optimization()
        
        # 打印统计信息
        print(optimizer.get_optimization_stats())
