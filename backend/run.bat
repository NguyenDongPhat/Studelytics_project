@echo off
echo ========================================
echo    LUMINA AI - RAG DOCUMENT SYSTEM
echo ========================================
echo.

echo Starting Lumina AI System...
echo.

echo [1/2] Starting Backend Server...
start "Lumina Backend" cmd /k "cd /d %~dp0 && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo [2/2] Starting Frontend Server...
start "Lumina Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo ========================================
echo System started successfully!
echo.
echo - Backend:  http://localhost:8000
echo - Frontend: http://localhost:5173
echo - API Docs: http://localhost:8000/docs
echo.
echo Press any key to close this window...
pause > nul