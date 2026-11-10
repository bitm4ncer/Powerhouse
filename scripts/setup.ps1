# setup.ps1 — Powerhouse setup for Windows.
# Renders opencode.json from config\opencode.json.tpl, copies jsonc files and all
# skills into the OpenCode config dir, and installs the pinned clipy-mcp package.
# Usage: powershell -NoProfile -File scripts\setup.ps1 [-CfgDir <path>] [-SkipInstall]
param(
    [string]$CfgDir = "$env:USERPROFILE\.config\opencode",
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

# 1) Prerequisites FIRST — before any file write
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error 'Node.js >= 20 with npm is required'
    exit 1
}

# 2) Repo root (this script lives in <repo>\scripts)
$repo = Split-Path $PSScriptRoot -Parent

# 3) Substitution values (forward slashes: portable across Windows and Unix)
$homeValue = $env:USERPROFILE.Replace('\', '/')
$tmpValue = $env:TEMP.Replace('\', '/')
$clipyEntry = "$repo\clipy-mcp\node_modules\@clipy\mcp\dist\index.js".Replace('\', '/')
$videowizardDir = if ($env:VIDEOWIZARD_DIR) { $env:VIDEOWIZARD_DIR.Replace('\', '/') } else { "$env:USERPROFILE/VideoWizard" }
$figmaServer = if ($env:FIGMA_SERVER) { $env:FIGMA_SERVER.Replace('\', '/') } else { "$env:USERPROFILE/tools/cursor-talk-to-figma-mcp/dist/server.js" }
$craftAnythingCli = if ($env:CRAFT_ANYTHING_CLI) { $env:CRAFT_ANYTHING_CLI.Replace('\', '/') } else { 'craft-anything-cli' }

# 5) Backup every overwrite target once per run (unique dir, never merged)
if (Test-Path $CfgDir) {
    $present = @(@('opencode.json', 'opencode-mem.jsonc', 'dcp.jsonc', 'skills') | Where-Object { Test-Path (Join-Path $CfgDir $_) })
    if ($present.Count -gt 0) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backup = Join-Path $CfgDir "backup-$stamp"
        $n = 0
        while (Test-Path $backup) { $n++; $backup = Join-Path $CfgDir "backup-$stamp-$n" }
        New-Item -ItemType Directory -Force $backup | Out-Null
        foreach ($item in $present) {
            Copy-Item -Recurse -Force (Join-Path $CfgDir $item) (Join-Path $backup $item)
        }
        Write-Host "Backup written to $backup"
    }
}

# 6) Render template via the shared JSON-safe renderer
New-Item -ItemType Directory -Force $CfgDir | Out-Null
node (Join-Path $repo 'scripts\render-config.js') forward (Join-Path $repo 'config\opencode.json.tpl') (Join-Path $CfgDir 'opencode.json') "HOME=$homeValue" "TMP=$tmpValue" "CLIPY_MCP_ENTRY=$clipyEntry" "VIDEOWIZARD_DIR=$videowizardDir" "FIGMA_SERVER=$figmaServer" "CRAFT_ANYTHING_CLI=$craftAnythingCli"
if ($LASTEXITCODE -ne 0) { Write-Error 'render-config failed'; exit 1 }

# 7) jsonc files 1:1
Copy-Item -Force (Join-Path $repo 'config\opencode-mem.jsonc') (Join-Path $CfgDir 'opencode-mem.jsonc')
Copy-Item -Force (Join-Path $repo 'config\dcp.jsonc') (Join-Path $CfgDir 'dcp.jsonc')

# 8) Skills
$skillsDst = Join-Path $CfgDir 'skills'
New-Item -ItemType Directory -Force $skillsDst | Out-Null
Get-ChildItem (Join-Path $repo 'skills') -Directory | ForEach-Object {
    $dst = Join-Path $skillsDst $_.Name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item -Recurse -Force $_.FullName $dst
}

# 9) Pinned clipy-mcp install
if (-not $SkipInstall) {
    Push-Location (Join-Path $repo 'clipy-mcp')
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { Write-Error 'npm ci failed'; exit 1 }
    } finally { Pop-Location }
}

# 10) Manual steps
Write-Host ''
Write-Host 'Setup done — manual steps remaining:'
Write-Host '  - Provider login: open OpenCode and sign in to your provider'
Write-Host '  - Clipy login: npx -y @clipy/cli@latest login'
Write-Host '  - MCP OAuth (if needed): use /mcps in OpenCode'
