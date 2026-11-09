@echo off
rem Starts the 2026 IPO Daily RRG app and opens it in the browser.
title IPO Daily RRG app - keep this window open while using the app
cd /d "%~dp0"

set PORT=8502
set URL=http://localhost:%PORT%
set PY=C:\Users\Lenovo\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PY%" set PY=python

netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
    echo App is already running - opening %URL%
    start "" "%URL%"
    exit /b 0
)

echo Starting IPO Daily RRG app on %URL% ...
echo Close this window to stop the app.
"%PY%" -m streamlit run app.py --server.port %PORT% --server.headless false --browser.serverAddress localhost --browser.gatherUsageStats false
pause
