# Test Windows workspace launching using production WorkspaceService.
# Usage:
#   .\scripts\test-workspace.ps1 -List
#   .\scripts\test-workspace.ps1 -Status
#   .\scripts\test-workspace.ps1 -AppId vscode
#   .\scripts\test-workspace.ps1
#   .\scripts\test-workspace.ps1 -NoFocus

param(
    [string]$AppId = "",
    [switch]$List,
    [switch]$Status,
    [switch]$NoFocus,
    [switch]$FocusOnly
)

$ErrorActionPreference = "Stop"

if ($env:OS -notlike "*Windows*") {
    Write-Error "Phase 4 workspace tools require Windows."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"
$configPath = Join-Path $backendDir "config\applications.json"

if (-not (Test-Path $venvActivate)) {
    Write-Error "Python venv not found under backend\.venv"
}

if (-not (Test-Path $configPath)) {
    Write-Warning "applications.json missing at $configPath"
}

Set-Location $backendDir
. $venvActivate

$argList = @()
if ($List) { $argList += "--list" }
elseif ($Status) { $argList += "--status" }
elseif ($AppId) {
    $argList += @("--app", $AppId)
    if ($FocusOnly) { $argList += "--focus-only" }
}
else {
    $argList += "--start"
    if ($NoFocus) { $argList += "--no-focus" }
}

python tools\test_workspace.py @argList
exit $LASTEXITCODE
