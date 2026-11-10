# snapshot.ps1 — Sync this machine's live OpenCode setup back into the repository.
# Usage: powershell -NoProfile -File scripts\snapshot.ps1 [-CfgDir <dir>] [-DryRun]
param(
  [string]$CfgDir = "$env:USERPROFILE\.config\opencode",
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent

$live = Join-Path $CfgDir 'opencode.json'
if (-not (Test-Path $live)) { Write-Error "No opencode.json at $live"; exit 1 }

$secretPattern = 'service\.json|\.auth-token|\.db($|/)|node_modules'

function Invoke-Git {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
  git -C $repo @GitArgs
  if ($LASTEXITCODE -ne 0) {
    Write-Error ("git " + ($GitArgs -join ' ') + " failed with exit code $LASTEXITCODE")
    exit 1
  }
}

function Get-Offenders {
  param([string[]]$Paths)
  return @($Paths | Where-Object { $_ -match $secretPattern })
}

function Assert-NoSecrets {
  $stagedRaw = git -C $repo diff --cached --name-only -z
  if ($LASTEXITCODE -ne 0) { Write-Error 'git diff --cached failed'; exit 1 }
  $staged = @()
  if ($stagedRaw) { $staged = @($stagedRaw -split "`0" | Where-Object { $_ }) }

  $treeRaw = git -C $repo status --porcelain -z
  if ($LASTEXITCODE -ne 0) { Write-Error 'git status failed'; exit 1 }
  $tree = @()
  if ($treeRaw) { $tree = @($treeRaw -split "`0" | Where-Object { $_ } | ForEach-Object { $_.Substring(3) }) }

  $offenders = @((Get-Offenders ($staged + $tree)) | Sort-Object -Unique)
  if ($offenders.Count -gt 0) {
    Write-Error ("SECRET GUARD: refusing to snapshot the following paths: " + ($offenders -join ', '))
    exit 1
  }
}

$renderer = Join-Path $repo 'scripts\render-config.js'
$clipyRepo = "$repo\clipy-mcp\node_modules\@clipy\mcp\dist\index.js"
$clipyLegacy = "$env:USERPROFILE\.clipy-mcp\node_modules\@clipy\mcp\dist\index.js"

function Invoke-Renderer {
  param([string]$Mode, [string]$InPath, [string]$OutPath)
  node $renderer $Mode $InPath $OutPath "CLIPY_MCP_ENTRY=$clipyRepo" "CLIPY_MCP_ENTRY=$clipyLegacy" "TMP=$env:TEMP" "HOME=$env:USERPROFILE" "VIDEOWIZARD_DIR=C:\GitHub\VideoWizard"
  if ($LASTEXITCODE -ne 0) { Write-Error "render-config ($Mode) failed"; exit 1 }
}

function Get-FolderFingerprint([string]$path) {
  $lines = Get-ChildItem $path -Recurse -File | Sort-Object FullName | ForEach-Object {
    $_.FullName.Substring($path.Length) + '|' + (Get-FileHash $_.FullName -Algorithm SHA256).Hash
  }
  return ($lines -join "`n")
}

# --- 1. Guard first: never snapshot secrets, even already-staged ones --------
Assert-NoSecrets

# --- 2. Skills union: .config > .claude > .agents; first occurrence wins -----
$sources = @(
  (Join-Path $CfgDir 'skills'),
  "$env:USERPROFILE\.claude\skills",
  "$env:USERPROFILE\.agents\skills"
)
$chosen = @{}
foreach ($src in $sources) {
  if (-not (Test-Path $src)) { continue }
  foreach ($d in Get-ChildItem $src -Directory) {
    if (-not $chosen.ContainsKey($d.Name)) { $chosen[$d.Name] = $d.FullName }
  }
}
$repoSkills = Join-Path $repo 'skills'
$stale = @()
foreach ($d in Get-ChildItem $repoSkills -Directory) {
  if (-not $chosen.ContainsKey($d.Name)) { $stale += $d.Name }
}
$tplPath = Join-Path $repo 'config\opencode.json.tpl'

# --- 3. Dry run: read-only report (no repo writes) ---------------------------
if ($DryRun) {
  $tmpOut = Join-Path $env:TEMP ("powerhouse-snapshot-check-" + [guid]::NewGuid().ToString('N') + ".tpl")
  Invoke-Renderer reverse $live $tmpOut
  $same = (Test-Path $tplPath) -and ([System.IO.File]::ReadAllText($tplPath) -eq [System.IO.File]::ReadAllText($tmpOut))
  Remove-Item $tmpOut -Force
  if ($same) { Write-Host 'template: unchanged' } else { Write-Host 'template: would update' }
  foreach ($name in ($chosen.Keys | Sort-Object)) {
    if (-not (Test-Path (Join-Path $repoSkills $name))) { Write-Host "skills/$name would add"; continue }
    if ((Get-FolderFingerprint $chosen[$name]) -ne (Get-FolderFingerprint (Join-Path $repoSkills $name))) {
      Write-Host "skills/$name would update"
    }
  }
  foreach ($name in ($stale | Sort-Object)) { Write-Host "stale (not deleted): $name" }
  foreach ($f in @('opencode-mem.jsonc', 'dcp.jsonc')) {
    $srcF = Join-Path $CfgDir $f
    if (-not (Test-Path $srcF)) { continue }
    $dstF = Join-Path $repo "config\$f"
    if (-not (Test-Path $dstF) -or ([System.IO.File]::ReadAllText($srcF) -ne [System.IO.File]::ReadAllText($dstF))) {
      Write-Host "config/$f would update"
    }
  }
  $mem = Join-Path $repo 'memory\export.json'
  $staleMem = $true
  if (Test-Path $mem) { $staleMem = ((Get-Date) - (Get-Item $mem).LastWriteTime).TotalDays -gt 7 }
  if ($staleMem) { Write-Host "MEMORY: Run in OpenCode: memory export to $mem (missing or older than 7 days)" }
  Write-Host 'DRY RUN - no files were written'
  git -C $repo status --short
  exit 0
}

# --- 4. Live run: writes, then commit + push ---------------------------------
Invoke-Renderer reverse $live $tplPath
Write-Host "Rendered template: $tplPath"

foreach ($name in ($chosen.Keys | Sort-Object)) {
  $target = Join-Path $repoSkills $name
  if (Test-Path $target) { Remove-Item $target -Recurse -Force }
  Copy-Item $chosen[$name] $target -Recurse -Force
}
Write-Host ("Synced skills: " + (($chosen.Keys | Sort-Object) -join ', '))
foreach ($name in ($stale | Sort-Object)) { Write-Host "stale (not deleted): $name" }

foreach ($f in @('opencode-mem.jsonc', 'dcp.jsonc')) {
  $srcF = Join-Path $CfgDir $f
  if (Test-Path $srcF) { Copy-Item $srcF (Join-Path $repo "config\$f") -Force }
}

$mem = Join-Path $repo 'memory\export.json'
$staleMem = $true
if (Test-Path $mem) { $staleMem = ((Get-Date) - (Get-Item $mem).LastWriteTime).TotalDays -gt 7 }
if ($staleMem) { Write-Host "MEMORY: Run in OpenCode: memory export to $mem (missing or older than 7 days)" }

Invoke-Git add -A

$stagedRaw = git -C $repo diff --cached --name-only -z
if ($LASTEXITCODE -ne 0) { Write-Error 'git diff --cached failed'; exit 1 }
$staged = @()
if ($stagedRaw) { $staged = @($stagedRaw -split "`0" | Where-Object { $_ }) }
$offenders = Get-Offenders $staged
if ($offenders.Count -gt 0) {
  git -C $repo reset -q
  Write-Error ("SECRET GUARD: refusing to commit the following paths: " + ($offenders -join ', '))
  exit 1
}

git -C $repo diff --cached --quiet
$rc = $LASTEXITCODE
if ($rc -eq 0) { Write-Host 'nothing to snapshot'; exit 0 }
if ($rc -ne 1) { Write-Error "git diff --cached --quiet failed with exit code $rc"; exit 1 }

Invoke-Git commit -m ("snapshot: " + (Get-Date -Format 'yyyy-MM-dd HH:mm'))
Invoke-Git push
Write-Host 'snapshot pushed'
