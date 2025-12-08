@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

goto :main

:: ========= 日志子程序 =========
:log
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "NOW=%%t"
echo [!NOW!] %*
exit /b

:: ========= 参数解析子程序 =========
:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="--no-mirror" set "USE_MIRROR=0" & shift & goto parse
if /I "%~1"=="--warmup"    set "RUN_WARMUP=1" & shift & goto parse
if /I "%~1"=="--upgrade"   set "UPGRADE=1"    & shift & goto parse
call :log ❌ 未知参数: %~1
exit /b 1
:after_parse
exit /b 0

:: ========= 重试安装（conda run + pip） =========
:install_with_retry
rem %1=ENV_NAME（仅用于日志），包列表取自 INSTALL_PACKAGES
setlocal EnableDelayedExpansion
set "ENV_NAME=%~1"
set /a MAX=3
set /a ATTEMPT=1
:retry_loop
call :log 正在为 %ENV_NAME% 安装依赖（第!ATTEMPT!次）...
call conda run -n "%ENV_NAME%" python -m pip install !INSTALL_PACKAGES! %INDEX_OPT%
if errorlevel 1 (
  if !ATTEMPT! geq !MAX! (
    call :log ❌ 安装失败，已达到最大重试次数 !MAX!。
    endlocal & exit /b 1
  ) else (
    call :log 安装失败，3 秒后重试...
    timeout /t 3 /nobreak >nul
    set /a ATTEMPT+=1
    goto :retry_loop
  )
) else (
  call :log 依赖项安装成功！
)
endlocal & exit /b 0

:: ========= 运行 babeldoc --warmup =========
:run_babeldoc_warmup
set "ENV_NAME=%~1"
call :log 运行 babeldoc --warmup（%ENV_NAME%）...
call conda run -n "%ENV_NAME%" babeldoc --warmup
if errorlevel 1 (call :log ❌ babeldoc --warmup 执行失败。& exit /b 1)
call :log babeldoc --warmup 执行成功！
exit /b 0

:: ========= 升级 pdf2zh_next =========
:upgrade_pdf2zh_next
set "ENV_NAME=%~1"
call :log 升级 pdf2zh_next（%ENV_NAME%）...
call conda run -n "%ENV_NAME%" python -m pip install --upgrade pdf2zh_next %INDEX_OPT%
if errorlevel 1 (call :log ❌ pdf2zh_next 升级失败。& exit /b 1)
call :log pdf2zh_next 升级成功！
exit /b 0

:: ========= 创建 Conda 环境并安装 =========
:create_conda_env
rem 依赖包来自 CUR_PACKAGES
set "ENV_NAME=%~1"
set "PYVER=%~2"

call :log 为 %ENV_NAME% 创建 Conda 环境（Python %PYVER%）...
call conda create -n "%ENV_NAME%" python="%PYVER%" -y
if errorlevel 1 (call :log ❌ 创建环境失败。& exit /b 1)

set "INSTALL_PACKAGES=%CUR_PACKAGES%"
call :install_with_retry "%ENV_NAME%" || exit /b 1

echo %CUR_PACKAGES% | find /i "babeldoc" >nul
if %errorlevel%==0 if "%RUN_WARMUP%"=="1" if "%ENV_NAME%"=="zotero-pdf2zh-next-venv" (
  call :run_babeldoc_warmup "%ENV_NAME%" || exit /b 1
) else (
  call :log "skip babeldoc --warmup"（RUN_WARMUP=%RUN_WARMUP%, ENV_NAME=%ENV_NAME%, babeldoc in packages=%CUR_PACKAGES%）
)

echo %CUR_PACKAGES% | find /i "pdf2zh_next" >nul
if %errorlevel%==0 if "%UPGRADE%"=="1" call :upgrade_pdf2zh_next "%ENV_NAME%" || exit /b 1

exit /b 0

:: ========= 主流程 =========
:main
rem ---- 配置 ----
set "PY_VER=3.12"
set "ENV1=zotero-pdf2zh-venv"
set "ENV2=zotero-pdf2zh-next-venv"
set "PACKAGES1=pdf2zh==1.9.11 pypdf PyMuPDF flask numpy==2.2.0 toml pdfminer.six==20250416 packaging"
set "PACKAGES2=pdf2zh_next pypdf PyMuPDF flask toml babeldoc packaging"

rem ---- 默认参数 ----
set "USE_MIRROR=1"
set "RUN_WARMUP=0"
set "UPGRADE=0"

call :log 接收到的命令行参数: %*
call :parse %* || exit /b 1

if "%USE_MIRROR%"=="1" (set "INDEX_OPT=--index-url https://pypi.tuna.tsinghua.edu.cn/simple") else (set "INDEX_OPT=")

call :log 检查 Conda 是否已安装...
where conda >nul 2>&1 || (call :log "❌ Conda 未安装。请安装 Miniconda/Anaconda 并确保 conda 在 PATH 中（或先运行 `conda init cmd.exe` 后重开终端）。" & exit /b 1)
call :log Conda 已安装。

set "CUR_PACKAGES=%PACKAGES1%"
call :create_conda_env "%ENV1%" "%PY_VER%" || exit /b 1

set "CUR_PACKAGES=%PACKAGES2%"
call :create_conda_env "%ENV2%" "%PY_VER%" || exit /b 1

call :log Conda 环境创建并安装完成！
exit /b 0
