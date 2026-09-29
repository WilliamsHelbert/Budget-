@echo off
REM Double-click to start Tick Replay on Windows.
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt
if not exist data\ticks (
  echo No tick data found - generating sample NQ/ES data...
  python tools\make_sample.py
)
start "" http://localhost:8000
python -m uvicorn server.app:app --port 8000
pause
