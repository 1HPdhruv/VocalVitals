@echo off
echo ================================================
echo VocalVitals - Complete System Setup
echo ================================================
echo.

cd /d "%~dp0"

echo [1/6] Checking backend setup...
if not exist backend\venv (
    echo ERROR: Backend virtual environment not found!
    echo Please run: cd backend && python -m venv venv
    pause
    exit /b 1
)
echo OK: Backend venv exists

echo.
echo [2/6] Installing backend dependencies...
cd backend
call venv\Scripts\activate.bat
pip install imageio-ffmpeg pydub -q
if errorlevel 1 (
    echo WARNING: Some packages may have failed to install
)
echo OK: Dependencies installed

echo.
echo [3/6] Verifying ffmpeg...
python -c "import imageio_ffmpeg; print('ffmpeg path:', imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 (
    echo ERROR: ffmpeg verification failed
    pause
    exit /b 1
)
echo OK: ffmpeg available

echo.
echo [4/6] Checking ML model...
python -c "from pathlib import Path; p = Path('models/audio_classifier.pkl'); s = p.stat().st_size if p.exists() else 0; print(f'Model size: {s/1024:.1f} KB'); exit(0 if s > 100000 else 1)"
if errorlevel 1 (
    echo WARNING: Model not trained or too small. Training now...
    python ml\quick_train.py
    if errorlevel 1 (
        echo ERROR: Training failed
        pause
        exit /b 1
    )
)
echo OK: ML model ready

echo.
echo [5/6] Testing imports...
python -c "from routers.analyze import router; from services.storage import save_analysis_result; print('All imports OK')"
if errorlevel 1 (
    echo ERROR: Import test failed
    pause
    exit /b 1
)
echo OK: All imports work

cd ..

echo.
echo [6/6] Checking frontend setup...
if not exist frontend\node_modules (
    echo WARNING: Frontend node_modules not found
    echo Run: cd frontend && npm install
) else (
    echo OK: Frontend ready
)

echo.
echo ================================================
echo VocalVitals Setup Complete!
echo ================================================
echo.
echo Model Status:
cd backend
python -c "import json; m = json.load(open('models/audio_classifier_metrics.json')); print(f'  Accuracy: {m[\"accuracy\"]*100:.1f}%%'); print(f'  Samples: {m[\"num_samples\"]}')"
cd ..
echo.
echo To start the system, run: start.bat
echo.
pause
