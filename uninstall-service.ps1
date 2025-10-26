# GNS3 MCP HTTP Server - Service Uninstallation Script
# Run this script as Administrator to remove the Windows service

$ErrorActionPreference = "Stop"

$ServiceName = "GNS3-MCP-HTTP"

Write-Host "=== GNS3 MCP HTTP Service Uninstallation ===" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Check if service exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $existingService) {
    Write-Host "Service '$ServiceName' is not installed" -ForegroundColor Yellow
    exit 0
}

Write-Host "Found service '$ServiceName'" -ForegroundColor Yellow
Write-Host "Status: $($existingService.Status)" -ForegroundColor Cyan
Write-Host ""

# Confirm removal
$response = Read-Host "Remove this service? (y/N)"
if ($response -ne "y" -and $response -ne "Y") {
    Write-Host "Uninstallation cancelled" -ForegroundColor Yellow
    exit 0
}

# Stop service if running
if ($existingService.Status -eq "Running") {
    Write-Host "Stopping service..." -ForegroundColor Yellow
    nssm stop $ServiceName
    Start-Sleep -Seconds 2
}

# Remove service
Write-Host "Removing service..." -ForegroundColor Green
nssm remove $ServiceName confirm

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Service removed successfully!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to remove service" -ForegroundColor Red
    exit 1
}
