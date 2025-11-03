# Set Windows Environment Variables from .env file
# Run this script as Administrator to set system-wide environment variables
# Usage:
#   As Admin: .\set-env-vars.ps1
#   User-level only: .\set-env-vars.ps1 -UserLevel

param(
    [switch]$UserLevel
)

$ErrorActionPreference = "Stop"

# Check if running as Administrator (unless -UserLevel is specified)
if (-not $UserLevel) {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "ERROR: This script must be run as Administrator to set system environment variables" -ForegroundColor Red
        Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Alternatively, run with -UserLevel flag to set user-level variables only:" -ForegroundColor Yellow
        Write-Host "  .\set-env-vars.ps1 -UserLevel" -ForegroundColor Cyan
        exit 1
    }
}

# Determine target level
$target = if ($UserLevel) { "User" } else { "Machine" }
Write-Host "=== Setting Environment Variables ($target level) ===" -ForegroundColor Green
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $scriptDir ".env"

# Check if .env exists
if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found at: $envFile" -ForegroundColor Red
    Write-Host "Create a .env file first with your GNS3 credentials" -ForegroundColor Yellow
    exit 1
}

# Read .env file
Write-Host "Reading .env file: $envFile" -ForegroundColor Cyan
$envVars = @{}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    # Skip comments and empty lines
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            $envVars[$key] = $value
        }
    }
}

Write-Host "Found $($envVars.Count) variables" -ForegroundColor Green
Write-Host ""

# List of variables to set (only the ones needed for service)
$requiredVars = @(
    "GNS3_USER",
    "GNS3_PASSWORD",
    "GNS3_HOST",
    "GNS3_PORT",
    "HTTP_HOST",
    "HTTP_PORT",
    "LOG_LEVEL",
    "MCP_API_KEY",
    "GNS3_USE_HTTPS",
    "GNS3_VERIFY_SSL"
)

# Also check old variable names for backward compatibility
$compatibilityMap = @{
    "USER" = "GNS3_USER"
    "PASSWORD" = "GNS3_PASSWORD"
}

# Set environment variables
$setCount = 0
$skippedCount = 0

foreach ($varName in $requiredVars) {
    $value = $null

    # Try to get value from .env
    if ($envVars.ContainsKey($varName)) {
        $value = $envVars[$varName]
    }
    # Check compatibility mapping
    elseif ($compatibilityMap.ContainsKey($varName)) {
        $oldName = $compatibilityMap[$varName]
        if ($envVars.ContainsKey($oldName)) {
            $value = $envVars[$oldName]
            Write-Host "  Using $oldName -> $varName (compatibility)" -ForegroundColor Yellow
        }
    }

    if ($value) {
        # Mask password in output
        $displayValue = if ($varName -like "*PASSWORD*" -or $varName -like "*KEY*") { "***HIDDEN***" } else { $value }
        Write-Host "Setting $varName = $displayValue" -ForegroundColor Cyan
        [Environment]::SetEnvironmentVariable($varName, $value, $target)
        $setCount++
    }
    else {
        Write-Host "Skipping $varName (not found in .env)" -ForegroundColor Gray
        $skippedCount++
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Green
Write-Host "Set: $setCount variables" -ForegroundColor Green
Write-Host "Skipped: $skippedCount variables (not in .env)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Environment variables set successfully at $target level!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart any open command prompts/PowerShell windows" -ForegroundColor White
Write-Host "  2. Install/reinstall the service: .\server.cmd reinstall" -ForegroundColor White
Write-Host "  3. Check service status: .\server.cmd status" -ForegroundColor White
Write-Host ""
