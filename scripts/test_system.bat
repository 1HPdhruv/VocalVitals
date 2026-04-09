@echo off
echo ================================================
echo VocalVitals System Test
echo ================================================
echo.

cd /d "%~dp0\..\backend"

echo [1/4] Installing dependencies...
python -m pip install imageio-ffmpeg pydub -q
if errorlevel 1 (
    echo FAILED: Dependency installation
    pause
    exit /b 1
)
echo OK: Dependencies installed

echo.
echo [2/4] Testing ffmpeg...
python -c "import imageio_ffmpeg; print('ffmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 (
    echo FAILED: ffmpeg not available
    pause
    exit /b 1
)
echo OK: ffmpeg available

echo.
echo [3/4] Testing imports...
python -c "from routers.analyze import router; print('Analyze router OK')"
if errorlevel 1 (
    echo FAILED: Import error in analyze router
    pause
    exit /b 1
)
echo OK: All imports work

echo.
echo [4/4] Checking model...
python -c "from pathlib import Path; p = Path('models/audio_classifier.pkl'); print('Model exists:', p.exists(), 'Size:', p.stat().st_size if p.exists() else 0)"

echo.
echo ================================================
echo System Test Complete!
echo ================================================
echo.
echo To train the model, run: scripts\train_model.bat
echo To start the server, run: start.bat
echo.
pause
