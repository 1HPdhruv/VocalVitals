@echo off
echo ================================================
echo VocalVitals Audio Classifier Training
echo ================================================
echo.

cd /d "%~dp0\..\backend"

if not exist venv (
    echo [ERROR] Backend virtual environment 'venv' not found.
    echo Please set up the backend first.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages...
pip install imageio-ffmpeg pydub -q

echo.
echo Starting training (this may take a few minutes)...
echo.
python ml\quick_train.py

echo.
echo ================================================
echo Training process finished.
echo ================================================
pause
