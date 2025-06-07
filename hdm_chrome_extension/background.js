// background.js

let socket;
let isConnected = false;
let shouldDisableExtension = false;
let heartbeatInterval = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 999999; // 实际上不限制重连次数
const RECONNECT_INTERVAL = 3000; // 3秒

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
});

// 创建 WebSocket 连接
function connectWebSocket() {
    try {
        console.log(`尝试连接到WebSocket，第${reconnectAttempts + 1}次尝试...`);
        
        // 使用原来的端口20971
        let url = "ws://localhost:20971";
        console.log(`连接到: ${url}`);
        socket = new WebSocket(url);

        socket.onopen = () => {
            console.log("WebSocket连接已建立");
            updateConnectionStatus(true);
            startHeartbeat();
            reconnectAttempts = 0; // 重置重连计数
            
            // 更新导出的变量
            self.reconnectAttempts = reconnectAttempts;
            
            // 清除连接错误
            chrome.storage.local.remove("connectionError");
        };

        socket.onmessage = function(event) {
            try {
                const message = JSON.parse(event.data);
                console.log("收到消息:", message);
                
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
                    console.log("收到客户端Online信号");
                    updateConnectionStatus(true);
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
            
            // 尝试记录更多错误信息
            chrome.storage.local.set({ 
                connectionError: "WebSocket连接错误，等待客户端连接..." 
            });
            
            // 即使出错也继续尝试重连
            scheduleReconnect();
        };

        socket.onclose = (event) => {
            console.log(`WebSocket连接关闭: 代码=${event.code}, 原因=${event.reason || '未提供原因'}`);
            updateConnectionStatus(false);
            stopHeartbeat();
            
            // 存储当前状态
            chrome.storage.local.set({ 
                connectionError: "等待客户端连接...",
                clientStatus: "offline"
            });
            
            // 始终尝试重连，不管重试次数
            scheduleReconnect();
        };
    } catch (e) {
        console.error("WebSocket连接过程中发生异常:", e);
        updateConnectionStatus(false);
        
        // 尝试记录更多错误信息
        chrome.storage.local.set({ 
            connectionError: `等待客户端连接...` 
        });
        
        // 即使发生异常也继续尝试重连
        scheduleReconnect();
    }
}

// 安排重新连接
function scheduleReconnect() {
    if (!shouldDisableExtension) {
        reconnectAttempts++;
        // 更新导出的变量
        self.reconnectAttempts = reconnectAttempts;
        
        // 每10次重连后增加日志，避免日志过多
        if (reconnectAttempts % 10 === 1) {
            console.log(`将在${RECONNECT_INTERVAL/1000}秒后重新连接，重连次数: ${reconnectAttempts}`);
        }
        
        setTimeout(connectWebSocket, RECONNECT_INTERVAL);
    }
}

// 更新连接状态并更新扩展状态和徽章
function updateConnectionStatus(connected) {
    isConnected = connected;
    updateBadge(connected ? "connected" : "disconnected");
    updateStatus(connected);
    
    // 更新客户端状态
    chrome.storage.local.set({ clientStatus: connected ? "online" : "offline" });
    
    // 如果连接恢复，尝试发送排队的下载
    if (connected) {
        sendPendingDownloads();
    }
    
    // 通知所有打开的页面连接状态发生变化
    chrome.runtime.sendMessage({
        action: "connectionChanged",
        isConnected: connected
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
                    // 如果发送心跳出错，尝试重新连接
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
                if (downloadItem.finalUrl.startsWith("http")) {
                    // 发送下载信息到本地客户端，即使连接不成功也要尝试发送
                    sendDownloadInfo({
                        url: downloadItem.finalUrl,
                        filename: downloadItem.filename,
                        size: downloadItem.totalBytes,
                        mimeType: downloadItem.mime,
                        referrer: downloadItem.referrer
                    });
                    
                    // 取消原始下载，让客户端接管
                    chrome.downloads.cancel(downloadItem.id, () => {
                        console.log(`已取消原下载 ${downloadItem.id} 并转发至下载器`);
                    });
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

// 修改 sendDownloadInfo 函数，将请求信息发送到 WebSocket
function sendDownloadInfo(requestInfo) {
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
        
        // 如果WebSocket连接可用，直接发送数据
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(downloadData));
            console.log("已发送下载信息到本地客户端:", downloadData);
            
            // 使用批处理添加到队列（虽然已直接发送，但仍记录到批处理中用于通知）
            addToDownloadQueue(downloadData);
            
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
    }
}

// 在连接成功后发送所有排队的下载
function sendPendingDownloads() {
    if (pendingDownloads.length > 0 && socket && socket.readyState === WebSocket.OPEN) {
        console.log(`尝试发送${pendingDownloads.length}个待处理的下载任务`);
        
        // 创建副本以防在迭代过程中修改原数组
        const downloads = [...pendingDownloads];
        pendingDownloads = [];
        
        // 使用新的通知系统
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

// 启动 WebSocket 连接
connectWebSocket();

// 在扩展启动时检查禁用状态和加载等待队列
chrome.storage.local.get(["shouldDisableExtension", "pendingDownloads"], (result) => {
    shouldDisableExtension = result.shouldDisableExtension || false;
    console.log("插件禁用状态:", shouldDisableExtension);
    
    // 加载之前保存的下载队列
    if (result.pendingDownloads && Array.isArray(result.pendingDownloads)) {
        pendingDownloads = result.pendingDownloads;
        console.log(`已加载${pendingDownloads.length}个待处理的下载任务`);
    }
});

// 监听来自popup或content script的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "resetConnection") {
        // 重新连接
        if (socket) {
            try {
                socket.close();
            } catch (e) {
                console.error("关闭WebSocket时出错:", e);
            }
        }
        reconnectAttempts = 0;
        connectWebSocket();
        sendResponse({ success: true });
        return true;
    } 
    else if (message.action === "reconnect") {
        // 重新连接
        if (!isConnected) {
            reconnectAttempts = 0;
            connectWebSocket();
        }
        sendResponse({ success: true });
        return true;
    }
    else if (message.action === "manualDownload") {
        // 处理手动下载请求
        if (isConnected && socket && socket.readyState === WebSocket.OPEN) {
            try {
                const success = sendDownloadInfo(message.downloadInfo);
                sendResponse({ success });
            } catch (error) {
                console.error("处理下载请求时出错:", error);
                sendResponse({ success: false, error: error.message });
            }
        } else {
            sendResponse({ 
                success: false, 
                error: "未连接到下载管理器，请确保应用程序正在运行" 
            });
        }
        return true;
    }
    else if (message.action === "getConnectionStatus") {
        // 返回当前连接状态
        sendResponse({
            isConnected: isConnected,
            reconnectAttempts: reconnectAttempts
        });
        return true;
    }
    else if (message.action === "clearQueue") {
        // 清空下载队列
        const clearedCount = clearDownloadQueue();
        sendResponse({ 
            success: true, 
            clearedCount: clearedCount 
        });
        return true;
    }
    else if (message.action === "queueUpdated") {
        // 队列已通过popup更新
        if (message.pendingDownloads !== undefined) {
            pendingDownloads = message.pendingDownloads;
            chrome.storage.local.set({ pendingDownloads: pendingDownloads });
            sendResponse({ success: true });
        } else {
            sendResponse({ success: false, error: "未提供更新的队列" });
        }
        return true;
    }
});
