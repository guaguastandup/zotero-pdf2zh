@echo off
chcp 936 >nul 2>&1
setlocal enabledelayedexpansion
title Zotero PDF2zh 翻译服务 - 127.0.0.1:8890

rem ==========================================================
rem  可修改配置区（换电脑 / 换路径时只改这里）
rem ==========================================================
set "PROJECT_DIR=D:\Download\zotero-pdf2zh-main"
set "CONDA_ENV=zotero-pdf2zh-server"
set "PORT=8890"
set "HOST=127.0.0.1"
set "ENV_TOOL=conda"
set "ZOTERO_EXE=D:\APPs\zotero\zotero.exe"
set "LAUNCH_ZOTERO=1"
set "OPEN_BROWSER=1"
rem ==========================================================

set "SERVER_DIR=%PROJECT_DIR%\server"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%PROJECT_DIR%" 2>nul

echo(
echo  ==================================================
echo    Zotero PDF2zh 翻译服务 一键启动
echo  ==================================================
echo(

if not exist "%SERVER_DIR%\server.py" (
    echo  [错误] 找不到 server.py
    echo         期望路径: %SERVER_DIR%\server.py
    echo         请检查本脚本开头的 PROJECT_DIR 是否指向正确目录。
    goto :fail
)

rem ---------- 1. 端口检查：服务是否已在运行 ----------
set "RUNNING="
for /f "delims=" %%L in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do set "RUNNING=1"
if defined RUNNING (
    echo  [提示] 端口 %PORT% 已在监听，翻译服务可能已经在运行了。
    if "%OPEN_BROWSER%"=="1" start "" http://127.0.0.1:%PORT%
    echo         无需重复启动。若确认是残留进程，可先结束它：
    echo             netstat -ano ^| findstr :%PORT%
    echo             taskkill /PID 进程号 /F
    goto :done
)

rem ---------- 2. 定位 Python 解释器 ----------
set "PY="
set "CONDA_BASE=D:\Develop\Anaconda"
if exist "%CONDA_BASE%\envs\%CONDA_ENV%\python.exe" set "PY=%CONDA_BASE%\envs\%CONDA_ENV%\python.exe"

if not defined PY (
    for /f "delims=" %%B in ('conda info --base 2^>nul') do if not defined PY set "CONDA_BASE=%%B"
    if exist "!CONDA_BASE!\envs\%CONDA_ENV%\python.exe" set "PY=!CONDA_BASE!\envs\%CONDA_ENV%\python.exe"
)

if not defined PY (
    for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
)

if not defined PY (
    echo  [错误] 没有找到 Python。
    echo         请先安装 conda 环境 %CONDA_ENV%，或把 Python 加入 PATH，
    echo         然后修改脚本开头的 CONDA_ENV / CONDA_BASE。
    goto :fail
)

echo  [环境] Python: %PY%

rem ---------- 3. 检查 Server 自身依赖 ----------
"%PY%" -c "import importlib.util as u,sys;sys.exit(0 if all(u.find_spec(m) for m in ('flask','toml','pypdf','fitz','packaging')) else 1)" >nul 2>&1
if errorlevel 1 (
    echo  [提示] 当前环境缺少 Server 依赖，正在安装 requirements.txt ...
    "%PY%" -m pip install -r "%SERVER_DIR%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo  [错误] 依赖安装失败，请检查网络后重试。
        goto :fail
    )
    echo  [完成] 依赖安装完成。
)

rem ---------- 4. 顺带打开 Zotero（可选） ----------
if "%LAUNCH_ZOTERO%"=="1" (
    if exist "%ZOTERO_EXE%" (
        tasklist /FI "IMAGENAME eq zotero.exe" 2>nul | findstr /I "zotero.exe" >nul
        if errorlevel 1 (
            echo  [启动] 正在打开 Zotero ...
            start "" "%ZOTERO_EXE%"
        ) else (
            echo  [提示] Zotero 已在运行。
        )
    )
)

rem ---------- 5. 稍后自动打开服务页面（可选） ----------
if "%OPEN_BROWSER%"=="1" start "打开服务页面" /min cmd /c "timeout /t 8 >nul & start http://127.0.0.1:%PORT%"

echo(
echo  --------------------------------------------------
echo   服务地址: http://%HOST%:%PORT%
echo   翻译期间请勿关闭此窗口，按 Ctrl+C 可停止服务。
echo   首次翻译会自动创建/校验翻译环境，请耐心等待。
echo  --------------------------------------------------
echo(

rem ---------- 6. 启动服务 ----------
cd /d "%SERVER_DIR%"
"%PY%" server.py --host %HOST% --port %PORT% --env_tool %ENV_TOOL% %*
set "EXITCODE=%ERRORLEVEL%"

echo(
if "%EXITCODE%"=="0" (
    echo  [结束] 翻译服务已停止。
) else (
    echo  [错误] 翻译服务异常退出，退出码 %EXITCODE%
    echo         请把上方完整日志复制/截图后再排查问题。
)
goto :done

:fail
echo(
echo  启动未成功，请按上面的提示处理后重试。

:done
echo(
pause
