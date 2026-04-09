@echo off
echo ========================================
echo Starting Vocal Vitals on Localhost
echo ========================================

:: 1. Clear ports 3000 and 8000
echo Clearing ports 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a 2>nul

:: 2. Start Backend
echo Starting FastAPI Backend...
cd backend
if not exist venv (
    echo [ERROR] Backend virtual environment 'venv' not found.
    pause
    exit /b
)
start "VocalVitals-Backend" cmd /k "venv\Scripts\activate && uvicorn main:app --reload --port 8000"
cd ..

:: 3. Start Frontend
echo Starting Vite Frontend...
cd frontend
if not exist node_modules (
    echo [ERROR] Frontend 'node_modules' not found.
    pause
    exit /b
)
start "VocalVitals-Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo Vocal Vitals is starting!
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo ========================================
echo Opening browser in 5 seconds...
timeout /t 5
start http://localhost:3000
