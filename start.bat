@echo off
title LeadGen AI — Running
echo.
echo  ⚡ Starting LeadGen AI server...
echo  📊 Dashboard: http://localhost:8000
echo  📖 API Docs:  http://localhost:8000/docs
echo.
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
