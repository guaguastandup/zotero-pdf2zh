param(
    [string]$ProjectRoot = "",
    [string]$OutputRoot = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-HostPython {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{
            Exe = $pythonCmd.Source
            PrefixArgs = @()
        }
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @{
            Exe = $pyCmd.Source
            PrefixArgs = @("-3")
        }
    }

    throw "Python launcher was not found. Install Python 3.12+ and ensure 'python' or 'py' is available in PATH."
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $ProjectRoot "build\windows"
}

$DistPath = Join-Path $OutputRoot "pyinstaller-dist"
$WorkPath = Join-Path $OutputRoot "pyinstaller-work"
$BuildVenv = Join-Path $OutputRoot ".build-venv"
$ServerScript = Join-Path $ProjectRoot "server\server.py"
$LauncherScript = Join-Path $ProjectRoot "server\packaging\windows\launcher.py"
$RequirementsFile = Join-Path $ProjectRoot "server\requirements.txt"
$ConfigSource = Join-Path $ProjectRoot "server\config"
$AppIcon = Join-Path $ProjectRoot "server\packaging\windows\assets\zotero-pdf2zh-server.ico"

if ($Clean -and (Test-Path $OutputRoot)) {
    Remove-Item -Path $OutputRoot -Recurse -Force
}

New-Item -Path $OutputRoot -ItemType Directory -Force | Out-Null
New-Item -Path $DistPath -ItemType Directory -Force | Out-Null
New-Item -Path $WorkPath -ItemType Directory -Force | Out-Null

if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
    Write-Host "Creating isolated build venv..."
    $HostPython = Resolve-HostPython
    $CreateVenvArgs = @()
    $CreateVenvArgs += $HostPython.PrefixArgs
    $CreateVenvArgs += @("-m", "venv", "$BuildVenv")
    & $HostPython.Exe @CreateVenvArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create build virtual environment."
    }
}

$BuildPython = Join-Path $BuildVenv "Scripts\python.exe"
if (-not (Test-Path $BuildPython)) {
    throw "Build Python not found in virtual environment: $BuildPython"
}
if (-not (Test-Path $AppIcon)) {
    throw "Application icon was not found: $AppIcon"
}

Push-Location $ProjectRoot
try {
    Write-Host "Installing isolated build dependencies..."
    & $BuildPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in build virtual environment."
    }
    & $BuildPython -m pip install --upgrade pyinstaller -r "$RequirementsFile"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install build dependencies into isolated virtual environment."
    }

    Write-Host "Building pdf2zh-server-core.exe (onedir)..."
    & $BuildPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name "pdf2zh-server-core" `
        --icon "$AppIcon" `
        --distpath "$DistPath" `
        --workpath "$WorkPath" `
        --specpath "$WorkPath" `
        --paths "server" `
        --add-data "$ConfigSource;config" `
        "$ServerScript"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed while building pdf2zh-server-core."
    }

    Write-Host "Building pdf2zh-server.exe launcher (onefile, no console)..."
    & $BuildPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --noconsole `
        --name "pdf2zh-server" `
        --icon "$AppIcon" `
        --distpath "$DistPath" `
        --workpath "$WorkPath" `
        --specpath "$WorkPath" `
        --hidden-import "tkinter" `
        --hidden-import "tkinter.scrolledtext" `
        "$LauncherScript"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed while building pdf2zh-server launcher."
    }

    $CoreExe = Join-Path $DistPath "pdf2zh-server-core\pdf2zh-server-core.exe"
    $LauncherExe = Join-Path $DistPath "pdf2zh-server.exe"

    if (-not (Test-Path $CoreExe)) {
        throw "Core executable was not generated: $CoreExe"
    }
    if (-not (Test-Path $LauncherExe)) {
        throw "Launcher executable was not generated: $LauncherExe"
    }

    Write-Host "Build output ready:"
    Write-Host "  Core:      $CoreExe"
    Write-Host "  Launcher:  $LauncherExe"
}
finally {
    Pop-Location
}
