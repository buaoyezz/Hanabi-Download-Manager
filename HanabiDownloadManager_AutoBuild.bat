@echo off
chcp 65001
echo 开始构建 Hanabi Download Manager...
echo.

REM 检查必要文件是否存在
if not exist "main.py" (
    echo 错误: 找不到 main.py 文件
    pause
    exit /b 1
)

if not exist "resources\logo2.png" (
    echo 错误: 找不到图标文件 resources\logo2.png
    pause
    exit /b 1
)

REM 检查关键目录是否存在
if not exist "client" (
    echo 错误: 找不到 client 目录
    pause
    exit /b 1
)

if not exist "core" (
    echo 错误: 找不到 core 目录
    pause
    exit /b 1
)

if not exist "connect" (
    echo 错误: 找不到 connect 目录
    pause
    exit /b 1
)

REM 检查Fluent Icons字体文件是否存在
if not exist "core\font\icons\FluentSystemIcons-Regular.ttf" (
    echo 警告: 找不到Fluent Icons字体文件，图标可能无法正常显示
)

REM 检查version.json是否存在，如果不存在则创建一个默认的
if not exist "version.json" (
    echo 警告: version.json 不存在，创建默认版本文件...
    echo {"version": "1.0.0", "build": "1"} > version.json
)

REM 检查客户端版本文件并读取版本号
set VERSION=1.0.0.0
if exist "client\version\VERSION" (
    echo 正在从VERSION文件读取版本号...
    for /f "tokens=3" %%i in ('findstr "VERSION =" client\version\VERSION') do (
        set VERSION=%%i
    )
    echo 检测到软件版本: %VERSION%
) else (
    echo 警告: 找不到 client\version\VERSION 文件，使用默认版本号: %VERSION%
)

echo 开始 Nuitka 编译...
echo.

python -m nuitka ^
  --standalone ^
  --windows-icon-from-ico=resources/logo2.png ^
  --output-dir=dist ^
  --output-filename=HanabiDownloadManager.exe ^
  --windows-console-mode=disable ^
  --enable-plugin=pyside6 ^
  --include-package=connect ^
  --include-package=client ^
  --include-package=core ^
  --include-package=crash_report ^
  --include-data-dir=resources=resources ^
  --include-data-dir=core/font=core/font ^
  --include-data-dir=core/config=core/config ^
  --include-data-dir=core/download_core/core=core/download_core/core ^
  --include-data-dir=client/I18N=client/I18N ^
  --include-data-dir=client/languages=client/languages ^
  --include-data-dir=client/ui=client/ui ^
  --include-data-dir=client/version=client/version ^
  --include-data-dir=hdm_chrome_extension=hdm_chrome_extension ^
  --include-data-files=version.json=version.json ^
  --include-data-files=requirements.txt=requirements.txt ^
  --include-data-files=README.md=README.md ^
  --include-data-files=README_EN.md=README_EN.md ^
  --include-data-files=DevDoc.md=DevDoc.md ^
  --include-data-files=clean_pycache.py=clean_pycache.py ^
  --include-data-files=json_maker.py=json_maker.py ^
  --follow-imports ^
  --prefer-source-code ^
  --jobs=%NUMBER_OF_PROCESSORS% ^
  --lto=yes ^
  --assume-yes-for-downloads ^
  --remove-output ^
  --show-progress ^
  --show-memory ^
  --report=compilation-report.xml ^
  --windows-company-name="ZZBuAoYe" ^
  --windows-product-name="Hanabi Download Manager" ^
  --windows-file-description="Hanabi Download Manager - Developed By ZZBuAoYe" ^
  --windows-file-version="%VERSION%.0" ^
  --windows-product-version="%VERSION%.0" ^
  --python-flag=no_site ^
  --python-flag=no_warnings ^
  --python-flag=no_asserts ^
  --disable-console ^
  main.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================
    echo √ 构建成功完成！
    echo ========================================
    echo 输出文件: dist\HanabiDownloadManager.exe
    echo 编译报告: compilation-report.xml
    echo.
    echo 包含的组件:
    echo  - 客户端界面 (client/*)
    echo    ├── I18N 国际化系统
    echo    ├── languages 语言包
    echo    ├── ui 用户界面
    echo    └── version 版本管理
    echo.
    echo  - 核心功能 (core/*)
    echo    ├── download_core 下载引擎
    echo    ├── config 配置管理
    echo    ├── font 字体图标
    echo    ├── animations 动画效果
    echo    ├── autoboot 自启动
    echo    ├── history 历史记录
    echo    ├── log 日志系统
    echo    ├── thread 线程管理
    echo    └── update 更新系统
    echo.
    echo  - 连接管理 (connect/*)
    echo    ├── download_manager 下载管理器
    echo    ├── tcp_server TCP服务器
    echo    ├── websocket_server WebSocket服务器
    echo    └── http_status_server HTTP状态服务器
    echo.
    echo  - 崩溃报告 (crash_report/*)
    echo  - Chrome扩展 (hdm_chrome_extension/*)
    echo  - 资源文件 (resources/*)
    echo.
    echo 构建完成时间: %date% %time%
    echo 应用程序版本: %VERSION%
    echo ========================================
    
    REM 检查生成的exe文件大小
    if exist "dist\HanabiDownloadManager.exe" (
        for %%A in ("dist\HanabiDownloadManager.exe") do (
            set size=%%~zA
            set /a sizeMB=!size!/1024/1024
            echo 生成的可执行文件大小: !sizeMB! MB
        )
    )
    
) else (
    echo ========================================
    echo × 构建失败，错误代码: %ERRORLEVEL%
    echo ========================================
    echo 请检查以下问题:
    echo  1. 确保所有依赖已正确安装 (pip install -r requirements.txt)
    echo  2. 确保 Nuitka 已正确安装 (pip install nuitka)
    echo  3. 检查源代码是否有语法错误
    echo  4. 确保所有必要的文件都存在
    echo  5. 检查 Python 路径是否正确
    echo  6. 确保有足够的磁盘空间进行编译
    echo ========================================
)

echo.
echo 按任意键退出...
pause