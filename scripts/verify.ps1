param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ApiKey = "dev-xmem-key",
    [string]$UserId = "xmem-local-user",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[xmem] $Message"
}

function Get-ResponseErrorMessage {
    param([object]$ErrorRecord)

    if ($ErrorRecord.ErrorDetails.Message) {
        return $ErrorRecord.ErrorDetails.Message
    }

    return $ErrorRecord.Exception.Message
}

function Invoke-XMemJson {
    param(
        [string]$Uri,
        [string]$Method,
        [hashtable]$Headers = @{},
        [string]$Body = "",
        [int]$TimeoutSec = 60
    )

    try {
        if ($Body) {
            return Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -Body $Body -TimeoutSec $TimeoutSec
        }

        return Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -TimeoutSec $TimeoutSec
    } catch {
        $message = Get-ResponseErrorMessage $_
        throw "Request failed: $Method $Uri`n$message"
    }
}

function Test-HealthReady {
    param([object]$Health)

    if (-not $Health) {
        return $false
    }

    if ($Health.data) {
        return [bool]$Health.data.pipelines_ready
    }

    return [bool]$Health.pipelines_ready
}

function Get-HealthSummary {
    param([object]$Health)

    if ($Health.data) {
        return "status=$($Health.data.status), pipelines_ready=$($Health.data.pipelines_ready), error=$($Health.data.error)"
    }

    return "status=$($Health.status), pipelines_ready=$($Health.pipelines_ready), error=$($Health.error)"
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$health = $null

Write-Step "Waiting for API health at $BaseUrl/health"
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 10
        if (Test-HealthReady $health) {
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $health) {
    throw "XMem API did not become reachable within $TimeoutSeconds seconds."
}

Write-Step "Health: $(Get-HealthSummary $health)"
if (-not (Test-HealthReady $health)) {
    throw "XMem API is reachable but pipelines are not ready."
}

$headers = @{
    "Authorization" = "Bearer $ApiKey"
    "Content-Type" = "application/json"
}

$memoryText = "Remember that XMem local mode runs directly from the main XMem repository."

$ingestBody = @{
    user_query = $memoryText
    agent_response = "Got it. I will remember that XMem local mode runs from the main repository."
    user_id = $UserId
    effort_level = "low"
} | ConvertTo-Json

Write-Step "Ingesting a smoke-test memory"
$ingest = Invoke-XMemJson -Uri "$BaseUrl/v1/memory/ingest" -Method POST -Headers $headers -Body $ingestBody -TimeoutSec 650
Write-Step "Ingest status: $($ingest.status)"

$searchBody = @{
    query = "What is XMem local mode?"
    user_id = $UserId
    domains = @("profile", "temporal", "summary")
    top_k = 5
} | ConvertTo-Json

Write-Step "Searching memory"
$search = Invoke-XMemJson -Uri "$BaseUrl/v1/memory/search" -Method POST -Headers $headers -Body $searchBody -TimeoutSec 180
$resultCount = 0
if ($search.data -and $search.data.results) {
    $resultCount = @($search.data.results).Count
}
Write-Step "Search result count: $resultCount"

$retrieveBody = @{
    query = "Where does XMem local mode run from?"
    user_id = $UserId
    top_k = 5
} | ConvertTo-Json

Write-Step "Retrieving answer"
$retrieve = Invoke-XMemJson -Uri "$BaseUrl/v1/memory/retrieve" -Method POST -Headers $headers -Body $retrieveBody -TimeoutSec 240

Write-Host ""
Write-Host "Answer:"
Write-Host $retrieve.data.answer
Write-Host ""
Write-Step "Verification complete"
