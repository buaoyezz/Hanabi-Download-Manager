// popup.js

// 获取状态元素和按钮
const disableButton = document.getElementById("disable-button");
const enableButton = document.getElementById("enable-button");
const versionDiv = document.getElementById("version");
const clientStatusIndicator = document.getElementById("client-status-indicator");
const clientStatusText = document.getElementById("client-status-text");
const queueCount = document.getElementById("queue-count");
const extensionStatusIndicator = document.getElementById("extension-status-indicator");
const extensionStatusText = document.getElementById("extension-status-text");
const viewQueueBtn = document.getElementById("view-queue-btn");
const clearQueueBtn = document.getElementById("clear-queue-btn");
const queueList = document.getElementById("queue-list");

// 存储队列数据
let pendingDownloadsData = [];

// 更新状态文本
function updateStatus() {
    chrome.storage.local.get(["isConnected", "connectionError", "clientStatus", "pendingDownloads", "shouldDisableExtension"], (data) => {
        // 更新客户端状态
        updateClientStatus(data.clientStatus || "offline", data.isConnected);
        
        // 更新队列信息
        pendingDownloadsData = data.pendingDownloads || [];
        updateQueueInfo(pendingDownloadsData);
        
        // 更新插件启用状态
        updateExtensionStatus(!data.shouldDisableExtension);
        
        // 显示错误消息（如果有）
        if (!data.isConnected && data.connectionError && !document.getElementById("error-message")) {
            const errorDiv = document.createElement("div");
            errorDiv.id = "error-message";
            errorDiv.style.color = "#ff6e7f";
            errorDiv.style.fontSize = "12px";
            errorDiv.style.marginTop = "5px";
            errorDiv.textContent = data.connectionError;
            versionDiv.parentNode.insertBefore(errorDiv, versionDiv);
            
            // 添加重试按钮
            if (!document.getElementById("retry-button")) {
                const retryButton = document.createElement("button");
                retryButton.id = "retry-button";
                retryButton.className = "btn";
                retryButton.innerHTML = '<i class="material-icons">refresh</i>重试连接';
                retryButton.style.marginTop = "10px";
                retryButton.style.marginBottom = "10px";
                retryButton.onclick = retryConnection;
                
                errorDiv.parentNode.insertBefore(retryButton, errorDiv.nextSibling);
            }
        } else if (data.isConnected) {
            // 清除错误消息
            if (document.getElementById("error-message")) {
                document.getElementById("error-message").remove();
            }
            
            // 清除重试按钮
            if (document.getElementById("retry-button")) {
                document.getElementById("retry-button").remove();
            }
        }
    });

    // 检查禁用状态
    chrome.storage.local.get("shouldDisableExtension", (result) => {
        if (result.shouldDisableExtension) {
            disableButton.style.display = "none";
            enableButton.style.display = "block";
        } else {
            disableButton.style.display = "block";
            enableButton.style.display = "none";
        }
    });
}

// 更新客户端状态指示器
function updateClientStatus(status, isConnected) {
    if (status === "online" && isConnected) {
        clientStatusIndicator.className = "status-indicator status-online";
        clientStatusText.textContent = "已连接";
    } else if (isConnected === false) {
        clientStatusIndicator.className = "status-indicator status-offline";
        clientStatusText.textContent = "未连接";
    } else {
        clientStatusIndicator.className = "status-indicator status-checking";
        clientStatusText.textContent = "检测中...";
    }
}

// 更新插件启用状态
function updateExtensionStatus(isEnabled) {
    if (isEnabled) {
        extensionStatusIndicator.className = "status-indicator status-online";
        extensionStatusText.textContent = "已启用";
    } else {
        extensionStatusIndicator.className = "status-indicator status-offline";
        extensionStatusText.textContent = "已禁用";
    }
}

// 更新下载队列信息
function updateQueueInfo(pendingDownloads) {
    const count = Array.isArray(pendingDownloads) ? pendingDownloads.length : 0;
    queueCount.textContent = count.toString();
    
    // 可以根据队列长度添加特殊效果
    if (count > 0) {
        queueCount.style.color = "#ffffff";
        clearQueueBtn.disabled = false;
        clearQueueBtn.style.opacity = "1";
    } else {
        queueCount.style.color = "#ffffff";
        clearQueueBtn.disabled = true;
        clearQueueBtn.style.opacity = "0.5";
    }
    
    // 更新队列列表
    updateQueueList(pendingDownloads);
}

// 更新队列列表
function updateQueueList(pendingDownloads) {
    // 清空现有列表
    queueList.innerHTML = '';
    
    if (!Array.isArray(pendingDownloads) || pendingDownloads.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'queue-empty';
        emptyMsg.textContent = '队列为空';
        queueList.appendChild(emptyMsg);
        return;
    }
    
    // 添加任务项
    pendingDownloads.forEach((download, index) => {
        const item = document.createElement('div');
        item.className = 'queue-item';
        
        const name = document.createElement('div');
        name.className = 'queue-item-name';
        
        // 获取文件名
        let fileName = '下载任务 #' + (index + 1);
        if (download && download.url) {
            try {
                // 尝试从URL中提取文件名
                const url = new URL(download.url);
                const pathParts = url.pathname.split('/');
                const lastPart = pathParts[pathParts.length - 1];
                if (lastPart && lastPart.trim() !== '') {
                    fileName = decodeURIComponent(lastPart);
                }
            } catch (e) {
                console.error('URL解析错误:', e);
            }
        }
        
        name.textContent = fileName;
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'queue-item-remove';
        removeBtn.innerHTML = '<i class="material-icons">close</i>';
        removeBtn.setAttribute('data-index', index);
        removeBtn.addEventListener('click', function(e) {
            e.stopPropagation(); // 防止触发父元素的事件
            removeQueueItem(index);
        });
        
        item.appendChild(name);
        item.appendChild(removeBtn);
        queueList.appendChild(item);
    });
}

// 移除队列中的单个项目
function removeQueueItem(index) {
    if (index >= 0 && index < pendingDownloadsData.length) {
        const newQueue = [...pendingDownloadsData];
        newQueue.splice(index, 1);
        
        // 保存到存储
        chrome.storage.local.set({ pendingDownloads: newQueue }, () => {
            pendingDownloadsData = newQueue;
            updateQueueInfo(newQueue);
            
            // 通知后台脚本队列已更新
            chrome.runtime.sendMessage({ action: "queueUpdated", pendingDownloads: newQueue });
        });
    }
}

// 清空整个队列
function clearQueue() {
    chrome.storage.local.set({ pendingDownloads: [] }, () => {
        pendingDownloadsData = [];
        updateQueueInfo([]);
        
        // 通知后台脚本队列已清空
        chrome.runtime.sendMessage({ action: "queueUpdated", pendingDownloads: [] });
    });
}

// 重试连接
function retryConnection() {
    // 清除连接错误
    chrome.storage.local.remove("connectionError");
    
    // 发送消息给后台脚本，要求重置连接
    chrome.runtime.sendMessage({ action: "resetConnection" }, (response) => {
        console.log("重置连接请求已发送:", response);
        
        // 更新客户端状态为检测中
        clientStatusIndicator.className = "status-indicator status-checking";
        clientStatusText.textContent = "检测中...";
        
        // 移除重试按钮
        if (document.getElementById("retry-button")) {
            document.getElementById("retry-button").remove();
        }
        
        // 移除错误消息
        if (document.getElementById("error-message")) {
            document.getElementById("error-message").remove();
        }
    });
}

// 切换队列列表显示/隐藏
function toggleQueueList() {
    queueList.classList.toggle('show');
    if (queueList.classList.contains('show')) {
        viewQueueBtn.innerHTML = '<i class="material-icons">visibility_off</i>隐藏';
    } else {
        viewQueueBtn.innerHTML = '<i class="material-icons">list</i>查看';
    }
}

// 添加按钮事件监听器
disableButton.addEventListener("click", () => {
    chrome.storage.local.set({ shouldDisableExtension: true }, () => {
        console.log("插件已禁用");
        updateStatus();
    });
});

enableButton.addEventListener("click", () => {
    chrome.storage.local.set({ shouldDisableExtension: false }, () => {
        console.log("插件已启用");
        updateStatus();
        
        // 重新连接
        chrome.runtime.sendMessage({ action: "reconnect" }, (response) => {
            console.log("重新连接请求已发送:", response);
        });
    });
});

// 查看队列按钮点击事件
viewQueueBtn.addEventListener("click", toggleQueueList);

// 清空队列按钮点击事件
clearQueueBtn.addEventListener("click", function() {
    if (confirm('确定要清空所有下载任务吗？')) {
        clearQueue();
    }
});

// 监听存储变化
chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === 'local' && 
        (changes.isConnected || changes.shouldDisableExtension || 
         changes.connectionError || changes.clientStatus || changes.pendingDownloads)) {
        updateStatus(); // 当相关状态发生变化时，更新状态
    }
});

function isVersionNewer(v1, v2) {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
        const num1 = parts1[i] || 0;
        const num2 = parts2[i] || 0;
        if (num1 !== num2) {
            return num1 > num2; // 如果 v1 更新，返回 true
        }
    }
    return false;
}

// 打印插件版本到插件页面
document.addEventListener('DOMContentLoaded', () => {
    const ExtensionVersion = chrome.runtime.getManifest().version;

    // 获取客户端版本和最新插件版本
    chrome.storage.local.get(["ClientVersion", "LatestExtensionVersion"], (result) => {
        const ClientVersion = result.ClientVersion || "Unknown";
        const LatestExtensionVersion = result.LatestExtensionVersion || "Unknown";

        if (isVersionNewer(LatestExtensionVersion, ExtensionVersion)) {
            document.getElementById('version').innerHTML = `插件版本: ${ExtensionVersion} 客户端版本: ${ClientVersion}<br/><span style="color: #ff6e7f;">插件有新版本可用!</span>`;
        } else {
            document.getElementById('version').innerHTML = `插件版本: ${ExtensionVersion} 客户端版本: ${ClientVersion}`;
        }
    });

    // 检测系统颜色模式并在初始时设置
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.body.classList.add('dark-mode');
    }
});

// 添加检测系统颜色模式变化的事件监听器
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
    document.body.classList.toggle('dark-mode', event.matches);
});

// 模拟数据变化（仅用于测试）
function simulateDataChanges() {
    // 随机客户端状态
    const clientStatus = Math.random() > 0.5 ? "online" : "offline";
    const isConnected = clientStatus === "online";
    
    // 随机队列数据
    const queueSize = Math.floor(Math.random() * 5);
    const pendingDownloads = Array(queueSize).fill(null).map((_, i) => ({
        url: `https://example.com/file${i + 1}.zip`,
        fileName: `示例文件${i + 1}.zip`,
        id: `task_${Date.now()}_${i}`
    }));
    
    // 存储数据
    chrome.storage.local.set({
        clientStatus: clientStatus,
        isConnected: isConnected,
        pendingDownloads: pendingDownloads
    });
    
    console.log("模拟数据已更新:", { clientStatus, isConnected, queueSize });
}

// 每5秒模拟数据变化（仅在开发环境使用）
const isDevelopment = false; // 设置为true可启用模拟数据
if (isDevelopment) {
    setInterval(simulateDataChanges, 5000);
    simulateDataChanges(); // 立即执行一次
}

// 更新状态
updateStatus();
