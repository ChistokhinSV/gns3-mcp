@echo off
REM Wrapper script to run uvx with full path
REM This ensures Windows service can find uvx even when PATH is not inherited

setlocal enabledelayedexpansion

REM Try to find uvx in common locations
set "UVX_PATH="

REM 1. Check if uvx is in PATH (works in normal command prompt)
where uvx >nul 2>&1
if %errorlevel% equ 0 (
    REM If in PATH, just use it directly
    uvx %*
    exit /b !errorlevel!
)

REM 2. Check default uv standalone install location (most common)
set "TEST_PATH=%USERPROFILE%\.cargo\bin\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=%LOCALAPPDATA%\bin\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM 3. Check user Python Scripts directory (pip install)
set "TEST_PATH=%LOCALAPPDATA%\Programs\Python\Python313\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=%LOCALAPPDATA%\Programs\Python\Python312\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=%LOCALAPPDATA%\Programs\Python\Python311\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=%LOCALAPPDATA%\Programs\Python\Python310\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM 4. Check AppData\Roaming (pip install --user)
set "TEST_PATH=%APPDATA%\Python\Python313\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=%APPDATA%\Python\Python312\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM 5. Check system Python (C:\Python)
set "TEST_PATH=C:\Python313\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=C:\Python312\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM 6. Check ProgramFiles Python
set "TEST_PATH=C:\Program Files\Python313\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

set "TEST_PATH=C:\Program Files\Python312\Scripts\uvx.exe"
if exist "!TEST_PATH!" (
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM Not found - try to install uv automatically
echo.
echo ===============================================
echo uvx not found - attempting auto-install
echo ===============================================
echo.

REM Create install directory for current user
set "UV_INSTALL_DIR=%LOCALAPPDATA%\uv"
if not exist "%UV_INSTALL_DIR%" mkdir "%UV_INSTALL_DIR%"

echo Installing uv to: %UV_INSTALL_DIR%
echo This will take a moment...
echo.

REM Download and install uv using the official standalone installer
REM This is the recommended installation method for Windows
REM Use -ExecutionPolicy Bypass to work around restricted policy for service accounts
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& { try { irm https://astral.sh/uv/install.ps1 | iex } catch { Write-Host 'ERROR: Failed to install uv:' $_.Exception.Message; exit 1 } }"

if %errorlevel% neq 0 (
    echo.
    echo ===============================================
    echo ERROR: Failed to auto-install uv
    echo ===============================================
    echo.
    echo Please install manually:
    echo   Option 1: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo   Option 2: pip install uv
    echo.
    echo Or ensure uvx.exe is in one of these locations:
    echo   - %%LOCALAPPDATA%%\Programs\Python\Python3XX\Scripts\
    echo   - %%APPDATA%%\Python\Python3XX\Scripts\
    echo   - C:\Python3XX\Scripts\
    echo   - C:\Program Files\Python3XX\Scripts\
    echo.
    exit /b 1
)

echo.
echo [OK] uv installed successfully
echo.

REM Retry finding uvx in common locations after installation
echo Searching for uvx after installation...

REM Check default uv install location first
set "TEST_PATH=%USERPROFILE%\.cargo\bin\uvx.exe"
if exist "!TEST_PATH!" (
    echo [OK] Found uvx at: !TEST_PATH!
    echo.
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM Check user's .local directory (common on Windows)
set "TEST_PATH=%LOCALAPPDATA%\bin\uvx.exe"
if exist "!TEST_PATH!" (
    echo [OK] Found uvx at: !TEST_PATH!
    echo.
    "!TEST_PATH!" %*
    exit /b !errorlevel!
)

REM Check PATH again (installer may have updated it)
where uvx >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Found uvx in PATH
    echo.
    uvx %*
    exit /b !errorlevel!
)

REM Still not found after installation
echo.
echo ===============================================
echo ERROR: uvx installed but not found
echo ===============================================
echo.
echo uv was installed, but uvx is not in expected locations.
echo.
echo Try:
echo   1. Close this window
echo   2. Open a new command prompt (to refresh PATH)
echo   3. Run the command again
echo.
echo Or add uvx manually to PATH:
echo   Location: %USERPROFILE%\.cargo\bin
echo.
exit /b 1
