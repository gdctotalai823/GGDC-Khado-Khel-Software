@echo off
TITLE GGDC Khado Khel - Enterprise Fine & Management System
COLOR 0B
echo ========================================================
echo   Starting GGDC Khado Khel College Management System...
echo ========================================================
cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH.
    pause
    exit /b
)

:: Launch the application
echo [INFO] Launching main.py...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application encountered an unexpected error or crashed.
    pause
)