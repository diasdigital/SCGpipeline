<#
.SYNOPSIS
    Runs the entire SCGpipeline stack in a single command.
.PARAMETER NoMLflow
    Skip MLflow UI.
.PARAMETER NoDB
    Skip MySQL check.
.EXAMPLE
    .\start.ps1
    .\start.ps1 -NoMLflow
    .\start.ps1 -NoDB
#>
param(
    [switch]$NoMLflow,
    [switch]$NoDB
)

function Write-Step  { param($msg) Write-Host "  $msg"   -ForegroundColor Cyan   }
function Write-OK    { param($msg) Write-Host "  v $msg" -ForegroundColor Green  }
function Write-Warn  { param($msg) Write-Host "  ! $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "  x $msg" -ForegroundColor Red    }
function Write-Title { param($msg) Write-Host "`n$msg"   -ForegroundColor White  }

$ProjectRoot = $PSScriptRoot
$Shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Fail ".env file not found. Run the script from the project root folder."
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "        SCGpipeline -- Start Script         " -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

# Read LLM_PROVIDER from .env
$LlmProvider = "ollama"
foreach ($line in Get-Content "$ProjectRoot\.env") {
    if ($line -match '^\s*LLM_PROVIDER\s*=\s*([^\s#]+)') {
        $LlmProvider = $Matches[1].Trim()
        break
    }
}
Write-Step "LLM Provider: $LlmProvider"

# ============================================================
# 1. CHECK PREREQUISITES
# ============================================================
Write-Title "[ 1/4 ] Checking prerequisites..."

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Fail "uv not found. Install: https://docs.astral.sh/uv"
    exit 1
}
Write-OK "uv found"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Fail "npm not found. Install Node.js: https://nodejs.org"
    exit 1
}
Write-OK "npm found"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "Docker not found. Install Docker Desktop."
    exit 1
}
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop is not running. Open Docker Desktop and try again."
    exit 1
}
Write-OK "Docker running"

if (-not $NoDB) {
    $mysqlUp = Test-NetConnection -ComputerName 127.0.0.1 -Port 3306 `
        -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    if (-not $mysqlUp.TcpTestSucceeded) {
        Write-Warn "MySQL (port 3306) is not running."
        Write-Warn "Start Laragon, then press Enter to continue."
        Read-Host "  Press Enter after Laragon is running"
    } else {
        Write-OK "MySQL detected on port 3306"
    }
}

if ($LlmProvider -eq "ollama") {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Warn "ollama not found in PATH. Download: https://ollama.ai"
    } else {
        Write-OK "ollama found"
    }
}

# ============================================================
# 2. START REDIS
# ============================================================
Write-Title "[ 2/4 ] Starting Redis..."

Set-Location $ProjectRoot
docker compose up -d redis 2>&1 | Out-Null

$redisReady = $false
for ($i = 0; $i -lt 15; $i++) {
    $ping = docker exec scgpipeline-redis redis-cli ping 2>$null
    if ($ping -eq "PONG") { $redisReady = $true; break }
    Start-Sleep -Seconds 1
}
if ($redisReady) { Write-OK "Redis ready at localhost:6379" }
else             { Write-Warn "Redis has not responded to PING, but proceeding anyway." }

# ============================================================
# 3. CHECK FRONTEND DEPENDENCIES
# ============================================================
Write-Title "[ 3/4 ] Checking frontend dependencies..."

if (-not (Test-Path "$ProjectRoot\frontend\node_modules")) {
    Write-Step "Running npm install..."
    Set-Location "$ProjectRoot\frontend"
    npm install --silent
    Set-Location $ProjectRoot
    Write-OK "npm install finished"
} else {
    Write-OK "node_modules already exists"
}

# ============================================================
# 4. START ALL SERVICES (each in its own window)
# ============================================================
Write-Title "[ 4/4 ] Starting all services..."

# Helper: open a new window with a specific title and command
function Start-Service {
    param(
        [string]$Title,
        [string]$Command
    )
    # Set window title via $host.UI.RawUI.WindowTitle before running command
    $fullCmd = "`$host.UI.RawUI.WindowTitle = '$Title'; $Command"
    Start-Process $Shell -ArgumentList "-NoExit", "-Command", $fullCmd
    Start-Sleep -Milliseconds 600
    Write-OK "Opening: $Title"
}

Start-Service `
    -Title   "SCGpipeline - Backend" `
    -Command "Set-Location '$ProjectRoot'; uv run uvicorn app.main:app --reload"

Start-Service `
    -Title   "SCGpipeline - Celery" `
    -Command "Set-Location '$ProjectRoot'; uv run celery -A app.services.detection_task.celery_app worker --loglevel=info --pool=solo"

Start-Service `
    -Title   "SCGpipeline - Frontend" `
    -Command "Set-Location '$ProjectRoot\frontend'; npm run dev"

if (-not $NoMLflow) {
    Start-Service `
        -Title   "SCGpipeline - MLflow" `
        -Command "Set-Location '$ProjectRoot'; uv run mlflow ui --port 5000"
}

if ($LlmProvider -eq "ollama") {
    Start-Service `
        -Title   "SCGpipeline - Ollama" `
        -Command "ollama serve"
}

# ============================================================
# FINISHED
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  All services are starting up. URLs:" -ForegroundColor Green
Write-Host ""
Write-Host "    Frontend  -->  http://localhost:5174" -ForegroundColor Green
Write-Host "    Backend   -->  http://localhost:8000" -ForegroundColor Green
Write-Host "    API Docs  -->  http://localhost:8000/docs" -ForegroundColor Green
if (-not $NoMLflow) {
    Write-Host "    MLflow    -->  http://localhost:5000" -ForegroundColor Green
}
Write-Host ""
Write-Host "  To stop everything:  .\stop.ps1" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""