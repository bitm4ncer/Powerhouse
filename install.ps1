# Powerhouse installer - Windows.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\setup.ps1') @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
