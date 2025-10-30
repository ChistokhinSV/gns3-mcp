@echo off
REM GNS3 MCP HTTP Server Management Script
REM Usage: server.cmd [install|uninstall|reinstall|status]
REM   (no params) - Start server directly with venv auto-setup
REM   install     - Install as Windows service
REM   uninstall   - Remove Windows service
REM   reinstall   - Reinstall Windows service
REM   status      - Show service status

setlocal enabledelayedexpansion

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "SERVER_DIR=%SCRIPT_DIR%\mcp-server"
set "REQUIREMENTS=%SCRIPT_DIR%\requirements.txt"
set "SERVICE_NAME=GNS3-MCP-HTTP"

REM Check for NSSM
where nssm >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: nssm not found in PATH
    echo Install NSSM from https://nssm.cc/ or add to PATH
    exit /b 1
)

REM Parse command
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=start"

if /i "%COMMAND%"=="install" goto :install
if /i "%COMMAND%"=="uninstall" goto :uninstall
if /i "%COMMAND%"=="reinstall" goto :reinstall
if /i "%COMMAND%"=="status" goto :status
if /i "%COMMAND%"=="start" goto :start

echo Unknown command: %COMMAND%
echo Usage: server.cmd [install^|uninstall^|reinstall^|status]
exit /b 1

:start
echo === GNS3 MCP HTTP Server ===
echo.
call :check_venv
if %errorlevel% neq 0 exit /b 1

echo Starting server...
cd /d "%SERVER_DIR%"
"%VENV_PYTHON%" start_mcp_http.py
exit /b %errorlevel%

:install
echo === Installing GNS3 MCP HTTP Service ===
echo.
call :check_venv
if %errorlevel% neq 0 exit /b 1

REM Check if already installed
nssm status %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo Service already installed. Use 'reinstall' to update.
    exit /b 1
)

echo Installing service...
nssm install %SERVICE_NAME% "%VENV_PYTHON%" start_mcp_http.py
if %errorlevel% neq 0 (
    echo ERROR: Failed to install service
    exit /b 1
)

REM Configure service
echo Configuring service...
nssm set %SERVICE_NAME% DisplayName "GNS3 MCP HTTP Server"
nssm set %SERVICE_NAME% Description "MCP server providing HTTP access to GNS3 network labs"
nssm set %SERVICE_NAME% AppDirectory "%SERVER_DIR%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%SCRIPT_DIR%\mcp-http-server.log"
nssm set %SERVICE_NAME% AppStderr "%SCRIPT_DIR%\mcp-http-server.log"
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateOnline 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760

echo Starting service...
nssm start %SERVICE_NAME%
if %errorlevel% neq 0 (
    echo ERROR: Failed to start service
    exit /b 1
)

echo.
echo Service installed and started successfully!
echo Logs: %SCRIPT_DIR%\mcp-http-server.log
exit /b 0

:uninstall
echo === Uninstalling GNS3 MCP HTTP Service ===
echo.

REM Check if installed
nssm status %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo Service not installed
    exit /b 0
)

echo Stopping service...
nssm stop %SERVICE_NAME%
timeout /t 2 /nobreak >nul

echo Removing service...
nssm remove %SERVICE_NAME% confirm
if %errorlevel% neq 0 (
    echo ERROR: Failed to remove service
    exit /b 1
)

echo Service uninstalled successfully!
exit /b 0

:reinstall
echo === Reinstalling GNS3 MCP HTTP Service ===
echo.
call :uninstall
echo.
call :install
exit /b %errorlevel%

:status
nssm status %SERVICE_NAME%
exit /b %errorlevel%

:check_venv
REM Check if venv exists
if not exist "%VENV_DIR%" (
    echo Venv not found. Creating...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create venv
        exit /b 1
    )
    echo Venv created successfully
    set "NEED_INSTALL=1"
) else (
    echo Venv found: %VENV_DIR%
    set "NEED_INSTALL=0"
)

REM Check if dependencies are installed (check if lib folder in venv has mcp package)
if not exist "%VENV_DIR%\Lib\site-packages\mcp" set "NEED_INSTALL=1"

REM Install dependencies if needed
if "%NEED_INSTALL%"=="1" (
    echo Installing dependencies...
    "%VENV_PIP%" install -r "%REQUIREMENTS%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies
        exit /b 1
    )
    echo Dependencies installed successfully
) else (
    echo Dependencies already installed
)

REM Show Python version
echo.
echo Python: %VENV_PYTHON%
"%VENV_PYTHON%" --version
echo.

exit /b 0
