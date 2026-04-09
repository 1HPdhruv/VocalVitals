@echo off
REM ============================================
REM VocalVitals - Complete Twilio Live Setup
REM ============================================

echo.
echo ============================================
echo    VOCALVITALS TWILIO LIVE CALLS
echo ============================================
echo.

cd /d "%~dp0"

REM Check if ngrok is running
echo [1/4] Checking ngrok...
curl -s http://localhost:4040/api/tunnels >nul 2>&1
if errorlevel 1 (
    echo      ngrok not running!
    echo      Please run: ngrok http 8000
    echo      Then run this script again.
    pause
    exit /b 1
)

REM Get ngrok URL
for /f "tokens=*" %%i in ('curl -s http://localhost:4040/api/tunnels ^| findstr /r "https://[^\"]*\.ngrok"') do set NGROK_LINE=%%i
echo      ngrok detected

echo.
echo [2/4] Starting backend...
cd backend
start "VocalVitals Backend" cmd /k "python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
cd ..

echo      Waiting for backend to start...
timeout /t 5 /nobreak >nul

echo.
echo [3/4] Starting frontend...
cd frontend
start "VocalVitals Frontend" cmd /k "npm run dev"
cd ..

echo.
echo [4/4] Setup complete!
echo.
echo ============================================
echo    TWILIO CONFIGURATION
echo ============================================
echo.
echo 1. Go to: https://console.twilio.com
echo 2. Phone Numbers → +17625722165
echo 3. Voice ^& Fax → A Call Comes In
echo 4. Set Webhook URL to your ngrok URL:
echo    https://YOUR_NGROK_URL/twilio/incoming
echo 5. Method: HTTP POST
echo 6. Save
echo.
echo ============================================
echo    TESTING
echo ============================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000/live
echo API Docs: http://localhost:8000/docs
echo.
echo Test endpoints:
echo   curl http://localhost:8000/twilio/test
echo   curl -X POST http://localhost:8000/twilio/test/simulate-call
echo.
echo Call your Twilio number to test live!
echo ============================================
echo.
pause
