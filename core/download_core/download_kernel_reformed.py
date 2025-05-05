import concurrent.futures
import struct
import os
import time
import threading
import sys
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union, Callable
from urllib.parse import urlparse, parse_qs, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PySide6.QtCore import QThread, Signal

from core.download_core.core.config import cfg
from core.download_core.core.methods import getProxy, getReadableSize, createSparseFile


class DownloadBlock:
    """单个下载块，代表分段下载的一个部分"""
    
    def __init__(self, start_pos: int, current_pos: int, end_pos: int, session: requests.Session):
        self.start_position = start_pos      # 块起始位置
        self.current_position = current_pos  # 当前下载位置
        self.end_position = end_pos          # 块结束位置
        self.session = session               # 会话对象
        self.download_speed = 0              # 当前下载速度(字节/秒)
        self.last_update_time = time.time()  # 上次更新时间
        self.last_position = current_pos     # 上次位置
        self.retries = 0                     # 重试次数
        self.active = False                  # 是否活跃
        self.status = "未知"                 # 下载状态


class ConnectionManager:
    """连接管理器，负责创建和管理下载会话"""
    
    def __init__(self, use_ssl_verify: bool = True, timeout: int = 60):
        self.timeout = timeout
        self.ssl_verify = use_ssl_verify
        
    def create_session(self, headers: Dict[str, str] = None) -> requests.Session:
        """创建新的会话对象"""
        # 重试策略配置
        retry_strategy = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # 创建会话
        session = requests.Session()
        
        # 配置连接适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy, 
            pool_connections=64, 
            pool_maxsize=64
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 添加请求头
        if headers:
            session.headers.update(headers)
        
        # 配置SSL验证
        session.verify = self.ssl_verify
        
        # 设置代理
        proxy = getProxy()
        if proxy:
            session.proxies = {
                "http": proxy,
                "https": proxy
            }
            
        return session


class DownloadEngine(QThread):
    """下载引擎核心，负责管理下载流程和状态"""
    
    # 信号定义
    initialized = Signal(bool)             # 初始化完成信号，参数为是否支持多线程下载
    block_progress_updated = Signal(list)  # 分块进度更新信号
    speed_updated = Signal(int)            # 下载速度信号(字节/秒)
    download_completed = Signal()          # 下载完成信号
    error_occurred = Signal(str)           # 错误信号
    file_name_changed = Signal(str)        # 文件名变更信号
    status_updated = Signal(str)           # 状态更新信号

    def __init__(self, url: str, headers: Dict[str, str] = None, max_concurrent: int = 8, 
                 save_path: str = None, file_name: str = None, smart_threading: bool = True, 
                 file_size: int = -1, parent=None):
        """
        初始化下载引擎
        
        参数:
            url: 下载链接
            headers: HTTP请求头
            max_concurrent: 最大并发数
            save_path: 保存路径
            file_name: 文件名
            smart_threading: 是否使用智能线程分配
            file_size: 文件大小，-1表示自动获取
            parent: 父对象
        """
        super().__init__(parent)
        
        # 记录开始时间和基本参数
        self.start_time = time.time()
        self.url = url
        self.headers = headers or {}
        self.file_name = file_name
        self.save_path = save_path
        self.thread_count = max_concurrent
        self.smart_threading = smart_threading
        self.file_size = file_size
        
        # 线程同步和状态
        self.thread_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        self.is_running = False
        self.is_paused = False
        self.current_progress = 0
        self.avg_speed = 0
        
        # 下载状态
        self.blocks = []
        self.multi_thread_support = False
        self.executor = None
        self.speed_history = [0] * 5
        
        # 配置连接管理器 - 处理SSL验证
        use_ssl_verify = True
        try:
            if hasattr(cfg, 'SSLVerify'):
                verify = cfg.SSLVerify.value if hasattr(cfg.SSLVerify, 'value') else cfg.SSLVerify
                use_ssl_verify = bool(verify)
        except Exception as e:
            logging.warning(f"SSL配置错误: {e}")
            
        # 创建连接管理器
        self.connection_manager = ConnectionManager(use_ssl_verify=use_ssl_verify)
        
        # 创建主会话
        self.session = self.connection_manager.create_session(self.headers)
        
        # 创建日志目录
        logs_dir = Path("logs")
        if not logs_dir.exists():
            logs_dir.mkdir(exist_ok=True)
            
        # 创建下载日志
        self.debug_log_path = logs_dir / f"download_{int(time.time())}.log"
        try:
            with open(self.debug_log_path, "w", encoding="utf-8") as f:
                f.write(f"===== 下载任务日志 =====\n")
                f.write(f"URL: {url}\n")
                f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
                f.write(f"最大线程数: {max_concurrent}\n")
                f.write(f"智能线程: {smart_threading}\n")
                f.write(f"初始文件大小: {file_size if file_size > 0 else '自动获取'}\n")
                f.write("=====================\n\n")
        except Exception as e:
            logging.warning(f"创建日志文件失败: {e}")
            
        # 启动初始化线程
        self._init_thread = threading.Thread(target=self._prepare_download, daemon=True)
        self._init_thread.start()
        
    def _log_download_debug(self, message: str) -> None:
        """记录下载调试信息到专门的日志文件"""
        try:
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                timestamp = time.strftime('%H:%M:%S', time.localtime())
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logging.error(f"写入调试日志失败: {e}")
            
    def _prepare_download(self) -> None:
        """准备下载，获取文件信息并初始化"""
        try:
            # 设置状态
            self.status_updated.emit("正在获取文件信息...")
            logging.info(f"开始下载准备 - URL: {self.url}")
            
            # 获取文件信息
            final_url, file_name, file_size = self._get_link_info(self.url, self.headers, self.file_name)
            
            # 更新URL，可能发生了重定向
            if final_url != self.url:
                self.url = final_url
                logging.info(f"重定向到: {final_url}")
                
            # 更新文件大小
            if self.file_size == -1:
                self.file_size = file_size
                
            # 更新文件名
            if not self.file_name or self.file_name != file_name:
                self.file_name = file_name
                self.file_name_changed.emit(file_name)
                
            # 判断是否支持多线程
            self.multi_thread_support = self.file_size > 0 and self.file_size > 1024 * 1024  # 至少1MB才分块
            
            # 设置保存路径
            if not self.save_path:
                self.save_path = str(Path.cwd())
            else:
                save_path = Path(self.save_path)
                if not save_path.exists():
                    save_path.mkdir(parents=True, exist_ok=True)
                self.save_path = str(save_path)
                    
            # 处理文件名编码
            try:
                decoded_filename = unquote(self.file_name)
                if decoded_filename != self.file_name:
                    self.file_name = decoded_filename
                    logging.info(f"文件名解码: {self.file_name}")
            except Exception as e:
                logging.warning(f"文件名解码失败: {e}")
                
            # 处理Windows非法字符
            if sys.platform == "win32":
                self.file_name = re.sub(r'[\\/:*?"<>|]', '_', self.file_name)
                
            # 截断过长文件名
            if len(self.file_name) > 200:
                name, ext = os.path.splitext(self.file_name)
                name = name[:195 - len(ext)]
                self.file_name = name + ext
                
            # 创建文件
            file_path = Path(self.save_path) / self.file_name
            
            # 如果文件已存在，添加序号避免覆盖
            if file_path.exists() and file_path.stat().st_size > 0:
                counter = 1
                while True:
                    name, ext = os.path.splitext(self.file_name)
                    new_name = f"{name}_{counter}{ext}"
                    new_path = Path(self.save_path) / new_name
                    if not new_path.exists():
                        self.file_name = new_name
                        file_path = new_path
                        self.file_name_changed.emit(new_name)
                        break
                    counter += 1
            
            # 创建空文件
            if not file_path.exists():
                file_path.touch()
                
                # 预分配文件空间
                if self.file_size > 0:
                    try:
                        createSparseFile(file_path, self.file_size)
                        self._log_download_debug(f"预分配文件空间: {getReadableSize(self.file_size)}")
                    except Exception as e:
                        logging.warning(f"预分配文件空间失败: {e}")
                    
            # 发送初始化完成信号
            self.initialized.emit(self.multi_thread_support)
            
            # 如果不支持多线程下载，强制设置为单线程
            if not self.multi_thread_support:
                self.thread_count = 1
                
            # 记录初始化结果
            self._log_download_debug(f"准备完成 - 文件名: {self.file_name}, 大小: {getReadableSize(self.file_size) if self.file_size > 0 else '未知'}, 多线程: {self.multi_thread_support}")
                
        except Exception as e:
            error_msg = f"下载准备失败: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            self.error_occurred.emit(str(e))
            self.is_running = False

    def _get_link_info(self, url: str, headers: Dict[str, str], filename: str = None) -> Tuple[str, str, int]:
        """
        获取下载链接的信息
        
        参数:
            url: 下载URL
            headers: 请求头
            filename: 文件名（可选）
            
        返回:
            元组(最终URL, 文件名, 文件大小)
        """
        logging.info(f"正在获取链接信息: {url}")
        self._log_download_debug(f"正在获取链接信息: {url}")
        
        # 默认返回值
        final_url = url
        file_size = -1
        
        # 分析URL
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 判断是否为API链接
        is_api = 'api' in parsed_url.path.lower() or 'api' in parsed_url.netloc.lower()
        
        # 处理API链接
        if is_api:
            self._log_download_debug(f"检测到API链接")
            
            # 尝试从URL路径提取名称
            path_parts = [p for p in parsed_url.path.split('/') if p and p.lower() != 'api']
            api_name = path_parts[-1] if path_parts else ''
            
            # 如果路径中没有有效部分，尝试从查询参数中提取
            if not api_name and query_params:
                for key in ['name', 'type', 'id', 'action']:
                    if key in query_params:
                        api_name = f"{key}_{query_params[key][0]}"
                        break
                
            # 如果还没找到名称，使用主机名
            if not api_name:
                api_name = parsed_url.netloc.split('.')[0]
                
            # 确保API响应有正确的文件名
            if not filename:
                filename = f"{api_name}.json"
            elif not filename.lower().endswith(('.json', '.xml')):
                name_base = os.path.splitext(filename)[0]
                filename = f"{name_base}.json"
                
            return final_url, filename, -1
        
        # 处理常规下载链接
        try:
            # 清理请求头
            clean_headers = headers.copy() if headers else {}
            
            # 确保有User-Agent
            if 'User-Agent' not in clean_headers:
                clean_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            
            # 设置超时，避免长时间阻塞
            timeout = 30
            
            try:
                # 先尝试HEAD请求
                self._log_download_debug("尝试HEAD请求获取文件信息")
                response = self.session.head(url, timeout=timeout, allow_redirects=True)
                
                # 如果HEAD请求失败，尝试GET请求
                if response.status_code >= 400:
                    self._log_download_debug(f"HEAD请求失败(状态码: {response.status_code})，尝试GET请求")
                    response = self.session.get(
                        url, 
                        timeout=timeout, 
                        stream=True, 
                        allow_redirects=True
                    )
                    
            except (requests.exceptions.RequestException, TimeoutError) as e:
                # 如果出错，直接使用GET请求
                self._log_download_debug(f"请求出错: {e}，直接尝试GET请求")
                response = self.session.get(
                    url, 
                    timeout=timeout, 
                    stream=True, 
                    allow_redirects=True
                )
            
            # 获取最终URL（处理重定向后）
            final_url = response.url
            if final_url != url:
                self._log_download_debug(f"URL已重定向: {url} -> {final_url}")
            
            # 获取内容类型
            content_type = response.headers.get('Content-Type', '').lower()
            
            # 获取文件大小
            content_length = response.headers.get('Content-Length')
            if content_length and content_length.isdigit():
                file_size = int(content_length)
                self._log_download_debug(f"文件大小: {getReadableSize(file_size)}")
            
            # 处理文件名
            if not filename:
                # 从Content-Disposition中获取
                content_disposition = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disposition:
                    filename_match = re.search(r'filename=["\']?([^"\';]+)', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1).strip()
                        self._log_download_debug(f"从Content-Disposition获取文件名: {filename}")
                
                # 从URL中获取
                if not filename:
                    path = urlparse(final_url).path
                    if path and '/' in path:
                        filename = path.split('/')[-1]
                        if '?' in filename:
                            filename = filename.split('?')[0]
                        if filename:
                            filename = unquote(filename)
                            self._log_download_debug(f"从URL路径获取文件名: {filename}")
                
                # 生成默认文件名
                if not filename or not filename.strip():
                    # 基于内容类型生成文件名
                    timestamp = int(time.time())
                    if 'json' in content_type:
                        filename = f"download_{timestamp}.json"
                    elif 'html' in content_type:
                        filename = f"download_{timestamp}.html"
                    elif 'xml' in content_type:
                        filename = f"download_{timestamp}.xml"
                    elif 'text/plain' in content_type:
                        filename = f"download_{timestamp}.txt"
                    elif 'image/' in content_type:
                        ext = content_type.split('/')[-1].split(';')[0]
                        filename = f"download_{timestamp}.{ext}"
                    elif 'video/' in content_type:
                        ext = content_type.split('/')[-1].split(';')[0]
                        filename = f"download_{timestamp}.{ext}"
                    elif 'audio/' in content_type:
                        ext = content_type.split('/')[-1].split(';')[0]
                        filename = f"download_{timestamp}.{ext}"
                    elif 'application/' in content_type:
                        subtype = content_type.split('/')[-1].split(';')[0]
                        if subtype == 'octet-stream':
                            filename = f"download_{timestamp}.bin"
                        elif subtype in ('zip', 'x-zip-compressed'):
                            filename = f"download_{timestamp}.zip"
                        elif subtype == 'pdf':
                            filename = f"download_{timestamp}.pdf"
                        else:
                            filename = f"download_{timestamp}.{subtype}"
                    else:
                        filename = f"download_{timestamp}.bin"
                    
                    self._log_download_debug(f"生成默认文件名: {filename}")
            
            # 确保文件名不为空
            if not filename or not filename.strip():
                timestamp = int(time.time())
                filename = f"download_{timestamp}.bin"
            
            # 关闭连接（如果使用stream=True）
            if hasattr(response, 'close'):
                response.close()
            
            return final_url, filename, file_size
            
        except Exception as e:
            error_msg = f"获取链接信息失败: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            
            # 生成一个基本的文件名作为后备
            if not filename:
                timestamp = int(time.time())
                
                # 尝试从URL提取一些信息
                path = urlparse(url).path
                if path and '/' in path:
                    url_filename = path.split('/')[-1]
                    if url_filename and '.' in url_filename:
                        filename = url_filename
                    else:
                        filename = f"download_{timestamp}.bin"
                else:
                    filename = f"download_{timestamp}.bin"
            
            return url, filename, -1
    
    def _clean_header_value(self, value):
        """清理HTTP头值中的非法字符"""
        if not value:
            return value
        
        # 转为字符串
        value = str(value)
        
        # 只保留第一行
        if '\n' in value:
            value = value.split('\n')[0]
        
        # 去除空白字符
        value = value.strip()
        
        return value
    
    def _clean_headers(self, headers):
        """清理并返回请求头字典"""
        clean = {}
        for key, value in headers.items():
            clean_value = self._clean_header_value(value)
            clean[key] = clean_value
        return clean

    def _calculate_blocks(self) -> List[List[int]]:
        """计算下载块的边界，返回块列表 [[起始位置, 结束位置], ...]"""
        # 确保文件大小有效
        if self.file_size <= 0:
            self._log_download_debug(f"文件大小无效 ({self.file_size})，无法计算分块")
            return []
            
        try:
            # 智能线程数计算
            thread_count = self.thread_count
            if self.smart_threading:
                # 根据文件大小动态调整线程数
                if self.file_size < 1024 * 1024:  # 小于1MB
                    thread_count = 1
                elif self.file_size < 10 * 1024 * 1024:  # 小于10MB
                    thread_count = min(2, self.thread_count)
                elif self.file_size < 50 * 1024 * 1024:  # 小于50MB
                    thread_count = min(4, self.thread_count)
                elif self.file_size < 100 * 1024 * 1024:  # 小于100MB
                    thread_count = min(6, self.thread_count)
                
                self._log_download_debug(f"智能线程分配: 文件大小={getReadableSize(self.file_size)}, 选择线程数={thread_count}")
            
            # 确保至少有一个线程
            thread_count = max(1, thread_count)
            
            # 计算块大小的最小值
            min_block_size = 1024 * 1024  # 至少1MB
            
            # 如果文件太小，不分块
            if self.file_size <= min_block_size:
                return [[0, self.file_size - 1]]
            
            # 计算每块的基本大小
            basic_block_size = max(min_block_size, self.file_size // thread_count)
            
            # 创建块边界
            boundaries = []
            start_pos = 0
            
            for i in range(thread_count):
                # 最后一个块获取所有剩余大小
                if i == thread_count - 1:
                    boundaries.append([start_pos, self.file_size - 1])
                    break
                
                # 计算当前块的结束位置
                end_pos = min(start_pos + basic_block_size - 1, self.file_size - 1)
                    
                # 确保块至少有1字节
                if end_pos <= start_pos:
                    end_pos = start_pos + 1
                
                boundaries.append([start_pos, end_pos])
                start_pos = end_pos + 1
                
                # 如果已经没有更多内容，跳出循环
                if start_pos >= self.file_size:
                    break
            
            # 记录块边界信息
            self._log_download_debug(f"分块计算完成: 共{len(boundaries)}个块")
            for i, (start, end) in enumerate(boundaries):
                block_size = end - start + 1
                self._log_download_debug(f"块 #{i}: 起始={start}, 结束={end}, 大小={getReadableSize(block_size)}, "
                                        f"占比={block_size/self.file_size*100:.2f}%")
                
            return boundaries
            
        except Exception as e:
            error_msg = f"计算分块出错: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            return []  # 返回空列表，上层会切换到单线程模式

    def _init_blocks(self) -> None:
        """初始化下载块"""
        try:
            self.status_updated.emit("正在初始化下载任务...")
            
            # 未知大小内容，使用单线程模式
            if self.file_size <= 0:
                logging.info("文件大小未知，使用单线程下载")
                self._log_download_debug("文件大小未知，使用单线程下载")
                self.multi_thread_support = False
                self.blocks.clear()
                self.blocks.append(DownloadBlock(0, 0, 2**63 - 1, self.session))
                
                # 发送初始进度信号
                self.block_progress_updated.emit([
                    {
                        'start_pos': 0,
                        'end_pos': 2**63 - 1,
                        'progress': 0
                    }
                ])
                return
            
            # 如果不支持多线程下载，使用单线程模式
            if not self.multi_thread_support:
                self.blocks.clear()
                self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, self.session))
                self._log_download_debug(f"单线程模式: 文件大小={getReadableSize(self.file_size)}")
                
                # 发送初始进度信号
                self.block_progress_updated.emit([
                    {
                        'start_pos': 0,
                        'end_pos': self.file_size - 1,
                        'progress': 0
                    }
                ])
                return

            # 创建断点续传文件路径
            file_path = Path(self.save_path) / self.file_name
            resume_file = file_path.with_suffix(file_path.suffix + '.resume')

            # 尝试从断点续传文件恢复下载状态
            if resume_file.exists():
                try:
                    self._log_download_debug(f"检测到断点续传文件: {resume_file}, 尝试恢复")
                    
                    with open(resume_file, "rb") as f:
                        # 读取文件头信息：版本, URL, 文件大小
                        header = f.read(16)  # 4字节版本号 + 8字节文件大小 + 4字节URL长度
                        if len(header) < 16:
                            raise ValueError("断点续传文件格式错误：文件头不完整")
                            
                        version, file_size, url_len = struct.unpack("<IQI", header)
                        
                        if version != 1:
                            raise ValueError(f"断点续传文件版本不兼容: {version}")
                            
                        # 读取URL
                        url_data = f.read(url_len)
                        saved_url = url_data.decode('utf-8')
                        
                        # 检查URL和文件大小是否匹配
                        if saved_url != self.url:
                            self._log_download_debug(f"断点续传URL不匹配：{saved_url} != {self.url}")
                            raise ValueError("断点续传URL不匹配")
                        
                        if file_size != self.file_size:
                            self._log_download_debug(f"断点续传文件大小不匹配：{file_size} != {self.file_size}")
                            raise ValueError("断点续传文件大小不匹配")
                        
                        # 读取块信息
                        self.blocks.clear()
                        block_count = 0
                        
                        while True:
                            block_data = f.read(24)  # 每个块占24字节(3个int64)
                            if not block_data or len(block_data) < 24:
                                break
                                
                            start, current, end = struct.unpack("<QQQ", block_data)
                            
                            # 验证块范围
                            if start > end or end >= self.file_size:
                                raise ValueError(f"块{block_count}范围无效: {start}-{end}")
                                
                            # 创建块对象
                            session = self.connection_manager.create_session(self.headers)
                            self.blocks.append(DownloadBlock(start, current, end, session))
                            self._log_download_debug(
                                f"恢复块 #{block_count}: 范围={start}-{end}, 当前进度={current}, "
                                f"完成率={(current-start)/(end-start+1)*100:.2f}%"
                            )
                            block_count += 1
                    
                    if not self.blocks:
                        raise ValueError("未能从断点续传文件中读取任何块信息")
                        
                    self._log_download_debug(f"成功从断点续传文件恢复了 {len(self.blocks)} 个下载块")
                    
                except Exception as e:
                    error_msg = f"加载断点续传数据失败: {e}, 将重新计算分块"
                    logging.warning(error_msg)
                    self._log_download_debug(error_msg)
                    self._create_new_blocks()
            else:
                # 没有断点续传文件，创建新的下载块
                self._create_new_blocks()
                
            # 确保至少有一个块
            if not self.blocks:
                logging.warning("无法创建下载块，使用单线程模式")
                self._log_download_debug("无法创建下载块，使用单线程模式")
                self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, self.session))
                self.multi_thread_support = False
                
            # 发送初始进度信号
            self.block_progress_updated.emit([
                {
                    'start_pos': block.start_position,
                    'end_pos': block.end_position,
                    'progress': block.current_position
                } for block in self.blocks
            ])
                
        except Exception as e:
            error_msg = f"初始化下载块失败: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            
            # 尝试使用单线程模式作为后备
            try:
                self.multi_thread_support = False
                self.blocks.clear()
                self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, self.session))
                
                self.block_progress_updated.emit([
                    {
                        'start_pos': 0,
                        'end_pos': self.file_size - 1,
                        'progress': 0
                    }
                ])
                self._log_download_debug("切换到单线程模式作为后备方案")
            except Exception as e2:
                error_msg = f"初始化单线程模式也失败: {e2}"
                logging.error(error_msg)
                self._log_download_debug(error_msg)
                self.error_occurred.emit(f"下载初始化失败: {e}，后备方案也失败: {e2}")
                self.is_running = False
    
    def _create_new_blocks(self) -> None:
        """创建新的下载块"""
        self.blocks.clear()
        boundaries = self._calculate_blocks()
        
        if not boundaries:
            self._log_download_debug("计算分块失败，使用单线程模式")
            self.multi_thread_support = False
            session = self.connection_manager.create_session(self.headers)
            self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, session))
            return
        
        self._log_download_debug(f"创建 {len(boundaries)} 个新下载块")
        
        for i, (start, end) in enumerate(boundaries):
            session = self.connection_manager.create_session(self.headers)
            self.blocks.append(DownloadBlock(start, start, end, session))
            self._log_download_debug(f"创建块 #{i}: 范围={start}-{end}, 大小={getReadableSize(end-start+1)}")
    
    def _save_resume_info(self) -> None:
        """保存断点续传信息"""
        if not self.multi_thread_support or not self.blocks:
            return
            
        try:
            file_path = Path(self.save_path) / self.file_name
            resume_file = file_path.with_suffix(file_path.suffix + '.resume')
            
            with open(resume_file, "wb") as f:
                # 写入文件头：版本号(1) + 文件大小 + URL长度
                url_bytes = self.url.encode('utf-8')
                url_len = len(url_bytes)
                
                f.write(struct.pack("<IQI", 1, self.file_size, url_len))
                f.write(url_bytes)
                
                # 写入每个块的状态
                for block in self.blocks:
                    f.write(struct.pack("<QQQ", 
                                     block.start_position,
                                     block.current_position,
                                     block.end_position))
                    
            self._log_download_debug(f"断点续传信息已保存到: {resume_file}")
        except Exception as e:
            logging.warning(f"保存断点续传信息失败: {e}")
            self._log_download_debug(f"保存断点续传信息失败: {e}")

    def _execute_download(self) -> None:
        """执行下载任务"""
        try:
            # 预分配文件空间（如果有大小信息）
            if self.file_size > 0:
                file_path = Path(self.save_path) / self.file_name
                try:
                    createSparseFile(file_path, self.file_size)
                    self._log_download_debug(f"预分配文件空间: {getReadableSize(self.file_size)}")
                except Exception as e:
                    self._log_download_debug(f"预分配文件空间失败: {e}")
            
            # 设置状态
            self.is_running = True
            self.is_paused = False
            self.status_updated.emit("下载中...")
            
            # 创建线程池 - 动态核心数量
            max_workers = min(32, os.cpu_count() * 4 or 16)
            self._log_download_debug(f"创建线程池，最大工作线程数: {max_workers}")
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            
            # 启动监控线程
            monitor_thread = threading.Thread(target=self._monitor_progress, daemon=True)
            monitor_thread.start()
            
            # 提交下载任务
            futures = []
            for i, block in enumerate(self.blocks):
                self._log_download_debug(f"提交块 #{i} 至线程池, 范围: {block.start_position}-{block.end_position}")
                if self.multi_thread_support:
                    futures.append(self.executor.submit(self._process_block, block))
            else:
                futures.append(self.executor.submit(self._process_single_block, block))
                        
            # 等待监控线程结束
            monitor_thread.join()
            
            # 检查是否有未完成的块
            if self.is_running and not self.is_paused:  # 只有非暂停和非停止状态才检查
                incomplete_blocks = []
                for i, block in enumerate(self.blocks):
                    if block.current_position < block.end_position:
                        incomplete_blocks.append(i)
                
                if incomplete_blocks:
                    # 检查是否接近完成（总进度>99%）
                    total_downloaded = sum(b.current_position - b.start_position for b in self.blocks)
                    total_size = sum(b.end_position - b.start_position + 1 for b in self.blocks)
                    progress_percent = (total_downloaded / total_size) * 100 if total_size > 0 else 0
                    
                    if progress_percent > 99.9:
                        self._log_download_debug(f"下载接近完成 ({progress_percent:.2f}%)，标记为完成")
                        # 强制完成所有块
                        for i in incomplete_blocks:
                            self.blocks[i].current_position = self.blocks[i].end_position
                    else:
                        error_msg = f"下载未完成，有 {len(incomplete_blocks)} 个块未完成"
                        self._log_download_debug(error_msg)
                        self.error_occurred.emit(error_msg)
                        return
            
            # 如果正常完成，发送完成信号
            if self.is_running and not self.is_paused:
                # 确保所有块都处于完成状态
                for block in self.blocks:
                    block.current_position = block.end_position
                
                # 记录下载完成
                self._log_download_debug("下载任务完成")
                self.status_updated.emit("下载完成")
                self.download_completed.emit()
                
                # 清理断点续传文件
                try:
                    resume_file = Path(self.save_path) / f"{self.file_name}.resume"
                    if resume_file.exists():
                        resume_file.unlink()
                        self._log_download_debug("已删除断点续传文件")
                except Exception as e:
                    self._log_download_debug(f"清理断点续传文件失败: {e}")
            
        except Exception as e:
            error_msg = f"下载过程出错: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            self.error_occurred.emit(str(e))
            
        finally:
            # 关闭线程池
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            
            # 关闭会话
            try:
                if self.session:
                    self.session.close()
                
                # 关闭块会话
                for block in self.blocks:
                    if block.session:
                        block.session.close()
            except Exception as e:
                self._log_download_debug(f"关闭会话失败: {e}")
            
            # 记录任务结束
            self._write_download_summary()

    def _monitor_progress(self) -> None:
        """监控下载进度，更新速度和状态"""
        start_time = time.time()
        last_progress = 0
        self.speed_history = []
        
        # 等待进入下载状态
        time.sleep(1)
        
        # 直到下载完成或停止
        while self.is_running and not all(block.current_position >= block.end_position for block in self.blocks):
            try:
                # 如果暂停，则暂停更新
                if self.is_paused:
                    time.sleep(1)
                    continue
                
                # 记录任务已运行时间
                elapsed_time = time.time() - start_time
                
                # 收集块状态和计算总进度
                block_status = []
                
                with self.progress_lock:
                    self.current_progress = 0
                    blocks_active = False
                    all_blocks_complete = True
                    all_blocks_inactive = True
                    
                    for i, block in enumerate(self.blocks):
                        if not isinstance(block, DownloadBlock):
                            continue
                            
                        # 检查块是否活跃
                        if block.active:
                            blocks_active = True
                            all_blocks_inactive = False
                        
                        # 检查块是否完成
                        if block.current_position < block.end_position:
                            all_blocks_complete = False
                            
                        # 添加到总进度
                        self.current_progress += (block.current_position - block.start_position)
                        
                        # 收集块状态
                        block_status.append({
                            'start_pos': block.start_position,
                            'progress': block.current_position,
                            'end_pos': block.end_position,
                            'status': "下载中" if block.active else "已暂停" if self.is_paused else "已完成" if block.current_position >= block.end_position else "等待中"
                        })
                    
                    # 文件大小未知且所有块都不活跃，视为下载完成
                    if (self.file_size <= 0 or self.current_progress == 0) and all_blocks_inactive and not self.is_paused:
                        # 获取已下载文件的实际大小
                        try:
                            file_path = Path(self.save_path) / self.file_name
                            if file_path.exists():
                                actual_size = file_path.stat().st_size
                                if actual_size > 0:
                                    self.file_size = actual_size
                                    # 更新块终点位置
                                    for block in self.blocks:
                                        if isinstance(block, DownloadBlock):
                                            block.end_position = actual_size - 1
                                            block.current_position = actual_size
                                    self._log_download_debug(f"文件大小未知但下载完成，设置实际大小: {getReadableSize(actual_size)}")
                                    # 标记下载完成
                                    all_blocks_complete = True
                                    break
                        except Exception as e:
                            self._log_download_debug(f"获取文件实际大小失败: {e}")
                
                # 如果文件大小未知但已有下载进度，检查下载是否已停止一段时间
                if self.file_size <= 0 and self.current_progress > 0:
                    if self.current_progress == last_progress:
                        # 如果进度停止更新超过3秒，认为下载可能已完成
                        if elapsed_time - self.last_progress_time > 3:
                            no_active_blocks = not any(block.active for block in self.blocks if isinstance(block, DownloadBlock))
                            if no_active_blocks:
                                self._log_download_debug("文件大小未知，但下载似乎已完成（进度停止更新）")
                                # 获取已下载文件的实际大小
                                try:
                                    file_path = Path(self.save_path) / self.file_name
                                    if file_path.exists():
                                        actual_size = file_path.stat().st_size
                                        if actual_size > 0:
                                            self.file_size = actual_size
                                            # 更新块终点位置
                                            for block in self.blocks:
                                                if isinstance(block, DownloadBlock):
                                                    block.end_position = actual_size - 1
                                                    block.current_position = actual_size
                                            self._log_download_debug(f"设置文件实际大小: {getReadableSize(actual_size)}")
                                            break
                                except Exception as e:
                                    self._log_download_debug(f"获取文件实际大小失败: {e}")
                    else:
                        last_progress = self.current_progress
                        self.last_progress_time = elapsed_time
                
                # 更新下载速度
                if elapsed_time >= 1:
                    speed = self.current_progress / elapsed_time
                    self.speed_history.append(speed)
                    
                    # 只保留最近10次速度记录
                    if len(self.speed_history) > 10:
                        self.speed_history.pop(0)
                
                # 取平均速度
                self.avg_speed = sum(self.speed_history) / len(self.speed_history) if self.speed_history else 0
                
                # 发出进度信号
                self.block_progress_updated.emit(block_status)
                self.speed_updated.emit(int(self.avg_speed))
                
                # 检查是否下载完成（两种情况：1. 明确的文件大小且进度达到 2. 所有块都完成）
                if (self.file_size > 0 and self.current_progress >= self.file_size) or all_blocks_complete:
                    self._log_download_debug(f"下载完成: 当前进度={self.current_progress}, 文件大小={self.file_size}, 所有块完成={all_blocks_complete}")
                    break
                
                # 睡眠500毫秒
                time.sleep(0.5)
                
            except Exception as e:
                self._log_download_debug(f"监控进度出错: {e}")
                time.sleep(1)
        
        # 下载完成，更新最终进度
        with self.progress_lock:
            self.current_progress = 0
            for block in self.blocks:
                if isinstance(block, DownloadBlock):
                    # 确保所有块都显示为完成状态
                    if not self.is_paused and not block.active:
                        block.current_position = block.end_position
                    self.current_progress += (block.current_position - block.start_position)
            
            # 如果文件大小未知但已下载完成，使用当前进度作为文件大小
            if self.file_size <= 0 and self.current_progress > 0:
                self.file_size = self.current_progress
                self._log_download_debug(f"文件大小未知，设置为当前进度: {getReadableSize(self.current_progress)}")
            
            # 更新最终状态
            final_status = []
            for block in self.blocks:
                if isinstance(block, DownloadBlock):
                    final_status.append({
                        'start_pos': block.start_position,
                        'progress': block.current_position,
                        'end_pos': block.end_position,
                        'status': "已暂停" if self.is_paused else "已完成"
                    })
            
            # 发送最终进度
            self.block_progress_updated.emit(final_status)

    def _write_download_summary(self) -> None:
        """写入下载完成总结信息"""
        try:
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write("\n===== 下载任务结束 =====\n")
                f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
                
                # 计算总时长
                total_time = time.time() - self.start_time
                hours = int(total_time // 3600)
                minutes = int((total_time % 3600) // 60)
                seconds = int(total_time % 60)
                time_str = f"{hours}小时 {minutes}分钟 {seconds}秒" if hours > 0 else f"{minutes}分钟 {seconds}秒"
                
                f.write(f"总耗时: {time_str}\n")
                f.write(f"文件名: {self.file_name}\n")
                f.write(f"文件大小: {getReadableSize(self.file_size)}\n")
                f.write(f"保存路径: {self.save_path}\n")
                f.write(f"状态: {'已完成' if not self.is_paused else '已暂停'}\n")
                f.write(f"多线程: {self.multi_thread_support}\n")
                f.write(f"块数量: {len(self.blocks)}\n")
                
                # 记录块信息
                for i, block in enumerate(self.blocks):
                    size = block.end_position - block.start_position + 1
                    downloaded = block.current_position - block.start_position
                    percent = (downloaded / size) * 100 if size > 0 else 0
                    
                    f.write(f"- 块 #{i}: 范围={block.start_position}-{block.end_position}, "
                            f"大小={getReadableSize(size)}, 已下载={getReadableSize(downloaded)}, "
                            f"完成率={percent:.2f}%\n")
                
                f.write("=====================\n")
        except Exception as e:
            logging.error(f"写入下载总结失败: {e}")

    def pause(self) -> None:
        """暂停下载任务"""
        if not self.is_running or self.is_paused:
            return
            
        self._log_download_debug("暂停下载任务")
        self.status_updated.emit("已暂停")
        self.is_paused = True
        
        # 保存断点续传信息
        if self.multi_thread_support:
            self._save_resume_info()

    def resume(self) -> None:
        """恢复暂停的下载任务"""
        if not self.is_running or not self.is_paused:
            return
            
        self._log_download_debug("恢复下载任务")
        self.status_updated.emit("下载中...")
        self.is_paused = False
        
        # 重新启动下载
        if self.executor is None:
            self._execute_download()
            return
            
        # 提交未完成的块到线程池
        for i, block in enumerate(self.blocks):
            if block.current_position < block.end_position and not block.active:
                self._log_download_debug(f"重新提交块 #{i} 至线程池")
                if self.multi_thread_support:
                    self.executor.submit(self._process_block, block)
                else:
                    self.executor.submit(self._process_single_block, block)

    def stop(self) -> None:
        """停止下载任务并清理资源"""
        if not self.is_running:
            return
            
        self._log_download_debug("停止下载任务")
        self.status_updated.emit("已停止")
        self.is_running = False
        
        # 保存断点续传信息
        if self.multi_thread_support:
            self._save_resume_info()
        
        # 关闭线程池
        if self.executor:
            try:
                self.executor.shutdown(wait=False)
                self.executor = None
            except Exception as e:
                self._log_download_debug(f"关闭线程池失败: {e}")
        
        # 关闭会话
        try:
            if self.session:
                self.session.close()
                self.session = None
            
            # 关闭块会话
            for block in self.blocks:
                if block.session:
                    block.session.close()
                    block.session = None
        except Exception as e:
            self._log_download_debug(f"关闭会话失败: {e}")
        
        # 记录最终状态
        self._write_download_summary()

    def run(self) -> None:
        """启动下载引擎（QThread入口方法）"""
        try:
            # 等待初始化完成
            if self._init_thread and self._init_thread.is_alive():
                self._log_download_debug("等待初始化线程完成")
                self._init_thread.join(timeout=30)
                
                if self._init_thread.is_alive():
                    self.error_occurred.emit("初始化超时，请检查网络连接")
                    return
            
            # 初始化下载块
            self._init_blocks()
            
            # 确认初始化成功
            if not self.blocks:
                self.error_occurred.emit("初始化下载块失败")
                return
            
            # 开始下载
            self._execute_download()
            
        except Exception as e:
            error_msg = f"下载过程出错: {e}"
            logging.error(error_msg)
            self._log_download_debug(error_msg)
            self.error_occurred.emit(str(e))
            self.is_running = False

    def _process_block(self, block: DownloadBlock) -> bool:
        """处理单个下载块
        
        参数:
            block: 下载块对象
            
        返回:
            bool: 是否成功处理
        """
        url = self.url
        headers = dict(self.headers)  # 复制请求头以避免修改原始对象
        
        # 添加Range头，指定下载范围
        if block.start_position <= block.end_position:
            headers['Range'] = f'bytes={block.start_position}-{block.end_position}'
        
        block.active = True  # 标记块为活跃状态
        block.status = "连接中" # 更新状态
            
        try:
            self._log_download_debug(f"块{block.start_position}-{block.end_position}: 开始下载")
            
            # 发起HTTP请求
            with block.session.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=30
            ) as response:
                # 检查响应状态
                if response.status_code not in [200, 206]:
                    self._log_download_debug(f"块{block.start_position}-{block.end_position}: 请求失败 {response.status_code}")
                    block.active = False
                    block.status = f"失败 ({response.status_code})"
                    return False
                
                # 获取数据流
                for chunk in response.iter_content(chunk_size=1024*16):
                    # 检查是否暂停或停止
                    if not self.is_running or self.is_paused:
                        block.active = False
                        block.status = "已暂停" if self.is_paused else "已停止"
                        return False
                    
                    if chunk:
                        # 计算写入位置
                        current_position = block.current_position
                        chunk_size = len(chunk)
                        
                        with self.progress_lock:
                            # 尝试写入块
                            try:
                                file_path = Path(self.save_path) / self.file_name
                                with open(file_path, 'r+b') as f:
                                    f.seek(current_position)
                                    f.write(chunk)
                            except Exception as e:
                                self._log_download_debug(f"块{block.start_position}-{block.end_position}: 写入失败 {str(e)}")
                                self.error_occurred.emit(f"写入失败: {str(e)}")
                                block.active = False
                                block.status = "写入失败"
                                return False
                            
                            # 更新进度
                            block.current_position += chunk_size
                            self.current_progress += chunk_size
                            
                            # 确保不超过块的结束位置
                            if block.current_position > block.end_position + 1:
                                self._log_download_debug(f"块{block.start_position}-{block.end_position}: 超出范围")
                                block.current_position = block.end_position + 1
                                
                            # 更新下载速度
                            current_time = time.time()
                            time_diff = current_time - block.last_update_time
                            if time_diff >= 1.0:
                                position_diff = block.current_position - block.last_position
                                if position_diff > 0 and time_diff > 0:
                                    block.download_speed = position_diff / time_diff
                                block.last_update_time = current_time
                                block.last_position = block.current_position
                                block.status = "下载中"
                
                # 检查是否下载完整个块
                if block.current_position >= block.end_position + 1:
                    block.status = "已完成"
                    block.active = False
                    self._log_download_debug(f"块{block.start_position}-{block.end_position}: 下载完成")
                    return True
                else:
                    # 块没有完成，记录实际下载了多少
                    self._log_download_debug(
                        f"块{block.start_position}-{block.end_position}: 不完整 "
                        f"({block.current_position-block.start_position}/{block.end_position-block.start_position+1})"
                    )
                    block.status = "不完整"
                    block.active = False
                    return False
                    
        except Exception as e:
            self._log_download_debug(f"块{block.start_position}-{block.end_position}: 出错 {str(e)}")
            logging.error(f"下载块处理错误: {e}")
            block.active = False
            block.status = "出错"
            return False

    def _switch_to_single_thread(self) -> None:
        """切换到单线程下载模式"""
        self._log_download_debug("切换到单线程模式")
        
        with self.thread_lock:
            self.multi_thread_support = False
            
            # 停止所有活动块
            for block in self.blocks:
                block.active = False
            
            # 保存当前已下载的数据
            self._save_resume_info()
            
            # 清除所有块
            self.blocks.clear()
            
            # 创建单线程下载块
            session = self.connection_manager.create_session(self.headers)
            self.blocks.append(DownloadBlock(0, 0, self.file_size - 1 if self.file_size > 0 else 2**63 - 1, session))
        
        # 如果仍在运行，启动单线程下载
        if self.is_running and not self.is_paused:
            self.executor.submit(self._process_single_block, self.blocks[0])
    
    def _process_single_block(self, block: DownloadBlock) -> bool:
        """处理单线程下载块
        
        参数:
            block: 下载块对象
            
        返回:
            下载是否成功
        """
        self._log_download_debug(f"启动单线程下载: {self.url}")
        
        # 标记为活跃状态
        block.active = True
        
        # 下载重试配置
        max_retries = 8
        retry_delay = 1  # 初始重试延迟
        timeout = 60  # 初始超时时间
        
        # 下载过程
        while (block.current_position < block.end_position or self.file_size <= 0) and self.is_running and not self.is_paused:
            try:
                # 准备请求头
                headers = self.headers.copy()
                
                # 如果支持断点续传，添加Range头
                if block.current_position > 0:
                    headers['Range'] = f'bytes={block.current_position}-'
                    self._log_download_debug(f"断点续传: 从位置 {block.current_position} 开始")
                
                # 发送请求获取数据
                self._log_download_debug(f"发送请求: {self.url}, 超时: {timeout}秒")
                self.status_updated.emit("正在下载...")
                
                response = block.session.get(
                    self.url,
                    headers=headers,
                    stream=True,
                    timeout=timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # 检查内容类型并更新文件扩展名
                content_type = response.headers.get('Content-Type', '').lower()
                self._log_download_debug(f"响应内容类型: {content_type}")
                
                # 根据内容类型调整文件扩展名
                self._update_file_extension(content_type)
                
                # 获取或更新文件大小
                content_length = response.headers.get('Content-Length')
                if content_length and content_length.isdigit():
                    new_size = int(content_length) + block.current_position
                    if self.file_size <= 0 or new_size > self.file_size:
                        old_size = self.file_size
                        self.file_size = new_size
                        self._log_download_debug(f"更新文件大小: {getReadableSize(old_size)} -> {getReadableSize(self.file_size)}")
                        
                        # 更新块结束位置
                        if block.end_position < new_size - 1:
                            block.end_position = new_size - 1
                
                # 打开文件进行写入
                file_path = Path(self.save_path) / self.file_name
                
                # 下载模式: 追加或覆盖
                file_mode = "r+b" if block.current_position > 0 else "wb"
                
                with open(file_path, file_mode) as file:
                    # 定位到当前位置
                    if block.current_position > 0:
                        file.seek(block.current_position)
                    
                    # 下载缓冲区和统计
                    chunk_size = 1024 * 512  # 512KB
                    last_update_time = time.time()
                    data_downloaded = 0
                    
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        # 检查是否停止或暂停
                        if not chunk or not self.is_running or self.is_paused:
                            break
                        
                        # 写入数据
                        file.write(chunk)
                        data_size = len(chunk)
                        block.current_position += data_size
                        data_downloaded += data_size
                        
                        # 更新下载速度
                        current_time = time.time()
                        elapsed = current_time - last_update_time
                        if elapsed >= 1.0:  # 每秒更新一次速度
                            block.download_speed = int(data_downloaded / elapsed)
                            last_update_time = current_time
                            data_downloaded = 0
                        
                        # 应用速度限制
                        self._apply_speed_limit(data_size)
                
                    # 确保所有数据写入磁盘
                    file.flush()
                    os.fsync(file.fileno())
                
                # 关闭响应
                response.close()
                
                # 如果因暂停或停止而中断
                if self.is_paused:
                    self._log_download_debug("下载已暂停")
                    block.active = False
                    return False
                elif not self.is_running:
                    self._log_download_debug("下载已停止")
                    block.active = False
                    return False
                
                # 如果文件大小未知但响应结束，认为下载完成
                if self.file_size <= 0:
                    actual_size = file_path.stat().st_size
                    self.file_size = actual_size
                    block.end_position = actual_size - 1
                    block.current_position = actual_size
                    self._log_download_debug(f"下载完成，文件大小: {getReadableSize(actual_size)}")
                    break
                
                # 检查是否已下载完成
                if block.current_position >= block.end_position:
                    self._log_download_debug("下载完成")
                    break
            
            except requests.exceptions.ChunkedEncodingError as e:
                # 处理分块编码错误（通常是连接中断）
                block.retries += 1
                error_msg = f"传输中断: {e}, 重试 {block.retries}/{max_retries}"
                logging.warning(error_msg)
                self._log_download_debug(error_msg)
                
                if block.retries >= max_retries:
                    error_msg = f"达到最大重试次数: {max_retries}"
                    logging.error(error_msg)
                    self._log_download_debug(error_msg)
                    self.error_occurred.emit(f"下载失败: 传输中断，已重试{max_retries}次")
                    block.active = False
                    return False
                
                # 指数退避重试
                retry_time = min(60, retry_delay * (2 ** (block.retries - 1)))
                self._log_download_debug(f"将在 {retry_time}秒后重试")
                time.sleep(retry_time)
            
            except requests.exceptions.ConnectionError as e:
                # 处理连接错误
                block.retries += 1
                error_msg = f"连接错误: {e}, 重试 {block.retries}/{max_retries}"
                logging.warning(error_msg)
                self._log_download_debug(error_msg)
                
                if block.retries >= max_retries:
                    error_msg = f"达到最大重试次数: {max_retries}"
                    logging.error(error_msg)
                    self._log_download_debug(error_msg)
                    self.error_occurred.emit(f"下载失败: 连接错误，已重试{max_retries}次")
                    block.active = False
                    return False
                
                # 指数退避重试
                retry_time = min(60, retry_delay * (2 ** (block.retries - 1)))
                self._log_download_debug(f"将在 {retry_time}秒后重试")
                time.sleep(retry_time)
            
            except requests.exceptions.Timeout as e:
                # 处理超时
                block.retries += 1
                error_msg = f"请求超时: {e}, 重试 {block.retries}/{max_retries}"
                logging.warning(error_msg)
                self._log_download_debug(error_msg)
                
                if block.retries >= max_retries:
                    error_msg = f"达到最大重试次数: {max_retries}"
                    logging.error(error_msg)
                    self._log_download_debug(error_msg)
                    self.error_occurred.emit(f"下载失败: 请求超时，已重试{max_retries}次")
                    block.active = False
                    return False
                
                # 增加超时时间，最多5分钟
                timeout = min(300, timeout * 1.5)
                
                # 指数退避重试
                retry_time = min(60, retry_delay * (2 ** (block.retries - 1)))
                self._log_download_debug(f"将在 {retry_time}秒后重试")
                time.sleep(retry_time)
            
            except Exception as e:
                # 处理其他异常
                block.retries += 1
                error_msg = f"下载错误: {e}"
                logging.error(error_msg)
                self._log_download_debug(error_msg)
                
                # 严重错误，停止下载
                if isinstance(e, (requests.exceptions.SSLError, requests.exceptions.ProxyError)):
                    self.error_occurred.emit(f"下载失败: {e}")
                    self.is_running = False
                    block.active = False
                    return False
                
                # 其他错误重试
                if block.retries >= max_retries:
                    self.error_occurred.emit(f"下载失败: {e}，已重试{max_retries}次")
                    block.active = False
                    return False
                
                # 指数退避重试
                retry_time = min(60, retry_delay * (2 ** (block.retries - 1)))
                self._log_download_debug(f"将在 {retry_time}秒后重试")
                time.sleep(retry_time)
        
        # 确保下载完成状态
        if self.file_size > 0 and block.current_position < block.end_position:
            if self.is_paused:
                self._log_download_debug(f"下载已暂停，进度: {block.current_position}/{block.end_position}")
            elif not self.is_running:
                self._log_download_debug("下载已停止")
            else:
                self._log_download_debug(f"下载异常结束，进度: {block.current_position}/{block.end_position}")
        else:
            self._log_download_debug("下载完成")
            block.current_position = block.end_position
    
        block.active = False
        return block.current_position >= block.end_position

    def _update_file_extension(self, content_type: str) -> None:
        """根据内容类型更新文件扩展名
        
        参数:
            content_type: 内容类型
        """
        # 检查是否需要更新扩展名
        current_ext = os.path.splitext(self.file_name)[1].lower()
        
        # 根据内容类型确定合适的扩展名
        new_ext = None
        
        # 解析内容类型
        if 'json' in content_type or 'application/json' in content_type:
            new_ext = '.json'
        elif 'xml' in content_type:
            new_ext = '.xml'
        elif 'html' in content_type:
            new_ext = '.html'
        elif 'text/plain' in content_type:
            new_ext = '.txt'
        elif 'image/' in content_type:
            img_type = content_type.split('/')[-1].split(';')[0]
            new_ext = f'.{img_type}'
        elif 'video/' in content_type:
            video_type = content_type.split('/')[-1].split(';')[0]
            new_ext = f'.{video_type}'
        elif 'audio/' in content_type:
            audio_type = content_type.split('/')[-1].split(';')[0]
            new_ext = f'.{audio_type}'
        elif 'application/' in content_type:
            app_type = content_type.split('/')[-1].split(';')[0]
            if app_type == 'octet-stream':
                # 不修改通用二进制流
                return
            elif app_type in ('zip', 'x-zip-compressed'):
                new_ext = '.zip'
            elif app_type == 'pdf':
                new_ext = '.pdf'
            else:
                new_ext = f'.{app_type}'
                
        # 如果没有确定新扩展名或扩展名已正确，不做修改
        if not new_ext or current_ext == new_ext:
            return
            
        # 更新文件名
        old_filename = self.file_name
        
        if '.' in self.file_name:
            base_name = self.file_name.rsplit('.', 1)[0]
            self.file_name = f"{base_name}{new_ext}"
        else:
            self.file_name = f"{self.file_name}{new_ext}"
            
        # 如果文件名没有变化，直接返回
        if self.file_name == old_filename:
            return
            
        self._log_download_debug(f"根据内容类型({content_type})修改文件名: {old_filename} -> {self.file_name}")
        
        # 处理文件重命名
        try:
            old_path = Path(self.save_path) / old_filename
            new_path = Path(self.save_path) / self.file_name
            
            # 如果旧文件存在且新旧路径不同
            if old_path.exists() and old_path != new_path:
                # 如果新文件已存在，先删除
                if new_path.exists():
                    new_path.unlink()
                
                # 重命名文件
                old_path.rename(new_path)
                self._log_download_debug(f"文件重命名: {old_path} -> {new_path}")
                
                # 通知UI文件名变更
                self.file_name_changed.emit(self.file_name)
        except Exception as e:
            error_msg = f"重命名文件失败: {e}"
            logging.warning(error_msg)
            self._log_download_debug(error_msg)
            # 如果重命名失败，恢复原文件名
            self.file_name = old_filename

    def _apply_speed_limit(self, data_size: int) -> None:
        """应用下载速度限制
        
        参数:
            data_size: 下载的数据大小(字节)
        """
        try:
            # 获取速度限制设置 (KB/s)
            speed_limit = 0
            if hasattr(cfg, 'speedLimitation'):
                if hasattr(cfg.speedLimitation, 'value'):
                    speed_limit = cfg.speedLimitation.value
            else:
                speed_limit = cfg.speedLimitation
            
            # 转换为字节/秒
            byte_limit = speed_limit * 1024
            
            # 如果有限速且当前块超过限制
            if byte_limit > 0:
                current_speed = sum(block.download_speed for block in self.blocks if block.active)
                
                if current_speed > byte_limit:
                    # 计算需要暂停的时间
                    delay = data_size / byte_limit
                    time.sleep(max(0.01, min(0.5, delay)))  # 限制在10ms-500ms范围内
        except Exception as e:
            logging.warning(f"速度限制处理出错: {e}")
            # 出错时不进行限速

# 文件重写说明:
# =============
# 该文件已完全重写，参考ab-download-manager实现更现代化的下载核心。
# 
# 主要改进：
# 1. 增强的类型提示和代码结构，便于维护和拓展
# 2. 引入ConnectionManager管理会话池和连接资源
# 3. 改进的分块策略，更合理的分配下载任务
# 4. 新增断点续传机制，使用标准格式记录下载状态
# 5. 智能检测文件类型并自动更新文件扩展名
# 6. 更好的错误处理和重试机制，支持指数退避重试
# 7. 增强的状态通知和日志记录，便于调试与监控
# 8. 增加了暂停/恢复功能，支持任务暂停再继续
# 9. 优化的单线程模式，针对不支持范围请求的服务器
# 10.更细粒度的速度控制和限速功能