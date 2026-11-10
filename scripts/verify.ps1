param(
    [string]$CfgDir = "$env:USERPROFILE\.config\opencode"
)

$fail = 0

# 1. Rendered config exists and has no leftover template tokens
$cfgFile = Join-Path $CfgDir 'opencode.json'
if (-not (Test-Path $cfgFile)) {
    Write-Host "[fail] config: $cfgFile not found"
    $fail = 1
}
else {
    $text = Get-Content $cfgFile -Raw
    if ($text.Contains('{{')) {
        Write-Host "[fail] config: leftover {{...}} placeholder"
        $fail = 1
    }
    else {
        Write-Host "[ok] config: $cfgFile (no placeholders)"
    }
}

# 2. Rendered config parses as JSON (node check)
if (Test-Path $cfgFile) {
    node -e "JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))" "$cfgFile"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[fail] config: JSON parse failed"
        $fail = 1
    }
    else {
        Write-Host "[ok] config: valid JSON"
    }
}

# 3. Skills: at least 8 folders
$skillsDir = Join-Path $CfgDir 'skills'
$count = 0
if (Test-Path $skillsDir) {
    $count = (Get-ChildItem $skillsDir -Directory).Count
}
if ($count -lt 8) {
    Write-Host "[fail] skills: $count found (< 8)"
    $fail = 1
}
else {
    Write-Host "[ok] skills: $count"
}

# 4. Memory status line (export age + import hint)
$repo = Split-Path $PSScriptRoot -Parent
$export = Join-Path $repo 'memory\export.json'
if (Test-Path $export) {
    $days = [int](New-TimeSpan -Start (Get-Item $export).LastWriteTime).Days
    if ($days -gt 7) {
        Write-Host "[info] memory export: $days days old - refresh with snapshot on the maintained machine"
    }
    else {
        Write-Host "[info] memory export: fresh ($days days) - import with the memory tool (mode=import)"
    }
}
else {
    Write-Host "[info] memory export: missing - run snapshot on the maintained machine"
}

exit $fail
