@echo off
REM GNS3 MCP HTTP Server Management Script
REM Uses WinSW (Windows Service Wrapper) to run as Windows service
REM Usage: server.cmd [run|start|stop|restart|install|uninstall|reinstall|status|venv-recreate|create-user]
REM   (no params)      - Run server directly (development mode)
REM   run             - Run server directly (development mode)
REM   start           - Start Windows service
REM   stop            - Stop Windows service
REM   restart         - Restart Windows service
REM   install         - Install Windows service
REM   uninstall       - Remove Windows service
REM   reinstall       - Reinstall Windows service
REM   status          - Show service status
REM   venv-recreate   - Recreate Python virtual environment (clean install)
REM   create-user     - Create service user account (requires admin)

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
    REM Use Windows PowerShell explicitly (not PowerShell Core/7)
    %SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -Command "try { Invoke-WebRequest -Uri '%WINSW_DOWNLOAD_URL%' -OutFile '%WINSW_EXE%' -UseBasicParsing; Write-Host 'WinSW downloaded successfully!' } catch { Write-Host 'ERROR: Failed to download WinSW:' $_.Exception.Message; exit 1 }"
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

REM Check for admin privileges if running install/uninstall/reinstall/start/stop/restart/create-user
if /i "%COMMAND%"=="install" goto :check_admin
if /i "%COMMAND%"=="uninstall" goto :check_admin
if /i "%COMMAND%"=="reinstall" goto :check_admin
if /i "%COMMAND%"=="start" goto :check_admin
if /i "%COMMAND%"=="stop" goto :check_admin
if /i "%COMMAND%"=="restart" goto :check_admin
if /i "%COMMAND%"=="create-user" goto :check_admin
if /i "%COMMAND%"=="status" goto :status
if /i "%COMMAND%"=="run" goto :run_direct
if /i "%COMMAND%"=="venv-recreate" goto :venv_recreate

echo Unknown command: %COMMAND%
echo Usage: server.cmd [run^|start^|stop^|restart^|install^|uninstall^|reinstall^|status^|venv-recreate^|create-user]
echo   run            - Run server directly (no service)
echo   start          - Start Windows service
echo   stop           - Stop Windows service
echo   restart        - Restart Windows service
echo   install        - Install Windows service
echo   uninstall      - Remove Windows service
echo   reinstall      - Reinstall Windows service
echo   status         - Show service status
echo   venv-recreate  - Recreate Python virtual environment
echo   create-user    - Create service user account (admin required)
exit /b 1

:check_admin
REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    echo.
    REM Use Windows PowerShell explicitly (not PowerShell Core/7)
    REM Note: Using & instead of && for pause to ensure window stays open even on errors
    %SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -Command "Start-Process cmd -ArgumentList '/c cd /d \"%SCRIPT_DIR%\" && \"%~f0\" %COMMAND% & echo. & echo. & echo Press any key to close... & pause >nul' -Verb RunAs"
    exit /b 0
)
REM Running as admin, proceed to command
if /i "%COMMAND%"=="install" goto :install
if /i "%COMMAND%"=="uninstall" goto :uninstall
if /i "%COMMAND%"=="reinstall" goto :reinstall
if /i "%COMMAND%"=="start" goto :service_start
if /i "%COMMAND%"=="stop" goto :service_stop
if /i "%COMMAND%"=="restart" goto :service_restart
if /i "%COMMAND%"=="create-user" goto :create_user

:run_direct
echo === GNS3 MCP HTTP Server (Direct Mode) ===
echo.
call :check_venv
if %errorlevel% neq 0 exit /b 1

echo Starting server directly (not as service)...
cd /d "%SCRIPT_DIR%"
"%SCRIPT_DIR%\venv\Scripts\gns3-mcp.exe" --transport http --http-port 8100
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

    REM Install package in editable mode for Windows service
    echo Installing gns3-mcp package...
    "%VENV_PIP%" install -e "%SCRIPT_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install gns3-mcp package
        exit /b 1
    )
    echo Package installed successfully
) else (
    echo Dependencies already installed
)

REM Show Python version
echo.
echo Python: %VENV_PYTHON%
"%VENV_PYTHON%" --version
echo.

exit /b 0

:venv_recreate
echo === Recreating Python Virtual Environment ===
echo.

REM 1. Remove old venv
if exist "%VENV_DIR%" (
    echo [1/5] Removing old venv...
    rmdir /s /q "%VENV_DIR%" 2>nul
    if exist "%VENV_DIR%" (
        echo   Warning: Could not remove some files, retrying...
        timeout /t 2 /nobreak >nul
        rmdir /s /q "%VENV_DIR%" 2>nul
    )
    if not exist "%VENV_DIR%" (
        echo   [OK] Old venv removed
    ) else (
        echo   [ERROR] Failed to remove venv
        echo   Try manually: rmdir /s /q "%VENV_DIR%"
        echo   Or close all programs using Python and retry
        exit /b 1
    )
) else (
    echo [1/5] No existing venv found
)

REM 2. Create new venv
echo [2/5] Creating fresh venv...
python -m venv "%VENV_DIR%"
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to create venv
    echo   Ensure Python 3.10+ is installed and in PATH
    exit /b 1
)
echo   [OK] Venv created

REM 3. Upgrade pip
echo [3/5] Upgrading pip...
"%VENV_PIP%" install --upgrade pip --quiet
if %errorlevel% equ 0 (
    echo   [OK] Pip upgraded
) else (
    echo   [WARNING] Failed to upgrade pip
)

REM 4. Install dependencies
echo [4/5] Installing dependencies from requirements.txt...
"%VENV_PIP%" install -r "%REQUIREMENTS%"
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to install dependencies
    exit /b 1
)
echo   [OK] Dependencies installed

REM 5. Rebuild lib folder for desktop extension
echo [5/5] Rebuilding lib folder for desktop extension...
set "LIB_DIR=%SCRIPT_DIR%\mcp-server\lib"

REM Clean old lib folder
if exist "%LIB_DIR%" (
    echo   Removing old lib folder...
    rmdir /s /q "%LIB_DIR%" 2>nul
)

REM Create fresh lib folder
mkdir "%LIB_DIR%" 2>nul
if not exist "%LIB_DIR%" (
    echo   [ERROR] Failed to create lib folder
    exit /b 1
)

REM Install dependencies from requirements.txt (exclude dev dependencies)
echo   Installing production dependencies to lib folder...
"%VENV_PIP%" install --target="%LIB_DIR%" --upgrade ^
    fastmcp>=2.13.0.2 ^
    fastapi>=0.115.0 ^
    httpx>=0.28.1 ^
    telnetlib3>=2.0.8 ^
    pydantic>=2.12.3 ^
    python-dotenv>=1.2.1 ^
    cairosvg>=2.8.2 ^
    docker>=7.1.0 ^
    tabulate>=0.9.0 ^
    --no-warn-script-location ^
    --quiet

if %errorlevel% neq 0 (
    echo   [ERROR] Failed to rebuild lib folder
    exit /b 1
)
echo   [OK] Lib folder rebuilt (%LIB_DIR%)

REM 6. Install package in editable mode
echo [6/6] Installing gns3-mcp package in editable mode...
"%VENV_PIP%" install -e "%SCRIPT_DIR%" --quiet
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to install package
    exit /b 1
)
echo   [OK] Package installed

echo.
echo === Rebuild Complete ===
echo.
echo Venv: %VENV_DIR%
echo Lib: %LIB_DIR%
echo Package: gns3-mcp (editable mode)
echo.
echo Next steps:
echo   1. Test CLI: gns3-mcp --version
echo   2. Test server: .\server.cmd run
echo   3. Rebuild desktop extension: cd mcp-server ^&^& npx @anthropic-ai/mcpb pack
echo   4. Reinstall service (if installed): .\server.cmd reinstall
echo.
exit /b 0

:create_user
echo === Creating Service User Account ===
echo.

set "USERNAME=GNS3MCPService"
set "PASSWORD=GNS3mcp!2025"
set "DESCRIPTION=GNS3 MCP Service Account (Low Privilege)"

REM 1. Check if user exists
echo [1/3] Checking if user exists...
net user "%USERNAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] User already exists: %USERNAME%
    goto :set_permissions
)

REM 2. Create user
echo   Creating user: %USERNAME%
net user "%USERNAME%" "%PASSWORD%" /add /comment:"%DESCRIPTION%" /passwordchg:no /expires:never /active:yes
if %errorlevel% neq 0 (
    echo   [ERROR] Failed to create user
    echo   Common causes:
    echo     - Password policy not met
    echo     - Insufficient privileges (must run as Administrator)
    exit /b 1
)

REM Set password to never expire
wmic useraccount where "name='%USERNAME%'" set PasswordExpires=FALSE >nul 2>&1

echo   [OK] User created successfully

:set_permissions
REM 3. Set folder permissions
echo [2/3] Setting folder permissions...
echo   Path: %SCRIPT_DIR%

REM Grant read/execute permissions
icacls "%SCRIPT_DIR%" /grant "%USERNAME%:(OI)(CI)RX" /T /Q >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Read/Execute permissions set
) else (
    echo   [WARNING] Could not set folder permissions
    echo   Service may not start correctly
)

REM Grant write permission for log files (current directory only)
icacls "%SCRIPT_DIR%" /grant "%USERNAME%:W" /Q >nul 2>&1

REM Set .env permissions
if exist "%SCRIPT_DIR%\.env" (
    icacls "%SCRIPT_DIR%\.env" /grant "%USERNAME%:R" /Q >nul 2>&1
    echo   [OK] .env file readable by service account
) else (
    echo   [WARNING] .env file not found
)

REM 4. Grant "Log on as a service" right
echo [3/3] Granting 'Log on as a service' right...
echo   This may require manual configuration

REM Try using ntrights if available (Windows Resource Kit)
ntrights +r SeServiceLogonRight -u "%USERNAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Service logon right granted
    goto :create_user_complete
)

REM Fallback: Show manual instructions
echo   [WARNING] Could not grant service logon right automatically
echo.
echo   Please grant manually:
echo     1. Run: secpol.msc
echo     2. Navigate to: Local Policies -^> User Rights Assignment
echo     3. Open: 'Log on as a service'
echo     4. Add user: %USERNAME%
echo.

:create_user_complete
echo.
echo === Setup Complete ===
echo.
echo Service account: %USERNAME%
echo Password: (stored in GNS3-MCP-HTTP.xml)
echo.
echo Next steps:
echo   1. Ensure .env contains GNS3 credentials
echo   2. Ensure .env contains MCP_API_KEY (or leave empty for auto-gen)
echo   3. Run: .\server.cmd install
echo   4. Service will run as low-privilege user
echo.
echo Verify service user:
echo   .\server.cmd status
echo.
exit /b 0
