#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q -r requirements.txt
python -m app.import_catalog >/dev/null 2>&1 || true
python -m app.seed_panther
python scripts/seed_training.py
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
