@echo off
call venv\Scripts\activate.bat
set PYTHONPATH=backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause

