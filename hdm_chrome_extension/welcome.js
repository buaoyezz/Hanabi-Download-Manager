// 欢迎页面JavaScript

// 页面加载后执行
document.addEventListener('DOMContentLoaded', function() {
    const connectionStatus = document.getElementById('connection-status');
    const versionElement = document.getElementById('version');
    const checkConnectionButton = document.getElementById('checkConnection');
    const closeWindowButton = document.getElementById('closeWindow');
    
    // 获取后台页的状态和版本信息
    function checkConnection() {
        connectionStatus.textContent = "Checking connection status...";
        connectionStatus.className = "connection-status";
        
        // 从存储获取连接状态
        chrome.storage.local.get(['isConnected', 'ClientVersion', 'connectionError'], function(result) {
            if (result.isConnected) {
                connectionStatus.textContent = "Connected to Hanabi Download Manager";
                connectionStatus.className = "connection-status connected";
            } else {
                if (result.connectionError) {
                    connectionStatus.textContent = "Not connected: " + result.connectionError;
                } else {
                    connectionStatus.textContent = "Not connected to Hanabi Download Manager, please ensure the application is started";
                }
                connectionStatus.className = "connection-status disconnected";
                
                // 尝试重新连接
                chrome.runtime.sendMessage({action: "reconnect"});
            }
            
            // 显示版本信息
            if (result.ClientVersion) {
                versionElement.textContent = result.ClientVersion;
            } else {
                versionElement.textContent = "Unknown";
            }
        });
    }
    
    // 初始检查连接
    checkConnection();
    
    // 点击检查连接按钮
    checkConnectionButton.addEventListener('click', function() {
        // 先尝试重新连接
        chrome.runtime.sendMessage({action: "resetConnection"}, function(response) {
            // 等待一秒后检查连接状态
            setTimeout(checkConnection, 1000);
        });
    });
    
    // 点击关闭窗口按钮
    closeWindowButton.addEventListener('click', function() {
        window.close();
    });
    
    // 每5秒自动刷新一次连接状态
    setInterval(checkConnection, 5000);
});

// 监听来自后台的消息
chrome.runtime.onMessage.addListener(function(message, sender, sendResponse) {
    if (message.action === "connectionChanged") {
        // 当连接状态改变时更新UI
        const connectionStatus = document.getElementById('connection-status');
        if (connectionStatus) {
            if (message.isConnected) {
                connectionStatus.textContent = "Connected to Hanabi Download Manager";
                connectionStatus.className = "connection-status connected";
            } else {
                connectionStatus.textContent = "Not connected to Hanabi Download Manager, please ensure the application is started";
                connectionStatus.className = "connection-status disconnected";
            }
        }
    }
}); 