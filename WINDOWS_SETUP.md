# Windows Setup Guide

## ✅ Virtual Environment Created

A virtual environment has been created and all dependencies are installed!

## 🚀 Starting the Application

### Option 1: Use the Batch File (Easiest)

**Start Backend:**
```powershell
.\run_backend.bat
```

**Start Frontend (in a new terminal):**
```powershell
.\run_frontend.bat
```

### Option 2: Manual Start

**Start Backend:**
```powershell
# Activate virtual environment
venv\Scripts\Activate.ps1

# Navigate to backend
cd backend

# Start server
python main.py
```

**Start Frontend (in a new terminal):**
```powershell
cd frontend
npm install  # First time only
npm start
```

## 🔧 If PowerShell Script Execution is Disabled

If you get an error about script execution, run this in PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## ✅ Verification

Once the backend is running, you should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Then open your browser to:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## 📝 Quick Test

Test the API in PowerShell:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/" -Method Get
```

You should see:
```json
{
  "message": "Email Finder & Verifier API",
  "version": "1.0.0"
}
```

## 🎯 Next Steps

1. Start the backend server
2. Start the frontend (in a separate terminal)
3. Open http://localhost:3000 in your browser
4. Start finding and verifying emails!

