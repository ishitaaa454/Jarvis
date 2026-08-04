# Test the offline wake-phrase listener using the backend VoiceService.
# Usage:
#   .\scripts\test-wake-listener.ps1
#   .\scripts\test-wake-listener.ps1 -DeviceId 1
#   .\scripts\test-wake-listener.ps1 -ListDevices

param(
    [int]$DeviceId = -1,
    [switch]$ListDevices
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"
$modelDir = Join-Path $backendDir "models\vosk-model-small-en-us"

if (-not (Test-Path $venvActivate)) {
    Write-Error "Python virtual environment not found at $venvActivate. Create it with: cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt"
}

if (-not (Test-Path (Join-Path $modelDir "am"))) {
    Write-Warning "Vosk model not found at $modelDir"
    Write-Host "Download a small English model and extract it. See backend\models\README.md"
}

Set-Location $backendDir
. $venvActivate

Write-Host "Windows microphone permissions:"
Write-Host "  Settings > Privacy & security > Microphone > allow desktop apps"
Write-Host "  Close apps that may hold the mic exclusively (Zoom, Teams, etc.)"
Write-Host ""

if ($ListDevices) {
    python tools\test_wake_phrase.py --list-devices
    exit $LASTEXITCODE
}

if ($DeviceId -ge 0) {
    python tools\test_wake_phrase.py --device-id $DeviceId
} else {
    python tools\test_wake_phrase.py
}

exit $LASTEXITCODE
