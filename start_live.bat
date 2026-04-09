@echo off
REM VocalVitals - Start Live Streaming Server
REM Run this from the project root

echo ============================================
echo VocalVitals - Live Streaming Server
echo ============================================

cd /d "%~dp0backend"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.9+
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate 2>nul

echo Installing dependencies...
pip install fastapi uvicorn python-dotenv numpy -q 2>nul

REM Check if audioop-lts is needed (Python 3.13+)
python -c "import audioop" 2>nul
if errorlevel 1 (
    pip install audioop-lts -q 2>nul
)

echo.
echo Starting server on http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.
echo For Twilio testing:
echo   1. Run in another terminal: ngrok http 8000
echo   2. Set Twilio webhook: https://[ngrok-url]/twilio/incoming
echo   3. Call your Twilio number
echo.
echo Press Ctrl+C to stop
echo ============================================

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
