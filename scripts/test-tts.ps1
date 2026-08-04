# Test offline Piper TTS using production TtsService.
# Usage:
#   .\scripts\test-tts.ps1
#   .\scripts\test-tts.ps1 -DeviceId 4
#   .\scripts\test-tts.ps1 -ListDevices
#   .\scripts\test-tts.ps1 -Line 1

param(
    [int]$DeviceId = -1,
    [int]$Line = 0,
    [switch]$ListDevices
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendDir = Join-Path $repoRoot "backend"
$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"
$model = Join-Path $backendDir "voices\en_GB-alan-medium\en_GB-alan-medium.onnx"
$config = Join-Path $backendDir "voices\en_GB-alan-medium\en_GB-alan-medium.onnx.json"

if (-not (Test-Path $venvActivate)) {
    Write-Error "Python venv not found. Create it under backend\.venv and install requirements-dev.txt"
}

if (-not (Test-Path $model) -or -not (Test-Path $config)) {
    Write-Warning "Piper voice files missing. See backend\voices\README.md"
}

Set-Location $backendDir
. $venvActivate

Write-Host "Checking Piper configuration..."
if (-not (Get-Command piper -ErrorAction SilentlyContinue)) {
    $envPath = Join-Path $backendDir ".env"
    if (Test-Path $envPath) {
        $piperLine = Select-String -Path $envPath -Pattern "^PIPER_EXECUTABLE_PATH=" | Select-Object -First 1
        if ($piperLine) {
            Write-Host "  $($piperLine.Line)"
        } else {
            Write-Warning "piper.exe not on PATH and PIPER_EXECUTABLE_PATH may be unset"
        }
    }
}

if ($ListDevices) {
    python tools\test_tts.py --list-devices
    exit $LASTEXITCODE
}

$argList = @()
if ($DeviceId -ge 0) { $argList += @("--device-id", "$DeviceId") }
if ($Line -ge 1 -and $Line -le 3) {
    $argList += @("--line", "$Line")
} else {
    $argList += "--welcome"
}

python tools\test_tts.py @argList
exit $LASTEXITCODE
