$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot "backend"
Set-Location $backendDir

$venvActivate = Join-Path $backendDir ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "Virtual environment not found at backend\.venv" -ForegroundColor Yellow
    Write-Host "Create it with:" -ForegroundColor Yellow
    Write-Host "  cd `"$backendDir`""
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements-dev.txt"
    exit 1
}

. $venvActivate

Write-Host "Starting Jarvis backend (Uvicorn reload)..." -ForegroundColor Cyan
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
