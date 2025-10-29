# GNS3 MCP HTTP Server - Automated Service Installation Script
# Run this script as Administrator to install and start the Windows service

$ErrorActionPreference = "Stop"

# Configuration
$ServiceName = "GNS3-MCP-HTTP"
$DisplayName = "GNS3 MCP HTTP Server"
$Description = "MCP server providing HTTP access to GNS3 network labs"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "mcp-server\start_mcp_http.py"
$WorkingDir = Join-Path $ScriptDir "mcp-server"
$LogPath = Join-Path $ScriptDir "mcp-http-server.log"
$EnvPath = Join-Path $ScriptDir ".env"

Write-Host "=== GNS3 MCP HTTP Service Installation ===" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Check if NSSM is installed
$nssmPath = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssmPath) {
    Write-Host "ERROR: NSSM is not installed" -ForegroundColor Red
    Write-Host "Install with: choco install nssm -y" -ForegroundColor Yellow
    exit 1
}

# Auto-detect Python executable
Write-Host "Detecting Python installation..." -ForegroundColor Cyan

$PythonExe = $null

# Try venv first (if it exists in project)
$VenvPath = Join-Path $ScriptDir "venv\Scripts\python.exe"
if (Test-Path $VenvPath) {
    $PythonExe = $VenvPath
    Write-Host "  Found venv Python: $PythonExe" -ForegroundColor Green
} else {
    # Try python from PATH
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        $PythonExe = $PythonCmd.Source
        Write-Host "  Found system Python: $PythonExe" -ForegroundColor Green
    } else {
        # Try py launcher
        $PyCmd = Get-Command py -ErrorAction SilentlyContinue
        if ($PyCmd) {
            $PythonExe = (py -c "import sys; print(sys.executable)" 2>$null)
            if ($PythonExe) {
                Write-Host "  Found Python via py launcher: $PythonExe" -ForegroundColor Green
            }
        }
    }
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Host ""
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Searched locations:" -ForegroundColor Yellow
    Write-Host "  1. venv: $VenvPath"
    Write-Host "  2. PATH: python command"
    Write-Host "  3. py launcher: py command"
    Write-Host ""
    Write-Host "Install Python 3.10+ or activate venv" -ForegroundColor Yellow
    exit 1
}

# Verify Python version
$PythonVersion = & $PythonExe --version 2>&1
Write-Host "  Python version: $PythonVersion" -ForegroundColor Cyan

# Check if script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

# Validate .env file exists
if (-not (Test-Path $EnvPath)) {
    Write-Host ""
    Write-Host "ERROR: .env file not found at $EnvPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Create .env file with required variables:" -ForegroundColor Yellow
    Write-Host "  USER=admin"
    Write-Host "  PASSWORD=your_gns3_password"
    Write-Host "  GNS3_HOST=192.168.1.20"
    Write-Host "  GNS3_PORT=80"
    Write-Host "  HTTP_HOST=127.0.0.1"
    Write-Host "  HTTP_PORT=8100"
    Write-Host "  LOG_LEVEL=INFO"
    Write-Host ""
    exit 1
}

Write-Host "  .env file validated" -ForegroundColor Green
Write-Host ""

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Service '$ServiceName' already exists. Removing..." -ForegroundColor Yellow

    # Stop service if running
    if ($existingService.Status -eq "Running") {
        Write-Host "Stopping service..." -ForegroundColor Yellow
        nssm stop $ServiceName
        Start-Sleep -Seconds 2
    }

    # Remove service
    Write-Host "Removing existing service..." -ForegroundColor Yellow
    nssm remove $ServiceName confirm
    Start-Sleep -Seconds 1
}

Write-Host "Installing service '$ServiceName'..." -ForegroundColor Green

# Install service
nssm install $ServiceName $PythonExe $ScriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install service" -ForegroundColor Red
    exit 1
}

# Configure service
Write-Host "Configuring service..." -ForegroundColor Green

# Set display name and description
nssm set $ServiceName DisplayName $DisplayName
nssm set $ServiceName Description $Description

# Set working directory
nssm set $ServiceName AppDirectory $WorkingDir

# Configure startup
nssm set $ServiceName Start SERVICE_AUTO_START

# Configure restart on failure
nssm set $ServiceName AppThrottle 1500
nssm set $ServiceName AppStopMethodSkip 0
nssm set $ServiceName AppStopMethodConsole 1500
nssm set $ServiceName AppStopMethodWindow 1500
nssm set $ServiceName AppStopMethodThreads 1500

# Configure restart behavior
nssm set $ServiceName AppExit Default Restart
nssm set $ServiceName AppRestartDelay 5000

# Configure logging
nssm set $ServiceName AppStdout $LogPath
nssm set $ServiceName AppStderr $LogPath

# Rotate logs (10MB max)
nssm set $ServiceName AppRotateFiles 1
nssm set $ServiceName AppRotateOnline 1
nssm set $ServiceName AppRotateBytes 10485760

Write-Host ""
Write-Host "=== Service Installed Successfully ===" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Service Name:    $ServiceName"
Write-Host "  Display Name:    $DisplayName"
Write-Host "  Python:          $PythonExe"
Write-Host "  Script:          $ScriptPath"
Write-Host "  Log File:        $LogPath"
Write-Host "  HTTP Endpoint:   http://127.0.0.1:8100/mcp/"
Write-Host ""

# Auto-start the service
Write-Host "Starting service..." -ForegroundColor Green
nssm start $ServiceName
Start-Sleep -Seconds 3

$status = nssm status $ServiceName
if ($status -match "SERVICE_RUNNING") {
    Write-Host "Service started successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Management Commands:" -ForegroundColor Yellow
    Write-Host "  Stop:    nssm stop $ServiceName"
    Write-Host "  Restart: nssm restart $ServiceName"
    Write-Host "  Status:  nssm status $ServiceName"
    Write-Host "  Remove:  nssm remove $ServiceName confirm"
    Write-Host ""
    Write-Host "View logs:" -ForegroundColor Cyan
    Write-Host "  Get-Content '$LogPath' -Tail 50 -Wait"
} else {
    Write-Host "WARNING: Service may not have started correctly" -ForegroundColor Yellow
    Write-Host "Status: $status" -ForegroundColor Yellow
    Write-Host "Check logs at: $LogPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
