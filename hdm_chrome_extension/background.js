// background.js

let socket;
let isConnected = false;
let shouldDisableExtension = false;
let heartbeatInterval = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10; // 增加到10次
const RECONNECT_INTERVAL = 3000; // 3秒

// 导出变量和函数供其他脚本使用
self.reconnectAttempts = reconnectAttempts;
self.connectWebSocket = connectWebSocket;

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
                connectionError: "WebSocket连接错误，可能是服务器未启动或端口被占用" 
            });
        };

        socket.onclose = (event) => {
            console.log(`WebSocket连接关闭: 代码=${event.code}, 原因=${event.reason || '未提供原因'}`);
            updateConnectionStatus(false);
            stopHeartbeat();
            
            // 如果需要重新连接且未达到最大尝试次数
            if (!shouldDisableExtension && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                // 更新导出的变量
                self.reconnectAttempts = reconnectAttempts;
                console.log(`将在${RECONNECT_INTERVAL/1000}秒后重新连接，尝试次数: ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`);
                
                // 存储当前重试次数
                chrome.storage.local.set({ 
                    connectionError: `连接失败，正在重试 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})` 
                });
                
                setTimeout(connectWebSocket, RECONNECT_INTERVAL);
            } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                console.error(`已达到最大重连尝试次数(${MAX_RECONNECT_ATTEMPTS})，停止重连`);
                chrome.storage.local.set({ 
                    connectionError: "已达到最大重连尝试次数，请确认下载管理器是否正在运行，或尝试重启下载管理器" 
                });
            }
        };
    } catch (e) {
        console.error("WebSocket连接过程中发生异常:", e);
        updateConnectionStatus(false);
        
        // 尝试记录更多错误信息
        chrome.storage.local.set({ 
            connectionError: `WebSocket连接过程中发生异常: ${e.message}` 
        });
        
        // 如果需要重新连接且未达到最大尝试次数
        if (!shouldDisableExtension && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            // 更新导出的变量
            self.reconnectAttempts = reconnectAttempts;
            console.log(`将在${RECONNECT_INTERVAL/1000}秒后重新连接，尝试次数: ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`);
            setTimeout(connectWebSocket, RECONNECT_INTERVAL);
        } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`已达到最大重连尝试次数(${MAX_RECONNECT_ATTEMPTS})，停止重连`);
            chrome.storage.local.set({ 
                connectionError: "已达到最大重连尝试次数，请确认下载管理器是否正在运行，或尝试重启下载管理器" 
            });
        }
    }
}

// 更新连接状态并更新扩展状态和徽章
function updateConnectionStatus(connected) {
    isConnected = connected;
    updateBadge(connected ? "connected" : "disconnected");
    updateStatus(connected);
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

// 监听下载开始事件并阻止下载
chrome.downloads.onDeterminingFilename.addListener((downloadItem) => {
    if (downloadItem.state === "in_progress") {
        chrome.storage.local.get(["shouldDisableExtension"], (result) => {
            if (!result.shouldDisableExtension && isConnected && socket.readyState === WebSocket.OPEN) {
                console.log("Download started: ", downloadItem);
                if (downloadItem.finalUrl.startsWith("http")) {
                    // 发送下载信息到本地客户端
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
        if (socket && socket.readyState === WebSocket.OPEN) {
            // 获取当前标签页的URL作为referrer
            let referrer = requestInfo.referrer;
            
            // 准备发送的数据
            const downloadData = {
                type: 'download', // 确保始终包含type字段
                url: requestInfo.url,
                filename: requestInfo.filename,
                size: requestInfo.size || -1,
                mimeType: requestInfo.mimeType,
                timestamp: Date.now(),
                referrer: referrer,
                headers: {
                    'User-Agent': navigator.userAgent,
                    'Referer': referrer
                }
            };
            
            // 添加Cookie如果需要（可能需要额外权限）
            // if (requestInfo.cookies) {
            //     downloadData.cookies = requestInfo.cookies;
            // }
            
            // 发送数据到本地服务器
            socket.send(JSON.stringify(downloadData));
            console.log("已发送下载信息到本地客户端:", downloadData);
            
            // 显示通知（可选）
            chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon128.png',
                title: '下载已捕获',
                message: `文件 "${requestInfo.filename}" 正在被Hanabi下载管理器处理`
            });
            
            return true;
        } else {
            console.error("无法发送下载信息：WebSocket未连接");
            return false;
        }
    } catch (error) {
        console.error("发送下载信息时出错:", error);
        return false;
    }
}


// 启动 WebSocket 连接
connectWebSocket();

// 在扩展启动时检查禁用状态
chrome.storage.local.get(["shouldDisableExtension"], (result) => {
    shouldDisableExtension = result.shouldDisableExtension || false;
    console.log("插件禁用状态:", shouldDisableExtension);
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
});
