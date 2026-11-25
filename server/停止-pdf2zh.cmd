@echo off
setlocal EnableExtensions
chcp 65001 >nul
title PDF2zh Stop
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0utils\pdf2zh-service.ps1" -Action Stop %*
exit /b %errorlevel%
