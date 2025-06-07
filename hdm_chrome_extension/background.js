// background.js

let socket;
let isConnected = false;
let shouldDisableExtension = false;
let heartbeatInterval = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 1; // 只尝试连接一次，不重连
const RECONNECT_INTERVAL = 3000; // 3秒，仅用于初始化连接

// 创建一个队列来存储离线时的下载请求
let pendingDownloads = [];
const MAX_PENDING_DOWNLOADS = 50; // 限制队列大小

// 通知控制变量
const NOTIFICATION_COOLDOWN = 10000; // 通知冷却时间（10秒）
let lastNotificationTime = 0; // 上次显示通知的时间
let notificationQueue = []; // 通知队列
let processingNotificationQueue = false; // 是否正在处理通知队列
const MAX_BATCH_NOTIFICATIONS = 5; // 批量通知中最多显示的下载项数量
let pendingNotificationsCount = 0; // 待处理的通知数量

// 队列任务批处理控制
const QUEUE_BATCH_DELAY = 3000; // 队列批处理延迟时间（3秒）
let queueBatchTimer = null; // 队列批处理定时器
let queueBatchItems = []; // 队列批处理项目
let isProcessingQueueBatch = false; // 是否正在处理队列批次

// 连接控制变量
let lastActiveTime = 0; // 上次活动时间
let hasTasksToProcess = false; // 是否有任务需要处理
let isWaitingForSignal = false; // 是否正在等待alive信号
let isManualReconnect = false; // 是否手动重连
let clientStatus = "offline"; // 添加客户端状态变量

// 导出变量和函数供其他脚本使用
self.reconnectAttempts = reconnectAttempts;
self.connectWebSocket = connectWebSocket;

// 监听扩展安装或更新事件
chrome.runtime.onInstalled.addListener(function(details) {
    // 当扩展被安装或更新时
    if (details.reason === "install") {
        console.log("扩展安装完成，打开欢迎页面");
        // 安装时打开欢迎页面
        chrome.tabs.create({ url: "welcome.html" });
    } else if (details.reason === "update") {
        console.log("扩展更新完成，从版本", details.previousVersion);
        // 更新时也可以打开欢迎页面，或者打开更新日志页面
        // chrome.tabs.create({ url: "welcome.html" });
    }
    
    // 安装或更新时检查是否有任务需要处理
    checkForTasks();
});

// 只在有任务时检查是否需要连接
function checkForTasks() {
    // 如果已经连接，或者已禁用，则不执行
    if (isConnected || shouldDisableExtension) {
        return;
    }
    
    // 如果有待处理的任务，尝试连接
    if (pendingDownloads.length > 0 || hasTasksToProcess) {
        console.log("检测到有待处理任务，尝试连接");
        connectIfNeeded();
    }
}

// 检查是否需要连接，只在有下载任务时连接
function connectIfNeeded() {
    // 禁用模式下不连接
    isExtensionDisabled(function(disabled) {
        if (disabled) {
            console.log("扩展已禁用，不连接到客户端");
            return;
        }
        
        // 设置标志，表示正在等待alive信号
        isWaitingForSignal = true;
        
        // 只有当有新的下载任务或手动触发时才尝试连接
        if (pendingDownloads.length > 0 || isManualReconnect) {
            // 重置手动重连标志
            isManualReconnect = false;
            
            // 如果当前已连接，无需再次连接
            if (isConnected && socket && socket.readyState === WebSocket.OPEN) {
                console.log("已经连接到客户端，尝试发送待处理的下载任务");
                sendPendingDownloads();
                return;
            }
            
            // 否则，连接并发送任务
            connectWebSocket();
        } else {
            console.log("没有待处理的下载任务，不尝试连接");
        }
    });
}

// 创建 WebSocket 连接
function connectWebSocket() {
    // 如果已经连接，则不重复连接
    if (isConnected && socket && socket.readyState === WebSocket.OPEN) {
        console.log("WebSocket已连接，不再重复连接");
        return;
    }
    
    try {
        console.log("尝试连接到WebSocket...");
        
        // 标记正在等待信号
        isWaitingForSignal = true;
        
        // 使用原来的端口20971
        let url = "ws://localhost:20971";
        console.log(`连接到: ${url}`);
        socket = new WebSocket(url);

        socket.onopen = () => {
            console.log("WebSocket连接已建立");
            updateConnectionStatus(true);
            startHeartbeat();
            reconnectAttempts = 0; // 重置重连计数
            lastActiveTime = Date.now(); // 更新活动时间
            isWaitingForSignal = false; // 连接成功，不再等待信号
            
            // 更新导出的变量
            self.reconnectAttempts = reconnectAttempts;
            
            // 清除连接错误
            chrome.storage.local.remove("connectionError");
            
            // 发送所有待处理的下载
            if (pendingDownloads.length > 0) {
                sendPendingDownloads();
            }
        };

        socket.onmessage = function(event) {
            try {
                const message = JSON.parse(event.data);
                console.log("收到消息:", message);
                lastActiveTime = Date.now(); // 更新活动时间
                
                if (message.type === "version") {
                    // 保存版本信息到 chrome.storage.local
                    chrome.storage.local.set({ ClientVersion: message.ClientVersion }, function() {
                        console.log("客户端版本已存储:", message.ClientVersion);
                    });
                    chrome.storage.local.set({ LatestExtensionVersion: message.LatestExtensionVersion }, function() {
                        console.log("最新扩展版本已存储:", message.LatestExtensionVersion);
                    });
                } else if (message.type === "heartbeat") {
                    console.log("收到心跳响应");
                } else if (message.type === "alive") {
                    // 处理客户端发送的活着信号
                    console.log("收到客户端Online信号:", message);
                    updateConnectionStatus(true);
                    isWaitingForSignal = false; // 收到alive信号，不再等待
                    clientStatus = "online"; // 更新客户端状态变量
                    
                    // 更新存储中的状态
                    chrome.storage.local.set({ 
                        isConnected: true,
                        clientStatus: "online",
                        connectionError: null // 清除连接错误
                    });
                    
                    // 响应alive信号
                    try {
                        if (socket && socket.readyState === WebSocket.OPEN) {
                            const response = {
                                type: "alive",
                                timestamp: Date.now(),
                                response: "扩展已接收alive信号"
                            };
                            socket.send(JSON.stringify(response));
                            console.log("已响应alive信号");
                        }
                    } catch (error) {
                        console.error("响应alive信号时出错:", error);
                    }
                    
                    // 如果有积压的下载任务，尝试发送
                    if (pendingDownloads.length > 0) {
                        sendPendingDownloads();
                    }
                } else {
                    console.log("收到其他消息:", message);
                }
            } catch (e) {
                console.error("处理消息时出错:", e, "原始消息:", event.data);
            }
        };

        socket.onerror = (error) => {
            console.error("WebSocket错误:", error);
            updateConnectionStatus(false);
            stopHeartbeat();
            
            // 设置等待信号状态
            isWaitingForSignal = true;
            
            // 尝试记录更多错误信息
            chrome.storage.local.set({ 
                connectionError: "WebSocket连接错误，等待客户端启动..." 
            });
            
            // 连接失败，不再自动重连，只在收到alive信号时重连
            console.log("连接失败，等待alive信号来触发重连");
            
            // 不再调用connectIfNeeded函数，而是直接返回
        };

        socket.onclose = (event) => {
            console.log(`WebSocket连接关闭: 代码=${event.code}, 原因=${event.reason || '未提供原因'}`);
            updateConnectionStatus(false);
            stopHeartbeat();
            
            // 设置等待信号状态
            isWaitingForSignal = true;
            
            // 存储当前状态
            chrome.storage.local.set({ 
                connectionError: "等待客户端启动...",
                clientStatus: "offline"
            });
            
            // 连接关闭，不再自动重连，只在收到alive信号时重连
            console.log("连接关闭，等待alive信号来触发重连");
        };
    } catch (e) {
        console.error("WebSocket连接过程中发生异常:", e);
        updateConnectionStatus(false);
        
        // 设置等待信号状态
        isWaitingForSignal = true;
        
        // 尝试记录更多错误信息
        chrome.storage.local.set({ 
            connectionError: `等待客户端启动...` 
        });
        
        // 连接失败，不再自动重连，只在收到alive信号时重连
        console.log("连接出错，等待alive信号来触发重连");
    }
}

// 更新连接状态并更新扩展状态和徽章
function updateConnectionStatus(connected) {
    isConnected = connected;
    updateBadge(connected ? "connected" : "disconnected");
    updateStatus(connected);
    lastActiveTime = Date.now(); // 更新活动时间
    
    // 更新客户端状态
    clientStatus = connected ? "online" : "offline";
    chrome.storage.local.set({ 
        clientStatus: clientStatus,
        isConnected: connected,
        connectionError: connected ? null : "等待客户端连接..."
    });
    
    // 如果连接恢复，尝试发送排队的下载
    if (connected && pendingDownloads.length > 0) {
        sendPendingDownloads();
    }
    
    // 通知所有打开的页面连接状态发生变化
    chrome.runtime.sendMessage({
        action: "connectionChanged",
        isConnected: connected,
        clientStatus: clientStatus
    }).catch(error => {
        // 忽略没有页面监听的错误
        console.debug("发送连接状态变化消息时出错:", error);
    });
}

// 更新扩展图标徽章
function updateBadge(status) {
    const badgeColor = (status === "connected") ? "green" : "pink";
    const badgeText = (status === "connected") ? "√" : "×";
    chrome.action.setBadgeBackgroundColor({ color: badgeColor });
    chrome.action.setBadgeText({ text: badgeText });
}

// 更新扩展状态
function updateStatus(connected) {
    chrome.storage.local.set({ isConnected: connected }, () => {
        console.log(`Status updated: ${connected ? "Connected" : "Disconnected"}`);
    });
}

// 启动心跳机制
function startHeartbeat() {
    if (!heartbeatInterval) { // 检查是否已有定时器
        heartbeatInterval = setInterval(() => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                try {
                    // 发送心跳包
                    const heartbeatData = {
                        type: 'heartbeat',
                        timestamp: Date.now()
                    };
                    socket.send(JSON.stringify(heartbeatData));
                    console.log("已发送心跳包:", heartbeatData);
                } catch (error) {
                    console.error("发送心跳包时出错:", error);
                    // 如果发送心跳出错，关闭连接
                    stopHeartbeat();
                    if (socket) {
                        try {
                            socket.close();
                        } catch (e) {
                            console.error("关闭WebSocket时出错:", e);
                        }
                    }
                }
            } else if (!socket || socket.readyState !== WebSocket.OPEN) {
                console.warn("心跳检测发现WebSocket未连接，停止心跳");
                stopHeartbeat();
            }
        }, 10000); // 每10秒发送一次心跳
        console.log("已启动心跳机制");
    }
}

// 停止心跳机制
function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval); // 清除定时器
        heartbeatInterval = null; // 重置定时器变量
        console.log("已停止心跳机制");
    }
}

// 提取获取 shouldDisableExtension 的逻辑到一个单独的函数
function isExtensionDisabled(callback) {
    chrome.storage.local.get(["shouldDisableExtension"], (result) => {
        callback(result.shouldDisableExtension || false);
    });
}

// 显示通知，带防抖和冷却功能
function showNotification(options) {
    const currentTime = Date.now();
    
    // 将通知添加到队列
    notificationQueue.push(options);
    
    // 如果当前没有在处理队列，并且距离上次通知已经过了冷却时间，则处理队列
    if (!processingNotificationQueue && (currentTime - lastNotificationTime >= NOTIFICATION_COOLDOWN)) {
        processNotificationQueue();
    }
}

// 处理通知队列
function processNotificationQueue() {
    if (notificationQueue.length === 0) {
        processingNotificationQueue = false;
        return;
    }
    
    processingNotificationQueue = true;
    lastNotificationTime = Date.now();
    
    // 如果队列中只有一个通知，直接显示
    if (notificationQueue.length === 1) {
        const notification = notificationQueue.shift();
        chrome.notifications.create(notification);
        
        // 设置定时器，在冷却时间结束后检查队列
        setTimeout(() => {
            processNotificationQueue();
        }, NOTIFICATION_COOLDOWN);
        
        return;
    }
    
    // 如果队列中有多个通知，合并为一个批量通知
    const batchSize = Math.min(notificationQueue.length, MAX_BATCH_NOTIFICATIONS);
    const firstNotification = notificationQueue[0];
    
    // 准备批量通知消息
    let batchMessage = `正在处理 ${notificationQueue.length} 个下载任务:\n`;
    
    // 添加前几个任务的文件名
    for (let i = 0; i < batchSize; i++) {
        const filename = notificationQueue[i].message.replace(/^文件 "(.+)" 正在.*$/, '$1');
        batchMessage += `- ${filename}\n`;
    }
    
    // 如果还有更多任务，添加省略号
    if (notificationQueue.length > batchSize) {
        batchMessage += `... 还有 ${notificationQueue.length - batchSize} 个任务`;
    }
    
    // 创建合并后的通知
    chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon128.png',
        title: '批量下载处理中',
        message: batchMessage
    });
    
    // 清空通知队列
    notificationQueue = [];
    
    // 设置定时器，在冷却时间结束后检查队列
    setTimeout(() => {
        processNotificationQueue();
    }, NOTIFICATION_COOLDOWN);
}

// 添加任务到队列，带批处理功能
function addToDownloadQueue(downloadData) {
    // 限制队列大小，防止内存溢出
    if (pendingDownloads.length >= MAX_PENDING_DOWNLOADS) {
        pendingDownloads.shift(); // 移除最旧的下载请求
    }
    
    // 添加到主队列
    pendingDownloads.push(downloadData);
    
    // 添加到批处理队列
    queueBatchItems.push(downloadData);
    
    // 如果没有活动的批处理定时器，启动一个
    if (queueBatchTimer === null && !isProcessingQueueBatch) {
        queueBatchTimer = setTimeout(() => {
            processQueueBatch();
        }, QUEUE_BATCH_DELAY);
    }
    
    // 更新存储中的队列信息
    chrome.storage.local.set({ pendingDownloads: pendingDownloads });
    
    return pendingDownloads.length;
}

// 处理队列批次
function processQueueBatch() {
    isProcessingQueueBatch = true;
    
    // 清除定时器
    if (queueBatchTimer) {
        clearTimeout(queueBatchTimer);
        queueBatchTimer = null;
    }
    
    // 获取当前批次中的项目
    const batchItems = [...queueBatchItems];
    queueBatchItems = []; // 清空批处理队列
    
    // 如果批次中有项目，进行处理
    if (batchItems.length > 0) {
        console.log(`处理队列批次，包含 ${batchItems.length} 个项目`);
        
        // 显示批次通知
        showBatchQueueNotification(batchItems);
    }
    
    isProcessingQueueBatch = false;
}

// 显示批次队列通知
function showBatchQueueNotification(batchItems) {
    if (batchItems.length === 0) return;
    
    // 如果只有一个项目，使用单独通知
    if (batchItems.length === 1) {
        const item = batchItems[0];
        showNotification({
            type: 'basic',
            iconUrl: 'icon128.png',
            title: '下载已加入队列',
            message: `文件 "${item.filename}" 已${isConnected ? '发送至下载器' : '添加到队列'}`
        });
        return;
    }
    
    // 如果有多个项目，创建批量通知
    const displayCount = Math.min(batchItems.length, MAX_BATCH_NOTIFICATIONS);
    let message = `已${isConnected ? '发送' : '添加'} ${batchItems.length} 个下载任务：\n`;
    
    for (let i = 0; i < displayCount; i++) {
        message += `- ${batchItems[i].filename}\n`;
    }
    
    if (batchItems.length > displayCount) {
        message += `... 还有 ${batchItems.length - displayCount} 个任务`;
    }
    
    showNotification({
        type: 'basic',
        iconUrl: 'icon128.png',
        title: '批量下载已处理',
        message: message
    });
}

// 监听下载开始事件并阻止下载
chrome.downloads.onDeterminingFilename.addListener((downloadItem) => {
    if (downloadItem.state === "in_progress") {
        chrome.storage.local.get(["shouldDisableExtension"], (result) => {
            if (!result.shouldDisableExtension) {
                console.log("Download started: ", downloadItem);
                
                // 检查URL是否有效
                if (downloadItem.finalUrl && downloadItem.finalUrl.startsWith("http")) {
                    // 创建一个下载请求ID作为唯一标识
                    const requestId = `download_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                    
                    // 发送下载信息到本地客户端
                    const result = sendDownloadInfo({
                        url: downloadItem.finalUrl,
                        filename: downloadItem.filename,
                        size: downloadItem.totalBytes,
                        mimeType: downloadItem.mime,
                        referrer: downloadItem.referrer,
                        requestId: requestId // 添加请求ID用于跟踪
                    });
                    
                    // 仅当成功发送到客户端时才取消原始下载
                    if (result) {
                        // 取消原始下载，让客户端接管
                        chrome.downloads.cancel(downloadItem.id, () => {
                            console.log(`已取消原下载 ${downloadItem.id} 并转发至下载器`);
                        });
                    } else {
                        console.warn(`未能成功发送下载请求，保留原始下载 ${downloadItem.id}`);
                    }
                } else {
                    console.log(`跳过非HTTP下载: ${downloadItem.id}`);
                }
            }
        });
    }
});

let requestHeadersMap = new Map(); // 存储请求头信息的映射表

// 监听 onBeforeSendHeaders 事件，捕获请求头信息并转为字典形式
chrome.webRequest.onBeforeSendHeaders.addListener(
    (details) => {
        // 将请求头数组转换为字典（键值对形式）
        const requestHeadersDict = details.requestHeaders.reduce((acc, header) => {
            acc[header.name.toLowerCase()] = header.value;
            return acc;
        }, {});

        // 存储请求头信息到映射表中，以请求 ID 为键
        requestHeadersMap.set(details.url, requestHeadersDict);
        console.log("Details url:", details.url);
    },
    {
        urls: ["<all_urls>"], // 监听所有请求
        types: ["main_frame", "sub_frame", "xmlhttprequest", "other"], // 资源类型
    },
    ["requestHeaders", "extraHeaders"] // 需要访问请求头
);

// 在连接成功后发送所有排队的下载
function sendPendingDownloads() {
    if (pendingDownloads.length > 0 && socket && socket.readyState === WebSocket.OPEN) {
        console.log(`尝试发送${pendingDownloads.length}个待处理的下载任务`);
        
        // 创建副本以防在迭代过程中修改原数组
        const downloads = [...pendingDownloads];
        pendingDownloads = [];
        
        // 清空存储
        chrome.storage.local.set({ pendingDownloads: [] });
        
        // 使用新的通知系统 - 只发送一次通知
        showNotification({
            type: 'basic',
            iconUrl: 'icon128.png',
            title: '正在处理队列中的下载',
            message: `正在发送${downloads.length}个排队的下载任务到客户端`
        });
        
        // 分批发送，避免一次性发送过多
        let successCount = 0;
        let failedItems = [];
        
        downloads.forEach((download, index) => {
            // 添加延迟，避免同时发送太多请求
            setTimeout(() => {
                try {
                    if (socket && socket.readyState === WebSocket.OPEN) {
                        // 添加一个发送时间戳，避免重复处理
                        download.sendTime = Date.now();
                        socket.send(JSON.stringify(download));
                        successCount++;
                        console.log(`成功发送排队的下载任务 ${index+1}/${downloads.length}: ${download.filename}`);
                    } else {
                        // 如果连接中断，将此项添加到失败列表
                        failedItems.push(download);
                    }
                    
                    // 在所有任务处理完毕后更新存储和显示结果
                    if (index === downloads.length - 1) {
                        // 将失败的项目重新添加到队列
                        failedItems.forEach(item => {
                            addToDownloadQueue(item);
                        });
                        
                        if (successCount > 0) {
                            // 使用新的通知系统
                            showNotification({
                                type: 'basic',
                                iconUrl: 'icon128.png',
                                title: '队列处理完成',
                                message: `成功发送 ${successCount}/${downloads.length} 个排队的下载任务`
                            });
                        }
                    }
                } catch (error) {
                    console.error(`发送排队下载任务失败: ${error.message}`);
                    failedItems.push(download); // 添加到失败列表
                }
            }, index * 300); // 每300ms发送一个任务
        });
    }
}

// 清空下载队列
function clearDownloadQueue() {
    const queueSize = pendingDownloads.length;
    pendingDownloads = [];
    queueBatchItems = [];
    
    // 更新存储
    chrome.storage.local.set({ pendingDownloads: [] });
    
    // 返回清空的队列大小
    return queueSize;
}

// 修改 sendDownloadInfo 函数，将请求信息发送到 WebSocket
function sendDownloadInfo(requestInfo) {
    hasTasksToProcess = true; // 标记有任务需要处理
    
    try {
        // 准备发送的数据
        const downloadData = {
            type: 'download', // 确保始终包含type字段
            url: requestInfo.url,
            filename: requestInfo.filename,
            size: requestInfo.size || -1,
            mimeType: requestInfo.mimeType,
            timestamp: Date.now(),
            referrer: requestInfo.referrer,
            headers: {
                'User-Agent': navigator.userAgent,
                'Referer': requestInfo.referrer
            }
        };
        
        // 在有新任务时，尝试连接
        if (!isConnected) {
            console.log("有新的下载任务，尝试连接");
            connectWebSocket(); // 直接尝试连接
        }
        
        // 如果WebSocket连接可用，直接发送数据
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(downloadData));
            console.log("已发送下载信息到本地客户端:", downloadData);
            
            // 不再将已发送的下载加入队列，避免重复处理
            // 只添加通知提示用户下载已成功发送
            showNotification({
                type: 'basic',
                iconUrl: 'icon128.png',
                title: '下载已发送',
                message: `文件 "${downloadData.filename}" 已发送至下载器`
            });
            
            return true;
        } else {
            // 如果WebSocket未连接，将数据添加到待发送队列
            console.warn("WebSocket未连接，将下载任务加入队列:", downloadData.filename);
            
            // 使用批处理添加到队列
            addToDownloadQueue(downloadData);
            
            return false;
        }
    } catch (error) {
        console.error("发送下载信息时出错:", error);
        return false;
    } finally {
        // 处理完成后，在短时间内重置任务标记
        setTimeout(() => {
            hasTasksToProcess = false;
        }, 5000);
    }
}

// 在扩展启动时初始化
function initialize() {
    // 在扩展启动时检查禁用状态和加载等待队列
    chrome.storage.local.get(["shouldDisableExtension", "pendingDownloads"], (result) => {
        shouldDisableExtension = result.shouldDisableExtension || false;
        console.log("插件禁用状态:", shouldDisableExtension);
        
        // 加载之前保存的下载队列
        if (result.pendingDownloads && Array.isArray(result.pendingDownloads)) {
            pendingDownloads = result.pendingDownloads;
            console.log(`已加载${pendingDownloads.length}个待处理的下载任务`);
        }
        
        // 如果扩展未禁用，尝试立即连接一次
        if (!shouldDisableExtension) {
            console.log("扩展启动时尝试连接一次");
            // 不使用connectIfNeeded，直接调用connectWebSocket
            setTimeout(connectWebSocket, 1000);
        }
    });
    
    // 设置一个特殊监听器，监听来自客户端的HTTP请求
    setupGlobalTcpListener();
    
    // 设置一个监听扩展消息的处理器，用于处理通过其他渠道收到的alive信号
    chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
        if (request && request.action === "receivedAliveSignal") {
            console.log("通过消息通道收到alive信号，尝试重新连接");
            connectWebSocket();
            sendResponse({result: "attempting_connection"});
            return true;
        }
        return true;
    });
}

// 启动初始化
initialize();

// 手动触发重连
function manualReconnect() {
    isManualReconnect = true;
    console.log("用户手动触发重连");
    connectIfNeeded();
}

// 处理来自popup或其他页面的消息
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log("收到内部消息:", request);
    
    if (request.action === "getConnectionStatus") {
        sendResponse({
            isConnected: isConnected,
            pendingDownloads: pendingDownloads.length,
            clientStatus: clientStatus
        });
    } else if (request.action === "manualReconnect") {
        // 手动触发重连
        manualReconnect();
        sendResponse({ result: "reconnecting" });
    } else if (request.action === "clearQueue") {
        // 清空下载队列
        clearDownloadQueue();
        sendResponse({ result: "queue_cleared" });
    }
    
    return true; // 保持消息通道开放以支持异步响应
});

// 设置一个全局的TCP监听端口，用于接收来自客户端的alive信号
function setupGlobalTcpListener() {
    // 这个函数在浏览器环境中无法直接实现TCP监听
    // 我们需要使用其他方式让客户端触发连接
    console.log("设置全局TCP监听器");
    
    // 创建一个特殊的HTTP请求监听，用于检测alive信号
    // 这只是一个模拟方案，实际上需要通过其他方式
    
    // 设置一个定期检查本地文件或HTTP请求的功能
    setInterval(checkAliveSignal, 5000); // 每5秒检查一次
}

// 检查是否有新的alive信号
function checkAliveSignal() {
    // 在浏览器环境中，我们可以尝试通过HTTP请求检查客户端状态
    
    try {
        // 创建一个特殊的HTTP请求到本地客户端
        const checkUrl = "http://localhost:20972/status";
        
        fetch(checkUrl, { 
            method: 'GET',
            mode: 'no-cors', // 非CORS模式
            cache: 'no-cache',
            headers: {
                'X-Extension-Check': 'true'
            },
            timeout: 1000 // 1秒超时
        })
        .then(response => {
            console.log("收到客户端状态响应");
            // 如果能收到响应，说明客户端在线
            if (!isConnected) {
                console.log("检测到客户端在线，尝试重新连接");
                connectWebSocket();
            }
        })
        .catch(error => {
            // 忽略错误，客户端可能未启动
            console.debug("检查客户端状态失败，可能未启动:", error);
        });
    } catch (error) {
        console.debug("尝试检查客户端状态时出错:", error);
    }
}
