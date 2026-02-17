param(
    [string]$ProjectRoot = "",
    [string]$OutputRoot = "",
    [string]$ManifestPath = "",
    [string]$EngineSha256 = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Download-File {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$OutFile
    )
    $maxAttempts = 5
    $tempFile = "$OutFile.part"
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue

    if ($curl) {
        if (Test-Path $tempFile) {
            Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
        }

        Write-Host "Downloading with curl: $Url"
        & $curl.Source `
            --fail `
            --location `
            --retry 5 `
            --retry-delay 5 `
            --retry-all-errors `
            --output $tempFile `
            $Url

        if ($LASTEXITCODE -eq 0 -and (Test-Path $tempFile) -and (Get-Item $tempFile).Length -gt 0) {
            Move-Item -Path $tempFile -Destination $OutFile -Force
            return
        }

        Write-Warning "curl download failed, falling back to Invoke-WebRequest retry loop."
        if (Test-Path $tempFile) {
            Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
        }
    }

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            if (Test-Path $tempFile) {
                Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
            }

            Write-Host "Downloading (attempt $attempt/$maxAttempts): $Url"
            Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $tempFile

            if (-not (Test-Path $tempFile)) {
                throw "Download did not produce a file: $tempFile"
            }

            if ((Get-Item $tempFile).Length -le 0) {
                throw "Downloaded file is empty: $tempFile"
            }

            Move-Item -Path $tempFile -Destination $OutFile -Force
            return
        }
        catch {
            Write-Warning "Download failed on attempt $attempt/${maxAttempts}: $($_.Exception.Message)"
            if (Test-Path $tempFile) {
                Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
            }

            if ($attempt -eq $maxAttempts) {
                throw
            }

            Start-Sleep -Seconds (5 * $attempt)
        }
    }
}

function Ensure-ValidSha256 {
    param([string]$Value)
    return $Value -and $Value -notmatch "REPLACE_WITH_ACTUAL_SHA256" -and $Value.Length -eq 64
}

function ConvertTo-PythonLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    $escaped = $Value.Replace('\', '\\').Replace("'", "\\'")
    return "'$escaped'"
}

function Invoke-EnginePython {
    param(
        [Parameter(Mandatory = $true)][string]$EnginePython,
        [Parameter(Mandatory = $true)][string]$Code
    )
    $previousErrorActionPreference = $ErrorActionPreference
    $output = ""
    $exitCode = 0
    try {
        $ErrorActionPreference = "Continue"
        $output = (& $EnginePython -c $Code 2>&1 | ForEach-Object { $_.ToString() } | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return @{
        ExitCode = $exitCode
        Output = $output
    }
}

function Test-EngineModuleImport {
    param(
        [Parameter(Mandatory = $true)][string]$EnginePython,
        [Parameter(Mandatory = $true)][string]$EngineSitePackages,
        [Parameter(Mandatory = $true)][string]$ModuleName
    )
    $engineSitePackagesLiteral = ConvertTo-PythonLiteral -Value $EngineSitePackages
    $moduleNameLiteral = ConvertTo-PythonLiteral -Value $ModuleName
    $code = @"
import importlib
import sys
sys.path.insert(0, $engineSitePackagesLiteral)
importlib.import_module($moduleNameLiteral)
"@
    $result = Invoke-EnginePython -EnginePython $EnginePython -Code $code
    return @{
        Success = $result.ExitCode -eq 0
        Output = $result.Output
    }
}

function Ensure-EnginePip {
    param(
        [Parameter(Mandatory = $true)][string]$EngineRoot,
        [Parameter(Mandatory = $true)][string]$CacheRoot
    )
    $EnginePython = Join-Path $EngineRoot "runtime\python.exe"
    if (-not (Test-Path $EnginePython)) {
        throw "Engine python runtime was not found: $EnginePython"
    }

    $RuntimeSitePackages = Join-Path $EngineRoot "runtime\Lib\site-packages"
    $runtimeSitePackagesLiteral = ConvertTo-PythonLiteral -Value $RuntimeSitePackages
    $pipCheckCode = @"
import sys
sys.path.insert(0, $runtimeSitePackagesLiteral)
import pip
"@
    $pipCheckResult = Invoke-EnginePython -EnginePython $EnginePython -Code $pipCheckCode
    if ($pipCheckResult.ExitCode -eq 0) {
        return @{
            EnginePython = $EnginePython
            RuntimeSitePackages = $RuntimeSitePackages
        }
    }

    $GetPipScript = Join-Path $CacheRoot "get-pip.py"
    if (-not (Test-Path $GetPipScript)) {
        Download-File -Url "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPipScript
    }

    Write-Host "Bootstrapping pip into engine runtime..."
    $previousErrorActionPreference = $ErrorActionPreference
    $bootstrapOutput = ""
    $bootstrapExitCode = 0
    try {
        $ErrorActionPreference = "Continue"
        $bootstrapOutput = (& $EnginePython $GetPipScript 2>&1 | ForEach-Object { $_.ToString() } | Out-String)
        $bootstrapExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($bootstrapExitCode -ne 0) {
        $bootstrapDetails = $bootstrapOutput.Trim()
        throw "Failed to bootstrap pip for engine runtime. exit_code=$bootstrapExitCode`n$bootstrapDetails"
    }

    $pipCheckAfterBootstrap = Invoke-EnginePython -EnginePython $EnginePython -Code $pipCheckCode
    if ($pipCheckAfterBootstrap.ExitCode -ne 0) {
        $details = $pipCheckAfterBootstrap.Output.Trim()
        throw "pip is still unavailable in engine runtime after bootstrap. details: $details"
    }

    return @{
        EnginePython = $EnginePython
        RuntimeSitePackages = $RuntimeSitePackages
    }
}

function Invoke-EnginePip {
    param(
        [Parameter(Mandatory = $true)][string]$EnginePython,
        [Parameter(Mandatory = $true)][string]$RuntimeSitePackages,
        [Parameter(Mandatory = $true)][string[]]$PipArgs
    )
    $runtimeSitePackagesLiteral = ConvertTo-PythonLiteral -Value $RuntimeSitePackages
    $pipCode = @"
import json
import os
import sys
sys.path.insert(0, $runtimeSitePackagesLiteral)
from pip._internal.cli.main import main
args = json.loads(os.environ['PDF2ZH_PIP_ARGS_JSON'])
raise SystemExit(main(args))
"@
    $exitCode = 0
    $output = ""
    $previousErrorActionPreference = $ErrorActionPreference
    $env:PDF2ZH_PIP_ARGS_JSON = ($PipArgs | ConvertTo-Json -Compress)
    try {
        $ErrorActionPreference = "Continue"
        $output = (& $EnginePython -c $pipCode 2>&1 | ForEach-Object { $_.ToString() } | Out-String)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item Env:PDF2ZH_PIP_ARGS_JSON -ErrorAction SilentlyContinue
    }

    return @{
        ExitCode = $exitCode
        Output = $output
    }
}

function Install-EnginePackage {
    param(
        [Parameter(Mandatory = $true)][string]$EnginePython,
        [Parameter(Mandatory = $true)][string]$RuntimeSitePackages,
        [Parameter(Mandatory = $true)][string]$EngineSitePackages,
        [Parameter(Mandatory = $true)][string]$PackageSpec,
        [Parameter(Mandatory = $true)][string]$WheelCacheRoot
    )
    if (-not (Test-Path $WheelCacheRoot)) {
        New-Item -Path $WheelCacheRoot -ItemType Directory -Force | Out-Null
    }

    $offlineInstallArgs = @(
        "install",
        "--upgrade",
        "--only-binary=:all:",
        "--target",
        $EngineSitePackages,
        "--no-index",
        "--find-links",
        $WheelCacheRoot,
        $PackageSpec
    )
    $offlineResult = Invoke-EnginePip `
        -EnginePython $EnginePython `
        -RuntimeSitePackages $RuntimeSitePackages `
        -PipArgs $offlineInstallArgs
    if ($offlineResult.ExitCode -eq 0) {
        return
    }

    $offlineDetails = $offlineResult.Output.Trim()
    if (-not [string]::IsNullOrWhiteSpace($offlineDetails)) {
        Write-Warning "Offline wheel install failed for '$PackageSpec', fallback to online install.`n$offlineDetails"
    }

    $onlineInstallArgs = @(
        "install",
        "--upgrade",
        "--only-binary=:all:",
        "--target",
        $EngineSitePackages,
        $PackageSpec
    )
    $onlineResult = Invoke-EnginePip `
        -EnginePython $EnginePython `
        -RuntimeSitePackages $RuntimeSitePackages `
        -PipArgs $onlineInstallArgs
    if ($onlineResult.ExitCode -ne 0) {
        $onlineDetails = $onlineResult.Output.Trim()
        throw "Failed to install package '$PackageSpec' into $EngineSitePackages.`n$onlineDetails"
    }

    $downloadWheelArgs = @(
        "download",
        "--dest",
        $WheelCacheRoot,
        "--only-binary=:all:",
        $PackageSpec
    )
    $downloadResult = Invoke-EnginePip `
        -EnginePython $EnginePython `
        -RuntimeSitePackages $RuntimeSitePackages `
        -PipArgs $downloadWheelArgs
    if ($downloadResult.ExitCode -ne 0) {
        $downloadDetails = $downloadResult.Output.Trim()
        Write-Warning "Installed '$PackageSpec' but failed to cache wheel locally.`n$downloadDetails"
    }
}

function Repair-EngineDependencies {
    param(
        [Parameter(Mandatory = $true)][string]$EngineRoot,
        [Parameter(Mandatory = $true)][string]$CacheRoot
    )
    $EngineSitePackages = Join-Path $EngineRoot "site-packages"
    if (-not (Test-Path $EngineSitePackages)) {
        throw "Engine site-packages path was not found: $EngineSitePackages"
    }

    $WheelCacheRoot = Join-Path $CacheRoot "wheels"
    $pipCtx = Ensure-EnginePip -EngineRoot $EngineRoot -CacheRoot $CacheRoot
    $EnginePython = $pipCtx.EnginePython
    $RuntimeSitePackages = $pipCtx.RuntimeSitePackages

    # The upstream with-assets bundle is not always dependency-complete.
    # Ensure runtime-critical modules exist before shipping installer artifacts.
    $Required = @(
        @{ module = "typing_extensions"; package = "typing-extensions==4.15.0" },
        @{ module = "typing_inspection"; package = "typing-inspection==0.4.2" },
        @{ module = "pymupdf"; package = "pymupdf==1.25.2" },
        @{ module = "numpy"; package = "numpy==2.4.2" },
        @{ module = "pyzstd"; package = "pyzstd==0.19.1" },
        @{ module = "regex"; package = "regex==2026.1.15" },
        @{ module = "distro"; package = "distro==1.9.0" },
        @{ module = "xsdata"; package = "xsdata==26.1" },
        @{ module = "orjson"; package = "orjson==3.11.7" },
        @{ module = "onnx"; package = "onnx==1.20.1" }
    )

    foreach ($dep in $Required) {
        $probeBeforeInstall = Test-EngineModuleImport `
            -EnginePython $EnginePython `
            -EngineSitePackages $EngineSitePackages `
            -ModuleName $dep.module
        if (-not $probeBeforeInstall.Success) {
            Write-Host "Missing engine module '$($dep.module)'; installing '$($dep.package)'..."
            Install-EnginePackage `
                -EnginePython $EnginePython `
                -RuntimeSitePackages $RuntimeSitePackages `
                -EngineSitePackages $EngineSitePackages `
                -PackageSpec $dep.package `
                -WheelCacheRoot $WheelCacheRoot

            $probeAfterInstall = Test-EngineModuleImport `
                -EnginePython $EnginePython `
                -EngineSitePackages $EngineSitePackages `
                -ModuleName $dep.module
            if (-not $probeAfterInstall.Success) {
                $details = $probeAfterInstall.Output.Trim()
                throw "Module '$($dep.module)' is still unavailable after installing '$($dep.package)'.`n$details"
            }
        }
    }

    $SmokeModules = @(
        "pdf2zh_next.main",
        "babeldoc.docvision.doclayout"
    )
    foreach ($moduleName in $SmokeModules) {
        $smokeProbe = Test-EngineModuleImport `
            -EnginePython $EnginePython `
            -EngineSitePackages $EngineSitePackages `
            -ModuleName $moduleName
        if (-not $smokeProbe.Success) {
            $details = $smokeProbe.Output.Trim()
            throw "Engine dependency smoke test failed when importing '$moduleName'.`n$details"
        }
    }

    $EngineExe = Join-Path $EngineRoot "pdf2zh.exe"
    if (-not (Test-Path $EngineExe)) {
        throw "Engine executable was not found for smoke check: $EngineExe"
    }
    $previousErrorActionPreference = $ErrorActionPreference
    $engineHelpOutput = ""
    $engineHelpExitCode = 0
    try {
        $ErrorActionPreference = "Continue"
        $engineHelpOutput = (& $EngineExe --help 2>&1 | ForEach-Object { $_.ToString() } | Out-String)
        $engineHelpExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($engineHelpExitCode -ne 0) {
        $helpDetails = $engineHelpOutput.Trim()
        throw "Engine smoke check failed: '$EngineExe --help' exited with code $engineHelpExitCode.`n$helpDetails"
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $ProjectRoot "build\windows"
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $PSScriptRoot "bundle-manifest.json"
}

$DistPath = Join-Path $OutputRoot "pyinstaller-dist"
$StageRoot = Join-Path $OutputRoot "full-stage"
$AppRoot = Join-Path $StageRoot "app"
$CacheRoot = Join-Path $OutputRoot "cache"
$EngineCacheRoot = Join-Path $CacheRoot "engine"
$PrereqCacheRoot = Join-Path $CacheRoot "prerequisites"

$CoreDir = Join-Path $DistPath "pdf2zh-server-core"
$CoreExe = Join-Path $CoreDir "pdf2zh-server-core.exe"
$LauncherExe = Join-Path $DistPath "pdf2zh-server.exe"
$AppIcon = Join-Path $ProjectRoot "server\packaging\windows\assets\zotero-pdf2zh-server.ico"

if (-not (Test-Path $CoreExe)) {
    throw "Missing core executable: $CoreExe. Run build-server-core.ps1 first."
}
if (-not (Test-Path $LauncherExe)) {
    throw "Missing launcher executable: $LauncherExe. Run build-server-core.ps1 first."
}
if (-not (Test-Path $AppIcon)) {
    throw "Application icon file was not found: $AppIcon"
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$Engine = $Manifest.engine

$ExpectedSha = if ([string]::IsNullOrWhiteSpace($EngineSha256)) {
    $Engine.sha256
}
else {
    $EngineSha256
}

if (-not (Ensure-ValidSha256 $ExpectedSha)) {
    throw "A valid SHA256 is required. Provide -EngineSha256 or update bundle-manifest.json."
}

if (Test-Path $StageRoot) {
    Remove-Item -Path $StageRoot -Recurse -Force
}
New-Item -Path $AppRoot -ItemType Directory -Force | Out-Null
New-Item -Path $EngineCacheRoot -ItemType Directory -Force | Out-Null
New-Item -Path $PrereqCacheRoot -ItemType Directory -Force | Out-Null

Write-Host "Copying server core runtime..."
Copy-Item -Path (Join-Path $CoreDir "*") -Destination $AppRoot -Recurse -Force
Copy-Item -Path $LauncherExe -Destination (Join-Path $AppRoot "pdf2zh-server.exe") -Force
Copy-Item -Path $AppIcon -Destination (Join-Path $AppRoot "zotero-pdf2zh-server.ico") -Force

$EngineZip = Join-Path $EngineCacheRoot $Engine.asset_name
if (Test-Path $EngineZip) {
    Write-Host "Found local cached engine archive: $EngineZip"
}
else {
    Download-File -Url $Engine.download_url -OutFile $EngineZip
}

Write-Host "Verifying engine archive SHA256..."
$ActualHash = (Get-FileHash -Path $EngineZip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $ExpectedSha.ToLowerInvariant()) {
    throw "Engine SHA256 mismatch. expected=$ExpectedSha actual=$ActualHash"
}

$ExpectedExeName = if ($Engine.expected_exe_name) { $Engine.expected_exe_name } else { "pdf2zh.exe" }
$EngineExtractRoot = Join-Path $EngineCacheRoot ([IO.Path]::GetFileNameWithoutExtension($Engine.asset_name))
$FoundExe = $null
if (Test-Path $EngineExtractRoot) {
    Write-Host "Checking cached extracted engine directory..."
    $FoundExe = Get-ChildItem -Path $EngineExtractRoot -Recurse -Filter $ExpectedExeName -ErrorAction SilentlyContinue | Select-Object -First 1
}

if (-not $FoundExe) {
    Write-Host "Extracting engine archive to cache directory..."
    if (Test-Path $EngineExtractRoot) {
        Remove-Item -Path $EngineExtractRoot -Recurse -Force
    }
    New-Item -Path $EngineExtractRoot -ItemType Directory -Force | Out-Null
    Expand-Archive -Path $EngineZip -DestinationPath $EngineExtractRoot -Force
    $FoundExe = Get-ChildItem -Path $EngineExtractRoot -Recurse -Filter $ExpectedExeName | Select-Object -First 1
    if (-not $FoundExe) {
        throw "Could not find $ExpectedExeName in extracted engine package."
    }
}

$EngineRuntimeRoot = $FoundExe.Directory.FullName
$FinalEngineRoot = Join-Path $AppRoot "engine"
New-Item -Path $FinalEngineRoot -ItemType Directory -Force | Out-Null
Write-Host "Copying engine runtime files..."
$null = & robocopy $EngineRuntimeRoot $FinalEngineRoot /E /NFL /NDL /NJH /NJS /NC /NS /NP
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed when copying engine runtime. exit_code=$LASTEXITCODE"
}

if (-not (Test-Path (Join-Path $FinalEngineRoot "pdf2zh.exe"))) {
    throw "Final engine directory is invalid. Missing pdf2zh.exe under $FinalEngineRoot"
}

Write-Host "Repairing and validating engine runtime dependencies..."
Repair-EngineDependencies -EngineRoot $FinalEngineRoot -CacheRoot $CacheRoot

$PrereqDir = Join-Path $AppRoot "prerequisites"
New-Item -Path $PrereqDir -ItemType Directory -Force | Out-Null
foreach ($Redistributable in $Manifest.redistributables) {
    if (-not $Redistributable.url -or -not $Redistributable.name) {
        continue
    }
    $Cached = Join-Path $PrereqCacheRoot $Redistributable.name
    if (-not (Test-Path $Cached)) {
        Download-File -Url $Redistributable.url -OutFile $Cached
    }
    $Dest = Join-Path $PrereqDir $Redistributable.name
    Copy-Item -Path $Cached -Destination $Dest -Force
}

$BundleInfo = [ordered]@{
    build_time_utc = (Get-Date).ToUniversalTime().ToString("o")
    engine_provider = $Engine.provider
    engine_release_tag = $Engine.release_tag
    engine_asset_name = $Engine.asset_name
    engine_sha256 = $ExpectedSha
}
$BundleInfo | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $AppRoot "bundle-info.json") -Encoding UTF8

Write-Host "Full stage assembled successfully:"
Write-Host "  Stage root: $StageRoot"
Write-Host "  App root:   $AppRoot"
