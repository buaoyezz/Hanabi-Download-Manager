@echo off
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

REM 检查version.json是否存在，不存在则创建一个默认的
if not exist "version.json" (
    echo 警告: version.json 不存在，创建默认版本文件...
    echo {"version": "1.0.0", "build": "1"} > version.json
)

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
  --include-data-dir=core/download_core/core=core/download_core/core ^
  --include-data-dir=hdm_chrome_extension=hdm_chrome_extension ^
  --include-data-files=version.json=version.json ^
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
  --windows-file-description="HDM A Download Manager" ^
  --windows-file-version="1.0.0.0" ^
  --windows-product-version="1.0.0.0" ^
  --python-flag=no_site ^
  --python-flag=no_warnings ^
  --python-flag=no_asserts ^
  main.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo ? 构建成功完成！
    echo 输出文件: dist\HanabiDownloadManager.exe
    echo 构建报告: compilation-report.xml
) else (
    echo ? 构建失败，错误代码: %ERRORLEVEL%
)
pause