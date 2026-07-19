param(
    [string]$Destination = "apps/desktop/src-tauri/resources/sidecar"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Join-Path $repoRoot "output/pyinstaller"
$destinationPath = Join-Path $repoRoot $Destination

uv run --with pyinstaller==6.16.0 pyinstaller `
    --noconfirm `
    --clean `
    --distpath (Join-Path $outputRoot "dist") `
    --workpath (Join-Path $outputRoot "build") `
    (Join-Path $repoRoot "packaging/survival-agent-api.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $destinationPath) {
    Remove-Item -LiteralPath $destinationPath -Recurse -Force
}
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
Copy-Item -Path (Join-Path $outputRoot "dist/survival-agent-api/*") -Destination $destinationPath -Recurse -Force
New-Item -ItemType File -Path (Join-Path $destinationPath ".gitkeep") -Force | Out-Null

$executable = Join-Path $destinationPath "survival-agent-api.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Sidecar executable was not produced: $executable"
}
Write-Output $executable
