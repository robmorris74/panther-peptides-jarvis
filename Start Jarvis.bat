@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Jarvis needs Python 3. Please install Python from https://www.python.org/downloads/windows/ and choose "Add Python to PATH".
  start https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist .jarvis-venv py -3 -m venv .jarvis-venv
call .jarvis-venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if not exist data mkdir data
start "" "http://127.0.0.1:8000/"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
