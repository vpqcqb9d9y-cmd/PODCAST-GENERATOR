@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo ============================================================
echo   M.B.S Studio - EXE Builder
echo   יוצר קובץ הפעלה עצמאי מהאפליקציה
echo ============================================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python לא נמצא! התקן Python 3.9+ והוסף ל-PATH
    pause
    exit /b 1
)

:: Check if PyInstaller is installed, install if not
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] מתקין PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] התקנת PyInstaller נכשלה!
        pause
        exit /b 1
    )
)

:: Check if Pillow is installed (for icon conversion)
pip show pillow >nul 2>&1
if errorlevel 1 (
    echo [INFO] מתקין Pillow לעיבוד לוגו...
    pip install pillow
)

echo [INFO] PyInstaller מותקן. מתחיל לבנות EXE...
echo.

:: Set paths
set "SCRIPT_DIR=%~dp0"
set "SRC_DIR=%SCRIPT_DIR%src"
set "ASSETS_DIR=%SCRIPT_DIR%assets"
set "CONFIG_DIR=%SCRIPT_DIR%config"
set "LOGO_JPEG=%SCRIPT_DIR%LOGO.JPEG"
set "LOGO_ICO=%SCRIPT_DIR%LOGO.ico"

:: Convert LOGO.JPEG to LOGO.ico if it doesn't exist
if exist "%LOGO_JPEG%" (
    if not exist "%LOGO_ICO%" (
        echo [INFO] ממיר לוגו לפורמט ICO...
        python -c "from PIL import Image; img = Image.open(r'%LOGO_JPEG%'); img.save(r'%LOGO_ICO%', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])"
        if errorlevel 1 (
            echo [WARNING] לא ניתן להמיר את הלוגו. ממשיך ללא אייקון.
            set "ICON_ARG="
        ) else (
            echo [INFO] לוגו הומר בהצלחה ל-ICO
            set "ICON_ARG=--icon "%LOGO_ICO%""
        )
    ) else (
        echo [INFO] משתמש בקובץ ICO קיים
        set "ICON_ARG=--icon "%LOGO_ICO%""
    )
) else (
    echo [WARNING] לא נמצא קובץ לוגו. ממשיך ללא אייקון.
    set "ICON_ARG="
)

:: Build command with all necessary options
echo [INFO] בונה את האפליקציה...
echo.

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "MBS_Studio" ^
    %ICON_ARG% ^
    --add-data "%SRC_DIR%;src" ^
    --add-data "%ASSETS_DIR%;assets" ^
    --add-data "%CONFIG_DIR%;config" ^
    --add-data "%LOGO_JPEG%;." ^
    --hidden-import "PyQt6" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "pyqtgraph" ^
    --hidden-import "azure.cognitiveservices.speech" ^
    --hidden-import "openai" ^
    --hidden-import "google.generativeai" ^
    --hidden-import "pydub" ^
    --hidden-import "pydub.effects" ^
    --hidden-import "moviepy" ^
    --hidden-import "moviepy.editor" ^
    --hidden-import "manim" ^
    --hidden-import "pptx" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "elevenlabs" ^
    --collect-all "PyQt6" ^
    --collect-all "pyqtgraph" ^
    --collect-all "pydub" ^
    "%SCRIPT_DIR%run_gui.py"

if errorlevel 1 (
    echo.
    echo [ERROR] בניית ה-EXE נכשלה!
    echo בדוק את הלוגים למעלה לפרטים נוספים.
    pause
    exit /b 1
)

:: Copy .env file if exists
if exist "%SCRIPT_DIR%.env" (
    echo [INFO] מעתיק קובץ .env...
    copy "%SCRIPT_DIR%.env" "%SCRIPT_DIR%dist\MBS_Studio\.env" >nul
)

:: Copy logo to dist folder
if exist "%LOGO_JPEG%" (
    echo [INFO] מעתיק לוגו...
    copy "%LOGO_JPEG%" "%SCRIPT_DIR%dist\MBS_Studio\LOGO.JPEG" >nul
)

echo.
echo ============================================================
echo   [SUCCESS] EXE נוצר בהצלחה!
echo   מיקום: dist\MBS_Studio\MBS_Studio.exe
echo ============================================================
echo.
echo לשימוש:
echo   1. העבר את תיקיית dist\MBS_Studio למחשב היעד
echo   2. הפעל MBS_Studio.exe
echo   3. ודא שקובץ .env קיים באותה תיקייה
echo.

:: Ask if user wants to open the dist folder
set /p OPEN_DIST="לפתוח את תיקיית הפלט? (y/n): "
if /i "%OPEN_DIST%"=="y" (
    explorer "%SCRIPT_DIR%dist\MBS_Studio"
)

pause
