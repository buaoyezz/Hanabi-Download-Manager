# ================================================
# Hanabi Automatic Scheduling Kernel
# Code Name: H-AS Main
# Developed By ZZBuAoYe
# Version: 1.0.0 Stable
# Tips: This Kernel is Central Control Core
#================================================

import os
import re
import logging
import asyncio
import urllib.parse
from typing import Dict, List, Optional, Tuple, Union, Any, Callable

# Kernel List
from core.download_core.Hanabi_NSF_Kernel import DownloadEngine as NSFKernel
from core.download_core.Hanabi_NCT_Kernel import HanabiNCTAsyncKernel as NCTKernel

# log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class HanabiASKernel:
    # Main Kernel
    
    def __init__(self):
        """
        初始化自动调度内核
        """
        self.logger = logging.getLogger("HanabiASKernel")
        # 内核实例
        self.nsf_kernel = None  # NSF内核实例
        self.nct_kernel = None  # NCT内核实例
        self.current_kernel = None  # 当前使用的内核
        self.current_kernel_type = None  # 当前内核类型
        
    def analyze_url(self, url: str) -> str:
        """
        参数:
            url: link
            
        返回:
            kernel type: "NSF" or "NCT"
        """
        try:
            parsed_url = urllib.parse.urlparse(url)
            scheme = parsed_url.scheme.lower()
            netloc = parsed_url.netloc.lower()
            path = parsed_url.path.lower()
            
            # 检查是否是FTP/SFTP链接
            if scheme in ["ftp", "sftp"]:
                self.logger.info(f"检测到FTP/SFTP链接: {url}, 将使用NCT内核")
                return "NCT"
            
            # 检查是否是HTTP/HTTPS链接
            if scheme in ["http", "https"]:
                # 检查是否是已知的FTP网关服务
                ftp_gateways = ["ftpproxy", "ftpgate", "ftpbridge", "ftpweb"]
                if any(gateway in netloc for gateway in ftp_gateways):
                    self.logger.info(f"检测到FTP网关链接: {url}, 将使用NCT内核")
                    return "NCT"
                
                # 检查文件扩展名，某些大文件类型更适合NSF内核
                large_file_extensions = [".iso", ".zip", ".rar", ".7z", ".tar", ".gz", ".mp4", ".mkv", ".avi", ".mov"]
                if any(path.endswith(ext) for ext in large_file_extensions):
                    self.logger.info(f"检测到大文件类型: {path}, 将使用NSF内核")
                    return "NSF"
                
                # 默认使用NSF内核处理HTTP/HTTPS链接
                self.logger.info(f"检测到HTTP/HTTPS链接: {url}, 将使用NSF内核")
                return "NSF"
            
            # 未知协议，默认使用NSF内核
            self.logger.warning(f"未知协议链接: {url}, 默认使用NSF内核")
            return "NSF"
            
        except Exception as e:
            self.logger.error(f"分析URL时出错: {str(e)}, 默认使用NSF内核")
            return "NSF"
    
    async def initialize_download(self, url: str, headers: Dict[str, str] = None, 
                               save_path: str = None, file_name: str = None, 
                               max_concurrent: int = 8, **kwargs) -> Tuple[bool, str]:
        """
        初始化下载任务，自动选择合适的内核
        
        参数:
            url: link
            headers: HTTP request headers
            save_path: save path
            file_name: file name
            max_concurrent: max concurrent
            **kwargs: other parameters, will pass to specific kernel
            
        返回:
            (是否成功初始化, error message)
        """
        try:
            # 分析URL，确定使用哪个内核
            kernel_type = self.analyze_url(url)
            self.current_kernel_type = kernel_type
            
            # 根据内核类型初始化相应内核
            if kernel_type == "NSF":
                # 初始化NSF内核 (HTTP/HTTPS下载)
                self.nsf_kernel = NSFKernel(
                    url=url,
                    headers=headers or {},
                    max_concurrent=max_concurrent,
                    save_path=save_path,
                    file_name=file_name,
                    **kwargs
                )
                self.current_kernel = self.nsf_kernel
                self.logger.info(f"已初始化NSF内核用于下载: {url}")
                return True, ""
                
            elif kernel_type == "NCT":
                # 初始化NCT内核 (FTP/SFTP下载)
                self.nct_kernel = NCTKernel(max_workers=max_concurrent)
                self.current_kernel = self.nct_kernel
                
                # 解析FTP连接信息
                parsed_url = urllib.parse.urlparse(url)
                host = parsed_url.netloc
                port = 21  # 默认FTP端口
                if ":" in host:
                    host, port_str = host.split(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        pass
                
                # 提取用户名和密码
                username = "anonymous"
                password = ""
                if parsed_url.username:
                    username = parsed_url.username
                if parsed_url.password:
                    password = parsed_url.password
                
                # 连接到FTP服务器
                connected = await self.nct_kernel.connect(
                    host=host,
                    port=port,
                    user=username,
                    password=password
                )
                
                if not connected:
                    return False, f"无法连接到FTP服务器: {host}:{port}"
                
                self.logger.info(f"已初始化NCT内核用于下载: {url}")
                return True, ""
            
            else:
                return False, f"未知内核类型: {kernel_type}"
                
        except Exception as e:
            error_msg = f"初始化下载任务时出错: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    async def start_download(self) -> bool:
        """
        开始下载任务
        
        返回:
            是否成功启动下载
        """
        try:
            if not self.current_kernel:
                self.logger.error("未初始化下载内核，无法开始下载")
                return False
            
            if self.current_kernel_type == "NSF":
                # NSF内核使用QThread，直接start()
                self.nsf_kernel.start()
                return True
                
            elif self.current_kernel_type == "NCT":
                # NCT内核已经是异步的，这里不需要额外操作
                # 实际下载会在download_file方法中执行
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"启动下载任务时出错: {str(e)}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str, 
                         progress_callback=None) -> bool:
        """
        下载文件（主要用于NCT内核）
        
        参数:
            remote_path: 远程文件路径
            local_path: 本地保存路径
            progress_callback: 进度回调函数
            
        返回:
            下载是否成功
        """
        if not self.current_kernel or self.current_kernel_type != "NCT":
            self.logger.error("当前内核不是NCT或未初始化，无法使用此方法下载文件")
            return False
        
        try:
            return await self.nct_kernel.download_file(
                remote_path=remote_path,
                local_path=local_path,
                progress_callback=progress_callback
            )
        except Exception as e:
            self.logger.error(f"下载文件时出错: {str(e)}")
            return False
    
    def pause_download(self) -> bool:
        """
        暂停下载任务
        
        返回:
            是否成功暂停
        """
        try:
            if not self.current_kernel:
                return False
                
            if self.current_kernel_type == "NSF":
                self.nsf_kernel.pause()
                return True
                
            elif self.current_kernel_type == "NCT":
                # NCT内核目前不支持暂停，只能取消
                self.logger.warning("NCT内核不支持暂停功能，请使用stop_download()")
                return False
                
            return False
            
        except Exception as e:
            self.logger.error(f"暂停下载任务时出错: {str(e)}")
            return False
    
    def resume_download(self) -> bool:
        """
        恢复下载任务
        
        返回:
            是否成功恢复
        """
        try:
            if not self.current_kernel:
                return False
                
            if self.current_kernel_type == "NSF":
                self.nsf_kernel.resume()
                return True
                
            elif self.current_kernel_type == "NCT":
                # NCT内核目前不支持恢复，需要重新开始
                self.logger.warning("NCT内核不支持恢复功能，请重新初始化下载")
                return False
                
            return False
            
        except Exception as e:
            self.logger.error(f"恢复下载任务时出错: {str(e)}")
            return False
    
    async def stop_download(self) -> bool:
        """
        停止下载任务
        
        返回:
            是否成功停止
        """
        try:
            if not self.current_kernel:
                return False
                
            if self.current_kernel_type == "NSF":
                self.nsf_kernel.stop()
                return True
                
            elif self.current_kernel_type == "NCT":
                await self.nct_kernel.disconnect()
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"停止下载任务时出错: {str(e)}")
            return False
    
    def get_download_status(self) -> Dict[str, Any]:
        """
        获取当前下载状态
        
        返回:
            包含下载状态信息的字典
        """
        try:
            if not self.current_kernel:
                return {"status": "未初始化", "progress": 0, "speed": 0}
                
            if self.current_kernel_type == "NSF":
                # 从NSF内核获取状态
                return {
                    "status": "运行中" if self.nsf_kernel.is_running else "已停止",
                    "progress": self.nsf_kernel.progress,
                    "speed": self.nsf_kernel.current_speed,
                    "file_size": self.nsf_kernel.file_size,
                    "downloaded": self.nsf_kernel.downloaded_size,
                    "remaining": self.nsf_kernel.file_size - self.nsf_kernel.downloaded_size if self.nsf_kernel.file_size > 0 else 0,
                    "kernel_type": "NSF"
                }
                
            elif self.current_kernel_type == "NCT":
                # 从NCT内核获取状态（需要实现）
                # 注意：NCT内核目前没有直接提供状态查询方法，这里只返回基本信息
                return {
                    "status": "运行中" if self.nct_kernel.is_connected else "已停止",
                    "progress": 0,  # 需要在实际使用时通过回调更新
                    "speed": 0,     # 需要在实际使用时通过回调更新
                    "kernel_type": "NCT"
                }
                
            return {"status": "未知", "progress": 0, "speed": 0}
            
        except Exception as e:
            self.logger.error(f"获取下载状态时出错: {str(e)}")
            return {"status": "错误", "progress": 0, "speed": 0, "error": str(e)}
    
    def __del__(self):
        """
        析构函数，确保资源被正确释放
        """
        try:
            # 停止并清理NSF内核
            if self.nsf_kernel:
                self.nsf_kernel.stop()
                
            # 断开NCT内核连接
            if self.nct_kernel and hasattr(self.nct_kernel, 'executor'):
                self.nct_kernel.executor.shutdown(wait=False)
                
        except Exception as e:
            self.logger.error(f"清理资源时出错: {str(e)}")
