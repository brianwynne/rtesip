@echo off
REM Build pjsua.exe for Windows with Opus/TLS/SRTP support
REM Run from "x64 Native Tools Command Prompt for VS 2022"
REM or "Developer Command Prompt for VS 2022"

setlocal

set PJPROJECT_VERSION=2.16
set BUILD_DIR=%TEMP%\pjproject-build
set SCRIPT_DIR=%~dp0
set PATCH_DIR=%SCRIPT_DIR%..\pjsua

echo ============================================================
echo  Building pjsua %PJPROJECT_VERSION% for Windows
echo ============================================================

REM Check for Visual Studio
where cl >nul 2>&1
if errorlevel 1 (
    echo ERROR: cl.exe not found. Run this from "Developer Command Prompt for VS 2022"
    exit /b 1
)

REM Download source
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
cd /d "%BUILD_DIR%"

if not exist "pjproject-%PJPROJECT_VERSION%" (
    echo Downloading pjproject %PJPROJECT_VERSION%...
    curl -L -o pjproject.tar.gz "https://github.com/pjsip/pjproject/archive/refs/tags/%PJPROJECT_VERSION%.tar.gz"
    tar xzf pjproject.tar.gz
)

cd pjproject-%PJPROJECT_VERSION%

REM Create config_site.h
echo Creating config_site.h...
(
echo #define PJMEDIA_HAS_OPUS_CODEC 1
echo #define PJ_HAS_SSL_SOCK 1
echo #define PJMEDIA_HAS_SRTP 1
echo #define PJMEDIA_SRTP_HAS_SDES 1
echo #define PJMEDIA_SRTP_HAS_DTLS 0
echo #define PJMEDIA_AUDIO_DEV_HAS_WMME 1
) > pjlib\include\pj\config_site.h

REM Apply patches
echo Applying rtesip patches...
if exist "%PATCH_DIR%\pjsua_app.c.patch" (
    echo   pjsua_app.c patch...
    REM Use Python to apply since Windows patch command may not exist
    python "%SCRIPT_DIR%\apply-patch-win.py" "%PATCH_DIR%\pjsua_app.c.patch" .
)
if exist "%PATCH_DIR%\opus.c.patch" (
    echo   opus.c patch...
    python "%SCRIPT_DIR%\apply-patch-win.py" "%PATCH_DIR%\opus.c.patch" .
)

REM Build with MSBuild
echo Building (this may take several minutes)...
msbuild pjproject-vs14.sln /t:pjsua /p:Configuration=Release /p:Platform=Win32 /m /v:m

if errorlevel 1 (
    echo ERROR: Build failed!
    exit /b 1
)

REM Find the built binary
set PJSUA_BIN=
for /r pjsip-apps\bin %%f in (pjsua*.exe) do set PJSUA_BIN=%%f

if "%PJSUA_BIN%"=="" (
    echo ERROR: pjsua.exe not found after build
    exit /b 1
)

REM Copy to project
echo.
echo Copying to project...
if not exist "%SCRIPT_DIR%..\..\pjsua" mkdir "%SCRIPT_DIR%..\..\pjsua"
copy "%PJSUA_BIN%" "%SCRIPT_DIR%..\..\pjsua\pjsua.exe"

echo.
echo ============================================================
echo  Build complete: pjsua\pjsua.exe
echo ============================================================
echo.
echo Test with: pjsua\pjsua.exe --help

endlocal
