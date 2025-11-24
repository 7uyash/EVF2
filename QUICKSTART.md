# Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Backend Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 3: Start Backend Server

**Windows:**
```bash
run_backend.bat
```

**Mac/Linux:**
```bash
chmod +x run_backend.sh
./run_backend.sh
```

**Or manually:**
```bash
cd backend
python main.py
```

Backend will run on `http://localhost:8000`

### Step 4: Start Frontend (New Terminal)

**Windows:**
```bash
run_frontend.bat
```

**Mac/Linux:**
```bash
chmod +x run_frontend.sh
./run_frontend.sh
```

**Or manually:**
```bash
cd frontend
npm start
```

Frontend will open at `http://localhost:3000`

## 📝 Testing

### Test Email Finder API
```bash
curl -X POST http://localhost:8000/api/find ^
  -H "Content-Type: application/json" ^
  -d "{\"first_name\": \"John\", \"last_name\": \"Doe\", \"domain\": \"example.com\"}"
```

### Test Email Verifier API
```bash
curl -X POST http://localhost:8000/api/verify ^
  -H "Content-Type: application/json" ^
  -d "{\"email\": \"test@example.com\"}"
```

## 📊 CSV Examples

See `examples/` folder for sample CSV files:
- `bulk_find_example.csv` - For bulk email finding
- `bulk_verify_example.csv` - For bulk email verification

## ⚠️ Troubleshooting

### Port Already in Use
- Backend: Change port in `backend/main.py` (line 253)
- Frontend: React will prompt to use different port

### Import Errors
- Make sure you're in the correct directory
- Virtual environment is activated
- All dependencies are installed

### SMTP Connection Issues
- Some networks block port 25
- Try from different network or use VPN
- Some mail servers block SMTP checks for security

## 🎯 Next Steps

1. Open `http://localhost:3000` in your browser
2. Try the Email Finder tab
3. Try the Email Verifier tab
4. Upload a CSV for bulk processing

Happy email finding! 📧

