@echo off
echo ========================================
echo VocalVitals Complete Setup
echo ========================================
echo.

cd /d "%~dp0..\backend"

echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found at backend\venv
    echo Please create it first with: python -m venv venv
    pause
    exit /b 1
)

echo [2/3] Installing ffmpeg package...
pip install imageio-ffmpeg pydub -q
echo Done.

echo [3/3] Training ML model (this may take a few minutes)...
python ml\quick_train.py
if errorlevel 1 (
    echo.
    echo Training had issues. Check the output above.
) else (
    echo.
    echo ========================================
    echo SUCCESS! Setup complete.
    echo ========================================
    echo.
    echo Now restart your backend server:
    echo   cd backend
    echo   venv\Scripts\activate
    echo   uvicorn main:app --reload --port 8000
    echo.
)

pause
