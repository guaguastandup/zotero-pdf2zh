@echo off
setlocal EnableExtensions
chcp 65001 >nul
title PDF2zh Start
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0utils\pdf2zh-service.ps1" -Action Start %*
exit /b %errorlevel%
