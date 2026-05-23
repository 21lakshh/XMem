param(
    [string]$ReposDir = "",
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

function Invoke-Native {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Assert-DockerRunning {
    if (-not (Test-Command "docker")) {
        Write-Host "[xmem] Docker was not found." -ForegroundColor Yellow
        Write-Host "[xmem] Install Docker Desktop or rerun npm run start -- -SkipDocker if local databases are already running elsewhere."
        exit 2
    }

    $oldErrorActionPreference = $ErrorActionPreference
    $oldNativePreference = $null
    $hasNativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue

    try {
        $ErrorActionPreference = "Continue"
        if ($hasNativePreference) {
            $oldNativePreference = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $null = & docker info 2>&1
        $dockerExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $oldNativePreference
        }
    }

    if ($dockerExitCode -ne 0) {
        Write-Host "[xmem] Docker Desktop is installed but not running." -ForegroundColor Yellow
        Write-Host "[xmem] Start Docker Desktop, wait until it says Docker is running, then rerun npm run dev."
        Write-Host "[xmem] Temporary escape hatch: rerun npm run start -- -SkipDocker if local databases are already running elsewhere."
        exit 2
    }
}

function Assert-OllamaRunning {
    if (-not (Test-Command "ollama")) {
        Write-Host "[xmem] Ollama was not found." -ForegroundColor Yellow
        Write-Host "[xmem] Install Ollama, or add a cloud LLM key to .env and rerun."
        exit 2
    }

    $oldErrorActionPreference = $ErrorActionPreference
    $oldNativePreference = $null
    $hasNativePreference = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue

    try {
        $ErrorActionPreference = "Continue"
        if ($hasNativePreference) {
            $oldNativePreference = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $null = & ollama list 2>&1
        $ollamaExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $oldNativePreference
        }
    }

    if ($ollamaExitCode -ne 0) {
        Write-Host "[xmem] XMem is configured to use local Ollama, but Ollama is not running." -ForegroundColor Yellow
        Write-Host "[xmem] Start Ollama, or add a cloud LLM key to .env and rerun."
        exit 2
    }
}

function Test-XMemUsesOllama {
    param([string]$EnvPath)
    if (-not (Test-Path $EnvPath)) {
        return $true
    }
    return [bool]((Get-Content -Raw -Path $EnvPath) -match "(?m)^\s*FALLBACK_ORDER\s*=.*ollama")
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
            if ($value) {
                return $value
            }
        }
    }

    return $Default
}

function Assert-OllamaModels {
    param([string]$EnvPath)

    $chatModel = Get-DotEnvValue -Path $EnvPath -Name "OLLAMA_MODEL" -Default "qwen2.5:1.5b"
    $embeddingModel = Get-DotEnvValue -Path $EnvPath -Name "OLLAMA_EMBEDDING_MODEL" -Default "nomic-embed-text"
    $installed = (& ollama list 2>$null | Select-Object -Skip 1) -join "`n"
    $missing = @()

    foreach ($model in @($chatModel, $embeddingModel)) {
        if (-not $model) {
            continue
        }
        $escaped = [regex]::Escape($model)
        $hasModel = ($installed -match "(?m)^$escaped(\s|:latest\s)")
        if (-not $hasModel) {
            $missing += $model
        }
    }

    if ($missing.Count -gt 0) {
        Write-Host "[xmem] Ollama is running, but required local model(s) are missing." -ForegroundColor Yellow
        foreach ($model in $missing) {
            Write-Host "[xmem] Pull it with: ollama pull $model"
        }
        Write-Host "[xmem] Or add a cloud LLM key to .env so XMem does not use Ollama."
        exit 2
    }
}

function Wait-ContainerHealthy {
    param(
        [string[]]$ContainerNames,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $pending = @($ContainerNames)

    while ((Get-Date) -lt $deadline) {
        $stillPending = @()
        foreach ($name in $pending) {
            $status = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $name 2>$null)
            if ($LASTEXITCODE -ne 0) {
                $stillPending += $name
                continue
            }

            $status = ($status | Select-Object -First 1).Trim()
            if ($status -in @("healthy", "running")) {
                continue
            }

            if ($status -eq "unhealthy") {
                throw "Container $name is unhealthy. Run npm run doctor or inspect it with: docker logs $name"
            }

            $stillPending += $name
        }

        if ($stillPending.Count -eq 0) {
            return
        }

        Write-Host "[xmem] Waiting for local database containers: $($stillPending -join ', ')"
        $pending = $stillPending
        Start-Sleep -Seconds 5
    }

    throw "Timed out waiting for local database containers: $($pending -join ', '). Run npm run doctor for details."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReposDir) {
    $ReposDir = Join-Path $Root "repos"
}

$XmemDir = $Root

$envTarget = Join-Path $XmemDir ".env"
if (-not (Test-Path $envTarget)) {
    throw "XMem .env not found at $envTarget. Run npm run setup first."
}

Invoke-Native { powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\configure-xmem-env.ps1") -EnvPath $envTarget }
if (Test-XMemUsesOllama -EnvPath $envTarget) {
    Assert-OllamaRunning
    Assert-OllamaModels -EnvPath $envTarget
}

if (-not $SkipDocker) {
    Assert-DockerRunning
    Invoke-Native { docker compose -f (Join-Path $Root "docker-compose.local.yml") up -d --remove-orphans }
    Wait-ContainerHealthy -ContainerNames @("xmem-postgres", "xmem-mongo", "xmem-neo4j")
}

$pythonExe = Join-Path $XmemDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

Set-Location $XmemDir
Write-Host "[xmem] Starting XMem API at http://localhost:8000"
Invoke-Native { & $pythonExe -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000 }
