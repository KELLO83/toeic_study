@echo off
setlocal
title TOEIC ASR Docker Launcher

cd /d "%~dp0"

echo ==========================================
echo   TOEIC ASR Docker Launcher (FW + WX)
echo ==========================================

if not exist "uploads" (
    mkdir "uploads"
)

echo.
echo [1/4] Cleaning previous ASR containers...
docker rm -f toeic-fw >nul 2>&1
docker rm -f toeic-wx >nul 2>&1

echo.
echo [2/4] Starting faster-whisper service (8010)...
start "ASR-FW (8010)" cmd /k docker run --gpus all --rm --name toeic-fw -p 8010:8010 -v "%CD%\uploads:/app/uploads" toeic-asr-fw

echo.
echo [3/4] Starting WhisperX service (8011)...
start "ASR-WX (8011)" cmd /k docker run --gpus all --rm --name toeic-wx -p 8011:8011 -v "%CD%\uploads:/app/uploads" toeic-asr-wx

echo.
echo [4/4] Waiting for services to boot...
timeout /t 5 /nobreak >nul

echo.
echo Health check:
curl http://localhost:8010/health
curl http://localhost:8011/health

echo.
echo ==========================================
echo   Expected:
echo   - FW: {"status":"ok"}
echo   - WX: {"status":"ok","device":"cuda"}
echo ==========================================
echo.
pause
