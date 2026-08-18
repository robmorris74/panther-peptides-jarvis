#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display dialog "Jarvis needs Python 3 installed on this Mac. Install Python from python.org, then double-click Start Jarvis again." buttons {"OK"} default button 1 with icon caution'
  open "https://www.python.org/downloads/macos/"
  exit 1
fi
if [ ! -d .jarvis-venv ]; then python3 -m venv .jarvis-venv; fi
. .jarvis-venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
mkdir -p data
( sleep 3; open "http://127.0.0.1:8000/" ) &
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
