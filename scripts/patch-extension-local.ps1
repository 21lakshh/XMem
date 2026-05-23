param(
    [string]$ExtensionDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ExtensionDir) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $ExtensionDir = Join-Path $Root "repos\xmem-extension"
}

$apiFile = Join-Path $ExtensionDir "src\api.ts"
if (-not (Test-Path $apiFile)) {
    throw "Could not find extension API file at $apiFile"
}

function New-HollowXIcon {
    param(
        [int]$Size,
        [string]$Path
    )

    Add-Type -AssemblyName System.Drawing
    $bitmap = New-Object System.Drawing.Bitmap $Size, $Size
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::White)

    $margin = [Math]::Max(3, [int]($Size * 0.22))
    $outerWidth = [Math]::Max(4, [int]($Size * 0.22))
    $innerWidth = [Math]::Max(2, [int]($Size * 0.105))

    $outerPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black), $outerWidth
    $outerPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $outerPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $outerPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    $innerPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), $innerWidth
    $innerPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $innerPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $innerPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    $graphics.DrawLine($outerPen, $margin, $margin, $Size - $margin, $Size - $margin)
    $graphics.DrawLine($outerPen, $Size - $margin, $margin, $margin, $Size - $margin)
    $graphics.DrawLine($innerPen, $margin, $margin, $Size - $margin, $Size - $margin)
    $graphics.DrawLine($innerPen, $Size - $margin, $margin, $margin, $Size - $margin)

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $outerPen.Dispose()
    $innerPen.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}

$iconDir = Join-Path $ExtensionDir "icons"
New-Item -ItemType Directory -Force -Path $iconDir | Out-Null
New-HollowXIcon -Size 16 -Path (Join-Path $iconDir "icon16.png")
New-HollowXIcon -Size 48 -Path (Join-Path $iconDir "icon48.png")
New-HollowXIcon -Size 128 -Path (Join-Path $iconDir "icon128.png")
New-HollowXIcon -Size 128 -Path (Join-Path $iconDir "logo.png")
$sourceFiles = @(
    "src\api.ts",
    "src\background.ts",
    "src\content.ts"
)

foreach ($relativePath in $sourceFiles) {
    $sourceFile = Join-Path $ExtensionDir $relativePath
    if (Test-Path $sourceFile) {
        $source = Get-Content -Raw -Path $sourceFile
        $source = $source.Replace("https://api.xmem.in", "http://localhost:8000")
        $source = $source.Replace(
            "new XMemClient(API_BASE_URL, config.apiKey, config.userId)",
            "new XMemClient(API_BASE_URL, config.apiKey)"
        )
        $source = $source.Replace(
            ".replace(/[^\\w.\\-@]+/g, '_')",
            ".replace(/[^A-Za-z0-9_.@-]+/g, '_')"
        )
        Set-Content -Path $sourceFile -Value $source -NoNewline
    }
}

$content = Get-Content -Raw -Path $apiFile

if ($content -notmatch "function normalizeUserId") {
    $content = [regex]::Replace(
        $content,
        "(const API_BASE_URL = 'http://localhost:8000';\r?\n)",
        "`$1`r`nfunction normalizeUserId(userId: string): string {`r`n  const normalized = (userId || '')`r`n    .trim()`r`n    .replace(/[^A-Za-z0-9_.@-]+/g, '_')`r`n    .replace(/^_+|_+$/g, '');`r`n  return normalized || 'xmem-local-user';`r`n}`r`n",
        1
    )
}

$content = $content.Replace(
    "userId: data.xmem_user_id || '',",
    "userId: normalizeUserId(data.xmem_user_id || ''),"
)

$backgroundFile = Join-Path $ExtensionDir "src\background.ts"
if (Test-Path $backgroundFile) {
    $background = Get-Content -Raw -Path $backgroundFile
    if ($background -notmatch "function normalizeUserId") {
        $background = [regex]::Replace(
            $background,
            "(interface XMemConfig \{\r?\n  apiKey: string;\r?\n  userId: string;\r?\n\}\r?\n)",
            "`$1`r`nfunction normalizeUserId(userId: string): string {`r`n  const normalized = (userId || '')`r`n    .trim()`r`n    .replace(/[^A-Za-z0-9_.@-]+/g, '_')`r`n    .replace(/^_+|_+$/g, '');`r`n  return normalized || 'xmem-local-user';`r`n}`r`n",
            1
        )
    }

    $background = $background.Replace(
        "userId: data.xmem_user_id || '',",
        "userId: normalizeUserId(data.xmem_user_id || ''),"
    )
    Set-Content -Path $backgroundFile -Value $background -NoNewline
}

$replacement = @'
export async function validateCredentials(apiKey: string, username: string): Promise<boolean> {
  const url = `${API_BASE_URL}/auth/verify-key`;
  try {
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${apiKey}`
      }
    });

    if (!response.ok) {
      console.log('[XMem] Validation failed: HTTP', response.status);
      return false;
    }

    const data = await response.json();
    console.log('[XMem] Validated user data:', data);

    // Local dev static keys do not always map to a real username. If the local
    // API accepted the key, allow any non-empty local user id from the popup.
    if (API_BASE_URL.includes('localhost') || API_BASE_URL.includes('127.0.0.1')) {
      return Boolean(username && username.trim());
    }

    return Boolean(data.username && data.username.toLowerCase() === username.toLowerCase());
  } catch (err) {
    console.error('[XMem] Credential validation network error:', err);
    return false;
  }
}

//
'@

$pattern = "export async function validateCredentials[\s\S]*?\r?\n}\r?\n\r?\n//"
$patched = [regex]::Replace($content, $pattern, $replacement, 1)

if ($patched -eq $content -and $content -notmatch "http://localhost:8000") {
    throw "Extension patch did not apply."
}

Set-Content -Path $apiFile -Value $patched -NoNewline
Write-Host "[xmem] Patched extension API for http://localhost:8000"
