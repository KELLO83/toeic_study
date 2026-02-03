@echo off
setlocal

REM Create and activate virtual environment (Python 3.11)
py -3.11 -m venv .venv
call .venv\Scripts\activate

REM Upgrade packaging tools
python -m pip install --upgrade pip setuptools wheel

REM Install CUDA-matched PyTorch stack first
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121

REM Install remaining locked dependencies
pip install -r requirements-lock.txt

echo.
echo [OK] Environment setup complete.
echo To activate later: .venv\Scripts\activate
endlocal
