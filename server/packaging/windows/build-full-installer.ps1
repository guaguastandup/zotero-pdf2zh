param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$EngineSha256,
    [string]$ProjectRoot = "",
    [string]$OutputRoot = "",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $ProjectRoot "build\windows"
}

Push-Location $ProjectRoot
try {
    ./server/packaging/windows/build-server-core.ps1 -ProjectRoot $ProjectRoot -OutputRoot $OutputRoot -Clean:$Clean
    ./server/packaging/windows/assemble-full.ps1 -ProjectRoot $ProjectRoot -OutputRoot $OutputRoot -EngineSha256 $EngineSha256

    $stageRoot = (Resolve-Path (Join-Path $OutputRoot "full-stage")).Path
    $installerOutput = Join-Path $OutputRoot "installer-output"
    New-Item -Path $installerOutput -ItemType Directory -Force | Out-Null

    $isccCandidates = @(
        $env:ISCC,
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    $iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        $isccCmd = Get-Command iscc -ErrorAction SilentlyContinue
        if ($isccCmd) {
            $iscc = $isccCmd.Source
        }
    }
    if (-not $iscc) {
        throw "ISCC.exe was not found. Install Inno Setup 6 or set env:ISCC to the compiler path."
    }

    & $iscc `
        "/DMyAppVersion=$Version" `
        "/DStageRoot=$stageRoot" `
        "/DOutputDir=$installerOutput" `
        "server/packaging/windows/installer.iss"

    Write-Host "Installer build completed:"
    Get-ChildItem -Path $installerOutput -Filter "*.exe" | ForEach-Object {
        Write-Host "  $($_.FullName)"
    }
}
finally {
    Pop-Location
}
