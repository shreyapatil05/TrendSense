@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\activate ^&^& python -m pip install -r requirements.txt
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python main.py --prepare --plots

echo.
echo TrendSense finished with exit code %ERRORLEVEL%.
pause
