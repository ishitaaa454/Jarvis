# Test Phase 6 system monitoring using production SystemMonitorService.
# Usage:
#   .\scripts\test-system-monitor.ps1 -Snapshot
#   .\scripts\test-system-monitor.ps1 -Watch -Seconds 30
#   .\scripts\test-system-monitor.ps1 -Processes
#   .\scripts\test-system-monitor.ps1 -Capabilities
#   .\scripts\test-system-monitor.ps1 -Disks
#   .\scripts\test-system-monitor.ps1 -Network
#   .\scripts\test-system-monitor.ps1 -Gpu
#   .\scripts\test-system-monitor.ps1 -Temperatures

param(
    [switch]$Capabilities,
    [switch]$Snapshot,
    [switch]$Watch,
    [switch]$Processes,
    [switch]$Disks,
    [switch]$Network,
    [switch]$Gpu,
    [switch]$Temperatures,
    [double]$Seconds = 30
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

$argList = @()
if ($Capabilities) { $argList += "--capabilities" }
elseif ($Watch) {
    $argList += @("--watch", "--seconds", "$Seconds")
}
elseif ($Processes) { $argList += "--processes" }
elseif ($Disks) { $argList += "--disks" }
elseif ($Network) { $argList += "--network" }
elseif ($Gpu) { $argList += "--gpu" }
elseif ($Temperatures) { $argList += "--temperatures" }
else {
    $argList += "--snapshot"
}

python tools\test_system_monitor.py @argList
exit $LASTEXITCODE
