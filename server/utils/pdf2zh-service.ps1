[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Stop')]
    [string]$Action,
    [ValidateRange(1, 65535)]
    [int]$Port = 0,
    [switch]$CheckUpdate,
    [switch]$Force,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$serverPath = Join-Path $projectRoot 'server.py'
$exitCode = 0
$startMutex = $null
$ownsMutex = $false
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

function Get-Listeners {
    # Query all listeners so an unused port does not produce a cmdlet error.
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalPort -eq $Port })
}

function Get-ProjectProcesses {
    $pattern = '(?i)(?:^|[\s"])' + [regex]::Escape($serverPath) + '(?=$|[\s"])'
    @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern })
}

function Get-Health {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
        $expected = [IO.Path]::GetFullPath((Join-Path $projectRoot 'translated'))
        if ($health.status -eq 'ok' -and $health.outputDir -and
            [IO.Path]::GetFullPath([string]$health.outputDir) -eq $expected) {
            return $health
        }
    } catch { }
    return $null
}

function Start-Pdf2zh {
    $hash = [Security.Cryptography.SHA256]::Create()
    try {
        $key = [BitConverter]::ToString($hash.ComputeHash(
            [Text.Encoding]::UTF8.GetBytes($serverPath.ToLowerInvariant() + ':' + $Port))).Replace('-', '')
    } finally { $hash.Dispose() }
    $script:startMutex = New-Object Threading.Mutex($false, ('Local\PDF2zh-' + $key))
    try { $script:ownsMutex = $script:startMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $script:ownsMutex = $true }
    if (-not $script:ownsMutex) {
        Write-Host '本目录的服务已在启动或运行，请查看已有启动窗口。'
        return
    }

    $listeners = @(Get-Listeners)
    if ($listeners.Count -gt 0) {
        $health = Get-Health
        if ($health) {
            Write-Host "PDF2zh $($health.version) 已在运行：http://localhost:$Port/"
            return
        }
        throw "端口 $Port 已被其他程序占用（PID: $(($listeners.OwningProcess | Select-Object -Unique) -join ', ')）。请更改端口或检查占用程序。"
    }
    $existing = @(Get-ProjectProcesses)
    if ($existing.Count -gt 0) {
        throw "本目录已有 Server 进程（PID: $($existing.ProcessId -join ', ')），可能正在启动或使用其他端口。请先运行停止脚本。"
    }

    $env:PATH = (Join-Path $env:USERPROFILE '.local\bin') + ';' + $env:PATH
    $env:PYTHONUNBUFFERED = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    # Prevent ambient Python settings from mixing unrelated environments.
    $env:PYTHONPATH = $null
    $env:PYTHONHOME = $null
    $env:PYTHONNOUSERSITE = '1'
    $runtime = $null
    foreach ($relative in @('zotero-pdf2zh-next-venv\Scripts\python.exe', 'zotero-pdf2zh-venv\Scripts\python.exe')) {
        $candidate = Join-Path $projectRoot $relative
        if (Test-Path -LiteralPath $candidate) {
            $ErrorActionPreference = 'Continue'
            & $candidate -c 'import flask, toml, pypdf, fitz, packaging' 2>$null
            $ErrorActionPreference = 'Stop'
            if ($LASTEXITCODE -eq 0) { $runtime = $candidate; break }
        }
    }
    $runtimeArgs = @()
    if (-not $runtime) {
        $uv = Get-Command uv.exe -ErrorAction SilentlyContinue
        if (-not $uv) { throw '找不到可用 Python 环境或 uv。请先按项目教程安装 uv。' }
        $runtime = $uv.Source
        $runtimeArgs = @('run', '--python', '3.12', '--with-requirements', (Join-Path $projectRoot 'requirements.txt'), 'python')
    }
    $updateValue = if ($CheckUpdate) { 'true' } else { 'false' }
    $consoleEntry = Join-Path $projectRoot 'utils\server_console.py'
    $runtimeArgs += @('-u', $consoleEntry, $serverPath, '--host=127.0.0.1', "--port=$Port", "--check_update=$updateValue")
    $logDir = Join-Path $projectRoot 'work\logs'
    [IO.Directory]::CreateDirectory($logDir) | Out-Null
    $logPath = Join-Path $logDir 'pdf2zh-server.log'
    Write-Host "目录：$projectRoot"
    Write-Host "运行时：$runtime"
    Write-Host "监控页：http://localhost:$Port/"
    Write-Host "日志：$logPath"
    Write-Host '启动后请保持本窗口开启；停止服务可按 Ctrl+C，或双击停止脚本。'
    if (-not $CheckUpdate) { Write-Host '快速启动：跳过源码更新检查。需要检查时，可在终端运行启动脚本并加 -CheckUpdate。' }
    # Preserve the native console and carriage returns; Python records logs.
    $ErrorActionPreference = 'Continue'
    & $runtime @runtimeArgs
    $nativeExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($nativeExit -ne 0) { throw "Server 已退出，退出码 $nativeExit。详情见 $logPath" }
}

function Stop-Pdf2zh {
    $projectProcesses = @(Get-ProjectProcesses)
    $processes = @($projectProcesses | Where-Object {
        $portArgument = [regex]::Match([string]$_.CommandLine, '(?:^|\s)--port(?:=|\s+)(\d+)(?=$|\s|")')
        $processPort = if ($portArgument.Success) { [int]$portArgument.Groups[1].Value } else { 8890 }
        $processPort -eq $Port
    })
    $listeners = @(Get-Listeners)
    if ($processes.Count -eq 0) {
        if ($projectProcesses.Count -gt 0) {
            throw "本目录 Server 正在使用其他端口；请用 -Port 指定正确端口，未停止任何程序。"
        }
        if ($listeners.Count -gt 0) {
            throw "端口 $Port 有进程监听，但无法确认属于本目录的 Server；未停止任何程序。"
        }
        Write-Host '本目录的 PDF2zh 服务已停止。'
        return
    }
    $health = Get-Health
    if ($health -and -not $Force) {
        try {
            $tasks = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/tasks" -TimeoutSec 3
            if ($tasks.status -ne 'success') { throw '任务查询失败' }
            $active = @($tasks.tasks | Where-Object { $_.active -eq $true })
            if ($active.Count -gt 0) {
                $answer = Read-Host "还有 $($active.Count) 个任务，停止会中断翻译。输入 Y 确认"
                if ($answer -notmatch '^(?i)y(es)?$') { Write-Host '已取消停止。'; return }
            }
        } catch { throw '无法检查翻译任务。请稍后重试；确需停止时可加 -Force。' }
    }
    # Snapshot descendants while their parent identity is still available.
    $allProcesses = @(Get-CimInstance Win32_Process)
    $tree = @($processes)
    $knownIds = @($processes.ProcessId)
    $frontier = @($processes.ProcessId)
    while ($frontier.Count -gt 0) {
        $children = @($allProcesses | Where-Object { $_.ParentProcessId -in $frontier -and $_.ProcessId -notin $knownIds })
        if ($children.Count -eq 0) { break }
        $tree += $children
        $frontier = @($children.ProcessId)
        $knownIds += $frontier
    }
    foreach ($process in $tree) {
        # Recheck command line and creation time to avoid a reused PID.
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.ProcessId)"
        if ($current -and $current.CommandLine -eq $process.CommandLine -and $current.CreationDate -eq $process.CreationDate) {
            $result = Invoke-CimMethod -InputObject $current -MethodName Terminate -Arguments @{ Reason = [uint32]0 }
            if ($result.ReturnValue -ne 0) { throw "停止 PID $($process.ProcessId) 失败，错误码 $($result.ReturnValue)。" }
            Write-Host "已停止本目录 Server（PID $($process.ProcessId)）。"
        }
    }
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (@(Get-ProjectProcesses).Count -eq 0) { Write-Host 'PDF2zh 服务已停止。'; return }
        Start-Sleep -Milliseconds 250
    }
    throw 'Server 进程仍未退出，请查看运行窗口。'
}

try {
    if ($Port -eq 0) {
        $Port = 8890
        if ($env:PDF2ZH_PORT) {
            $parsedPort = 0
            if (-not [int]::TryParse($env:PDF2ZH_PORT, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
                throw 'PDF2ZH_PORT 必须是 1 到 65535 的整数。'
            }
            $Port = $parsedPort
        }
    }
    Set-Location -LiteralPath $projectRoot
    if (-not (Test-Path -LiteralPath $serverPath)) { throw "找不到 $serverPath" }
    if ($Action -eq 'Start') { Start-Pdf2zh } else { Stop-Pdf2zh }
} catch {
    Write-Host "错误：$($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
} finally {
    if ($ownsMutex) { $startMutex.ReleaseMutex() }
    if ($startMutex) { $startMutex.Dispose() }
    if (-not $NoPause) { Read-Host '按 Enter 关闭窗口' | Out-Null }
}
exit $exitCode
