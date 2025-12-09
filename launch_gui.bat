@echo off

cd /d "%~dp0"

echo Checking environment...

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in .venv!
    pause
    exit /b 1
)

echo Starting Podcast Generator GUI...
echo Command: python -m src.gui.app
echo.

:: --- THE CRITICAL LINE ---
call .venv\Scripts\python.exe -m src.gui.app
:: -------------------------

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [CRASH] Application closed with error code %ERRORLEVEL%
    pause
)
