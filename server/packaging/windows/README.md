# Windows Full Installer Pipeline

This folder contains scripts to build a Windows "full" installer that does not
require Python/uv/conda on end-user machines.

## Output

- Installer: `zotero-pdf2zh-server-full-setup-x64-v<version>.exe`
- Installs to: `C:\Program Files\PDF2ZH Server`
- Runtime data directory: `C:\ProgramData\PDF2ZH Server`

## Prerequisites (build machine)

- Python 3.12+
- PowerShell
- Inno Setup 6 (`ISCC.exe`)
- Network access to download the engine full package

## Local build steps

From repository root:

```powershell
./server/packaging/windows/build-server-core.ps1 -Clean
./server/packaging/windows/assemble-full.ps1 -EngineSha256 "<engine_zip_sha256>"

$stageRoot = (Resolve-Path "build/windows/full-stage").Path
$outputDir = Join-Path (Resolve-Path "build/windows").Path "installer-output"
New-Item -Path $outputDir -ItemType Directory -Force | Out-Null

& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
  "/DMyAppVersion=3.0.38-dev" `
  "/DStageRoot=$stageRoot" `
  "/DOutputDir=$outputDir" `
  "server/packaging/windows/installer.iss"
```

## Notes

- `assemble-full.ps1` enforces SHA256 validation for the engine archive.
- Engine source metadata lives in `bundle-manifest.json`.
- The launcher (`pdf2zh-server.exe`) starts server core in packaged mode.
