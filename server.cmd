@echo off
REM GNS3 MCP HTTP Server Management Script
REM Uses WinSW (Windows Service Wrapper) to run as Windows service
REM Usage: server.cmd [run|start|stop|restart|install|uninstall|reinstall|status]
REM   (no params)  - Run server directly (development mode)
REM   run         - Run server directly (development mode)
REM   start       - Start Windows service
REM   stop        - Stop Windows service
REM   restart     - Restart Windows service
REM   install     - Install Windows service
REM   uninstall   - Remove Windows service
REM   reinstall   - Reinstall Windows service
REM   status      - Show service status

setlocal enabledelayedexpansion

REM WinSW download URL (change to x86 if needed)
set "WINSW_DOWNLOAD_URL=https://github.com/winsw/winsw/releases/download/latest/WinSW-x64.exe"
REM Alternative for 32-bit systems:
REM set "WINSW_DOWNLOAD_URL=https://github.com/winsw/winsw/releases/download/latest/WinSW-x86.exe"

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "SERVER_DIR=%SCRIPT_DIR%\mcp-server"
set "REQUIREMENTS=%SCRIPT_DIR%\requirements.txt"
set "SERVICE_NAME=GNS3-MCP-HTTP"
set "WINSW_EXE=%SCRIPT_DIR%\%SERVICE_NAME%.exe"

REM Check for WinSW executable, download if missing
if not exist "%WINSW_EXE%" (
    echo WinSW executable not found: %WINSW_EXE%
    echo Downloading WinSW from: %WINSW_DOWNLOAD_URL%
    echo.
    powershell -Command "try { Invoke-WebRequest -Uri '%WINSW_DOWNLOAD_URL%' -OutFile '%WINSW_EXE%' -UseBasicParsing; Write-Host 'WinSW downloaded successfully!' } catch { Write-Host 'ERROR: Failed to download WinSW:' $_.Exception.Message; exit 1 }"
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: Failed to download WinSW
        echo Please download manually from: https://github.com/winsw/winsw/releases
        echo Rename to: %SERVICE_NAME%.exe
        echo Place in: %SCRIPT_DIR%
        exit /b 1
    )
    echo.
)

REM Parse command
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=run"

REM Check for admin privileges if running install/uninstall/reinstall/start/stop/restart
if /i "%COMMAND%"=="install" goto :check_admin
if /i "%COMMAND%"=="uninstall" goto :check_admin
if /i "%COMMAND%"=="reinstall" goto :check_admin
if /i "%COMMAND%"=="start" goto :check_admin
if /i "%COMMAND%"=="stop" goto :check_admin
if /i "%COMMAND%"=="restart" goto :check_admin
if /i "%COMMAND%"=="status" goto :status
if /i "%COMMAND%"=="run" goto :run_direct

echo Unknown command: %COMMAND%
echo Usage: server.cmd [run^|start^|stop^|restart^|install^|uninstall^|reinstall^|status]
echo   run        - Run server directly (no service)
echo   start      - Start Windows service
echo   stop       - Stop Windows service
echo   restart    - Restart Windows service
echo   install    - Install Windows service
echo   uninstall  - Remove Windows service
echo   reinstall  - Reinstall Windows service
echo   status     - Show service status
exit /b 1

:check_admin
REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    echo.
    powershell -Command "Start-Process cmd -ArgumentList '/c cd /d \"%SCRIPT_DIR%\" && \"%~f0\" %COMMAND% && echo. && echo Press any key to close... && pause >nul' -Verb RunAs"
    exit /b 0
)
REM Running as admin, proceed to command
if /i "%COMMAND%"=="install" goto :install
if /i "%COMMAND%"=="uninstall" goto :uninstall
if /i "%COMMAND%"=="reinstall" goto :reinstall
if /i "%COMMAND%"=="start" goto :service_start
if /i "%COMMAND%"=="stop" goto :service_stop
if /i "%COMMAND%"=="restart" goto :service_restart

:run_direct
echo === GNS3 MCP HTTP Server (Direct Mode) ===
echo.
call :check_venv
if %errorlevel% neq 0 exit /b 1

echo Starting server directly (not as service)...
cd /d "%SERVER_DIR%"
"%VENV_PYTHON%" start_mcp_http.py
exit /b %errorlevel%

:service_start
echo Starting GNS3 MCP HTTP service...
"%WINSW_EXE%" start
if %errorlevel% neq 0 (
    echo ERROR: Failed to start service. Is it installed?
    echo Run 'server.cmd install' first.
    exit /b 1
)
echo Service started successfully!
exit /b 0

:service_stop
echo Stopping GNS3 MCP HTTP service...
"%WINSW_EXE%" stop
echo Service stopped.
exit /b 0

:service_restart
echo Restarting GNS3 MCP HTTP service...
"%WINSW_EXE%" restart
exit /b %errorlevel%

:install
echo === Installing GNS3 MCP HTTP Service ===
echo.
call :check_venv
if %errorlevel% neq 0 exit /b 1

REM Check if already installed
"%WINSW_EXE%" status >nul 2>&1
if %errorlevel% equ 0 (
    echo Service already installed. Use 'reinstall' to update.
    exit /b 1
)

echo Installing service with WinSW...
"%WINSW_EXE%" install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install service
    echo Check GNS3-MCP-HTTP.xml configuration
    exit /b 1
)

echo Starting service...
"%WINSW_EXE%" start
if %errorlevel% neq 0 (
    echo ERROR: Failed to start service
    echo Check logs: %SCRIPT_DIR%\GNS3-MCP-HTTP.wrapper.log
    exit /b 1
)

echo.
echo Service installed and started successfully!
echo Server log: %SCRIPT_DIR%\mcp-http-server.log
echo Wrapper log: %SCRIPT_DIR%\GNS3-MCP-HTTP.wrapper.log
exit /b 0

:uninstall
echo === Uninstalling GNS3 MCP HTTP Service ===
echo.

REM Check if installed
"%WINSW_EXE%" status >nul 2>&1
if %errorlevel% neq 0 (
    echo Service not installed
    exit /b 0
)

echo Stopping service...
"%WINSW_EXE%" stop
timeout /t 3 /nobreak >nul

echo Removing service...
"%WINSW_EXE%" uninstall
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
"%WINSW_EXE%" status
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
