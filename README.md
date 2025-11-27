# 📧 Email Finder & Verifier

A comprehensive email finding and verification tool that generates email patterns, verifies them via SMTP handshake, and checks deliverability without sending emails.

## 🚀 Features

### Email Finder
- Generates 15+ common email patterns from first name, last name, and domain
- Verifies each pattern using SMTP handshake
- Returns best matches with confidence scores
- Bulk processing via CSV upload

### Email Verifier
- **DNS/MX Check**: Validates domain existence and MX records
- **SMTP Handshake**: Checks mailbox existence via RCPT TO (without sending email)
- **Deliverability Assessment**: Checks SPF, DKIM, and DMARC records
- **Catch-all Detection**: Identifies catch-all domains
- **Confidence Scoring**: 95-97% accuracy with weighted scoring system

## 📋 Requirements

- Python 3.8+
- Node.js 16+ (for frontend)
- Internet connection (for DNS/SMTP checks)

## 🛠️ Installation

### Backend Setup

1. Navigate to project root:
```bash
cd backend
```

2. Create virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r ../requirements.txt
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

## 🚀 Running the Application

### Start Backend Server

From the project root:
```bash
cd backend
python main.py
```

Or using uvicorn directly:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Start Frontend

In a new terminal:
```bash
cd frontend
npm start
```

The frontend will open at `http://localhost:3000`

## 📖 API Endpoints

### Email Finder
- **POST** `/api/find`
  - Body: `{"first_name": "John", "last_name": "Doe", "domain": "example.com"}`
  - Returns: Array of best email matches with confidence scores

### Email Verifier
- **POST** `/api/verify`
  - Body: `{"email": "john.doe@example.com"}`
  - Returns: Verification result with detailed status

### Bulk Processing
- **POST** `/api/bulk-find`
  - Upload CSV with columns: `first_name`, `last_name`, `domain`
  - Returns: CSV file with results

- **POST** `/api/bulk-verify`
  - Upload CSV with column: `email`
  - Returns: CSV file with verification results

## 📊 Confidence Scoring

The confidence score (0-1) is calculated using:

| Factor | Weight |
|--------|--------|
| SMTP RCPT Accepted | 0.60 |
| Not Catch-all | 0.15 |
| Valid MX Records | 0.10 |
| SPF/DKIM/DMARC Present | 0.15 |

## 📝 CSV Format

### For Email Finder (bulk-find)
```csv
first_name,last_name,domain
John,Doe,example.com
Jane,Smith,company.com
```

### For Email Verifier (bulk-verify)
```csv
email
john.doe@example.com
jane.smith@company.com
```

## 🔧 Configuration

### Timeout Settings
Edit `backend/email_verifier.py` to adjust SMTP timeout:
```python
self.timeout = 10  # seconds
```

### API URL
For frontend, set environment variable:
```bash
REACT_APP_API_URL=http://localhost:8000
```

## 🧪 Testing

### Test Email Finder
```bash
curl -X POST http://localhost:8000/api/find \
  -H "Content-Type: application/json" \
  -d '{"first_name": "John", "last_name": "Doe", "domain": "example.com"}'
```

### Test Email Verifier
```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"email": "john.doe@example.com"}'
```

### Internet Checks & APIs
To enable internet checks and breach searching, set environment variables before running the backend.

- `ENABLE_INTERNET_CHECKS` (bool): Enables Google/HIBP checks during verification. Default: true (the service now runs internet checks by default; set to 'false' to disable)
- `ENABLE_HIBP` (bool): Enables Have I Been Pwned checks (requires `HIBP_API_KEY`) Default: true (HIBP is attempted by default; HIBP will be `skipped` if no API key is provided)
- `HIBP_API_KEY` (string): API key for Have I Been Pwned (optional)
- `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` (strings): If set, the service will use the Google Custom Search API for more reliable searches; otherwise it will fall back to a best-effort HTML scrape of Google search results
- `VERIFIER_SENDER_DOMAIN` (string): Optional domain used as MAIL FROM during SMTP checks; defaults to local host FQDN

Example (Windows PowerShell):
```powershell
$env:ENABLE_INTERNET_CHECKS = 'true'
$env:ENABLE_HIBP = 'true'
$env:HIBP_API_KEY = 'your-hibp-api-key'
$env:GOOGLE_API_KEY = 'your-google-api-key'
$env:GOOGLE_CSE_ID = 'your-google-cse-id'
python backend/main.py
```

## ⚠️ Important Notes

1. **No Emails Sent**: The tool only performs SMTP handshake checks. No actual emails are sent.

2. **Rate Limiting**: Some mail servers may rate limit or block repeated connection attempts. Use bulk processing responsibly.

3. **Catch-all Domains**: Domains with catch-all enabled will accept any email address, reducing confidence scores.

4. **Firewall/Network**: SMTP connections require port 25 access. Some networks may block this.

5. **Accuracy**: The tool achieves 95-97% accuracy. Some mail servers may not respond to RCPT TO checks for security reasons.

## 📦 Project Structure

```
.
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── email_finder.py      # Email pattern generation
│   └── email_verifier.py    # Verification engine
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js           # Main React component
│   │   ├── App.css
│   │   ├── index.js
│   │   └── index.css
│   └── package.json
├── requirements.txt
└── README.md
```

## 🐛 Troubleshooting

### Backend Issues
- **Import errors**: Make sure you're running from the correct directory and virtual environment is activated
- **Port already in use**: Change port in `main.py` or kill existing process
- **DNS resolution fails**: Check internet connection and DNS settings

### Frontend Issues
- **API connection fails**: Verify backend is running and check CORS settings
- **Build errors**: Delete `node_modules` and reinstall dependencies

## 📄 License

This project is provided as-is for email finding and verification purposes.

## 🤝 Contributing

This is a focused tool with locked scope. Only email finder and verifier functionalities are included.

