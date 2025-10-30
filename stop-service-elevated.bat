@echo off
REM Stop GNS3 MCP HTTP service with admin elevation
REM Watch the console window to verify graceful shutdown logs appear

powershell -Command "Start-Process powershell -ArgumentList '-Command','Write-Host \"Stopping GNS3 MCP HTTP service...\"; Write-Host \"Watch the server console window for shutdown logs.\"; Write-Host \"\"; nssm stop GNS3-MCP-HTTP; Start-Sleep -Seconds 15; Write-Host \"\"; Write-Host \"Service status:\"; nssm status GNS3-MCP-HTTP; Write-Host \"\"; Read-Host \"Press Enter to close\"' -Verb RunAs"
