import concurrent.futures
import struct
import os
import time
import threading
import sys
import re
import logging
from pathlib import Path
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PySide6.QtCore import QThread, Signal

from core.download_core.core.config import cfg
from core.download_core.core.methods import getProxy, getReadableSize, createSparseFile


class DownloadBlock:
    """单个下载块，代表分段下载的一个部分"""
    
    def __init__(self, start_pos, current_pos, end_pos, session: requests.Session):
        self.start_position = start_pos    # 块起始位置
        self.current_position = current_pos  # 当前下载位置
        self.end_position = end_pos        # 块结束位置
        self.session = session             # 会话对象


class DownloadEngine(QThread):
    """下载引擎核心，负责管理下载流程和状态"""
    
    # 信号定义
    initialized = Signal(bool)             # 初始化完成信号，参数为是否支持多线程下载
    block_progress_updated = Signal(list)  # 分块进度更新信号
    speed_updated = Signal(int)            # 下载速度信号(字节/秒)
    download_completed = Signal()          # 下载完成信号
    error_occurred = Signal(str)           # 错误信号

    def __init__(self, url, headers, max_concurrent=8, save_path=None, file_name=None, 
                 smart_threading=False, file_size=-1, parent=None):
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
        
        # 记录开始时间
        self.start_time = time.time()
        
        # 线程同步和状态
        self.thread_lock = Lock()
        self.current_progress = 0
        self.is_running = False
        
        # 下载信息
        self.url = url
        self.headers = headers
        self.file_name = file_name
        self.save_path = save_path
        self.thread_count = max_concurrent
        self.smart_threading = smart_threading
        self.file_size = file_size
        self.multi_thread_support = False
        
        # 创建专门用于测试断点续传和多线程的日志文件
        self.debug_log_path = "download_blocks_debug.log"
        with open(self.debug_log_path, "w") as f:
            f.write(f"===== 下载测试日志 =====\n")
            f.write(f"URL: {url}\n")
            f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
            f.write(f"最大线程数: {max_concurrent}\n")
            f.write(f"智能线程: {smart_threading}\n")
            f.write(f"初始文件大小: {file_size if file_size > 0 else '自动获取'}\n")
            f.write("=====================\n\n")
            
        # 记录初始化参数
        logging.info(f"下载引擎初始化 - URL: {url}, 线程数: {max_concurrent}, 智能线程: {smart_threading}")
        
        # 下载状态
        self.blocks = []
        self.speed_history = [0] * 10
        self.executor = None
        
        # 配置请求会话
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        self.session = requests.Session()
        self.session.mount("http://", HTTPAdapter(max_retries=retry_strategy, pool_connections=64, pool_maxsize=64))
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy, pool_connections=64, pool_maxsize=64))
        self.session.headers.update(headers)
        
        # 配置SSL验证
        try:
            if hasattr(cfg, 'SSLVerify'):
                verify = cfg.SSLVerify.value if hasattr(cfg.SSLVerify, 'value') else cfg.SSLVerify
                if verify is False:
                    self.session.verify = False
        except Exception as e:
            logging.warning(f"SSL配置错误: {e}")
            
        # 设置代理
        proxy = getProxy()
        if proxy:
            self.session.proxies = {
                "http": proxy,
                "https": proxy
            }
            
        # 启动初始化线程
        self._init_thread = Thread(target=self._prepare_download, daemon=True)
        self._init_thread.start()
        
    def _log_download_debug(self, message):
        """记录下载调试信息到专门的日志文件"""
        try:
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                timestamp = time.strftime('%H:%M:%S', time.localtime())
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logging.error(f"写入调试日志失败: {e}")
            
    def _prepare_download(self):
        """准备下载，获取文件信息并初始化"""
        try:
            # 允许手动处理重定向
            self.session.allow_redirects = False
            
            # 添加通用请求头
            default_headers = {
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": self.url
            }
            
            # 仅添加未指定的请求头
            for key, value in default_headers.items():
                if key.lower() not in map(str.lower, self.headers.keys()):
                    self.headers[key] = value
                    
            self.session.headers.update(self.headers)
            
            # 获取文件名和大小
            if self.file_size == -1 or not self.file_name:
                self.url, self.file_name, self.file_size = self._get_link_info(self.url, self.headers, self.file_name)
                
            # 判断是否支持多线程下载
            self.multi_thread_support = bool(self.file_size)
            
            # 设置保存路径
            if not self.save_path or not Path(self.save_path).is_dir():
                self.save_path = Path.cwd()
            else:
                self.save_path = Path(self.save_path)
                if not self.save_path.exists():
                    self.save_path.mkdir()
                    
            # 处理文件名编码
            try:
                decoded_filename = unquote(self.file_name)
                logging.info(f"文件名解码: {self.file_name} -> {decoded_filename}")
                self.file_name = decoded_filename
            except Exception as e:
                logging.warning(f"文件名解码失败: {e}")
                
            # 处理Windows非法字符
            if sys.platform == "win32":
                self.file_name = ''.join([c for c in self.file_name if c not in r'\/:*?"<>|'])
                
            # 截断过长文件名
            if len(self.file_name) > 255:
                self.file_name = self.file_name[:255]
                
            # 创建文件
            file_path = Path(f"{self.save_path}/{self.file_name}")
            if not file_path.exists():
                file_path.touch()
                try:
                    # 创建稀疏文件预分配空间
                    createSparseFile(file_path)
                except Exception as e:
                    logging.warning(f"创建稀疏文件失败: {e}")
                    
            # 发送初始化完成信号
            self.initialized.emit(self.multi_thread_support)
            if not self.multi_thread_support:
                self.thread_count = 1
                
        except Exception as e:
            logging.error(f"下载准备失败: {str(e)}")
            self.error_occurred.emit(str(e))
            self.is_running = False
            raise 

    def _get_link_info(self, url, headers, filename=None):
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
        
        # 处理重定向
        max_redirects = 8
        redirect_count = 0
        current_url = url
        
        # 检查是否为API链接
        parsed_url = urlparse(url)
        is_api = 'api' in parsed_url.path.lower() or 'api' in parsed_url.netloc.lower()
        
        # API链接简化处理
        if is_api:
            logging.info(f"检测到API链接: {url}")
            api_name = ""
            
            # 从路径中提取API名称
            path_parts = parsed_url.path.strip('/').split('/')
            for part in path_parts:
                if part and part.lower() != 'api':
                    api_name = part
                    break
            
            # 从查询参数提取名称
            if not api_name:
                query_params = parse_qs(parsed_url.query)
                if 'name' in query_params:
                    api_name = query_params['name'][0]
                elif 'type' in query_params:
                    api_name = query_params['type'][0]
                elif query_params:
                    first_param = list(query_params.keys())[0]
                    api_name = f"{first_param}_{query_params[first_param][0]}"
            
            # 使用主机名作为后备
            if not api_name:
                api_name = parsed_url.netloc.split('.')[0]
            
            # 生成文件名
            if not filename:
                filename = f"{api_name}.json"
            
            logging.info(f"API链接文件名: {filename}")
            return current_url, filename, -1
        
        # 处理普通链接
        try:
            # 清理请求头
            clean_headers = self._clean_headers(headers)
            
            # 发送HEAD请求获取基本信息
            response = self.session.head(current_url, headers=clean_headers, allow_redirects=True, timeout=15)
            
            # 获取最终URL
            current_url = response.url
            
            # 提取内容类型和大小
            content_type = response.headers.get('Content-Type', '')
            content_type = self._clean_header_value(content_type)
            
            content_length = response.headers.get('Content-Length', '-1')
            content_length = self._clean_header_value(content_length)
            
            # 处理文件名
            if not filename:
                # 尝试从Content-Disposition获取
                content_disposition = response.headers.get('Content-Disposition', '')
                content_disposition = self._clean_header_value(content_disposition)
                
                if 'filename=' in content_disposition:
                    matches = re.findall(r'filename=["\']?([^"\';]+)', content_disposition)
                    if matches:
                        filename = matches[0].strip()
                
                # 从URL中提取
                if not filename:
                    path = urlparse(current_url).path
                    if path and '/' in path:
                        filename = path.split('/')[-1]
                        # 去除查询参数
                        if '?' in filename:
                            filename = filename.split('?')[0]
                
                # 使用默认名称
                if not filename or filename == '':
                    filename = "download"
                    # 根据内容类型添加扩展名
                    if 'json' in content_type.lower():
                        filename += '.json'
                    elif 'html' in content_type.lower():
                        filename += '.html'
                    elif 'text/plain' in content_type.lower():
                        filename += '.txt'
                    elif 'xml' in content_type.lower():
                        filename += '.xml'
                    elif 'image/' in content_type.lower():
                        ext = content_type.split('/')[-1].split(';')[0]
                        filename += f'.{ext}'
                    else:
                        filename += '.bin'
            
            # 解析文件大小
            try:
                file_size = int(content_length)
            except (ValueError, TypeError):
                file_size = -1
            
            return current_url, filename, file_size
            
        except Exception as e:
            logging.error(f"获取链接信息失败: {e}")
            # 提供默认值
            if not filename:
                filename = "download.bin"
            return url, filename, -1
    
    def _clean_header_value(self, value):
        """清理HTTP头值中的非法字符"""
        if not value:
            return value
        
        # 转为字符串
        value = str(value)
        
        # 只保留第一行
        if '\n' in value:
            value = value.split('\n')[0].strip()
        
        # 去除空白字符
        value = value.strip()
        
        # 去除控制字符
        value = re.sub(r'[\x00-\x1F\x7F]', '', value)
        
        return value
    
    def _clean_headers(self, headers):
        """清理并返回请求头字典"""
        clean = {}
        for key, value in headers.items():
            clean_value = self._clean_header_value(value)
            clean[key] = clean_value
        return clean

    def _create_new_block(self):
        """创建新的下载块，通过分割现有最大块进行优化"""
        with self.thread_lock:
            max_remaining = 0
            max_current_pos = 0
            max_end_pos = 0
            largest_block = None
            largest_index = -1

            # 查找剩余大小最大的块
            for i, block in enumerate(self.blocks):
                remaining = block.end_position - block.current_position
                if remaining > max_remaining:
                    max_current_pos = block.current_position
                    max_end_pos = block.end_position
                    max_remaining = remaining
                    largest_block = block
                    largest_index = i

            # 如果找到合适的块并且大小超过阈值，则分割
            try:
                # 获取最小重分配大小
                min_size = 1048576 * 10  # 默认10MB
                if hasattr(cfg, 'maxReassignSize'):
                    if hasattr(cfg.maxReassignSize, 'value'):
                        min_size = cfg.maxReassignSize.value * 1048576
                    else:
                        min_size = cfg.maxReassignSize * 1048576
                
                if largest_block and max_remaining > min_size:
                    # 平均分配剩余工作
                    half_size = max_remaining // 2
                    remainder = max_remaining % 2

                    # 调整原始块的结束位置
                    largest_block.end_position = max_current_pos + half_size + remainder

                    # 创建新块
                    new_start_pos = max_current_pos + half_size + remainder + 1
                    new_block = DownloadBlock(new_start_pos, new_start_pos, max_end_pos, self.session)

                    # 插入新块
                    self.blocks.insert(largest_index + 1, new_block)
                    
                    # 提交到线程池
                    if self.executor:
                        self.executor.submit(self._process_block, new_block)

                    logging.info(
                        f"文件({self.file_name})分配新线程: 剩余数据量 {getReadableSize(max_remaining)},"
                        f"原线程新终点 {largest_block.end_position}，新线程起点 {new_start_pos}")
                    return True
                else:
                    logging.info(
                        f"文件({self.file_name})无法分配新线程: 剩余数据量 {getReadableSize(max_remaining)} 小于最小分块大小")
                    return False
            except Exception as e:
                logging.error(f"创建新块时出错: {e}")
                return False

    def _calculate_blocks(self):
        """计算下载块的边界"""
        # 确保文件大小有效
        if self.file_size <= 0:
            logging.error(f"文件大小无效 ({self.file_size})，无法计算分块")
            return []
            
        try:
            # 计算每个块的大小
            block_size = self.file_size // self.thread_count
            
            # 确保至少为1字节
            if block_size <= 0:
                block_size = 1
                
            # 创建块边界
            boundaries = list(range(0, self.file_size, block_size))

            if self.file_size % self.thread_count == 0:
                boundaries.append(self.file_size)

            blocks = []
            for i in range(len(boundaries) - 1):
                start, end = boundaries[i], boundaries[i + 1] - 1
                blocks.append([start, end])
                
            # 确保列表非空
            if blocks:
                # 修正最后一个块的结束位置
                blocks[-1][-1] = self.file_size - 1
            else:
                # 创建单一块覆盖整个文件
                logging.warning(f"分块计算失败，创建单一块覆盖整个文件 (0-{self.file_size-1})")
                blocks.append([0, self.file_size - 1])
                
            return blocks
        except Exception as e:
            # 任何异常都返回空列表，上层会切换到单线程模式
            logging.error(f"计算分块时出错: {e}，将切换到单线程模式")
            return []

    def _init_blocks(self):
        """初始化下载块"""
        try:
            # API链接或未知大小内容，切换到单线程模式
            if self.file_size <= 0:
                logging.info("检测到API链接或未知大小内容，使用单线程下载")
                self.multi_thread_support = False
                self.blocks.append(DownloadBlock(0, 0, 99999999, self.session))
                
                # 发送初始进度信号
                self.block_progress_updated.emit([
                    {
                        'start_pos': 0,
                        'end_pos': 99999999,
                        'progress': 0
                    }
                ])
                
                # 记录单线程模式信息
                self._log_download_debug(f"初始化为单线程模式: 文件大小未知, 使用默认大小99999999")
                return
            
            if not self.multi_thread_support:
                self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, self.session))
                self._log_download_debug(f"初始化为单线程模式: 不支持多线程下载, 文件大小: {self.file_size}")
                return

            # 尝试从断点续传文件恢复下载状态
            resume_file = Path(f"{self.save_path}/{self.file_name}.hdm")
            if resume_file.exists():
                try:
                    self._log_download_debug(f"检测到断点续传文件: {resume_file}, 尝试恢复")
                    with open(resume_file, "rb") as f:
                        block_count = 0
                        while True:
                            data = f.read(24)  # 每个块占24字节(3个64位整数)
                            if not data:
                                break
                            start, progress, end = struct.unpack("<QQQ", data)
                            self.blocks.append(
                                DownloadBlock(start, progress, end, self.session))
                            self._log_download_debug(f"恢复块 #{block_count}: 起始={start}, 当前进度={progress}, 结束={end}, 已完成={(progress-start)/(end-start+1)*100:.2f}%")
                            block_count += 1
                    self._log_download_debug(f"成功从断点续传文件恢复了 {len(self.blocks)} 个下载块")
                except Exception as e:
                    logging.error(f"加载断点续传数据失败: {e}")
                    self._log_download_debug(f"断点续传恢复失败: {e}")
                    blocks = self._calculate_blocks()
                    if not blocks:
                        # 分段计算失败时使用单线程模式
                        logging.warning("计算分块失败，切换到单线程模式")
                        self._log_download_debug("计算分块失败，切换到单线程模式")
                        self.multi_thread_support = False
                        self.blocks.append(DownloadBlock(0, 0, max(1, self.file_size - 1), self.session))
                        return
                        
                    for i in range(min(len(blocks), self.thread_count)):
                        self.blocks.append(
                            DownloadBlock(blocks[i][0], blocks[i][0], blocks[i][1], self.session))
                        self._log_download_debug(f"创建块 #{i}: 起始={blocks[i][0]}, 结束={blocks[i][1]}")
            else:
                # 创建新的下载块
                blocks = self._calculate_blocks()
                if not blocks:
                    # 分段计算失败时使用单线程模式
                    logging.warning("计算分块失败，切换到单线程模式")
                    self._log_download_debug("计算分块失败，切换到单线程模式")
                    self.multi_thread_support = False
                    self.blocks.append(DownloadBlock(0, 0, max(1, self.file_size - 1), self.session))
                    return
                    
                self._log_download_debug(f"计算了 {len(blocks)} 个下载块")
                for i in range(min(len(blocks), self.thread_count)):
                    self.blocks.append(
                        DownloadBlock(blocks[i][0], blocks[i][0], blocks[i][1], self.session))
                    self._log_download_debug(f"创建块 #{i}: 起始={blocks[i][0]}, 结束={blocks[i][1]}, 大小={blocks[i][1]-blocks[i][0]+1}")
                
            # 确保至少有一个块
            if not self.blocks:
                logging.warning("无法创建任何分块，使用单线程模式")
                self._log_download_debug("无法创建任何分块，使用单线程模式")
                self.blocks.append(DownloadBlock(0, 0, max(1, self.file_size - 1), self.session))
                self.multi_thread_support = False
                
            # 发送初始进度信号
            self.block_progress_updated.emit([
                {
                    'start_pos': s.start_position,
                    'end_pos': s.end_position,
                    'progress': s.current_position
                } for s in self.blocks
            ])
            
            # 记录分块信息总结
            self._log_download_debug(f"初始化完成，文件大小: {self.file_size}，共 {len(self.blocks)} 个下载块")
            for i, block in enumerate(self.blocks):
                block_size = block.end_position - block.start_position + 1
                self._log_download_debug(f"块 #{i}: 范围={block.start_position}-{block.end_position}, 大小={block_size}, 占比={block_size/self.file_size*100:.2f}%")
                
        except Exception as e:
            logging.error(f"初始化下载块失败: {str(e)}")
            self._log_download_debug(f"初始化下载块失败: {str(e)}")
            # 尝试使用单线程模式作为后备
            if "分块" in str(e) or "计算" in str(e):
                logging.warning("分块失败，尝试单线程模式")
                try:
                    self.multi_thread_support = False
                    self.blocks = []
                    self.blocks.append(DownloadBlock(0, 0, self.file_size - 1, self.session))
                    self.block_progress_updated.emit([
                        {
                            'start_pos': s.start_position,
                            'end_pos': s.end_position,
                            'progress': s.current_position
                        } for s in self.blocks
                    ])
                    return
                except Exception as e2:
                    logging.error(f"尝试单线程模式也失败: {str(e2)}")
                    self.error_occurred.emit(f"下载初始化失败: {str(e)} 尝试单线程模式也失败: {str(e2)}")
            else:
                self.error_occurred.emit(str(e))
            
            self.is_running = False
            raise 

    def _process_block(self, block: DownloadBlock):
        """处理单个下载块的下载"""
        block_id = next((i for i, b in enumerate(self.blocks) if b == block), -1)
        logging.debug(f"文件({self.file_name})启动线程 {block.start_position}-{block.end_position}...")
        self._log_download_debug(f"块 #{block_id} 开始下载: 范围={block.start_position}-{block.end_position}, 当前位置={block.current_position}")
        
        if block.current_position < block.end_position:
            finished = False
            while not finished and self.is_running:
                try:
                    # 手动处理重定向获取最终URL
                    current_url = self.url
                    redirect_count = 0
                    max_redirects = 8
                    final_url = current_url
                    
                    # 执行HEAD请求处理重定向
                    while redirect_count < max_redirects:
                        response = block.session.head(
                            current_url, 
                            headers=self.headers,
                            allow_redirects=False, 
                            timeout=15
                        )
                        
                        if response.status_code in (301, 302, 303, 307, 308):
                            redirect_url = response.headers.get('Location')
                            if not redirect_url:
                                break
                                
                            # 清理URL
                            redirect_url = self._clean_header_value(redirect_url)
                            if not redirect_url:
                                logging.warning("重定向URL无效，继续使用原始URL")
                                break
                                
                            # 处理相对URL
                            if not redirect_url.startswith(('http://', 'https://')):
                                from urllib.parse import urljoin
                                redirect_url = urljoin(current_url, redirect_url)
                                
                            logging.info(f"分块下载重定向: {current_url} -> {redirect_url}")
                            response.close()
                            current_url = redirect_url
                            redirect_count += 1
                            final_url = current_url
                            
                            # 更新会话cookie
                            block.session.cookies.update(response.cookies)
                        else:
                            break
                    
                    # 使用范围请求下载块数据
                    range_headers = self.headers.copy()
                    range_headers["range"] = f"bytes={block.current_position}-{block.end_position}"

                    with block.session.get(final_url, headers=range_headers, stream=True, timeout=30) as res:
                        if res.status_code != 206:
                            # 服务器不支持范围请求，切换到单线程模式
                            logging.warning(f"服务器不支持范围请求，状态码：{res.status_code}，切换到单线程")
                            self._log_download_debug(f"块 #{block_id} 服务器不支持范围请求，状态码：{res.status_code}，切换到单线程模式")
                            self.multi_thread_support = False
                            
                            # 停止其他线程
                            with self.thread_lock:
                                for b in self.blocks:
                                    if b != block:
                                        b.current_position = b.end_position
                            
                            # 切换到单线程模式
                            if self.is_running:
                                # 创建单线程下载
                                self._process_single_block(DownloadBlock(0, 0, self.file_size - 1, self.session))
                                return False
                            else:
                                raise requests.HTTPError(f"服务器拒绝范围请求，状态码：{res.status_code}")
                        
                        block_id = next((i for i, b in enumerate(self.blocks) if b == block), -1)
                        self._log_download_debug(f"块 #{block_id} 开始接收数据: 状态码={res.status_code}, 内容类型={res.headers.get('Content-Type')}")
                        last_log_pos = block.current_position
                        log_interval = 5 * 1024 * 1024  # 每5MB记录一次日志
                        
                        with open(f"{self.save_path}/{self.file_name}", "r+b") as file:
                            for chunk in res.iter_content(chunk_size=1024*1024):  # 1MB缓冲区
                                if not chunk or not self.is_running:
                                    break
                                    
                                file.seek(block.current_position)
                                file.write(chunk)
                                data_size = len(chunk)
                                block.current_position += data_size
                                
                                # 每接收一定数据量记录一次日志
                                if block.current_position - last_log_pos > log_interval:
                                    block_total = block.end_position - block.start_position + 1
                                    block_progress = block.current_position - block.start_position
                                    percent = (block_progress / block_total) * 100 if block_total > 0 else 0
                                    self._log_download_debug(f"块 #{block_id} 进度更新: {block_progress}/{block_total} ({percent:.2f}%)")
                                    last_log_pos = block.current_position
                                
                                try:
                                    # 处理速度限制
                                    speed_limit = 0
                                    if hasattr(cfg, 'speedLimitation'):
                                        if hasattr(cfg.speedLimitation, 'value'):
                                            speed_limit = cfg.speedLimitation.value
                                        else:
                                            speed_limit = cfg.speedLimitation
                                    
                                    if speed_limit > 0 and data_size > speed_limit:
                                        time.sleep(0.1)  # 简单限速
                                except Exception as e:
                                    logging.warning(f"速度限制处理出错: {e}")

                    # 标记任务完成
                    finished = True
                    
                    # 记录下载完成信息
                    block_total = block.end_position - block.start_position + 1
                    block_progress = block.current_position - block.start_position
                    self._log_download_debug(f"块 #{block_id} 下载完成: 总进度={block_progress}/{block_total} ({(block_progress/block_total*100):.2f}%)")
                    
                except Exception as e:
                    logging.error(f"文件({self.file_name})线程 {block.start_position}-{block.end_position} 下载错误: {str(e)}")
                    self._log_download_debug(f"块 #{block_id} 下载错误: {str(e)}")
                    
                    # 检查是否因为范围请求被拒绝
                    if isinstance(e, requests.HTTPError) and "206" in str(e):
                        logging.warning("服务器不支持范围请求，切换到单线程模式")
                        self._log_download_debug("服务器不支持范围请求，切换到单线程模式")
                        self.multi_thread_support = False
                        
                        # 停止其他线程
                        with self.thread_lock:
                            for b in self.blocks:
                                if b != block:
                                    b.current_position = b.end_position
                        
                        # 切换到单线程模式
                        if self.is_running:
                            self._process_single_block(DownloadBlock(0, 0, self.file_size - 1, self.session))
                            return False
                    else:
                        # 普通错误，发送错误信号
                        self.error_occurred.emit(str(e))
                        if isinstance(e, (requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
                            # SSL错误和连接错误直接停止
                            self.is_running = False
                            break
                        time.sleep(5)  # 等待后重试

            block.current_position = block.end_position
            self._log_download_debug(f"块 #{block_id} 标记为已完成, 范围={block.start_position}-{block.end_position}")

        # 尝试创建新块提高下载效率
        result = self._create_new_block()
        self._log_download_debug(f"尝试创建新块结果: {result}")
        return result

    def _process_single_block(self, block: DownloadBlock):
        """处理单线程下载块"""
        logging.debug(f"文件({self.file_name})单线程下载启动...")
        self._log_download_debug(f"启动单线程下载: 范围={block.start_position}-{block.end_position}, 当前位置={block.current_position}")
        if block.current_position < block.end_position or self.file_size <= 0:
            finished = False
            while not finished and self.is_running:
                try:
                    # 处理URL重定向
                    current_url = self.url
                    redirect_count = 0
                    max_redirects = 8
                    
                    while redirect_count < max_redirects:
                        try:
                            response = block.session.head(
                                current_url,
                                headers=self.headers,
                                allow_redirects=False,
                                timeout=15
                            )
                            
                            if response.status_code in (301, 302, 303, 307, 308):
                                redirect_url = response.headers.get('Location')
                                if not redirect_url:
                                    break
                                
                                redirect_url = self._clean_header_value(redirect_url)
                                if not redirect_url:
                                    logging.warning("重定向URL无效，继续使用原始URL")
                                    break
                                    
                                if not redirect_url.startswith(('http://', 'https://')):
                                    from urllib.parse import urljoin
                                    redirect_url = urljoin(current_url, redirect_url)
                                    
                                logging.info(f"下载重定向: {current_url} -> {redirect_url}")
                                current_url = redirect_url
                                redirect_count += 1
                                
                                try:
                                    cookies_dict = response.cookies.get_dict()
                                    for key, value in cookies_dict.items():
                                        cleaned_value = self._clean_header_value(value)
                                        if cleaned_value != value:
                                            cookies_dict[key] = cleaned_value
                                    block.session.cookies.update(cookies_dict)
                                except Exception as e:
                                    logging.warning(f"更新cookie出错: {e}")
                            else:
                                break
                        except Exception as e:
                            logging.warning(f"处理重定向出错: {e}，继续使用原始URL")
                            break
                    
                    logging.info(f"开始下载URL: {current_url}")
                    
                    # 准备请求头
                    get_headers = self.headers.copy()
                    if 'User-Agent' not in get_headers:
                        get_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
                    
                    clean_headers = self._clean_headers(get_headers)
                    
                    # 下载文件
                    response = block.session.get(
                        current_url,
                        headers=clean_headers,
                        stream=True,
                        timeout=60
                    )
                    response.raise_for_status()
                    
                    # 检查内容类型
                    content_type = response.headers.get('Content-Type', '').lower()
                    content_type = self._clean_header_value(content_type)
                    logging.info(f"响应内容类型: {content_type}")
                    
                    # 根据内容类型调整文件扩展名
                    if ('json' in content_type or 'application/json' in content_type) and not self.file_name.lower().endswith('.json'):
                        old_filename = self.file_name
                        if '.' in self.file_name:
                            base_name = self.file_name.rsplit('.', 1)[0]
                            self.file_name = f"{base_name}.json"
                        else:
                            self.file_name = f"{self.file_name}.json"
                        logging.info(f"检测到JSON内容，修改文件名: {old_filename} -> {self.file_name}")
                        
                        file_path = Path(f"{self.save_path}/{self.file_name}")
                        if not file_path.exists():
                            file_path.touch()
                    
                    # 获取文件大小
                    if self.file_size <= 0 and 'content-length' in response.headers:
                        try:
                            content_length = self._clean_header_value(response.headers.get('Content-Length', '-1'))
                            self.file_size = int(content_length)
                            logging.info(f"从响应获取文件大小: {self.file_size}")
                            block.end_position = self.file_size - 1
                        except (ValueError, TypeError):
                            logging.warning("无法从响应获取文件大小")
                    
                    # 下载并写入文件
                    logging.info(f"将内容写入文件: {self.save_path}/{self.file_name}")
                    with open(f"{self.save_path}/{self.file_name}", "wb") as file:
                        total_size = 0
                        chunk_count = 0
                        
                        for chunk in response.iter_content(chunk_size=4096):
                            if not chunk or not self.is_running:
                                break
                            
                            file.write(chunk)
                            file.flush()
                            os.fsync(file.fileno())
                            
                            data_size = len(chunk)
                            block.current_position += data_size
                            total_size += data_size
                            chunk_count += 1
                            
                            if chunk_count % 5 == 0:
                                logging.info(f"已下载 {total_size} 字节")
                            
                            if self.file_size <= 0 or block.current_position > self.file_size:
                                self.file_size = total_size
                                block.end_position = self.file_size - 1
                            
                            try:
                                speed_limit = 0
                                if hasattr(cfg, 'speedLimitation'):
                                    if hasattr(cfg.speedLimitation, 'value'):
                                        speed_limit = cfg.speedLimitation.value
                                    else:
                                        speed_limit = cfg.speedLimitation
                                
                                if speed_limit > 0 and data_size > speed_limit:
                                    time.sleep(0.1)
                            except Exception as e:
                                logging.warning(f"速度限制处理出错: {e}")
                    
                        file.flush()
                        os.fsync(file.fileno())
                    
                    # 更新文件信息
                    actual_file_size = os.path.getsize(f"{self.save_path}/{self.file_name}")
                    logging.info(f"文件下载完成，实际大小: {actual_file_size} 字节")
                    
                    if actual_file_size > 0:
                        self.file_size = actual_file_size
                        block.end_position = self.file_size - 1
                        block.current_position = block.end_position
                    
                    # 处理空响应
                    if actual_file_size == 0:
                        logging.warning("下载内容为空，写入默认JSON")
                        with open(f"{self.save_path}/{self.file_name}", "w") as file:
                            file.write('{"error": "Response was empty", "url": "' + current_url + '"}')
                            file.flush()
                            os.fsync(file.fileno())
                        
                        actual_file_size = os.path.getsize(f"{self.save_path}/{self.file_name}")
                        self.file_size = actual_file_size
                        block.end_position = self.file_size - 1
                        block.current_position = block.end_position
                    
                    # 预览文件内容
                    try:
                        with open(f"{self.save_path}/{self.file_name}", "r", encoding='utf-8', errors='ignore') as f:
                            preview = f.read(100)
                            logging.info(f"文件内容预览: {preview}...")
                    except Exception as e:
                        logging.warning(f"无法预览文件内容: {e}")
                    
                    finished = True
                    logging.info(f"单线程下载完成，总大小: {actual_file_size} 字节")
                
                except Exception as e:
                    logging.error(f"文件({self.file_name})单线程下载错误: {str(e)}")
                    self.error_occurred.emit(str(e))
                    if isinstance(e, (requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
                        self.is_running = False
                        return
                    time.sleep(5)
        
        if finished and block.end_position > 0:
            block.current_position = block.end_position

    def _monitor_progress(self):
        """监控下载进度"""
        last_progress = 0
        
        # 初始化总进度
        with self.thread_lock:
            for block in self.blocks:
                self.current_progress += (block.current_position - block.start_position + 1)
            last_progress = self.current_progress
            
        self._log_download_debug(f"开始监控下载进度，初始总进度: {self.current_progress}")

        if self.multi_thread_support:
            # 智能线程变量
            if self.smart_threading:
                max_speed_per_thread = 1
                new_thread_count = len(self.blocks)
                base_speed = 0
                time_counter = 0
                speed_target = 0
                
                self._log_download_debug(f"已启用智能线程分配，初始线程数: {len(self.blocks)}")

            # 创建断点续传文件
            history_file = open(f"{self.save_path}/{self.file_name}.hdm", "wb")
            self._log_download_debug(f"已创建断点续传文件: {self.save_path}/{self.file_name}.hdm")
            
            # 主监控循环
            while self.is_running and self.current_progress != self.file_size:
                with self.thread_lock:
                    self.current_progress = 0
                    block_info = []
                    all_completed = True
                    
                    blocks_status = []  # 用于记录每个块的状态
                    
                    for i, block in enumerate(self.blocks):
                        # 收集块进度信息
                        block_info.append({
                            'start_pos': block.start_position,
                            'end_pos': block.end_position,
                            'progress': block.current_position
                        })
                        
                        # 计算块的完成百分比
                        block_size = block.end_position - block.start_position + 1
                        block_progress = block.current_position - block.start_position
                        if block_size > 0:
                            block_percent = (block_progress / block_size) * 100
                        else:
                            block_percent = 0
                            
                        # 记录块状态
                        blocks_status.append(f"块 #{i}: {block_progress}/{block_size} ({block_percent:.2f}%)")
                        
                        # 累加总进度
                        self.current_progress += (block.current_position - block.start_position)
                        
                        # 检查是否全部完成
                        if block.current_position < block.end_position:
                            all_completed = False
                    
                    # 记录块状态
                    self._log_download_debug(f"总进度: {self.current_progress}/{self.file_size} ({(self.current_progress/self.file_size*100 if self.file_size>0 else 0):.2f}%)")
                    self._log_download_debug(f"块状态: {', '.join(blocks_status)}")
                    
                    # 小文件处理：如果文件小于10KB且进度超过99%，强制完成
                    small_file_threshold = 10 * 1024
                    if self.file_size <= small_file_threshold and self.current_progress > 0:
                        progress_percent = (self.current_progress / self.file_size) * 100
                        remaining_bytes = self.file_size - self.current_progress
                        
                        if progress_percent >= 99.0 or remaining_bytes <= 5:
                            logging.info(f"小文件下载接近完成，剩余{remaining_bytes}字节，标记为完成")
                            self._log_download_debug(f"小文件下载接近完成，剩余{remaining_bytes}字节，标记为完成")
                                
                            # 强制设置所有块为完成状态
                            for block in self.blocks:
                                block.current_position = block.end_position
                                
                            # 更新进度信息
                            block_info = []
                            for block in self.blocks:
                                block_info.append({
                                    'start_pos': block.start_position,
                                    'end_pos': block.end_position,
                                    'progress': block.end_position
                                })
                                
                            self.current_progress = self.file_size
                            all_completed = True
                    
                    # 大文件接近完成检测
                    if not all_completed and self.current_progress > 0 and self.file_size > small_file_threshold:
                        progress_percent = (self.current_progress / self.file_size) * 100
                        remaining_bytes = self.file_size - self.current_progress
                        
                        if progress_percent >= 99.5 or remaining_bytes <= 5:
                            logging.info(f"下载接近完成，剩余{remaining_bytes}字节，标记为完成")
                            self._log_download_debug(f"下载接近完成，剩余{remaining_bytes}字节，标记为完成")
                                
                            # 强制设置所有块为完成状态
                            for block in self.blocks:
                                block.current_position = block.end_position
                                
                            # 更新进度信息
                            block_info = []
                            for block in self.blocks:
                                block_info.append({
                                    'start_pos': block.start_position,
                                    'end_pos': block.end_position,
                                    'progress': block.end_position
                                })
                                
                            self.current_progress = self.file_size
                            all_completed = True
                
                # 发送进度更新信号
                self.block_progress_updated.emit(block_info)
                
                # 如果全部完成，退出循环
                if all_completed:
                    break

                # 计算下载速度
                transfer_speed = int((self.current_progress - last_progress) / 0.5)
                last_progress = self.current_progress
                self.speed_updated.emit(transfer_speed)
                
                # 记录速度
                self._log_download_debug(f"下载速度: {getReadableSize(transfer_speed)}/s")

                # 写入断点续传数据
                history_file.seek(0)
                for block in self.blocks:
                    history_file.write(struct.pack("<QQQ", 
                                                   block.start_position, 
                                                   block.current_position, 
                                                   block.end_position))
                history_file.flush()

                # 智能线程控制
                if self.smart_threading:
                    time_diff = int(time.time() - self.start_time)
                    if time_diff % 10 == 0 and time_counter != time_diff:
                        time_counter = time_diff
                        
                        thread_diff = new_thread_count - len(self.blocks)
                        if thread_diff > 0:
                            self._log_download_debug(f"智能线程调整: 尝试增加 {thread_diff} 个线程")
                            for _ in range(thread_diff):
                                success = self._create_new_block()
                                self._log_download_debug(f"创建新块结果: {success}")
                                
                # 休眠0.5秒继续监测
                time.sleep(0.5)
                
            # 关闭断点续传文件
            history_file.close()
            
            # 发送最终进度信号
            if self.is_running:
                # 确保显示为100%完成
                final_blocks = []
                for block in self.blocks:
                    final_blocks.append({
                        'start_pos': block.start_position,
                        'end_pos': block.end_position,
                        'progress': block.end_position
                    })
                self.block_progress_updated.emit(final_blocks)
            
            # 删除断点续传文件
            try:
                os.remove(f"{self.save_path}/{self.file_name}.hdm")
                self._log_download_debug("下载完成，删除断点续传文件")
            except:
                self._log_download_debug("删除断点续传文件失败")
                pass
        else:
            # 单线程模式进度监控
            self._log_download_debug("使用单线程模式监控下载进度")
            if not self.blocks:
                return
                
            history_file = None
            try:
                # 创建历史文件（可选）
                history_file = open(f"{self.save_path}/{self.file_name}.hdm", "wb")
                self._log_download_debug(f"已创建断点续传文件: {self.save_path}/{self.file_name}.hdm")
            except:
                self._log_download_debug("创建断点续传文件失败")
                pass
                
            # 进度状态标记
            progress_locked = False
            download_complete = False
            api_unknown_size = False
            
            # 检查是否未知大小
            if self.file_size == 0:
                api_unknown_size = True
                self._log_download_debug("检测到未知大小，使用特殊进度监控")
                
            # 主监控循环
            while self.is_running:
                with self.thread_lock:
                    # 如果已标记为完成，退出循环
                    if download_complete:
                        break
                        
                    # 更新进度信息
                    block_info = []
                    for block in self.blocks:
                        block_info.append({
                            'start_pos': block.start_position,
                            'end_pos': block.end_position,
                            'progress': block.current_position
                        })
                    
                    # 如果进度未锁定，更新总进度
                    if not progress_locked:
                        self.current_progress = self.blocks[0].current_position
                        self._log_download_debug(f"单线程进度: {self.current_progress}/{self.file_size if self.file_size>0 else '未知'}")
                
                # 发送进度更新信号
                self.block_progress_updated.emit(block_info)
                
                # 检查下载是否完成
                if not api_unknown_size and not progress_locked:
                    # 正常大小检查
                    if self.blocks and (
                        self.blocks[0].current_position >= self.blocks[0].end_position or
                        # 接近完成条件
                        (self.blocks[0].current_position >= self.blocks[0].end_position - 5 and 
                         self.blocks[0].current_position > 0 and
                         (self.blocks[0].current_position / (self.blocks[0].end_position + 1)) > 0.99)
                    ):
                        download_complete = True
                        progress_locked = True
                        
                        # 让进度显示为100%
                        if self.blocks[0].current_position < self.blocks[0].end_position:
                            logging.info(f"下载几乎完成，差{self.blocks[0].end_position - self.blocks[0].current_position}字节，设为100%")
                            self._log_download_debug(f"下载几乎完成，差{self.blocks[0].end_position - self.blocks[0].current_position}字节，设为100%")
                            with self.thread_lock:
                                self.blocks[0].current_position = self.blocks[0].end_position
                                self.current_progress = self.file_size
                                
                                # 更新显示为100%
                                block_info = []
                                for block in self.blocks:
                                    block_info.append({
                                        'start_pos': block.start_position,
                                        'end_pos': block.end_position, 
                                        'progress': block.end_position
                                    })
                                    
                                # 再发送一次100%信号
                                self.block_progress_updated.emit(block_info)
                        break
                elif api_unknown_size:
                    # 检查无内容错误
                    if self.blocks[0].current_position == 0 and (time.time() - self.start_time) > 10:
                        # in 10秒后仍然没有进度，可能下载失败
                        logging.warning("10秒后仍无进度，可能下载失败")
                        self._log_download_debug("10秒后仍无进度，可能下载失败")
                        self.error_occurred.emit("下载失败: 10秒后仍无进度")
                        break
                
                # 计算速度
                transfer_speed = int((self.current_progress - last_progress) / 0.5)
                last_progress = self.current_progress
                self.speed_updated.emit(transfer_speed)
                self._log_download_debug(f"下载速度: {getReadableSize(transfer_speed)}/s")
                
                # 如果需要，写入历史记录
                if history_file:
                    try:
                        history_file.seek(0)
                        for block in self.blocks:
                            history_file.write(struct.pack("<QQQ", 
                                                       block.start_position, 
                                                       block.current_position, 
                                                       block.end_position))
                        history_file.flush()
                    except:
                        self._log_download_debug("写入断点续传文件失败")
                        pass
                
                # 休眠0.5秒继续监测
                time.sleep(0.5)
            
            # 关闭历史文件
            if history_file:
                try:
                    history_file.close()
                except:
                    pass
            
            # 删除历史记录文件
            try:
                os.remove(f"{self.save_path}/{self.file_name}.hdm")
                self._log_download_debug("下载完成，删除断点续传文件")
            except:
                self._log_download_debug("删除断点续传文件失败")
                pass
        
        # 记录下载完成信息
        self._log_download_debug(f"下载监控完成，总进度: {self.current_progress}/{self.file_size}, 耗时: {time.time()-self.start_time:.2f}秒")

    def _execute_download(self):
        """执行下载任务"""
        try:
            # 创建文件
            open(f"{self.save_path}/{self.file_name}", "a").close()
            
            # 创建线程池
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=64)
            self.is_running = True
            
            # 启动监控线程
            monitor_thread = Thread(target=self._monitor_progress, daemon=True)
            monitor_thread.start()
            
            # 提交下载任务
            if self.multi_thread_support:
                futures = []
                for i, block in enumerate(self.blocks):
                    self._log_download_debug(f"提交块 #{i} 至线程池: 范围={block.start_position}-{block.end_position}")
                    futures.append(self.executor.submit(self._process_block, block))
            else:
                self._log_download_debug(f"提交单线程下载任务: 范围=0-{self.file_size-1 if self.file_size>0 else '未知'}")
                self.executor.submit(self._process_single_block, self.blocks[0])
                
            # 等待监控线程结束
            monitor_thread.join()
            
            # 发送下载完成信号
            self.download_completed.emit()
            self._log_download_debug(f"下载任务执行完成: {self.file_name}")
            
        except Exception as e:
            logging.error(f"下载过程出错: {repr(e)}")
            self._log_download_debug(f"下载过程出错: {repr(e)}")
            self.error_occurred.emit(repr(e))
        finally:
            self.is_running = False
            if self.executor:
                self.executor.shutdown(wait=False)
            self.session.close()
            
            # 写入下载完成总结
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write("\n===== 下载任务完成 =====\n")
                f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")
                f.write(f"总耗时: {time.time()-self.start_time:.2f}秒\n")
                f.write(f"下载文件: {self.file_name}\n")
                f.write(f"文件大小: {self.file_size}\n")
                f.write(f"保存路径: {self.save_path}\n")
                f.write(f"多线程支持: {self.multi_thread_support}\n")
                f.write(f"最终块数量: {len(self.blocks)}\n")
                for i, block in enumerate(self.blocks):
                    f.write(f"- 块 #{i}: 范围={block.start_position}-{block.end_position}, 大小={block.end_position-block.start_position+1}\n")
                f.write("=====================\n")

    def stop(self):
        """停止下载任务并清理资源"""
        logging.info(f"正在停止任务: {self.file_name}")
        self.is_running = False
        
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        
        # 关闭会话
        try:
            if self.session:
                self.session.close()
        except Exception as e:
            logging.error(f"关闭会话出错: {e}")
        
        logging.info(f"任务已停止: {self.file_name}")

    def run(self):
        """启动下载引擎（QThread入口方法）"""
        try:
            # 启动下载流程
            self._init_thread.join()  # 等待初始化完成
            self._init_blocks()       # 初始化下载块
            self._execute_download()  # 开始下载
        except Exception as e:
            # 确保所有异常被捕获并通知UI
            logging.error(f"下载过程出错: {str(e)}")
            self.error_occurred.emit(str(e))
            self.is_running = False