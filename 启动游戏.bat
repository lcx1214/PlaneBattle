@echo off
rem Plane Battle launcher (works on Windows 7+)
cd /d "%~dp0"

rem Prefer pythonw (no console window). Fall back to python if unavailable.
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw main.py
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo [Error] Python not found. Please install Python 3.7+ and check "Add to PATH".
    echo          Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
start "" python main.py
