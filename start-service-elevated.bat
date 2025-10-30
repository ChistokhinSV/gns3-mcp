@echo off
REM Start GNS3 MCP HTTP service with admin elevation
REM The service will run in background with visible console window (AppNoConsole=0)

powershell -Command "Start-Process powershell -ArgumentList '-Command','nssm start GNS3-MCP-HTTP; Write-Host \"Service started. Check console window for server output.\"; Write-Host \"Press Ctrl+C in console window or run stop-service-elevated.bat to stop.\"; Write-Host \"\"; Write-Host \"Service status:\"; nssm status GNS3-MCP-HTTP' -Verb RunAs"
