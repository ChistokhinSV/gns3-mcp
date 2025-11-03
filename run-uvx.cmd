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

REM 2. Check user Python Scripts directory (most common for pip install)
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

REM 3. Check AppData\Roaming (pip install --user)
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

REM 4. Check system Python (C:\Python)
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

REM 5. Check ProgramFiles Python
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

REM Not found
echo.
echo ===============================================
echo ERROR: uvx not found in any common location
echo ===============================================
echo.
echo Searched locations:
echo   - PATH environment variable
echo   - %%LOCALAPPDATA%%\Programs\Python\Python3XX\Scripts\
echo   - %%APPDATA%%\Python\Python3XX\Scripts\
echo   - C:\Python3XX\Scripts\
echo   - C:\Program Files\Python3XX\Scripts\
echo.
echo Please install uv:
echo   pip install uv
echo.
echo Or ensure uvx.exe is in one of the above locations.
echo.
exit /b 1
