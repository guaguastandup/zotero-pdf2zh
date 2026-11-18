@echo off
chcp 936 >nul 2>&1
setlocal enabledelayedexpansion
title 停止 Zotero PDF2zh 翻译服务

set "PORT=8890"

echo(
echo  ==================================================
echo    停止 Zotero PDF2zh 翻译服务（端口 %PORT%）
echo  ==================================================
echo(

set "FOUND="
for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    if not "%%A"=="0" (
        set "FOUND=1"
        echo  [结束] 正在终止进程 PID %%A ...
        taskkill /PID %%A /F >nul 2>&1
        if errorlevel 1 (
            echo  [失败] 无法结束 PID %%A，可尝试以管理员身份运行本脚本。
        ) else (
            echo  [完成] PID %%A 已结束。
        )
    )
)

if not defined FOUND (
    echo  [提示] 没有发现监听 %PORT% 端口的服务，可能已经停止了。
)

echo(
echo  现在可以关闭这个窗口了。
echo(
pause
