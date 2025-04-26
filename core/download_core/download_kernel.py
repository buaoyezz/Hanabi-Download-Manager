import concurrent.futures
import struct
import sys
import time
import threading
import os
from pathlib import Path
from threading import Thread, Lock

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PySide6.QtCore import QThread, Signal
import logging

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
        self.session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
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
        segmentSize = self.fileSize // self.threadCount
        boundaries = list(range(0, self.fileSize, segmentSize))

        if self.fileSize % self.threadCount == 0:
            boundaries.append(self.fileSize)

        segments = []
        for i in range(len(boundaries) - 1):
            start, end = boundaries[i], boundaries[i + 1] - 1
            segments.append([start, end])

        # fix last segment end position
        segments[-1][-1] = self.fileSize - 1

        return segments

    def __prepareDownload(self):
        try:
            # auto get filename and size
            if self.fileSize == -1 or not self.filename:
                self.url, self.filename, self.fileSize = getLinkInfo(self.url, self.headers, self.filename)

            # judge if supports multi-threading
            self.supportsMultiThreading = bool(self.fileSize)

            if not self.savePath or not Path(self.savePath).is_dir():
                self.savePath = Path.cwd()
            else:
                self.savePath = Path(self.savePath)
                if not self.savePath.exists():
                    self.savePath.mkdir()

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
            self.errorOccurred.emit(repr(e))

    def __loadSegments(self):
        if not self.supportsMultiThreading:
            self.segments.append(DownloadSegment(0, 0, 1, self.session))
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
                for i in range(self.threadCount):
                    self.segments.append(
                        DownloadSegment(segments[i][0], segments[i][0], segments[i][1], self.session))
        else:
            # 创建新的下载分段
            segments = self.__calculateSegments()
            for i in range(self.threadCount):
                self.segments.append(
                    DownloadSegment(segments[i][0], segments[i][0], segments[i][1], self.session))

    def __processSegment(self, segment: DownloadSegment):
        logging.debug(f"文件({self.filename})启动线程 {segment.startPos}-{segment.endPos}...")
        if segment.progress < segment.endPos:
            finished = False
            while not finished and self.isRunning:
                try:
                    rangeHeaders = self.headers.copy()
                    rangeHeaders["range"] = f"bytes={segment.progress}-{segment.endPos}"

                    with segment.session.get(self.url, headers=rangeHeaders, stream=True, timeout=30) as res:
                        if res.status_code != 206:
                            raise requests.HTTPError(f"服务器拒绝范围请求，状态码：{res.status_code}")
                        
                        with open(f"{self.savePath}/{self.filename}", "r+b") as file:
                            for chunk in res.iter_content(chunk_size=1024*1024):  # 1MB缓冲区
                                if not chunk or not self.isRunning or segment.endPos <= segment.progress:
                                    break
                                    
                                with self.threadLock:
                                    file.seek(segment.progress)
                                    file.write(chunk)
                                    dataSize = len(chunk)
                                    segment.progress += dataSize
                                    
                                    # 限速处理
                                    try:
                                        # 尝试访问cfg.speedLimitation，尝试多种可能形式
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

                    if segment.progress >= segment.endPos:
                        segment.progress = segment.endPos

                    finished = True

                except Exception as e:
                    logging.info(
                        f"文件({self.filename})线程 {segment.startPos}-{segment.endPos} 重连中: {repr(e)}")
                    self.errorOccurred.emit(repr(e))
                    time.sleep(5)  # 等待5秒后重试

            segment.progress = segment.endPos

        # try create new segment, improve download efficiency
        return self.__createNewSegment()

    def __processSingleSegment(self, segment: DownloadSegment):
        if segment.progress < segment.endPos:
            finished = False
            while not finished and self.isRunning:
                try:
                    with segment.session.get(self.url, headers=self.headers, stream=True, timeout=30) as res:
                        with open(f"{self.savePath}/{self.filename}", "r+b") as file:
                            for chunk in res.iter_content(chunk_size=1024*1024):  # 1MB缓冲区
                                if not chunk or not self.isRunning:
                                    break
                                    
                                file.seek(segment.progress)
                                file.write(chunk)
                                dataSize = len(chunk)
                                segment.progress += dataSize
                                
                                try:
                                    # 尝试访问cfg.speedLimitation，尝试多种可能形式
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
                    self.supportsMultiThreading = True
                    finished = True

                except requests.RequestException as e:
                    # retry
                    logging.info(
                        f"文件({self.filename})单线程下载重连中: {repr(e)}")
                    self.errorOccurred.emit(repr(e))
                    time.sleep(5)  # 5 s retry

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
                segmentInfo = []
                with self.threadLock:
                    self.progress = 0
                    historyFile.seek(0)
                    
                    # update segment info
                    for segment in self.segments:
                        segmentInfo.append({"start": segment.startPos, 
                                           "progress": segment.progress, 
                                           "end": segment.endPos})
                        self.progress += (segment.progress - segment.startPos + 1)
                        data = struct.pack("<QQQ", segment.startPos, segment.progress, segment.endPos)
                        historyFile.write(data)
                        
                    # ensure data write to disk
                    historyFile.flush()
                    os.fsync(historyFile.fileno())
                    historyFile.truncate()

                # send progress signal
                self.segmentProgressChanged.emit(segmentInfo)

                # calculate download speed
                currentSpeed = (self.progress - lastProgress)
                lastProgress = self.progress
                self.speedHistory.pop(0)
                self.speedHistory.append(currentSpeed)
                avgSpeed = sum(self.speedHistory) / 10

                # send speed signal
                self.transferSpeedChanged.emit(int(avgSpeed))

                if self.dynamicThreads:
                    if timeCounter < 10:
                        timeCounter += 1
                    else:
                        timeCounter = 0

                        if len(self.segments) > 0:
                            # calculate thread efficiency
                            threadSpeed = avgSpeed / len(self.segments)
                            if threadSpeed > maxSpeedPerThread:
                                maxSpeedPerThread = threadSpeed
                                speedTarget = (0.85 * maxSpeedPerThread * newThreadCount) + baseSpeed
                            
                            #  auto add thread
                            if avgSpeed >= speedTarget:
                                baseSpeed = avgSpeed
                                newThreadCount = 4
                                speedTarget = (0.85 * maxSpeedPerThread * newThreadCount) + baseSpeed

                                # limit max thread count to 32
                                if len(self.segments) < 32:
                                    for i in range(4):
                                        if not self.__createNewSegment():
                                            break

                time.sleep(1)  # 每秒更新一次
                
            # close resume file
            historyFile.close()
            
            # download complete
            if self.progress == self.fileSize and self.isRunning:
                try:
                    # delete resume file
                    Path(f"{self.savePath}/{self.filename}.hdm").unlink()
                except Exception as e:
                    logging.error(f"删除历史记录文件失败，请手动删除: {e}")
                    
                logging.info(f"文件({self.filename})下载完成！")
                self.downloadComplete.emit()
        else:
            # handle not support multi-threading
            while self.isRunning and not self.supportsMultiThreading:
                with self.threadLock:
                    self.progress = 0
                    for segment in self.segments:
                        self.progress += (segment.progress - segment.startPos + 1)

                # send empty progress info (single thread mode)
                self.segmentProgressChanged.emit([])

                # calculate speed
                currentSpeed = (self.progress - lastProgress)
                lastProgress = self.progress
                self.speedHistory.pop(0)
                self.speedHistory.append(currentSpeed)
                avgSpeed = sum(self.speedHistory) / 10

                # send speed signal
                self.transferSpeedChanged.emit(int(avgSpeed))

                time.sleep(1) 
                
            # download complete
            if self.isRunning and self.supportsMultiThreading:
                logging.info(f"文件({self.filename})下载完成！")
                self.downloadComplete.emit()

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
        # run start
        self.__setupThread.join()  # wait for init complete
        self.__loadSegments()      # load segments
        self.__executeDownload()   # download start
