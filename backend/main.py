"""
FastAPI Backend for Email Finder and Verifier
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import pandas as pd
import io
import csv
import tempfile
from datetime import datetime
import os

try:
    from email_finder import EmailFinder
    from email_verifier import EmailVerifier
except ImportError:
    # If running from parent directory
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from email_finder import EmailFinder
    from email_verifier import EmailVerifier

app = FastAPI(title="Email Finder & Verifier API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
finder = EmailFinder()
verifier = EmailVerifier()


# Request models
class EmailFindRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str
    max_results: Optional[int] = None
    max_patterns: Optional[int] = None


class EmailVerifyRequest(BaseModel):
    email: str


class BulkFindRequest(BaseModel):
    entries: List[EmailFindRequest]


# Response models
class EmailFindResponse(BaseModel):
    email: Optional[str] = None
    status: str
    confidence: float
    reason: Optional[str] = None


class EmailVerifyResponse(BaseModel):
    email: str
    status: str
    confidence: float
    reason: str
    details: dict


@app.get("/")
async def root():
    return {"message": "Email Finder & Verifier API", "version": "1.0.0"}


@app.post("/api/find", response_model=List[EmailFindResponse])
async def find_email(request: EmailFindRequest):
    """Find best email(s) for a person"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Finding email for {request.first_name} {request.last_name} @ {request.domain}")
    
    max_results = request.max_results or 2
    max_patterns = request.max_patterns or max_results * 4

    # Clamp values to keep response fast and avoid server overload
    max_results = max(1, min(max_results, 20))
    max_patterns = max(max_results, min(max_patterns, 60))

    try:
        results = finder.find_best_emails(
            request.first_name,
            request.last_name,
            request.domain,
            max_results=max_results,
            max_patterns=max_patterns
        )
        
        logger.info(f"Found {len(results)} results")
        
        if not results:
            return [EmailFindResponse(
                email=None,
                status="not_found",
                confidence=0.0,
                reason="No valid email patterns found"
            )]
        
        return [EmailFindResponse(**r) for r in results]
    except Exception as e:
        logger.error(f"Error finding email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify", response_model=EmailVerifyResponse)
async def verify_email(request: EmailVerifyRequest):
    """Verify a single email address"""
    try:
        result = verifier.verify_email(request.email)
        return EmailVerifyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bulk-find")
async def bulk_find_email(file: UploadFile = File(...)):
    """Bulk find emails from CSV file"""
    try:
        # Read CSV
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate columns
        required_columns = ['first_name', 'last_name', 'domain']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}"
            )
        
        # Process each row
        results = []
        for _, row in df.iterrows():
            try:
                emails = finder.find_best_emails(
                    str(row['first_name']),
                    str(row['last_name']),
                    str(row['domain']),
                    max_results=1
                )
                
                if emails:
                    result = emails[0]
                    results.append({
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'domain': row['domain'],
                        'email': result['email'],
                        'status': result['status'],
                        'confidence': result['confidence'],
                        'reason': result.get('reason', '')
                    })
                else:
                    results.append({
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'domain': row['domain'],
                        'email': '',
                        'status': 'not_found',
                        'confidence': 0.0,
                        'reason': 'No valid email found'
                    })
            except Exception as e:
                results.append({
                    'first_name': row.get('first_name', ''),
                    'last_name': row.get('last_name', ''),
                    'domain': row.get('domain', ''),
                    'email': '',
                    'status': 'error',
                    'confidence': 0.0,
                    'reason': str(e)
                })
        
        # Create output CSV
        output_df = pd.DataFrame(results)
        output_csv = output_df.to_csv(index=False)
        
        # Save to temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_finder_results_{timestamp}.csv"
        
        # Use temp directory (works on Windows and Unix)
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        output_df.to_csv(filepath, index=False)
        
        return FileResponse(
            filepath,
            media_type="text/csv",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bulk-verify")
async def bulk_verify_email(file: UploadFile = File(...)):
    """Bulk verify emails from CSV file"""
    try:
        # Read CSV
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate columns
        if 'email' not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Missing required column: email"
            )
        
        # Process each row
        results = []
        for _, row in df.iterrows():
            try:
                email = str(row['email']).strip()
                if not email:
                    continue
                
                verification = verifier.verify_email(email)
                results.append({
                    'email': email,
                    'status': verification['status'],
                    'confidence': verification['confidence'],
                    'reason': verification.get('reason', '')
                })
            except Exception as e:
                results.append({
                    'email': row.get('email', ''),
                    'status': 'error',
                    'confidence': 0.0,
                    'reason': str(e)
                })
        
        # Create output CSV
        output_df = pd.DataFrame(results)
        
        # Save to temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_verifier_results_{timestamp}.csv"
        
        # Use temp directory (works on Windows and Unix)
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        output_df.to_csv(filepath, index=False)
        
        return FileResponse(
            filepath,
            media_type="text/csv",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

