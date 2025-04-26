// popup.js

// 获取状态元素和按钮
const statusText = document.getElementById("status-text");
const disableButton = document.getElementById("disable-button");
const enableButton = document.getElementById("enable-button");
const versionDiv = document.getElementById("version");

// 更新状态文本
function updateStatus() {
    chrome.storage.local.get(["isConnected", "connectionError"], (data) => {
        if (data.isConnected) {
            statusText.textContent = "连接成功";
            statusText.style.color = "#4CAF50"; // 绿色
            
            // 清除错误消息
            if (document.getElementById("error-message")) {
                document.getElementById("error-message").remove();
            }
            
            // 清除重试按钮
            if (document.getElementById("retry-button")) {
                document.getElementById("retry-button").remove();
            }
        } else {
            statusText.textContent = "连接已断开";
            statusText.style.color = "#F44336"; // 红色
            
            // 显示错误消息（如果有）
            if (data.connectionError && !document.getElementById("error-message")) {
                const errorDiv = document.createElement("div");
                errorDiv.id = "error-message";
                errorDiv.style.color = "#F44336";
                errorDiv.style.fontSize = "12px";
                errorDiv.style.marginTop = "5px";
                errorDiv.textContent = data.connectionError;
                versionDiv.parentNode.insertBefore(errorDiv, versionDiv);
                
                // 添加重试按钮
                if (!document.getElementById("retry-button")) {
                    const retryButton = document.createElement("button");
                    retryButton.id = "retry-button";
                    retryButton.textContent = "重试连接";
                    retryButton.style.marginTop = "10px";
                    retryButton.style.backgroundColor = "#2196F3"; // 蓝色
                    retryButton.onclick = retryConnection;
                    
                    errorDiv.parentNode.insertBefore(retryButton, errorDiv.nextSibling);
                }
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

// 重试连接
function retryConnection() {
    // 清除连接错误
    chrome.storage.local.remove("connectionError");
    
    // 发送消息给后台脚本，要求重置连接
    chrome.runtime.sendMessage({ action: "resetConnection" }, (response) => {
        console.log("重置连接请求已发送:", response);
        
        // 更新UI
        statusText.textContent = "正在重新连接...";
        statusText.style.color = "#FF9800"; // 黄色
        
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

// 添加禁用按钮点击事件监听器
disableButton.addEventListener("click", () => {
    chrome.storage.local.set({ shouldDisableExtension: true }, () => {
        console.log("插件已禁用");
        updateStatus();
    });
});

// 添加启用按钮点击事件监听器
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

// 监听存储变化
chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === 'local' && 
        (changes.isConnected || changes.shouldDisableExtension || changes.connectionError)) {
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
// 打印插件版本到插件页面
document.addEventListener('DOMContentLoaded', () => {

    const ExtensionVersion = chrome.runtime.getManifest().version;

    // 获取客户端版本和最新插件版本
    chrome.storage.local.get(["ClientVersion", "LatestExtensionVersion"], (result) => {
        const ClientVersion = result.ClientVersion || "Unknown";
        const LatestExtensionVersion = result.LatestExtensionVersion || "Unknown";
        // console.log(ExtensionVersion, ClientVersion, LatestExtensionVersion);

        if (isVersionNewer(LatestExtensionVersion, ExtensionVersion)) {
            document.getElementById('version').innerHTML = `插件版本: ${ExtensionVersion}&nbsp;&nbsp客户端版本: ${ClientVersion}<br/><span style="color: palevioletred;">插件有新版本，请前往客户端手动更新!</span>`;
        } else {
            document.getElementById('version').innerHTML = `插件版本: ${ExtensionVersion}&nbsp;&nbsp客户端版本: ${ClientVersion}`;
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

// 更新状态
updateStatus();

// 添加下载按钮点击事件监听器
document.getElementById('download-button').addEventListener('click', () => {
    const urlInput = document.getElementById('url-input');
    const url = urlInput.value.trim();
    
    if (!url) {
        alert('请输入有效的下载链接');
        return;
    }
    
    // 获取当前标签页URL作为referrer
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        const currentTab = tabs[0];
        const referrer = currentTab ? currentTab.url : '';
        
        // 从URL中提取文件名
        let filename = url.split('/').pop();
        if (filename.includes('?')) {
            filename = filename.split('?')[0];
        }
        
        // 准备下载信息
        const downloadInfo = {
            url: url,
            filename: filename,
            referrer: referrer
        };
        
        // 发送消息给后台脚本处理下载
        chrome.runtime.sendMessage({
            action: 'manualDownload',
            downloadInfo: downloadInfo
        }, (response) => {
            if (response && response.success) {
                urlInput.value = '';
                alert('下载任务已添加');
            } else {
                alert('添加下载任务失败：' + (response ? response.error : '未知错误'));
            }
        });
    });
});
