param(
    [string]$ReposDir = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReposDir) {
    $ReposDir = Join-Path $Root "repos"
}

$pythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "XMem virtualenv not found. Run npm run setup first."
}

& $pythonExe (Join-Path $Root "scripts\context.py") import @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
