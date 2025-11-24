# 🔧 Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: Backend Won't Start

**Symptoms:**
- Error: "ModuleNotFoundError: No module named 'email_finder'"
- Error: "Cannot find module"

**Solution:**
The backend must be run from the project root, not from inside the `backend` folder.

**Correct way:**
```powershell
# From project root (D:\Projects_working\vanya)
.\run_backend.bat
```

**Or manually:**
```powershell
venv\Scripts\Activate.ps1
$env:PYTHONPATH="backend"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Issue 2: Port Already in Use

**Symptoms:**
- Error: "Address already in use"
- Port 8000 is busy

**Solution:**
```powershell
# Find and kill the process using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

Or change the port in `backend/main.py` (line 254):
```python
uvicorn.run(app, host="0.0.0.0", port=8001)  # Change to 8001
```

### Issue 3: Frontend Won't Start

**Symptoms:**
- Error: "npm: command not found"
- Error: "Cannot find module 'react'"

**Solution:**
```powershell
cd frontend
npm install
npm start
```

### Issue 4: CORS Errors in Browser

**Symptoms:**
- Browser console shows CORS errors
- API calls fail from frontend

**Solution:**
The backend already has CORS enabled. Make sure:
1. Backend is running on `http://localhost:8000`
2. Frontend is running on `http://localhost:3000`
3. Check browser console for exact error

### Issue 5: SMTP Connection Timeouts

**Symptoms:**
- Email verification takes too long
- Timeout errors

**Solution:**
Some mail servers block SMTP connections. This is normal. The tool will:
- Try multiple MX servers
- Return "unknown" status if all fail
- Still provide DNS/MX/SPF/DKIM/DMARC checks

### Issue 6: Virtual Environment Not Activating

**Symptoms:**
- "venv\Scripts\Activate.ps1 cannot be loaded"

**Solution:**
```powershell
# Run as Administrator, then:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or use the direct Python path:
```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Issue 7: Import Errors

**Symptoms:**
- "ImportError: cannot import name 'EmailFinder'"

**Solution:**
Make sure you're running from the project root:
```powershell
# Check current directory
pwd  # Should show: D:\Projects_working\vanya

# If in backend folder, go back:
cd ..
```

### Issue 8: CSV Upload Not Working

**Symptoms:**
- File upload fails
- No download starts

**Solution:**
1. Check CSV format matches examples in `examples/` folder
2. For bulk-find: CSV needs `first_name`, `last_name`, `domain` columns
3. For bulk-verify: CSV needs `email` column
4. Check browser console for errors

## ✅ Quick Health Check

Run these commands to verify everything is set up:

```powershell
# 1. Check Python and virtual environment
.\venv\Scripts\python.exe --version

# 2. Check if packages are installed
.\venv\Scripts\python.exe -c "import fastapi, dnspython, pandas; print('All packages OK')"

# 3. Test backend imports
$env:PYTHONPATH="backend"
.\venv\Scripts\python.exe -c "from email_finder import EmailFinder; print('Imports OK')"

# 4. Test backend API (after starting server)
Invoke-RestMethod -Uri "http://localhost:8000/" -Method Get

# 5. Check frontend dependencies
cd frontend
Test-Path "node_modules"
```

## 🚀 Step-by-Step Startup

1. **Start Backend:**
   ```powershell
   .\run_backend.bat
   ```
   Wait for: `INFO:     Uvicorn running on http://0.0.0.0:8000`

2. **Start Frontend (new terminal):**
   ```powershell
   cd frontend
   npm start
   ```
   Wait for browser to open at `http://localhost:3000`

3. **Test:**
   - Open http://localhost:3000
   - Try Email Finder tab
   - Try Email Verifier tab

## 📞 Still Having Issues?

1. Check all error messages carefully
2. Verify you're in the project root directory
3. Make sure virtual environment is activated
4. Check that ports 8000 and 3000 are available
5. Review browser console for frontend errors
6. Review terminal output for backend errors

## 🔍 Debug Mode

To see detailed error messages:

**Backend:**
```powershell
$env:PYTHONPATH="backend"
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

**Frontend:**
Check browser Developer Tools (F12) → Console tab

