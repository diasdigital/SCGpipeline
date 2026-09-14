<#
.SYNOPSIS
    Stops all SCGpipeline services.
.PARAMETER KeepRedis
    Do not stop Redis.
.EXAMPLE
    .\stop.ps1
    .\stop.ps1 -KeepRedis
#>
param([switch]$KeepRedis)

function Write-OK   { param($msg) Write-Host "  v $msg" -ForegroundColor Green  }
function Write-Step { param($msg) Write-Host "  $msg"   -ForegroundColor Cyan   }
function Write-Warn { param($msg) Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "============================================" -ForegroundColor Red
Write-Host "        SCGpipeline -- Stop Script          " -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""

Write-Step "Stopping Python processes..."
$pythonProcs = Get-Process python, python3 -ErrorAction SilentlyContinue
if ($pythonProcs) {
    $pythonProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-OK "Python processes stopped ($($pythonProcs.Count) processes)"
} else {
    Write-Warn "No Python processes running"
}

Write-Step "Stopping Node.js processes (Vite)..."
$nodeProcs = Get-Process node -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        $cmdLine -like "*vite*" -or $cmdLine -like "*npm*"
    } catch { $false }
}
if ($nodeProcs) {
    $nodeProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-OK "Node.js processes stopped"
} else {
    Write-Warn "No Vite processes found"
}

if (-not $KeepRedis) {
    Write-Step "Stopping Redis container..."
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        $ProjectRoot = $PSScriptRoot
        if (Test-Path "$ProjectRoot\docker-compose.yml") {
            Set-Location $ProjectRoot
            docker compose stop redis 2>&1 | Out-Null
            Write-OK "Redis container stopped"
        }
    } else {
        Write-Warn "Docker unavailable, skipping"
    }
} else {
    Write-Warn "Redis left running (-KeepRedis)"
}

Write-Host ""
Write-OK "All SCGpipeline services stopped."
Write-Host "  Laragon/MySQL untouched -- stop manually if needed." -ForegroundColor Gray
Write-Host "  Ollama untouched -- stop manually if needed." -ForegroundColor Gray
Write-Host ""