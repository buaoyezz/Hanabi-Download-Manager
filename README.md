# Hanabi Download Manager

Hanabi Download Manager 是一个高效多线程下载管理器，支持断点续传、智能线程管理和下载限速功能。

## 核心特性

- **多线程下载**：动态分配线程，最大化下载速度
- **断点续传**：支持意外中断后继续下载
- **智能线程管理**：根据网络状况自动调整线程数
- **下载速度限制**：可自定义下载带宽限制
- **代理支持**：支持系统代理或自定义代理

## 项目结构

```
HanabiDownloadManager/
├── core/
│   ├── config/         # 基础配置模块
│   │   ├── __init__.py
│   │   └── config.py
│   └── download_core/  # 下载核心模块
│       ├── __init__.py
│       ├── download_kernel.py # 下载内核实现
│       ├── core/       # 核心工具
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── methods.py
│       └── tests/      # 单元测试
│           └── test_download.py
```

## 主要组件

### `TransferManager` 类

下载任务的核心管理器。主要职责包括：

- 初始化下载任务
- 管理下载线程
- 处理断点续传
- 监控下载进度
- 发射进度和速度信号

### `DownloadSegment` 类

表示一个下载分段，包含：

- 起始位置
- 结束位置
- 当前进度
- 会话对象

## 技术细节

- 使用 Python 3.13 开发
- 依赖 PySide6 提供 UI 框架
- 使用 requests 库处理 HTTP 请求
- 使用线程池进行并发下载
- 支持稀疏文件创建，预分配文件空间

## 使用示例

```python
from core.download_core import TransferManager

# 创建下载管理器
transfer = TransferManager(
    url="https://example.com/large-file.zip",
    headers={"User-Agent": "MyDownloader/1.0"},
    maxThreads=8,
    savePath="/downloads",
    dynamicThreads=True
)

# 连接信号
transfer.segmentProgressChanged.connect(on_progress_changed)
transfer.transferSpeedChanged.connect(on_speed_changed)
transfer.downloadComplete.connect(on_download_complete)
transfer.errorOccurred.connect(on_error)

# 开始下载
transfer.start()
```

## 开发者教程
查看[DevDoc](./DevDoc.md)了解项目结构
UI控件样式采用部分[ClutUI-NG]([buaoyezz/ClutUI-Nextgen: The ClutUI's Next Generation](https://github.com/buaoyezz/ClutUI-Nextgen))

