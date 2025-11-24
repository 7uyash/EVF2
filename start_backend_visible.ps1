# Start backend in visible window with logging
$env:PYTHONPATH = "backend"
cd $PSScriptRoot
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info

