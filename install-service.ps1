# GNS3 MCP HTTP Server - Service Installation Script
# Run this script as Administrator to install the Windows service

$ErrorActionPreference = "Stop"

# Configuration
$ServiceName = "GNS3-MCP-HTTP"
$DisplayName = "GNS3 MCP HTTP Server"
$Description = "MCP server providing HTTP access to GNS3 network labs"
$PythonExe = "C:\Users\mail4\AppData\Local\Programs\Python\Python313\python.exe"
$ScriptPath = "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server\start_mcp_http.py"
$WorkingDir = "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server"
$LogPath = "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log"

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

# Check if Python exists
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python not found at $PythonExe" -ForegroundColor Red
    exit 1
}

# Check if script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Script not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

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
Write-Host "Service Name:    $ServiceName" -ForegroundColor Cyan
Write-Host "Display Name:    $DisplayName" -ForegroundColor Cyan
Write-Host "Log File:        $LogPath" -ForegroundColor Cyan
Write-Host "HTTP Endpoint:   http://127.0.0.1:8100/mcp/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Management Commands:" -ForegroundColor Yellow
Write-Host "  Start:   nssm start $ServiceName"
Write-Host "  Stop:    nssm stop $ServiceName"
Write-Host "  Restart: nssm restart $ServiceName"
Write-Host "  Status:  nssm status $ServiceName"
Write-Host "  Remove:  nssm remove $ServiceName confirm"
Write-Host ""

# Ask if user wants to start the service now
$response = Read-Host "Start the service now? (Y/n)"
if ($response -eq "" -or $response -eq "Y" -or $response -eq "y") {
    Write-Host "Starting service..." -ForegroundColor Green
    nssm start $ServiceName
    Start-Sleep -Seconds 2

    $status = nssm status $ServiceName
    if ($status -match "SERVICE_RUNNING") {
        Write-Host "Service started successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Check service health:" -ForegroundColor Cyan
        Write-Host "  curl http://127.0.0.1:8100/health"
        Write-Host ""
        Write-Host "View logs:" -ForegroundColor Cyan
        Write-Host "  Get-Content '$LogPath' -Tail 50 -Wait"
    } else {
        Write-Host "WARNING: Service may not have started correctly" -ForegroundColor Yellow
        Write-Host "Status: $status" -ForegroundColor Yellow
        Write-Host "Check logs at: $LogPath" -ForegroundColor Yellow
    }
} else {
    Write-Host "Service installed but not started" -ForegroundColor Yellow
    Write-Host "Start manually with: nssm start $ServiceName" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
