@echo off
title TOEIC Whisper Launcher
echo ==========================================
echo   TOEIC Whisper - All-in-One Launcher
echo ==========================================

echo.
echo [1/2] Starting Backend Server (Python/FastAPI)...
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start "Backend Server" cmd /k "set WHISPERX_SERVICE_URL=http://localhost:8011 && set WHISPER_FW_SERVICE_URL=http://localhost:8010 && .venv\Scripts\python.exe backend_server.py"
) else (
    echo [WARN] .venv not found. Using system Python.
    start "Backend Server" cmd /k "set WHISPERX_SERVICE_URL=http://localhost:8011 && set WHISPER_FW_SERVICE_URL=http://localhost:8010 && python backend_server.py"
)

echo.
echo [2/2] Starting Frontend (Next.js)...
cd "frontend"
start "Frontend Client" cmd /k "npm run dev"

echo.
echo ==========================================
echo   All services are starting!
echo   - Backend: http://localhost:8000
echo   - Frontend: http://localhost:3000
echo ==========================================
echo.
pause
