@echo off
title TOEIC Whisper Launcher
echo ==========================================
echo   TOEIC Whisper - All-in-One Launcher
echo ==========================================

echo.
echo [1/3] Starting Ollama Server...
:: Start Ollama in a new minimized window. 
:: If it's already running, this might just show an error usage message which is fine.
start "Ollama" /min cmd /k "ollama serve"

echo.
echo [2/3] Starting Backend Server (Python/FastAPI)...
cd /d "%~dp0"
start "Backend Server" cmd /k "python backend_server.py"

echo.
echo [3/3] Starting Frontend (Next.js)...
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
