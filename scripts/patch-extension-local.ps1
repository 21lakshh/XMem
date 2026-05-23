param(
    [string]$ExtensionDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ExtensionDir) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $ExtensionDir = Join-Path $Root "repos\xmem-extension"
}

$scriptPath = Join-Path $PSScriptRoot "patch-extension-local.js"
& node $scriptPath --extension-dir $ExtensionDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
