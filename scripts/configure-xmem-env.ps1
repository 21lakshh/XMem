param(
    [string]$EnvPath = "",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host "[xmem] $Message"
    }
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return ""
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
            return $value.Trim()
        }
    }

    return ""
}

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content -Path $Path)
    }

    $pattern = "^\s*$([regex]::Escape($Name))\s*="
    $updated = $false
    $next = foreach ($line in $lines) {
        if ($line -match $pattern) {
            $updated = $true
            "$Name=$Value"
        } else {
            $line
        }
    }

    if (-not $updated) {
        $next += "$Name=$Value"
    }

    Set-Content -Path $Path -Value $next
}

function Test-SecretValue {
    param([string]$Value)

    if (-not $Value) {
        return $false
    }

    $trimmed = $Value.Trim()
    if (-not $trimmed) {
        return $false
    }

    $placeholderPatterns = @(
        "^your[_-]",
        "your_.*_key",
        "example",
        "sample",
        "placeholder",
        "change[-_]?me",
        "^dummy([-_].*)?$",
        "^fake([-_].*)?$",
        "^test([-_].*)?$"
    )

    foreach ($pattern in $placeholderPatterns) {
        if ($trimmed -match $pattern) {
            return $false
        }
    }

    return $true
}

function Get-ConfiguredValue {
    param(
        [string]$Path,
        [string]$Name
    )

    $envValue = [Environment]::GetEnvironmentVariable($Name)
    if (Test-SecretValue $envValue) {
        return $envValue
    }

    $fileValue = Get-DotEnvValue -Path $Path -Name $Name
    if (Test-SecretValue $fileValue) {
        return $fileValue
    }

    return ""
}

if (-not $EnvPath) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $EnvPath = Join-Path $Root ".env"
}

if (-not (Test-Path $EnvPath)) {
    throw "XMem .env not found at $EnvPath"
}

$providers = @()
if (Get-ConfiguredValue -Path $EnvPath -Name "OPENROUTER_API_KEY") {
    $providers += "openrouter"
}
if (Get-ConfiguredValue -Path $EnvPath -Name "GEMINI_API_KEY") {
    $providers += "gemini"
}
if (Get-ConfiguredValue -Path $EnvPath -Name "CLAUDE_API_KEY") {
    $providers += "claude"
}
if (Get-ConfiguredValue -Path $EnvPath -Name "OPENAI_API_KEY") {
    $providers += "openai"
}

$awsAccessKey = Get-ConfiguredValue -Path $EnvPath -Name "AWS_ACCESS_KEY_ID"
$awsSecretKey = Get-ConfiguredValue -Path $EnvPath -Name "AWS_SECRET_ACCESS_KEY"
if ($awsAccessKey -and $awsSecretKey) {
    $providers += "bedrock"
}

if ($providers.Count -gt 0) {
    $providerJson = "[" + (($providers | ForEach-Object { '"' + $_ + '"' }) -join ",") + "]"
    Set-DotEnvValue -Path $EnvPath -Name "FALLBACK_ORDER" -Value "'$providerJson'"

    # Keep embeddings local and non-Ollama when a cloud LLM key is available.
    Set-DotEnvValue -Path $EnvPath -Name "EMBEDDING_PROVIDER" -Value "fastembed"
    Set-DotEnvValue -Path $EnvPath -Name "FASTEMBED_MODEL" -Value "BAAI/bge-small-en-v1.5"
    Set-DotEnvValue -Path $EnvPath -Name "EMBEDDING_MODEL" -Value "BAAI/bge-small-en-v1.5"
    Set-DotEnvValue -Path $EnvPath -Name "PINECONE_DIMENSION" -Value "384"

    Write-Step "Detected cloud LLM provider(s): $($providers -join ', ')"
    Write-Step "Configured XMem to avoid Ollama for LLM and embedding calls."
} else {
    Set-DotEnvValue -Path $EnvPath -Name "FALLBACK_ORDER" -Value "'[`"ollama`"]'"
    Set-DotEnvValue -Path $EnvPath -Name "EMBEDDING_PROVIDER" -Value "ollama"
    Set-DotEnvValue -Path $EnvPath -Name "OLLAMA_EMBEDDING_MODEL" -Value "nomic-embed-text"
    Set-DotEnvValue -Path $EnvPath -Name "EMBEDDING_MODEL" -Value "nomic-embed-text"
    Set-DotEnvValue -Path $EnvPath -Name "PINECONE_DIMENSION" -Value "768"

    Write-Step "No cloud LLM provider keys detected."
    Write-Step "Configured XMem to use local Ollama for LLM and embedding calls."
}
