@echo off
title IM Backend
cd /d "%~dp0"

echo Installing requirements...
python -m pip install -r requirements.txt >nul 2>&1

echo Starting IM Backend on http://localhost:8000
python IM_Backend.py
