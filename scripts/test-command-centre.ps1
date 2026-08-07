# Phase 7 Application Command Centre tools.
# Usage:
#   .\scripts\test-command-centre.ps1 -Windows
#   .\scripts\test-command-centre.ps1 -Recent
#   .\scripts\test-command-centre.ps1 -Hotkey
#   .\scripts\test-command-centre.ps1 -AppId vscode
#   .\scripts\test-command-centre.ps1 -Browser
#   .\scripts\test-command-centre.ps1 -Destination gmail

param(
    [switch]$Windows,
    [switch]$Recent,
    [switch]$Hotkey,
    [switch]$Browser,
    [string]$AppId = "",
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
    Write-Error "Python venv not found under backend\.venv"
}

Set-Location $backendDir
. $venvActivate

if ($Hotkey) {
    python tools\test_hotkey.py
    exit $LASTEXITCODE
}

if ($Browser -or $Destination) {
    $args = @()
    if ($Destination) {
        $args += @("--focus", $Destination)
    } else {
        $args += @("--status", "--destinations")
    }
    python tools\test_browser_integration.py @args
    exit $LASTEXITCODE
}

$winArgs = @()
if ($Recent) { $winArgs += "--recent" }
elseif ($AppId) { $winArgs += @("--app", $AppId, "--include-safe-titles") }
else { $winArgs += @("--list", "--include-safe-titles") }

python tools\test_windows.py @winArgs
exit $LASTEXITCODE
