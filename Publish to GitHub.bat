@echo off
rem Puts this app on GitHub (private repo "ipo-daily-rrg") so Streamlit Cloud can host it.
rem Run it by double-clicking. Safe to run again: it only pushes new commits the second time.
title Publish IPO RRG app to GitHub
cd /d "%~dp0"

echo === 1. GitHub login ===
gh auth status
if errorlevel 1 (
    echo Not logged in - a browser window will open. Enter the code it shows.
    gh auth login --web --git-protocol https --hostname github.com
)

echo.
echo === 2. Repository ===
gh repo view ipo-daily-rrg >nul 2>&1
if errorlevel 1 (
    echo Creating private repo ipo-daily-rrg and pushing the code...
    gh repo create ipo-daily-rrg --private --source=. --remote=origin --push
) else (
    echo Repo exists - pushing the latest commits...
    git remote get-url origin >nul 2>&1 || git remote add origin https://github.com/deepanshuswami8828-star/ipo-daily-rrg.git
    git push -u origin main
)

echo.
echo === 3. Check ===
git log origin/main --oneline -3
echo.
echo If you see commits above, it worked. Now open:
echo https://share.streamlit.io/deploy?repository=deepanshuswami8828-star/ipo-daily-rrg^&branch=main^&mainModule=app.py
echo.
pause
