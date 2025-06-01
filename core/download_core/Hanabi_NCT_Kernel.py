# ================================================
# Hanabi Nextgen Crystal Transfer Kernel (Async Version)
# Code Name: H-NCT-Async
# Hanabi's Async FTP/SFTP Kernel
# Developed By ZZBuAoYe
# Version: 1.0.0 Stable
#================================================

import os
import time
import logging
import ftplib
import socket
import threading
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class HanabiNCTAsyncKernel:
    """
    Hanabi的异步FTP下载核心
    使用线程池将同步ftplib包装为异步接口
    """
    
    def __init__(self, max_workers=10):
        """
        初始化异步FTP下载核心
        
        参数:
            max_workers: 线程池最大工作线程数
        """
        self.logger = logging.getLogger("HanabiNCTAsyncKernel")
        self.client = None
        self.is_connected = False
        self.current_dir = "/"
        self.transfer_tasks = {}
        self._lock = threading.Lock()
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def connect(self, host: str, port: int = 21, 
                    user: str = "anonymous", password: str = "",
                    timeout: int = 30) -> bool:
        """
        异步连接到FTP服务器
        
        参数:
            host: FTP服务器地址
            port: 端口号，默认21
            user: 用户名，默认anonymous
            password: 密码，默认为空
            timeout: 超时时间，默认30秒
            
        返回:
            连接是否成功
        """
        # 使用线程池运行同步连接方法
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, 
            functools.partial(self._connect_sync, host, port, user, password, timeout)
        )
    
    def _connect_sync(self, host: str, port: int, 
                    user: str, password: str,
                    timeout: int) -> bool:
        """同步连接实现"""
        try:
            self.client = ftplib.FTP()
            self.client.connect(host, port, timeout)
            self.client.login(user, password)
            self.is_connected = True
            self.current_dir = self.client.pwd()
            
            self.logger.info(f"已连接到FTP服务器: {host}:{port}")
            return True
        except Exception as e:
            self.logger.error(f"连接FTP服务器失败: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self) -> None:
        """异步断开与FTP服务器的连接"""
        if self.is_connected:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._disconnect_sync
            )
    
    def _disconnect_sync(self) -> None:
        """同步断开连接实现"""
        if self.client and self.is_connected:
            try:
                self.client.quit()
                self.logger.info("已断开FTP连接")
            except Exception as e:
                self.logger.error(f"断开FTP连接时出错: {str(e)}")
                try:
                    self.client.close()
                except:
                    pass
            finally:
                self.is_connected = False
                self.client = None
    
    async def list_files(self, path: str = "./") -> List[Dict[str, Any]]:
        """
        异步列出指定路径下的文件和目录
        
        参数:
            path: 要列出内容的路径，默认为当前目录
            
        返回:
            文件和目录信息的列表
        """
        if not self.is_connected:
            raise ConnectionError("未连接到FTP服务器")
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, functools.partial(self._list_files_sync, path)
        )
    
    def _list_files_sync(self, path: str) -> List[Dict[str, Any]]:
        """同步列出文件实现"""
        result = []
        try:
            # 保存当前目录
            original_dir = self.client.pwd()
            
            # 切换到目标目录
            self.client.cwd(path)
            
            # 获取目录列表
            file_list = []
            self.client.dir(lambda line: file_list.append(line))
            
            # 获取文件名列表
            names = self.client.nlst()
            
            # 解析目录列表，识别文件和目录
            for i, line in enumerate(file_list):
                if i < len(names):
                    name = names[i]
                    parts = line.split()
                    
                    # 判断是否为目录
                    is_dir = line.startswith('d')
                    
                    # 获取文件大小，如果是目录则为0
                    size = 0
                    if not is_dir and len(parts) >= 5:
                        try:
                            size = int(parts[4])
                        except:
                            pass
                    
                    # 创建文件或目录信息
                    file_info = {
                        "name": name,
                        "type": "directory" if is_dir else "file",
                        "size": size,
                        "modify_time": " ".join(parts[5:8]) if len(parts) >= 8 else ""
                    }
                    result.append(file_info)
            
            # 恢复原来的目录
            self.client.cwd(original_dir)
            
            return result
        except Exception as e:
            self.logger.error(f"列出文件失败: {str(e)}")
            raise
    
    async def download_file(self, remote_path: str, local_path: str, 
                          progress_callback=None) -> bool:
        """
        异步下载文件
        
        参数:
            remote_path: 远程文件路径
            local_path: 本地保存路径
            progress_callback: 进度回调函数，接收参数(已下载大小, 总大小)
            
        返回:
            下载是否成功
        """
        if not self.is_connected:
            raise ConnectionError("未连接到FTP服务器")
        
        # 确保本地目录存在
        local_dir = os.path.dirname(local_path)
        os.makedirs(local_dir, exist_ok=True)
        
        # 包装进度回调函数为协程
        async_callback = None
        if progress_callback:
            # 创建一个可以在线程池中安全使用的回调函数
            async_callback = lambda downloaded, total: progress_callback(downloaded, total)
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, 
            functools.partial(self._download_file_sync, remote_path, local_path, async_callback)
        )
    
    def _download_file_sync(self, remote_path, local_path, async_callback=None):
        """同步下载文件实现"""
        task_id = f"{remote_path}_{int(time.time())}"
        try:
            # 获取文件大小
            file_size = self._get_file_size(remote_path)
            if file_size == -1:
                self.logger.error(f"未找到远程文件或无法获取大小: {remote_path}")
                return False
            
            # 创建任务记录
            with self._lock:
                self.transfer_tasks[task_id] = {
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "total_size": file_size,
                    "downloaded": 0,
                    "status": "downloading"
                }
            
            # 设置进度回调
            downloaded = 0
            last_update_time = time.time()
            
            # 保存回调函数的引用
            _async_callback = async_callback
            
            def callback(data):
                nonlocal downloaded, last_update_time, _async_callback
                chunk_size = len(data)
                downloaded += chunk_size
                
                # 更新任务状态
                with self._lock:
                    self.transfer_tasks[task_id]["downloaded"] = downloaded
                
                # 限制进度回调频率并异步调用
                current_time = time.time()
                if current_time - last_update_time > 0.5 and _async_callback:
                    # 在线程池中不能直接使用 asyncio.create_task
                    # 使用回调函数而不尝试创建异步任务
                    try:
                        _async_callback(downloaded, file_size)
                        last_update_time = current_time
                    except Exception as e:
                        self.logger.warning(f"进度回调异常: {str(e)}")
                        # 出错时不再尝试回调
                        _async_callback = None
                
                return data
            
            # 下载文件
            with open(local_path, 'wb') as f:
                self.client.retrbinary(f"RETR {remote_path}", lambda data: f.write(callback(data)))
            
            # 最后一次回调确保显示100%
            if _async_callback:
                # 在线程池中不能直接使用 asyncio.create_task
                try:
                    _async_callback(file_size, file_size)
                except Exception as e:
                    self.logger.warning(f"最终进度回调异常: {str(e)}")
            
            # 更新任务状态
            with self._lock:
                self.transfer_tasks[task_id]["status"] = "completed"
            
            self.logger.info(f"文件下载完成: {remote_path} -> {local_path}")
            return True
            
        except Exception as e:
            with self._lock:
                if task_id in self.transfer_tasks:
                    self.transfer_tasks[task_id]["status"] = "failed"
            
            self.logger.error(f"下载文件失败 {remote_path}: {str(e)}")
            return False
    
    def _get_file_size(self, remote_path: str) -> int:
        """获取远程文件大小，如果失败返回-1"""
        try:
            self.client.voidcmd("TYPE I")  # 二进制模式
            size = self.client.size(remote_path)
            return size
        except:
            return -1
    
    async def get_transfer_status(self, task_id: str) -> Dict[str, Any]:
        """异步获取传输任务状态"""
        return await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(self._get_transfer_status_sync, task_id)
        )
    
    def _get_transfer_status_sync(self, task_id: str) -> Dict[str, Any]:
        """同步获取传输任务状态"""
        with self._lock:
            if task_id in self.transfer_tasks:
                return self.transfer_tasks[task_id].copy()
        return {"status": "not_found"}
    
    async def cancel_transfer(self, task_id: str) -> bool:
        """
        异步取消传输任务
        注意：ftplib不支持直接取消传输，但我们可以标记为已取消
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(self._cancel_transfer_sync, task_id)
        )
    
    def _cancel_transfer_sync(self, task_id: str) -> bool:
        """同步取消传输任务"""
        with self._lock:
            if task_id in self.transfer_tasks:
                self.transfer_tasks[task_id]["status"] = "canceled"
                return True
        return False
    
    async def upload_file(self, local_path: str, remote_path: str,
                        progress_callback=None) -> bool:
        """
        异步上传文件到FTP服务器
        
        参数:
            local_path: 本地文件路径
            remote_path: 远程保存路径
            progress_callback: 进度回调函数，接收参数(已上传大小, 总大小)
            
        返回:
            上传是否成功
        """
        if not self.is_connected:
            raise ConnectionError("未连接到FTP服务器")
        
        # 检查本地文件是否存在
        if not os.path.isfile(local_path):
            self.logger.error(f"本地文件不存在: {local_path}")
            return False
        
        # 包装进度回调函数为协程
        async_callback = None
        if progress_callback:
            async_callback = lambda uploaded, total: asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None, functools.partial(progress_callback, uploaded, total)
                )
            )
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, 
            functools.partial(self._upload_file_sync, local_path, remote_path, async_callback)
        )
    
    def _upload_file_sync(self, local_path, remote_path, async_callback=None):
        """同步上传文件实现"""
        task_id = f"upload_{local_path}_{int(time.time())}"
        try:
            # 获取文件大小
            file_size = os.path.getsize(local_path)
            
            # 创建任务记录
            with self._lock:
                self.transfer_tasks[task_id] = {
                    "remote_path": remote_path,
                    "local_path": local_path,
                    "total_size": file_size,
                    "uploaded": 0,
                    "status": "uploading"
                }
            
            # 设置进度回调
            uploaded = 0
            last_update_time = time.time()
            
            # 确保远程目录存在
            self._ensure_remote_dirs(os.path.dirname(remote_path))
            
            # 保存回调函数的引用
            _async_callback = async_callback
            
            # 上传文件
            with open(local_path, 'rb') as f:
                def callback(block):
                    nonlocal uploaded, last_update_time, _async_callback
                    uploaded += len(block)
                    
                    # 更新任务状态
                    with self._lock:
                        self.transfer_tasks[task_id]["uploaded"] = uploaded
                    
                    # 限制进度回调频率并异步调用
                    current_time = time.time()
                    if current_time - last_update_time > 0.5 and _async_callback:
                        # 在线程池中不能直接使用 asyncio.create_task
                        # 使用回调函数而不尝试创建异步任务
                        try:
                            _async_callback(uploaded, file_size)
                            last_update_time = current_time
                        except Exception as e:
                            self.logger.warning(f"上传进度回调异常: {str(e)}")
                            # 出错时不再尝试回调
                            _async_callback = None
                    
                    return block
                
                self.client.storbinary(f"STOR {remote_path}", f, 
                                    blocksize=8192, 
                                    callback=lambda block: callback(block))
            
            # 最后一次回调确保显示100%
            if _async_callback:
                # 在线程池中不能直接使用 asyncio.create_task
                try:
                    _async_callback(file_size, file_size)
                except Exception as e:
                    self.logger.warning(f"最终进度回调异常: {str(e)}")
            
            # 更新任务状态
            with self._lock:
                self.transfer_tasks[task_id]["status"] = "completed"
            
            self.logger.info(f"文件上传完成: {local_path} -> {remote_path}")
            return True
            
        except Exception as e:
            with self._lock:
                if task_id in self.transfer_tasks:
                    self.transfer_tasks[task_id]["status"] = "failed"
            
            self.logger.error(f"上传文件失败 {local_path}: {str(e)}")
            return False
    
    def _ensure_remote_dirs(self, remote_dir: str) -> None:
        """确保远程目录存在，如果不存在则创建"""
        if not remote_dir or remote_dir == "/" or remote_dir == ".":
            return
        
        try:
            # 保存当前目录
            original_dir = self.client.pwd()
            
            # 尝试切换到目标目录，如果成功则已经存在
            try:
                self.client.cwd(remote_dir)
                # 目录存在，切换回原来的目录
                self.client.cwd(original_dir)
                return
            except:
                # 目录不存在，需要创建
                pass
            
            # 切换回根目录
            self.client.cwd("/")
            
            # 逐级创建目录
            dirs = remote_dir.strip("/").split("/")
            for d in dirs:
                if not d:
                    continue
                try:
                    self.client.cwd(d)
                except:
                    try:
                        self.client.mkd(d)
                        self.client.cwd(d)
                    except Exception as e:
                        self.logger.error(f"创建远程目录失败: {d}, 错误: {str(e)}")
                        raise
            
            # 恢复原来的目录
            self.client.cwd(original_dir)
            
        except Exception as e:
            self.logger.error(f"确保远程目录存在时出错: {remote_dir}, 错误: {str(e)}")
            raise
    
    def __del__(self):
        """析构函数，确保关闭线程池"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)