param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ReposDir = ""
)

$ErrorActionPreference = "Stop"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [string]$Fix = ""
    )

    $label = if ($Ok) { "OK" } else { "FIX" }
    $color = if ($Ok) { "Green" } else { "Yellow" }
    Write-Host "[$label] $Name - $Message" -ForegroundColor $color
    if (-not $Ok -and $Fix) {
        Write-Host "      $Fix"
    }
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Default = ""
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }

    $pattern = "^\s*$([regex]::Escape($Name))\s*=\s*(.*)\s*$"
    foreach ($line in Get-Content -Path $Path) {
        if ($line -match $pattern) {
            $value = $Matches[1].Trim()
            if (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }

    return $Default
}

function Test-NativeOk {
    param([scriptblock]$Command)

    $oldErrorActionPreference = $ErrorActionPreference
    $oldNativePreference = $null
    $hasNativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue

    try {
        $ErrorActionPreference = "Continue"
        if ($hasNativePreference) {
            $oldNativePreference = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }
        $null = & $Command 2>&1
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $oldNativePreference
        }
    }
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReposDir) {
    $ReposDir = Join-Path $Root "repos"
}

$xmemDir = $Root
$extensionDir = Join-Path $ReposDir "xmem-extension"
$envPath = Join-Path $xmemDir ".env"
$failures = 0

Write-Host "[xmem] Doctor report"
Write-Host ""

foreach ($cmd in @("git", "python", "node", "npm")) {
    $ok = Test-CommandExists $cmd
    if (-not $ok) { $failures++ }
    Write-Check $cmd $ok "command lookup" "Install $cmd and reopen this terminal."
}

$dockerCommand = Test-CommandExists "docker"
$dockerRunning = $dockerCommand -and (Test-NativeOk { docker info })
if (-not $dockerCommand -or -not $dockerRunning) { $failures++ }
Write-Check "Docker" $dockerRunning "local database runtime" "Start Docker Desktop, then rerun npm run dev."

$xmemExists = Test-Path (Join-Path $xmemDir "pyproject.toml")
if (-not $xmemExists) { $failures++ }
Write-Check "XMem repo" $xmemExists $xmemDir "Run this from the XMem repository root."

$extensionExists = Test-Path $extensionDir
if (-not $extensionExists) { $failures++ }
Write-Check "Extension repo" $extensionExists $extensionDir "Run npm run setup."

$envExists = Test-Path $envPath
if (-not $envExists) { $failures++ }
Write-Check "XMem .env" $envExists $envPath "Run npm run setup to create it from templates/xmem.env.local."

if ($envExists) {
    $usesOllama = [bool]((Get-Content -Raw -Path $envPath) -match "(?m)^\s*FALLBACK_ORDER\s*=.*ollama")
    if ($usesOllama) {
        $ollamaCommand = Test-CommandExists "ollama"
        $ollamaRunning = $ollamaCommand -and (Test-NativeOk { ollama list })
        if (-not $ollamaCommand -or -not $ollamaRunning) { $failures++ }
        Write-Check "Ollama" $ollamaRunning "required because no cloud LLM key is configured" "Start Ollama, or add a cloud LLM key to .env."

        if ($ollamaRunning) {
            $chatModel = Get-DotEnvValue -Path $envPath -Name "OLLAMA_MODEL" -Default "qwen2.5:1.5b"
            $embeddingModel = Get-DotEnvValue -Path $envPath -Name "OLLAMA_EMBEDDING_MODEL" -Default "nomic-embed-text"
            $installed = (& ollama list 2>$null | Select-Object -Skip 1) -join "`n"
            foreach ($model in @($chatModel, $embeddingModel)) {
                $escaped = [regex]::Escape($model)
                $ok = ($installed -match "(?m)^$escaped(\s|:latest\s)")
                if (-not $ok) { $failures++ }
                Write-Check "Ollama model $model" $ok "local model availability" "Run: ollama pull $model"
            }
        }
    } else {
        Write-Check "LLM routing" $true "cloud key detected; Ollama is not required"
    }
}

try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 5
    $ready = if ($health.data) { [bool]$health.data.pipelines_ready } else { [bool]$health.pipelines_ready }
    if (-not $ready) { $failures++ }
    Write-Check "XMem API" $ready "$BaseUrl/health" "Start it with npm run dev and wait for pipelines_ready=true."
} catch {
    $failures++
    Write-Check "XMem API" $false "$BaseUrl is not reachable" "Start it with npm run dev."
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "[xmem] Everything looks ready." -ForegroundColor Green
} else {
    Write-Host "[xmem] Found $failures setup item(s) to fix." -ForegroundColor Yellow
}
