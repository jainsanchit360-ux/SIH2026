@echo off
title ResQtech One-Click Demo Launcher
cd /d "%~dp0.."
echo ===============================================================================
echo RESQTECH (SIH26001) - ONE-CLICK DEMO LAUNCHER
echo Starting FastAPI Backend (Port 8000) and React GIS Dashboard (Port 5173)
echo ===============================================================================
start "ResQtech Backend" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
timeout /t 3 /nobreak >nul
start "ResQtech Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo.
echo ResQtech environment launched.
echo Backend API: http://127.0.0.1:8000/docs
echo Frontend GIS Dashboard: http://localhost:5173
echo.
pause
