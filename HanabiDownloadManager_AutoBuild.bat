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

REM 检查Fluent Icons字体文件是否存在
if not exist "core\font\icons\FluentSystemIcons-Regular.ttf" (
    echo 警告: 找不到Fluent Icons字体文件，图标可能无法正常显示
    pause
)

REM 检查version.json是否存在，如果不存在则创建一个默认的
if not exist "version.json" (
    echo 警告: version.json 不存在，创建默认版本文件...
    echo {"version": "1.0.0", "build": "1"} > version.json
)

REM 检查客户端版本文件
if not exist "client\version\VERSION" (
    echo 警告: 找不到 client\version\VERSION 文件
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
  --enable-plugin=upx ^
  --include-package-data=connect,client,core,hdm_chrome_extension ^
  --include-data-dir=resources=resources ^
  --include-data-dir=core/font=core/font ^
  --include-data-dir=core/font/icons=core/font/icons ^
  --include-data-dir=core/font/font=core/font/font ^
  --include-data-dir=core/download_core/core=core/download_core/core ^
  --include-data-dir=core/config=core/config ^
  --include-data-dir=core/animations=core/animations ^
  --include-data-dir=core/autoboot=core/autoboot ^
  --include-data-dir=core/history=core/history ^
  --include-data-dir=core/i18n=core/i18n ^
  --include-data-dir=core/log=core/log ^
  --include-data-dir=core/page_manager=core/page_manager ^
  --include-data-dir=core/thread=core/thread ^
  --include-data-dir=core/update=core/update ^
  --include-data-dir=client/I18N=client/I18N ^
  --include-data-dir=client/languages=client/languages ^
  --include-data-dir=client/ui=client/ui ^
  --include-data-dir=client/version=client/version ^
  --include-data-dir=hdm_chrome_extension=hdm_chrome_extension ^
  --include-data-dir=connect=connect ^
  --include-data-files=version.json=version.json ^
  --include-data-files=requirements.txt=requirements.txt ^
  --include-data-files=README.md=README.md ^
  --include-data-files=README_EN.md=README_EN.md ^
  --include-data-files=DevDoc.md=DevDoc.md ^
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
  --windows-file-description="Hanabi Download Manager - Advanced Download Tool" ^
  --windows-file-version="1.0.0.0" ^
  --windows-product-version="1.0.0.0" ^
  --python-flag=no_site ^
  --python-flag=no_warnings ^
  --python-flag=no_asserts ^
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
    echo  - 核心下载引擎 (core/download_core)
    echo  - 用户界面 (client/ui)
    echo  - 国际化支持 (client/I18N, client/languages)
    echo  - 字体和图标 (core/font)
    echo  - Chrome扩展 (hdm_chrome_extension)
    echo  - 连接管理 (connect)
    echo  - 配置和日志 (core/config, core/log)
    echo  - 版本管理 (client/version)
    echo.
    echo 构建完成时间: %date% %time%
    echo ========================================
) else (
    echo ========================================
    echo × 构建失败，错误代码: %ERRORLEVEL%
    echo ========================================
    echo 请检查以下问题:
    echo  1. 确保所有依赖已正确安装 (pip install -r requirements.txt)
    echo  2. 确保 Nuitka 已正确安装 (pip install nuitka)
    echo  3. 检查源代码是否有语法错误
    echo  4. 确保所有必要的文件都存在
    echo ========================================
)

echo.
echo 按任意键退出...
pause