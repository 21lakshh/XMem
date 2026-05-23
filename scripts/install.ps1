param(
    [string]$ReposDir = "",
    [switch]$IncludeMcp,
    [switch]$IncludeSdk,
    [switch]$SkipModelPull,
    [switch]$SkipPythonInstall,
    [switch]$SkipNodeInstall,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[xmem] $Message"
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Native {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Test-DockerRunning {
    if (-not (Test-Command "docker")) {
        Write-Host "[xmem] Docker was not found." -ForegroundColor Yellow
        Write-Host "[xmem] Install Docker Desktop or rerun npm run setup -- -SkipDocker to skip local database startup."
        return $false
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
        Write-Host "[xmem] Start Docker Desktop, wait until it says Docker is running, then rerun this script."
        Write-Host "[xmem] Temporary escape hatch: rerun npm run setup -- -SkipDocker to continue cloning/building without local databases."
        return $false
    }

    return $true
}

function Test-OllamaRunning {
    if (-not (Test-Command "ollama")) {
        Write-Host "[xmem] Ollama was not found." -ForegroundColor Yellow
        Write-Host "[xmem] Install Ollama, or add a cloud LLM key to .env and rerun."
        return $false
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
        Write-Host "[xmem] Ollama is installed but not running." -ForegroundColor Yellow
        Write-Host "[xmem] Start Ollama, or add a cloud LLM key to .env and rerun."
        return $false
    }

    return $true
}

function Test-XMemUsesOllama {
    param([string]$EnvPath)
    if (-not (Test-Path $EnvPath)) {
        return $true
    }
    return [bool]((Get-Content -Raw -Path $EnvPath) -match "(?m)^\s*FALLBACK_ORDER\s*=.*ollama")
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

function Sync-Repo {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Branch
    )

    $target = Join-Path $ReposDir $Name
    if (Test-Path $target) {
        if (-not (Test-Path (Join-Path $target ".git"))) {
            throw "$target exists but is not a git checkout."
        }
        Write-Step "Updating $Name"
        Invoke-Native { git -C $target fetch origin }
        Invoke-Native { git -C $target checkout $Branch }
        Invoke-Native { git -C $target pull --ff-only origin $Branch }
    } else {
        Write-Step "Cloning $Name"
        Invoke-Native { git clone --branch $Branch $Url $target }
    }
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReposDir) {
    $ReposDir = Join-Path $Root "repos"
}

New-Item -ItemType Directory -Force -Path $ReposDir | Out-Null

foreach ($cmd in @("git", "python", "node", "npm")) {
    if (-not (Test-Command $cmd)) {
        throw "$cmd is required. Install it, then run this script again."
    }
}

Sync-Repo "xmem-extension" "https://github.com/XortexAI/xmem-extension.git" "main"

if ($IncludeMcp) {
    Sync-Repo "xmem-mcp" "https://github.com/XortexAI/xmem-mcp.git" "main"
}

if ($IncludeSdk) {
    Sync-Repo "xmem-sdk" "https://github.com/XortexAI/xmem-sdk.git" "master"
}

$XmemDir = $Root
$ExtensionDir = Join-Path $ReposDir "xmem-extension"

$envTemplate = Join-Path $Root "templates\xmem.env.local"
$envTarget = Join-Path $XmemDir ".env"
if (-not (Test-Path $envTarget)) {
    Copy-Item $envTemplate $envTarget
    Write-Step "Created .env from local template"
} else {
    Write-Step ".env already exists; leaving it unchanged"
}

Invoke-Native { powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\configure-xmem-env.ps1") -EnvPath $envTarget }
$usesOllama = Test-XMemUsesOllama -EnvPath $envTarget
$dockerSkipped = $false
$ollamaSkipped = $false

if (-not $SkipModelPull) {
    if ($usesOllama) {
        if (Test-OllamaRunning) {
            Write-Step "Pulling Ollama chat model"
            Invoke-Native { ollama pull qwen2.5:1.5b }
            Write-Step "Pulling Ollama embedding model"
            Invoke-Native { ollama pull nomic-embed-text }
        } else {
            $ollamaSkipped = $true
        }
    } else {
        Write-Step "Cloud LLM provider key detected; skipping Ollama model pulls"
    }
}

if (-not $SkipDocker) {
    if (Test-DockerRunning) {
        Write-Step "Starting local Docker services"
        Invoke-Native { docker compose -f (Join-Path $Root "docker-compose.local.yml") up -d --remove-orphans }
        Wait-ContainerHealthy -ContainerNames @("xmem-postgres", "xmem-mongo", "xmem-neo4j")
    } else {
        $dockerSkipped = $true
    }
}

if (-not $SkipPythonInstall) {
    $venvPython = Join-Path $XmemDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Step "Creating XMem virtualenv"
        Invoke-Native { python -m venv (Join-Path $XmemDir ".venv") }
    }
    Write-Step "Installing XMem local dependencies"
    Invoke-Native { & $venvPython -m pip install --upgrade pip }
    Invoke-Native { & $venvPython -m pip install -e "$XmemDir[local,dev]" }
}

Write-Step "Patching extension for local API"
Invoke-Native { powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\patch-extension-local.ps1") -ExtensionDir $ExtensionDir }

if (-not $SkipNodeInstall) {
    Write-Step "Installing and building Chrome extension"
    Invoke-Native { npm --prefix $ExtensionDir install }
    Invoke-Native { npm --prefix $ExtensionDir run build }
}

Write-Step "Install complete"
Write-Host ""
Write-Host "Next:"
Write-Host "  npm run dev"
Write-Host "  npm run verify"
if ($dockerSkipped) {
    Write-Host ""
    Write-Host "Docker services were not started. Start Docker Desktop before running npm run dev." -ForegroundColor Yellow
}
if ($ollamaSkipped) {
    Write-Host ""
    Write-Host "Ollama models were not pulled. Start Ollama, then rerun npm run setup or add a cloud LLM key." -ForegroundColor Yellow
}
