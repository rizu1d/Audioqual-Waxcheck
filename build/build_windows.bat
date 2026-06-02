@echo off
REM ╔════════════════════════════════════════════════════════════╗
REM ║  AudioQual — Windows Build Script                          ║
REM ║  Generates AudioQual.exe portable application              ║
REM ╚════════════════════════════════════════════════════════════╝
REM
REM Usage:
REM   cd <project_root>
REM   build\build_windows.bat            Build portable folder
REM   build\build_windows.bat --zip      Build + create .zip archive
REM
REM Prerequisites:
REM   pip install -r requirements.txt
REM   pip install pyinstaller

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set VERSION=0.1.0-beta
set APP_NAME=AudioQual

echo ========================================
echo   Building %APP_NAME% v%VERSION% for Windows
echo ========================================
echo.

cd /d "%PROJECT_ROOT%"

REM ── 1. Clean previous build ──
echo -- Cleaning previous build...
if exist "dist\AudioQual" rmdir /s /q "dist\AudioQual"
if exist "build\AudioQual" rmdir /s /q "build\AudioQual"

REM ── 2. Run PyInstaller ──
echo -- Running PyInstaller...
python -m PyInstaller build\audioqual_windows.spec --noconfirm --clean

if not exist "dist\AudioQual\AudioQual.exe" (
    echo [ERROR] Build failed - AudioQual.exe not found
    exit /b 1
)

echo.
echo [OK] AudioQual.exe built successfully in dist\AudioQual\

REM ── 3. Create ZIP if requested ──
if "%~1"=="--zip" (
    echo.
    echo -- Creating ZIP archive...

    set ZIP_NAME=%APP_NAME%-%VERSION%-Windows.zip

    REM Use PowerShell to create zip (available on Win10+)
    powershell -Command "Compress-Archive -Path 'dist\AudioQual\*' -DestinationPath 'dist\!ZIP_NAME!' -Force"

    if exist "dist\!ZIP_NAME!" (
        echo [OK] ZIP created: dist\!ZIP_NAME!
    ) else (
        echo [WARNING] ZIP creation failed. You can manually zip dist\AudioQual\
    )
)

REM ── 4. Summary ──
echo.
echo ========================================
echo   Build complete!
echo.
echo   Folder: dist\AudioQual\
echo   EXE:    dist\AudioQual\AudioQual.exe
if "%~1"=="--zip" (
    echo   ZIP:    dist\%ZIP_NAME%
)
echo.
echo   NOTE: Windows Defender or other antivirus
echo   may flag unsigned PyInstaller executables.
echo   This is a known false positive.
echo ========================================

endlocal
