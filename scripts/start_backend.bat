@echo off
title ResQtech FastAPI Backend Server
cd /d "%~dp0.."
echo ===============================================================================
echo RESQTECH (SIH26001) - FASTAPI BACKEND SERVER
echo Starting Uvicorn API server on http://127.0.0.1:8000
echo ===============================================================================
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
