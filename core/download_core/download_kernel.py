import concurrent.futures
import struct
import sys
import time
import threading
import os
import re
from pathlib import Path
from threading import Thread, Lock
from urllib.parse import urlparse, parse_qs, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PySide6.QtCore import QThread, Signal
import logging
import datetime

from core.download_core.core.config import cfg
from core.download_core.core.methods import getProxy, getReadableSize, getLinkInfo, createSparseFile


class DownloadSegment:
    def __init__(self, start, progress, end, session: requests.Session):
        self.startPos = start      # 分段起始位置
        self.progress = progress   # 当前进度位置
        self.endPos = end          # 分段结束位置
        self.session = session     # 会话对象


class TransferManager(QThread):
    initComplete = Signal(bool)            # 初始化完成信号，传递是否支持多线程下载的信息
    segmentProgressChanged = Signal(list)  # 分段进度更新信号
    transferSpeedChanged = Signal(int)     # 传输速度信号（字节/秒）
    downloadComplete = Signal()            # 下载完成信号
    errorOccurred = Signal(str)            # 错误信号

    def __init__(self, url, headers, maxThreads: int = 8, savePath:str=None, filename:str=None, 
                 dynamicThreads:bool=False, fileSize:int=-1, parent=None):
        """
        SOME DESCRIPTION
            url: 下载链接
            headers: HTTP请求头
            maxThreads: 最大线程数，默认为8
            savePath: 保存路径
            filename: 文件名
            dynamicThreads: 是否启用智能线程优化，根据网络状况动态调整线程数
            fileSize: 文件大小，-1表示自动获取
            parent: 父QObject
        """
        super().__init__(parent)

        # 添加startTime初始化，修复监控进度中的属性错误
        self.startTime = datetime.datetime.now()

        self.threadLock = Lock()           # 线程锁，保护共享资源
        self.progress = 0                  # 总下载进度
        self.url = url                     # 下载链接
        self.headers = headers             # HTTP请求头
        self.filename = filename           # 文件名
        self.savePath = savePath           # 保存路径
        self.threadCount = maxThreads      # 最大线程数
        self.dynamicThreads = dynamicThreads  # 是否启用智能线程优化
        self.fileSize = fileSize           # 文件大小
        self.supportsMultiThreading = False  # 是否支持多线程下载

        # 打印线程配置信息便于调试
        logging.info(f"TransferManager初始化 - URL: {url}, 线程数: {maxThreads}, 动态线程: {dynamicThreads}")
        print(f"[DEBUG] TransferManager初始化 - 线程数: {maxThreads}, 动态线程: {dynamicThreads}")

        self.segments = []                 # 下载分段列表
        self.isRunning = False             # 是否正在运行
        self.speedHistory = [0] * 10       # 速度历史，用于计算平均速度
        self.executor = None               # 线程池执行器
        
        # 配置请求会话，添加重试策略提高稳定性
        retry_strategy = Retry(
            total=3,                       # 最大重试次数
            backoff_factor=1,              # 重试延迟因子
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
        )
        self.session = requests.Session()
        self.session.mount("http://", HTTPAdapter(max_retries=retry_strategy, pool_connections=128, pool_maxsize=128))
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy, pool_connections=128, pool_maxsize=128))
        self.session.headers.update(headers)
        
        # 配置SSL验证和代理
        try:
            # 尝试访问cfg.SSLVerify，尝试多种可能形式
            if hasattr(cfg, 'SSLVerify'):
                if hasattr(cfg.SSLVerify, 'value'):
                    verify = cfg.SSLVerify.value
                else:
                    verify = cfg.SSLVerify
                
                if verify is False:
                    self.session.verify = False
            else:
                # 默认启用SSL验证
                pass
        except Exception as e:
            logging.warning(f"配置SSL验证时出错: {e}")
            
        proxy = getProxy()
        if proxy:
            self.session.proxies = {
                "http": proxy,
                "https": proxy
            }

        # start init thread
        self.__setupThread = Thread(target=self.__prepareDownload, daemon=True)
        self.__setupThread.start()

    def __createNewSegment(self):
        with self.threadLock:
            maxSize = 0
            maxProgressPos = 0
            maxEndPos = 0
            largestSegment = None
            largestIndex = -1

            # find the segment with the largest remaining size
            for i, segment in enumerate(self.segments):
                remainingSize = segment.endPos - segment.progress
                if remainingSize > maxSize:
                    maxProgressPos = segment.progress
                    maxEndPos = segment.endPos
                    maxSize = remainingSize
                    largestSegment = segment
                    largestIndex = i

            # if find suitable segment and size over threshold, then split
            try:
                # 获取最小重分配大小，尝试多种可能形式
                min_size = 1048576 * 10  # 默认10MB
                if hasattr(cfg, 'maxReassignSize'):
                    if hasattr(cfg.maxReassignSize, 'value'):
                        min_size = cfg.maxReassignSize.value * 1048576
                    else:
                        min_size = cfg.maxReassignSize * 1048576
                
                if largestSegment and maxSize > min_size:
                    # average assign remaining work
                    halfSize = maxSize // 2
                    remainder = maxSize % 2

                    # adjust original segment end position
                    largestSegment.endPos = maxProgressPos + halfSize + remainder

                    newStartPos = maxProgressPos + halfSize + remainder + 1
                    newSegment = DownloadSegment(newStartPos, newStartPos, maxEndPos, self.session)

                    self.segments.insert(largestIndex + 1, newSegment)
                    
                    # submit new segment to thread pool
                    if self.executor:
                        self.executor.submit(self.__processSegment, newSegment)

                    logging.info(
                        f"文件({self.filename})分配新线程：剩余数据量 {getReadableSize(maxSize)}，"
                        f"原线程新终点 {largestSegment.endPos}，新线程起点 {newStartPos}")
                    return True
                else:
                    logging.info(
                        f"文件({self.filename})无法分配新线程：剩余数据量 {getReadableSize(maxSize)} 小于最小分块大小")
                    return False
            except Exception as e:
                logging.error(f"创建新分段时出错: {e}")
                return False

    def __calculateSegments(self):
        """计算下载分段边界"""
        # 确保文件大小有效
        if self.fileSize <= 0:
            # 无法分段，返回空列表
            logging.error(f"文件大小无效 ({self.fileSize}), 无法计算分段")
            return []
            
        # 尝试保证分段计算不会失败
        try:
            # 计算每个分段的大小
            segmentSize = self.fileSize // self.threadCount
            
            # 至少1字节
            if segmentSize <= 0:
                segmentSize = 1
                
            # 创建分段边界
            boundaries = list(range(0, self.fileSize, segmentSize))

            if self.fileSize % self.threadCount == 0:
                boundaries.append(self.fileSize)

            segments = []
            for i in range(len(boundaries) - 1):
                start, end = boundaries[i], boundaries[i + 1] - 1
                segments.append([start, end])
                
            # 确保segments非空才修改最后一个元素
            if segments:
                # 修复最后一个分段的结束位置
                segments[-1][-1] = self.fileSize - 1
            else:
                # 如果分段计算失败，创建一个覆盖整个文件的单一分段
                logging.warning(f"分段计算产生空列表，创建单一分段覆盖整个文件 (0-{self.fileSize-1})")
                segments.append([0, self.fileSize - 1])
                
            return segments
        except Exception as e:
            # 如果分段计算过程中出现任何异常，返回空列表，上层会自动切换到单线程模式
            logging.error(f"计算分段过程中出错: {e}，将切换到单线程模式")
            return []

    def __prepareDownload(self):
        try:
            # 配置会话以更好地处理重定向
            self.session.allow_redirects = False  # 禁用自动重定向，我们将手动处理
            
            # 添加适合JSON和API请求的默认标头
            default_headers = {
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Referer": self.url,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            # 仅添加用户没有指定的头信息
            for key, value in default_headers.items():
                if key.lower() not in map(str.lower, self.headers.keys()):
                    self.headers[key] = value
            
            self.session.headers.update(self.headers)
            
            # auto get filename and size
            if self.fileSize == -1 or not self.filename:
                self.url, self.filename, self.fileSize = self.__getLinkInfoWithRedirect(self.url, self.headers, self.filename)

            # judge if supports multi-threading
            self.supportsMultiThreading = bool(self.fileSize)

            if not self.savePath or not Path(self.savePath).is_dir():
                self.savePath = Path.cwd()
            else:
                self.savePath = Path(self.savePath)
                if not self.savePath.exists():
                    self.savePath.mkdir()

            # 对文件名进行URL解码，处理中文文件名
            # fix: 因为非解码的文件会导致windows 资源管理器爆炸（爆炸原因：文件名中包含特殊字符（我猜的））
            try:
                from urllib.parse import unquote
                decoded_filename = unquote(self.filename)
                print(f"保存文件前解码文件名: {self.filename} -> {decoded_filename}")
                self.filename = decoded_filename
            except Exception as e:
                logging.warning(f"文件名解码失败: {e}, 使用原始文件名")

            # handle filename (remove illegal characters anti crash)
            if sys.platform == "win32":
                self.filename = ''.join([c for c in self.filename if c not in r'\/:*?"<>|'])
            if len(self.filename) > 255:
                self.filename = self.filename[:255]

            filePath = Path(f"{self.savePath}/{self.filename}")

            if not filePath.exists():
                filePath.touch()
                try:
                    # create sparse file, pre-allocate space but not occupy disk space
                    createSparseFile(filePath)
                except Exception as e:
                    logging.warning(f"create sparse file failed: {repr(e)}")

            # emit init complete signal
            self.initComplete.emit(self.supportsMultiThreading)
            if not self.supportsMultiThreading:
                self.threadCount = 1

        except Exception as e:
            logging.error(f"获取链接信息失败: {str(e)}")
            self.errorOccurred.emit(str(e))
            # 确保错误在UI上显示
            self.isRunning = False
            # 重新抛出异常便于调试跟踪
            raise
            
    def __getLinkInfoWithRedirect(self, url, headers, filename=None):
        """获取链接信息，处理重定向和生成文件名"""
        logging.info(f"获取链接信息: {url}")
        max_redirects = 10
        redirect_count = 0
        current_url = url
        
        # 检测是否为API链接 - 简化判断逻辑
        parsed_url = urlparse(url)
        is_api_link = 'api' in parsed_url.path.lower() or 'api' in parsed_url.netloc.lower()
        
        # 对于API链接，简化处理流程
        if is_api_link:
            logging.info(f"检测到API链接: {url}")
            api_endpoint_name = ""
            
            # 尝试从URL提取有意义的名称
            path_parts = parsed_url.path.strip('/').split('/')
            for part in path_parts:
                if part and part.lower() != 'api':
                    api_endpoint_name = part
                    break
            
            # 如果路径中没找到，检查查询参数
            if not api_endpoint_name:
                query_params = parse_qs(parsed_url.query)
                if 'name' in query_params:
                    api_endpoint_name = query_params['name'][0]
                elif 'type' in query_params:
                    api_endpoint_name = query_params['type'][0]
                elif query_params:
                    first_param = list(query_params.keys())[0]
                    api_endpoint_name = f"{first_param}_{query_params[first_param][0]}"
            
            # 如果没有找到名称，使用主机名
            if not api_endpoint_name:
                api_endpoint_name = parsed_url.netloc.split('.')[0]
            
            # 生成文件名
            if not filename:
                filename = f"{api_endpoint_name}.json"  # 默认假设JSON
            
            logging.info(f"API链接文件名: {filename}")
            return current_url, filename, -1  # API链接返回-1表示文件大小未知
        
        # 处理普通链接
        try:
            # 清理和验证请求头
            clean_headers = {}
            for key, value in headers.items():
                clean_value = self.__clean_header_value(value)
                clean_headers[key] = clean_value
            
            # 发送HEAD请求，获取基本信息
            response = self.session.head(current_url, headers=clean_headers, allow_redirects=True, timeout=15)
            
            # 处理最终URL（已经处理了重定向）
            current_url = response.url
            
            # 获取内容类型和大小
            content_type = response.headers.get('Content-Type', '')
            content_type = self.__clean_header_value(content_type)
            
            content_length = response.headers.get('Content-Length', '-1')
            content_length = self.__clean_header_value(content_length)
            
            # 处理文件名
            if not filename:
                # 尝试从Content-Disposition头获取
                content_disposition = response.headers.get('Content-Disposition', '')
                content_disposition = self.__clean_header_value(content_disposition)
                
                if 'filename=' in content_disposition:
                    matches = re.findall(r'filename=["\']?([^"\';]+)', content_disposition)
                    if matches:
                        filename = matches[0].strip()
                
                # 如果仍然没有文件名，从URL中提取
                if not filename:
                    path = urlparse(current_url).path
                    if path and '/' in path:
                        filename = path.split('/')[-1]
                        # 处理查询参数
                        if '?' in filename:
                            filename = filename.split('?')[0]
                
                # 如果文件名为空，使用默认名称
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
                fileSize = int(content_length)
            except (ValueError, TypeError):
                fileSize = -1
            
            return current_url, filename, fileSize
            
        except Exception as e:
            logging.error(f"获取链接信息时出错: {str(e)}")
            # 提供合理的默认值
            if not filename:
                filename = "download.bin"
            return url, filename, -1

    def __clean_header_value(self, value):
        """清理HTTP头值中的非法字符"""
        if not value:
            return value
        
        # 转换为字符串
        value = str(value)
        
        # 如果包含换行符，只保留第一行
        if '\n' in value:
            logging.warning(f"头值包含换行符，进行清理: {value[:50]}...")
            value = value.split('\n')[0].strip()
        
        # 去除前导和尾随空白字符
        value = value.strip()
        
        # 去除其他特殊控制字符
        import re
        value = re.sub(r'[\x00-\x1F\x7F]', '', value)
        
        return value

    def __loadSegments(self):
        try:
            # API链接或未知大小的内容，直接切换到单线程模式
            if self.fileSize <= 0:
                logging.info("检测到API链接或未知大小内容，使用单线程下载模式")
                self.supportsMultiThreading = False
                self.segments.append(DownloadSegment(0, 0, 99999999, self.session))  # 使用一个较大的默认终点
                
                # 发送初始进度信号
                self.segmentProgressChanged.emit([
                    {
                        'startPos': 0,
                        'endPos': 99999999,
                        'progress': 0
                    }
                ])
                return
            
            if not self.supportsMultiThreading:
                self.segments.append(DownloadSegment(0, 0, self.fileSize - 1, self.session))
                return

            # 尝试从断点续传文件恢复下载状态
            resumeFile = Path(f"{self.savePath}/{self.filename}.hdm")
            if resumeFile.exists():
                try:
                    with open(resumeFile, "rb") as f:
                        while True:
                            data = f.read(24)  # 每个分段占24字节（3个64位整数）
                            if not data:
                                break
                            start, progress, end = struct.unpack("<QQQ", data)
                            self.segments.append(
                                DownloadSegment(start, progress, end, self.session))
                except Exception as e:
                    logging.error(f"加载断点续传数据失败: {e}")
                    segments = self.__calculateSegments()
                    if not segments:
                        # 修改：不支持分段下载时自动创建单线程下载
                        logging.warning("计算分段失败，自动切换到单线程模式")
                        self.supportsMultiThreading = False
                        self.segments.append(DownloadSegment(0, 0, max(1, self.fileSize - 1), self.session))
                        return
                        
                    for i in range(min(len(segments), self.threadCount)):
                        self.segments.append(
                            DownloadSegment(segments[i][0], segments[i][0], segments[i][1], self.session))
            else:
                # 创建新的下载分段
                segments = self.__calculateSegments()
                if not segments:
                    # 修改：不支持分段下载时自动创建单线程下载
                    logging.warning("计算分段失败，自动切换到单线程模式")
                    self.supportsMultiThreading = False
                    self.segments.append(DownloadSegment(0, 0, max(1, self.fileSize - 1), self.session))
                    return
                    
                for i in range(min(len(segments), self.threadCount)):
                    self.segments.append(
                        DownloadSegment(segments[i][0], segments[i][0], segments[i][1], self.session))
                
            # 确保至少有一个分段
            if not self.segments:
                # 如果仍然没有分段，创建一个覆盖整个文件的单分段
                logging.warning("无法创建任何分段，使用单线程模式")
                self.segments.append(DownloadSegment(0, 0, max(1, self.fileSize - 1), self.session))
                self.supportsMultiThreading = False
                
            # 发送初始进度信号
            self.segmentProgressChanged.emit([
                {
                    'startPos': s.startPos,
                    'endPos': s.endPos,
                    'progress': s.progress
                } for s in self.segments
            ])
        except Exception as e:
            logging.error(f"准备下载分段失败: {str(e)}")
            # 修改：避免因为分段问题完全无法下载
            if "计算分段" in str(e) or "创建下载分段" in str(e):
                logging.warning("分段失败，尝试单线程下载模式")
                try:
                    self.supportsMultiThreading = False
                    self.segments = []
                    self.segments.append(DownloadSegment(0, 0, self.fileSize - 1, self.session))
                    self.segmentProgressChanged.emit([
                        {
                            'startPos': s.startPos,
                            'endPos': s.endPos,
                            'progress': s.progress
                        } for s in self.segments
                    ])
                    return
                except Exception as e2:
                    logging.error(f"尝试单线程下载失败: {str(e2)}")
                    self.errorOccurred.emit(f"下载准备失败: {str(e)} 尝试单线程下载也失败: {str(e2)}")
            else:
                self.errorOccurred.emit(str(e))
            
            # 停止下载以确保错误显示
            self.isRunning = False
            # 重新抛出异常便于调试跟踪
            raise

    def __processSegment(self, segment: DownloadSegment):
        logging.debug(f"文件({self.filename})启动线程 {segment.startPos}-{segment.endPos}...")
        if segment.progress < segment.endPos:
            finished = False
            while not finished and self.isRunning:
                try:
                    # 手动处理重定向，获取最终URL
                    current_url = self.url
                    redirect_count = 0
                    max_redirects = 10
                    final_url = current_url
                    
                    # 执行HEAD请求以处理任何重定向
                    while redirect_count < max_redirects:
                        response = segment.session.head(
                            current_url, 
                            headers=self.headers,
                            allow_redirects=False, 
                            timeout=30
                        )
                        
                        if response.status_code in (301, 302, 303, 307, 308):
                            redirect_url = response.headers.get('Location')
                            if not redirect_url:
                                break
                                
                            # 清理URL中的非法字符（换行符、前导/尾随空白字符）
                            redirect_url = self.__clean_header_value(redirect_url)
                            if not redirect_url:
                                logging.warning("重定向URL无效，继续使用原始URL")
                                break
                                
                            # 处理相对URL
                            if not redirect_url.startswith(('http://', 'https://')):
                                from urllib.parse import urljoin
                                redirect_url = urljoin(current_url, redirect_url)
                                
                            logging.info(f"分段下载重定向: {current_url} -> {redirect_url}")
                            response.close()
                            current_url = redirect_url
                            redirect_count += 1
                            final_url = current_url
                            
                            # 更新会话cookie
                            segment.session.cookies.update(response.cookies)
                        else:
                            break
                    
                    # 使用找到的最终URL进行范围请求
                    rangeHeaders = self.headers.copy()
                    rangeHeaders["range"] = f"bytes={segment.progress}-{segment.endPos}"

                    with segment.session.get(final_url, headers=rangeHeaders, stream=True, timeout=30) as res:
                        if res.status_code != 206:
                            # 服务器不支持范围请求，切换到单线程模式
                            logging.warning(f"服务器不支持范围请求，状态码：{res.status_code}，自动切换到单线程模式")
                            self.supportsMultiThreading = False
                            
                            # 停止其他所有线程
                            with self.threadLock:
                                for s in self.segments:
                                    if s != segment:
                                        s.progress = s.endPos
                            
                            # 自动切换到单线程模式
                            if self.isRunning:
                                # 创建单线程下载
                                self.__processSingleSegment(DownloadSegment(0, 0, self.fileSize - 1, self.session))
                                return False
                            else:
                                raise requests.HTTPError(f"服务器拒绝范围请求，状态码：{res.status_code}")
                        
                        with open(f"{self.savePath}/{self.filename}", "r+b") as file:
                            for chunk in res.iter_content(chunk_size=1024*1024):  # 1MB缓冲区
                                if not chunk or not self.isRunning:
                                    break
                                    
                                file.seek(segment.progress)
                                file.write(chunk)
                                dataSize = len(chunk)
                                segment.progress += dataSize
                                
                                try:
                                    # 尝试访问cfg.speedLimitation
                                    speed_limit = 0
                                    if hasattr(cfg, 'speedLimitation'):
                                        if hasattr(cfg.speedLimitation, 'value'):
                                            speed_limit = cfg.speedLimitation.value
                                        else:
                                            speed_limit = cfg.speedLimitation
                                    
                                    if speed_limit > 0 and dataSize > speed_limit:
                                        time.sleep(0.1)  # 简单限速，降低写入速度
                                except Exception as e:
                                    logging.warning(f"限速处理出错: {e}")

                    # mark task finished
                    finished = True
                except Exception as e:
                    logging.error(f"文件({self.filename})线程 {segment.startPos}-{segment.endPos} 下载错误: {str(e)}")
                    
                    # 检查是否为范围请求被拒绝的错误
                    if isinstance(e, requests.HTTPError) and "206" in str(e):
                        logging.warning(f"服务器不支持范围请求，自动切换到单线程模式")
                        self.supportsMultiThreading = False
                        
                        # 停止其他所有线程
                        with self.threadLock:
                            for s in self.segments:
                                if s != segment:
                                    s.progress = s.endPos
                        
                        # 自动切换到单线程模式
                        if self.isRunning:
                            # 创建单线程下载
                            self.__processSingleSegment(DownloadSegment(0, 0, self.fileSize - 1, self.session))
                            return False
                    else:
                        # 普通错误，发送错误信号
                        self.errorOccurred.emit(str(e))
                        if isinstance(e, (requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
                            # 对于SSL错误和连接错误，直接停止重试，避免用户等待
                            self.isRunning = False
                            break
                        time.sleep(5)  # 等待5秒后重试

            segment.progress = segment.endPos

        # try create new segment, improve download efficiency
        return self.__createNewSegment()

    def __processSingleSegment(self, segment: DownloadSegment):
        logging.debug(f"文件({self.filename})单线程下载启动...")
        if segment.progress < segment.endPos or self.fileSize <= 0:
            finished = False
            while not finished and self.isRunning:
                try:
                    current_url = self.url
                    redirect_count = 0
                    max_redirects = 10
                    
                    while redirect_count < max_redirects:
                        try:
                            response = segment.session.head(
                                current_url,
                                headers=self.headers,
                                allow_redirects=False,
                                timeout=15
                            )
                            
                            if response.status_code in (301, 302, 303, 307, 308):
                                redirect_url = response.headers.get('Location')
                                if not redirect_url:
                                    break
                                
                                redirect_url = self.__clean_header_value(redirect_url)
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
                                        cleaned_value = self.__clean_header_value(value)
                                        if cleaned_value != value:
                                            cookies_dict[key] = cleaned_value
                                    segment.session.cookies.update(cookies_dict)
                                except Exception as e:
                                    logging.warning(f"更新cookie时出错: {e}")
                            else:
                                break
                        except Exception as e:
                            logging.warning(f"处理重定向时出错: {e}，继续使用原始URL")
                            break
                    
                    logging.info(f"开始下载URL: {current_url}")
                    
                    get_headers = self.headers.copy()
                    if 'User-Agent' not in get_headers:
                        get_headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
                    
                    clean_headers = {}
                    for key, value in get_headers.items():
                        clean_value = self.__clean_header_value(value)
                        clean_headers[key] = clean_value
                    
                    response = segment.session.get(
                        current_url,
                        headers=clean_headers,
                        stream=True,
                        timeout=60
                    )
                    response.raise_for_status()
                    
                    content_type = response.headers.get('Content-Type', '').lower()
                    content_type = self.__clean_header_value(content_type)
                    logging.info(f"响应内容类型: {content_type}")
                    
                    if ('json' in content_type or 'application/json' in content_type) and not self.filename.lower().endswith('.json'):
                        old_filename = self.filename
                        if '.' in self.filename:
                            base_name = self.filename.rsplit('.', 1)[0]
                            self.filename = f"{base_name}.json"
                        else:
                            self.filename = f"{self.filename}.json"
                        logging.info(f"检测到JSON内容，修改文件名: {old_filename} -> {self.filename}")
                        
                        filePath = Path(f"{self.savePath}/{self.filename}")
                        if not filePath.exists():
                            filePath.touch()
                    
                    if self.fileSize <= 0 and 'content-length' in response.headers:
                        try:
                            content_length = self.__clean_header_value(response.headers.get('Content-Length', '-1'))
                            self.fileSize = int(content_length)
                            logging.info(f"从响应中获取文件大小: {self.fileSize}")
                            segment.endPos = self.fileSize - 1
                        except (ValueError, TypeError):
                            logging.warning("无法从响应中获取文件大小")
                    
                    logging.info(f"开始将内容写入文件: {self.savePath}/{self.filename}")
                    with open(f"{self.savePath}/{self.filename}", "wb") as file:
                        total_size = 0
                        chunk_count = 0
                        
                        for chunk in response.iter_content(chunk_size=4096):
                            if not chunk or not self.isRunning:
                                break
                            
                            file.write(chunk)
                            file.flush()
                            os.fsync(file.fileno())
                            
                            dataSize = len(chunk)
                            segment.progress += dataSize
                            total_size += dataSize
                            chunk_count += 1
                            
                            if chunk_count % 5 == 0:
                                logging.info(f"已下载 {total_size} 字节")
                            
                            if self.fileSize <= 0 or segment.progress > self.fileSize:
                                self.fileSize = total_size
                                segment.endPos = self.fileSize - 1
                            
                            try:
                                speed_limit = 0
                                if hasattr(cfg, 'speedLimitation'):
                                    if hasattr(cfg.speedLimitation, 'value'):
                                        speed_limit = cfg.speedLimitation.value
                                    else:
                                        speed_limit = cfg.speedLimitation
                                
                                if speed_limit > 0 and dataSize > speed_limit:
                                    time.sleep(0.1)
                            except Exception as e:
                                logging.warning(f"限速处理出错: {e}")
                    
                        file.flush()
                        os.fsync(file.fileno())
                    
                    actual_file_size = os.path.getsize(f"{self.savePath}/{self.filename}")
                    logging.info(f"文件下载完成，实际大小: {actual_file_size} 字节")
                    
                    if actual_file_size > 0:
                        self.fileSize = actual_file_size
                        segment.endPos = self.fileSize - 1
                        segment.progress = segment.endPos
                    
                    if actual_file_size == 0:
                        logging.warning("下载内容为空，写入默认JSON数据")
                        with open(f"{self.savePath}/{self.filename}", "w") as file:
                            file.write('{"error": "Response was empty", "url": "' + current_url + '"}')
                            file.flush()
                            os.fsync(file.fileno())
                        
                        actual_file_size = os.path.getsize(f"{self.savePath}/{self.filename}")
                        self.fileSize = actual_file_size
                        segment.endPos = self.fileSize - 1
                        segment.progress = segment.endPos
                    
                    try:
                        with open(f"{self.savePath}/{self.filename}", "r", encoding='utf-8', errors='ignore') as f:
                            preview = f.read(100)
                            logging.info(f"文件内容预览: {preview}...")
                    except Exception as e:
                        logging.warning(f"无法预览文件内容: {e}")
                    
                    finished = True
                    logging.info(f"单线程下载完成，总大小: {actual_file_size} 字节")
                
                except Exception as e:
                    logging.error(f"文件({self.filename})单线程下载错误: {str(e)}")
                    self.errorOccurred.emit(str(e))
                    if isinstance(e, (requests.exceptions.SSLError, requests.exceptions.ConnectionError)):
                        self.isRunning = False
                        return
                    time.sleep(5)
        
        if finished and segment.endPos > 0:
            segment.progress = segment.endPos

    def __monitorProgress(self):
        lastProgress = 0
        
        with self.threadLock:
            for segment in self.segments:
                self.progress += (segment.progress - segment.startPos + 1)
            lastProgress = self.progress

        if self.supportsMultiThreading:
            # dynamic thread control variables
            if self.dynamicThreads:
                maxSpeedPerThread = 1
                newThreadCount = len(self.segments)
                baseSpeed = 0
                timeCounter = 0
                speedTarget = 0

            # create resume file
            historyFile = open(f"{self.savePath}/{self.filename}.hdm", "wb")
            
            # main monitor loop
            while self.isRunning and self.progress != self.fileSize:
                with self.threadLock:
                    self.progress = 0
                    segmentInfo = []
                    allCompleted = True
                    for segment in self.segments:
                        # 记录每个段的进度信息
                        segmentInfo.append({
                            'startPos': segment.startPos,
                            'endPos': segment.endPos,
                            'progress': segment.progress
                        })
                        
                        # 累加总进度
                        self.progress += (segment.progress - segment.startPos)
                        
                        # 检查是否全部完成
                        if segment.progress < segment.endPos:
                            allCompleted = False
                    
                    # 考虑小文件的情况：如果文件小于10KB且进度已经超过99%，强制完成
                    small_file_threshold = 10 * 1024  # 增加到10KB
                    if self.fileSize <= small_file_threshold and self.progress > 0:
                        progress_percent = (self.progress / self.fileSize) * 100
                        remaining_bytes = self.fileSize - self.progress
                        
                        # 如果进度超过99%或只剩下不到5字节，认为下载完成
                        if progress_percent >= 99.0 or remaining_bytes <= 5:
                            # 显示详细日志，方便调试
                            if remaining_bytes <= 5:
                                print(f"[INFO] 小文件下载接近完成，仅剩{remaining_bytes}字节，标记为完成")
                            elif progress_percent >= 99.0:
                                print(f"[INFO] 小文件下载进度达到{progress_percent:.2f}%，标记为完成")
                                
                            # 强制设置所有段为完成状态
                            for segment in self.segments:
                                segment.progress = segment.endPos
                                
                            # 更新进度信息，使其显示100%
                            segmentInfo = []
                            for segment in self.segments:
                                segmentInfo.append({
                                    'startPos': segment.startPos,
                                    'endPos': segment.endPos,
                                    'progress': segment.endPos  # 修改为终点位置表示100%
                                })
                                
                            self.progress = self.fileSize  # 设置总进度为文件大小
                            allCompleted = True  # 标记为全部完成
                    
                    # 较大文件的接近完成检测逻辑
                    if not allCompleted and self.progress > 0 and self.fileSize > small_file_threshold:
                        progress_percent = (self.progress / self.fileSize) * 100
                        remaining_bytes = self.fileSize - self.progress
                        
                        # 如果进度超过99.5%或只剩下不到5字节，认为下载完成
                        if progress_percent >= 99.5 or remaining_bytes <= 5:
                            # 显示详细日志，方便调试
                            if remaining_bytes <= 5:
                                print(f"[INFO] 下载接近完成，仅剩{remaining_bytes}字节，标记为完成")
                            elif progress_percent >= 99.5:
                                print(f"[INFO] 下载进度达到{progress_percent:.2f}%，标记为完成")
                                
                            # 强制设置所有段为完成状态
                            for segment in self.segments:
                                segment.progress = segment.endPos
                                
                            # 更新进度信息，使其显示100%
                            segmentInfo = []
                            for segment in self.segments:
                                segmentInfo.append({
                                    'startPos': segment.startPos,
                                    'endPos': segment.endPos,
                                    'progress': segment.endPos  # 修改为终点位置表示100%
                                })
                                
                            self.progress = self.fileSize  # 设置总进度为文件大小
                            allCompleted = True  # 标记为全部完成
                
                # 发送进度变化信号
                self.segmentProgressChanged.emit(segmentInfo)
                
                # 如果全部完成，退出监控循环
                if allCompleted:
                    break

                # 计算速度
                transferSpeed = int((self.progress - lastProgress) / 0.5)
                lastProgress = self.progress
                self.transferSpeedChanged.emit(transferSpeed)

                # 写入历史记录
                historyFile.seek(0)
                content = []
                for segment in self.segments:
                    for key, value in segment.__dict__.items():
                        if key != 'header' and key != 'response' and key != 'downloader' and key != 'transferThread':
                            content.append(f"{key}={value}")
                    content.append("---")
                historyFile.write(bytes("\n".join(content), "utf-8"))
                historyFile.flush()

                # 控制动态线程
                if self.dynamicThreads:
                    timeDiff = int((datetime.datetime.now() - self.startTime).total_seconds())
                    if timeDiff % 10 == 0 and timeCounter != timeDiff:
                        timeCounter = timeDiff
                        
                        threadDiff = newThreadCount - len(self.segments)
                        if threadDiff > 0:
                            for _ in range(threadDiff):
                                self.__addThread()
                                
                # 休眠0.5秒继续监测
                time.sleep(0.5)
                
            # 关闭历史文件
            historyFile.close()
            
            # 发送最终的100%进度信号
            if self.isRunning:
                # 确保所有段都显示为100%完成
                final_segments = []
                for segment in self.segments:
                    final_segments.append({
                        'startPos': segment.startPos,
                        'endPos': segment.endPos,
                        'progress': segment.endPos  # 设置为完全下载完成
                    })
                self.segmentProgressChanged.emit(final_segments)
            
            # 删除历史记录文件
            try:
                os.remove(f"{self.savePath}/{self.filename}.hdm")
            except:
                pass
        else:
            # 单线程模式进度监控
            if not self.segments:
                return
                
            historyFile = None
            try:
                # 如果需要，创建历史文件
                if self.createHistory:
                    historyFile = open(f"{self.savePath}/{self.filename}.hdm", "wb")
            except:
                pass
                
            # 进度已经完成的标志
            progress_locked = False
            download_complete = False
            api_unknown_size = False
            
            # 检查是否是未知大小的特殊情况
            if self.fileSize == 0:
                api_unknown_size = True
                
            # 主监控循环
            while self.isRunning:
                with self.threadLock:
                    # 如果已经标记为下载完成，则直接退出循环
                    if download_complete:
                        break
                        
                    # 只有一个分段的情况下，更新进度信息
                    segmentInfo = []
                    for segment in self.segments:
                        segmentInfo.append({
                            'startPos': segment.startPos,
                            'endPos': segment.endPos,
                            'progress': segment.progress
                        })
                    
                    # 如果进度已锁定，不再更新
                    if not progress_locked:
                        self.progress = self.segments[0].progress
                
                # 发送进度变化信号
                self.segmentProgressChanged.emit(segmentInfo)
                
                # 检查是否下载完成
                if not api_unknown_size and not progress_locked:
                    # 正常大小检查，增加宽容度
                    if self.segments and (
                        self.segments[0].progress >= self.segments[0].endPos or
                        # 接近完成条件：允许差5字节以内或进度达到99%以上
                        (self.segments[0].progress >= self.segments[0].endPos - 5 and 
                         self.segments[0].progress > 0 and
                         # 进度至少要达到99%以上，才考虑这种情况
                         (self.segments[0].progress / (self.segments[0].endPos + 1)) > 0.99)
                    ):
                        # 允许较大误差完成下载
                        download_complete = True
                        progress_locked = True  # 锁定进度
                        
                        # 文件下载完成，让进度显示为100%
                        # 更新段信息使其显示下载完成
                        if self.segments[0].progress < self.segments[0].endPos:
                            logging.info(f"下载几乎完成（差{self.segments[0].endPos - self.segments[0].progress}字节），主动设置为100%")
                            with self.threadLock:
                                self.segments[0].progress = self.segments[0].endPos
                                self.progress = self.fileSize
                                
                                # 更新进度信息显示为100%
                                segmentInfo = []
                                for segment in self.segments:
                                    segmentInfo.append({
                                        'startPos': segment.startPos,
                                        'endPos': segment.endPos, 
                                        'progress': segment.endPos  # 设置进度等于终点
                                    })
                                    
                                # 再发送一次100%进度信号
                                self.segmentProgressChanged.emit(segmentInfo)
                        break  # 退出循环
                elif api_unknown_size:
                    # 检查是否发生错误(无内容)
                    if self.segments[0].progress == 0 and (datetime.datetime.now() - self.startTime).total_seconds() > 10:
                        # 10秒后仍然没有进度，可能下载失败
                        logging.warning("10秒后仍无进度，可能下载失败")
                        self.errorOccurred.emit("下载失败: 10秒后仍无进度")
                        break
                
                # 计算速度
                transferSpeed = int((self.progress - lastProgress) / 0.5)
                lastProgress = self.progress
                self.transferSpeedChanged.emit(transferSpeed)
                
                # 如果需要，写入历史记录
                if historyFile:
                    try:
                        historyFile.seek(0)
                        content = []
                        for segment in self.segments:
                            for key, value in segment.__dict__.items():
                                if key != 'header' and key != 'response' and key != 'downloader' and key != 'transferThread':
                                    content.append(f"{key}={value}")
                            content.append("---")
                        historyFile.write(bytes("\n".join(content), "utf-8"))
                        historyFile.flush()
                    except:
                        pass
                
                # 休眠0.5秒继续监测
                time.sleep(0.5)
            
            # 关闭历史文件
            if historyFile:
                try:
                    historyFile.close()
                except:
                    pass
            
            # 删除历史记录文件
            try:
                os.remove(f"{self.savePath}/{self.filename}.hdm")
            except:
                pass

    def __executeDownload(self):
        try:
            # create file
            open(f"{self.savePath}/{self.filename}", "a").close()
            
            # create thread pool
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=64)
            self.isRunning = True
            
            # start monitor thread
            monitorThread = Thread(target=self.__monitorProgress, daemon=True)
            monitorThread.start()
            
            # submit download task
            if self.supportsMultiThreading:
                futures = []
                for segment in self.segments:
                    futures.append(self.executor.submit(self.__processSegment, segment))
            else:
                self.executor.submit(self.__processSingleSegment, self.segments[0])
                
            # wait for monitor thread end
            monitorThread.join()
            
        except Exception as e:
            logging.error(f"下载过程出错: {repr(e)}")
            self.errorOccurred.emit(repr(e))
        finally:
            self.isRunning = False
            if self.executor:
                self.executor.shutdown(wait=False)
            self.session.close()

    def stop(self):
        """停止下载任务并清理资源"""
        logging.info(f"正在停止任务: {self.filename}")
        self.isRunning = False
        
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        
        # 关闭会话
        try:
            if self.session:
                self.session.close()
        except Exception as e:
            logging.error(f"关闭会话时出错: {e}")
        
        logging.info(f"任务已停止: {self.filename}")

    def run(self):
        try:
            # run start
            self.__setupThread.join()  # wait for init complete
            self.__loadSegments()      # load segments
            self.__executeDownload()   # download start
        except Exception as e:
            # 确保所有异常都被捕获并通知UI
            logging.error(f"下载过程出错: {str(e)}")
            self.errorOccurred.emit(str(e))
            self.isRunning = False
