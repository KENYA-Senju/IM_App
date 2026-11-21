# Starts the IM backend server (IM_Backend.py) in the foreground.
# Usage:  powershell -File start_backend.ps1
# Stop with Ctrl+C.

Set-Location (Split-Path -Parent $PSCommandPath)

Write-Host "Installing requirements..."
& python -m pip install -r requirements.txt

Write-Host "Starting IM Backend on http://localhost:8000"
& python IM_Backend.py
