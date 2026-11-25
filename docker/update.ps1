param([ValidateSet('server', 'all')][string]$Mode = 'server')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & docker compose version *> $null
    $script:ComposeV2 = ($LASTEXITCODE -eq 0)
    if (-not $script:ComposeV2 -and -not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        throw 'Docker Compose is required.'
    }
    function Invoke-Compose {
        if ($script:ComposeV2) { & docker compose @args }
        else { & docker-compose @args }
        if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
    }
    Invoke-Compose config --quiet
    Write-Host 'Wait for active translations to finish before updating. Building the new Server image...'
    Invoke-Compose build --pull --no-cache pdf2zh-server
    if ($Mode -eq 'all') {
        Invoke-Compose run --rm -T --no-deps --entrypoint sh pdf2zh-server -c 'exec docker pull "${ZOTERO_PDF2ZH_FROM_IMAGE:-awwaawwa/pdfmathtranslate-next:latest}"'
    }
    Invoke-Compose up -d --no-deps --no-build pdf2zh-server
    Invoke-Compose ps pdf2zh-server
    Write-Host 'Update command completed. Check readiness with: docker compose logs --tail=50 pdf2zh-server'
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    Pop-Location
}
