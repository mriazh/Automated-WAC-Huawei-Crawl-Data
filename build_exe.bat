@echo off
setlocal enabledelayedexpansion

echo Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

echo Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller is not installed. Please run: pip install pyinstaller
    exit /b 1
)

echo Cleaning old build directories...
if exist "dist" rmdir /s /q "dist"
if exist "build\temp" rmdir /s /q "build\temp"

echo Building executable...
python -m PyInstaller build\build.spec --distpath dist --workpath build\temp
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed!
    exit /b 1
)

echo.
echo Build succeeded!
echo dist\WAC-Crawl\WAC-Crawl.exe
exit /b 0
