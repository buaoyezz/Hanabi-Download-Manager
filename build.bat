@echo off
echo ��ʼ���� Hanabi Download Manager...
echo.

REM ����Ҫ�ļ��Ƿ����
if not exist "main.py" (
    echo ����: �Ҳ��� main.py �ļ�
    pause
    exit /b 1
)

if not exist "resources\logo2.png" (
    echo ����: �Ҳ���ͼ���ļ� resources\logo2.png
    pause
    exit /b 1
)

REM ���version.json�Ƿ���ڣ��������򴴽�һ��Ĭ�ϵ�
if not exist "version.json" (
    echo ����: version.json �����ڣ�����Ĭ�ϰ汾�ļ�...
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
    echo ? �����ɹ���ɣ�
    echo ����ļ�: dist\HanabiDownloadManager.exe
    echo ��������: compilation-report.xml
) else (
    echo ? ����ʧ�ܣ��������: %ERRORLEVEL%
)
pause