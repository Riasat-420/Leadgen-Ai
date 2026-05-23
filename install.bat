@echo off
title LeadGen AI — Installer
echo.
echo  ███████████████████████████████████████████
echo   LeadGen AI — Installing dependencies...
echo  ███████████████████████████████████████████
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b
)

echo [1/4] Installing Python packages...
pip install -r requirements.txt

echo.
echo [2/4] Installing Playwright browsers...
playwright install chromium

echo.
echo [3/4] Creating .env file from example...
if not exist .env (
    copy .env.example .env
    echo     Created .env — please edit it with your API keys!
) else (
    echo     .env already exists — skipping
)

echo.
echo [4/4] Creating database...
cd backend
python -c "from database import create_tables; create_tables(); print('Database created!')"
cd ..

echo.
echo  ████████████████████████████████████████████████
echo   ✅ Installation complete!
echo.
echo   NEXT STEPS:
echo   1. Edit .env and add your GEMINI_API_KEY
echo   2. Add your GMAIL_USER and GMAIL_APP_PASSWORD
echo   3. Run start.bat to launch the server
echo   4. Open http://localhost:8000 in your browser
echo  ████████████████████████████████████████████████
echo.
pause
