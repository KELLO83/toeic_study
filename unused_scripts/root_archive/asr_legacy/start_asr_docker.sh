#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=========================================="
echo "  TOEIC ASR Docker Launcher (FW + WX)"
echo "=========================================="

mkdir -p uploads

echo "[1/4] Cleaning previous ASR containers..."
docker rm -f toeic-fw >/dev/null 2>&1 || true
docker rm -f toeic-wx >/dev/null 2>&1 || true

echo "[2/4] Starting faster-whisper service (8010)..."
docker run -d --gpus all --name toeic-fw -p 8010:8010 -v "$PWD/uploads:/app/uploads" toeic-asr-fw >/dev/null

echo "[3/4] Starting WhisperX service (8011)..."
docker run -d --gpus all --name toeic-wx -p 8011:8011 -v "$PWD/uploads:/app/uploads" toeic-asr-wx >/dev/null

echo "[4/4] Waiting for services to boot..."
sleep 5

echo "Health check:"
curl -fsS http://localhost:8010/health && echo
curl -fsS http://localhost:8011/health && echo

echo "Done."
echo "Logs:"
echo "  docker logs -f toeic-fw"
echo "  docker logs -f toeic-wx"

