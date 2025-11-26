"""
FastAPI Backend for Email Finder and Verifier
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import csv
import tempfile
from datetime import datetime
import os
from job_manager import JobManager

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
job_manager = JobManager()
bulk_executor = ThreadPoolExecutor(max_workers=4)


# Request models
class EmailFindRequest(BaseModel):
    first_name: str
    last_name: str
    domain: str
    max_results: Optional[int] = None
    max_patterns: Optional[int] = None
    custom_patterns: Optional[List[str]] = None
    include_default_patterns: bool = True
    fast_mode: bool = True
    confidence_mode: Optional[str] = "balanced"


class EmailVerifyRequest(BaseModel):
    email: str
    fast_mode: bool = True
    confidence_mode: Optional[str] = "balanced"


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
    fast_mode = request.fast_mode if request.fast_mode is not None else True
    confidence_mode = (request.confidence_mode or "balanced").lower()

    # Clamp values to keep response fast and avoid server overload
    max_results = max(1, min(max_results, 20))
    max_patterns = max(max_results, min(max_patterns, 60))

    try:
        results = finder.find_best_emails(
            request.first_name,
            request.last_name,
            request.domain,
            max_results=max_results,
            max_patterns=max_patterns,
            custom_patterns=request.custom_patterns,
            include_defaults=request.include_default_patterns,
            fast_mode=fast_mode,
            confidence_mode=confidence_mode,
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
        result = verifier.verify_email(
            request.email,
            fast_mode=request.fast_mode,
            confidence_mode=request.confidence_mode or "balanced",
        )
        return EmailVerifyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bulk-find")
async def bulk_find_email(
    file: UploadFile = File(...),
    fast_mode: bool = Form(True),
    confidence_mode: str = Form("balanced"),
):
    """Schedule bulk find job from CSV file"""
    temp_path = None
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(contents)
            temp_path = tmp.name
        
        df = pd.read_csv(temp_path)
        required_columns = ['first_name', 'last_name', 'domain']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}"
            )
        
        total_rows = len(df.index)
        job_id = job_manager.create_job(
            "bulk_find",
            total_rows,
            {"fast_mode": fast_mode, "confidence_mode": confidence_mode},
        )
        bulk_executor.submit(
            process_bulk_find_job,
            job_id,
            temp_path,
            fast_mode,
            confidence_mode,
        )
        temp_path = None  # Worker owns cleanup
        
        return {"job_id": job_id, "total_rows": total_rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/bulk-verify")
async def bulk_verify_email(
    file: UploadFile = File(...),
    fast_mode: bool = Form(True),
    confidence_mode: str = Form("balanced"),
):
    """Schedule bulk verify job from CSV file"""
    temp_path = None
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(contents)
            temp_path = tmp.name
        
        df = pd.read_csv(temp_path)
        if 'email' not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Missing required column: email"
            )
        
        total_rows = len(df.index)
        job_id = job_manager.create_job(
            "bulk_verify",
            total_rows,
            {"fast_mode": fast_mode, "confidence_mode": confidence_mode},
        )
        bulk_executor.submit(
            process_bulk_verify_job,
            job_id,
            temp_path,
            fast_mode,
            confidence_mode,
        )
        temp_path = None
        
        return {"job_id": job_id, "total_rows": total_rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    total = job["total_rows"] or 0
    progress = 0.0
    if total > 0:
        progress = job["processed_rows"] / total
    
    return {
        "id": job["id"],
        "type": job["type"],
        "status": job["status"],
        "total_rows": total,
        "processed_rows": job["processed_rows"],
        "success_rows": job["success_rows"],
        "error_rows": job["error_rows"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "message": job["message"],
        "progress": round(progress * 100, 2),
        "download_ready": job["status"] == "completed" and bool(job["output_path"]),
        "recent_errors": job["errors"],
    }


@app.get("/api/jobs/{job_id}/download")
async def download_job_file(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "completed" or not job["output_path"]:
        raise HTTPException(status_code=400, detail="Job output not ready")
    if not os.path.exists(job["output_path"]):
        raise HTTPException(status_code=404, detail="Output file missing")
    
    filename = job["output_filename"] or os.path.basename(job["output_path"])
    return FileResponse(
        job["output_path"],
        media_type="text/csv",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _normalize_cell(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def process_bulk_find_job(
    job_id: str,
    input_path: str,
    fast_mode: bool,
    confidence_mode: str,
) -> None:
    job_manager.start_job(job_id)
    output_path = None
    try:
        df = pd.read_csv(input_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_finder_results_{timestamp}.csv"
        output_path = os.path.join(tempfile.gettempdir(), filename)
        fieldnames = ['first_name', 'last_name', 'domain', 'email', 'status', 'confidence', 'reason']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for _, row in df.iterrows():
                first = _normalize_cell(row.get('first_name', ''))
                last = _normalize_cell(row.get('last_name', ''))
                domain = _normalize_cell(row.get('domain', ''))
                
                if not first or not last or not domain:
                    writer.writerow({
                        'first_name': first,
                        'last_name': last,
                        'domain': domain,
                        'email': '',
                        'status': 'missing_fields',
                        'confidence': 0.0,
                        'reason': 'Required fields missing'
                    })
                    job_manager.increment(job_id, success=False, error_detail="Missing required fields")
                    continue
                
                try:
                    emails = finder.find_best_emails(
                        first,
                        last,
                        domain,
                        max_results=1,
                        fast_mode=fast_mode,
                        confidence_mode=confidence_mode,
                    )
                    if emails:
                        result = emails[0]
                        writer.writerow({
                            'first_name': first,
                            'last_name': last,
                            'domain': domain,
                            'email': result['email'],
                            'status': result['status'],
                            'confidence': result['confidence'],
                            'reason': result.get('reason', '')
                        })
                        job_manager.increment(job_id, success=True, message=result['status'])
                    else:
                        writer.writerow({
                            'first_name': first,
                            'last_name': last,
                            'domain': domain,
                            'email': '',
                            'status': 'not_found',
                            'confidence': 0.0,
                            'reason': 'No valid email found'
                        })
                        job_manager.increment(job_id, success=False, message="not_found")
                except Exception as exc:
                    writer.writerow({
                        'first_name': first,
                        'last_name': last,
                        'domain': domain,
                        'email': '',
                        'status': 'error',
                        'confidence': 0.0,
                        'reason': str(exc)
                    })
                    job_manager.increment(job_id, success=False, error_detail=str(exc))
        
        job_manager.complete_job(job_id, output_path, filename)
    except Exception as exc:
        job_manager.fail_job(job_id, str(exc))
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


def process_bulk_verify_job(
    job_id: str,
    input_path: str,
    fast_mode: bool,
    confidence_mode: str,
) -> None:
    job_manager.start_job(job_id)
    output_path = None
    try:
        df = pd.read_csv(input_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_verifier_results_{timestamp}.csv"
        output_path = os.path.join(tempfile.gettempdir(), filename)
        fieldnames = ['email', 'status', 'confidence', 'reason']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for _, row in df.iterrows():
                email = _normalize_cell(row.get('email', ''))
                if not email:
                    writer.writerow({
                        'email': '',
                        'status': 'missing_email',
                        'confidence': 0.0,
                        'reason': 'Email value missing'
                    })
                    job_manager.increment(job_id, success=False, error_detail="Email value missing")
                    continue
                
                try:
                    verification = verifier.verify_email(
                        email,
                        fast_mode=fast_mode,
                        confidence_mode=confidence_mode,
                    )
                    writer.writerow({
                        'email': email,
                        'status': verification['status'],
                        'confidence': verification['confidence'],
                        'reason': verification.get('reason', '')
                    })
                    job_manager.increment(job_id, success=True, message=verification['status'])
                except Exception as exc:
                    writer.writerow({
                        'email': email,
                        'status': 'error',
                        'confidence': 0.0,
                        'reason': str(exc)
                    })
                    job_manager.increment(job_id, success=False, error_detail=str(exc))
        
        job_manager.complete_job(job_id, output_path, filename)
    except Exception as exc:
        job_manager.fail_job(job_id, str(exc))
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

