# Email Finder & Verifier - Setup Test Script
Write-Host "=== Testing Email Finder & Verifier Setup ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Check Python
Write-Host "1. Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = .\venv\Scripts\python.exe --version
    Write-Host "   [OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "   [FAIL] Python not found in venv" -ForegroundColor Red
    exit 1
}

# Test 2: Check packages
Write-Host "2. Checking Python packages..." -ForegroundColor Yellow
try {
    $result = .\venv\Scripts\python.exe -c "import fastapi, dnspython, pandas, smtplib; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] All required packages installed" -ForegroundColor Green
    } else {
        Write-Host "   [FAIL] Missing packages" -ForegroundColor Red
    }
} catch {
    Write-Host "   [FAIL] Error checking packages" -ForegroundColor Red
}

# Test 3: Check imports
Write-Host "3. Testing module imports..." -ForegroundColor Yellow
$env:PYTHONPATH = "backend"
try {
    $result = .\venv\Scripts\python.exe -c "from email_finder import EmailFinder; from email_verifier import EmailVerifier; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Module imports working" -ForegroundColor Green
    } else {
        Write-Host "   [FAIL] Import failed" -ForegroundColor Red
    }
} catch {
    Write-Host "   [FAIL] Import error" -ForegroundColor Red
}

# Test 4: Check backend server
Write-Host "4. Testing backend server..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "   [OK] Backend is running on port 8000" -ForegroundColor Green
    Write-Host "   [OK] API Response: $($response.message)" -ForegroundColor Green
} catch {
    Write-Host "   [WARN] Backend not running. Start it with: .\run_backend.bat" -ForegroundColor Yellow
}

# Test 5: Check frontend
Write-Host "5. Checking frontend..." -ForegroundColor Yellow
if (Test-Path "frontend\node_modules") {
    Write-Host "   [OK] Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "   [WARN] Frontend dependencies not installed. Run: cd frontend; npm install" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the application:" -ForegroundColor White
Write-Host "  1. Backend:  .\run_backend.bat" -ForegroundColor Cyan
Write-Host "  2. Frontend: cd frontend; npm start" -ForegroundColor Cyan
Write-Host ""
