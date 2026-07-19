@echo off
setlocal enabledelayedexpansion
title scrcpy Phone Mirror

cd /d "%~dp0"
color 0B

echo ============================================================
echo   scrcpy - Wireless Phone Mirror
echo   QR + USB-assisted + fully customizable
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Download from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [*] Python %PYVER%

python -c "import qrcode" 2>nul
if errorlevel 1 (
    echo [*] Installing qrcode[pil], pillow...
    pip install qrcode[pil] pillow
    if errorlevel 1 ( echo [X] Failed. & pause & exit /b 1 )
)

echo [*] Starting...
python scrcpy_qr_pair.py
