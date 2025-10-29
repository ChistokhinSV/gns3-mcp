# Configure GNS3-MCP-HTTP service with nssm
$ServiceName = "GNS3-MCP-HTTP"
$DisplayName = "GNS3 MCP HTTP Server"
$Description = "MCP server providing HTTP access to GNS3 network labs"
$WorkingDir = "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-server"
$LogPath = "C:\HOME\1. Scripts\008. GNS3 MCP\mcp-http-server.log"

Write-Host "Configuring service $ServiceName..." -ForegroundColor Cyan

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

Write-Host "Configuration complete!" -ForegroundColor Green
