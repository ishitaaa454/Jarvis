$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $projectRoot "frontend"
Set-Location $frontendDir

$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "Frontend dependencies not installed (node_modules missing)." -ForegroundColor Yellow
    Write-Host "Install them with:" -ForegroundColor Yellow
    Write-Host "  cd `"$frontendDir`""
    Write-Host "  npm install"
    exit 1
}

Write-Host "Starting Jarvis frontend (Vite)..." -ForegroundColor Cyan
npm run dev
