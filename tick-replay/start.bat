@echo off
REM Run Tick Replay from source (needs Python). Most people should use TickReplay.exe instead.
cd /d "%~dp0"
python -m pip install --quiet -r requirements.txt
python desktop.py
