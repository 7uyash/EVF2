"""
Simple in-memory job manager for tracking long running CSV bulk operations.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional


class JobManager:
    """Thread-safe job registry used by bulk find/verify operations."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(self, job_type: str, total_rows: int, metadata: Optional[Dict[str, Any]] = None) -> str:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "type": job_type,
            "status": "pending",
            "total_rows": total_rows,
            "processed_rows": 0,
            "success_rows": 0,
            "error_rows": 0,
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "message": None,
            "output_path": None,
            "output_filename": None,
            "errors": [],
            "metadata": metadata or {},
        }
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def start_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "running"
            job["started_at"] = time.time()

    def increment(
        self,
        job_id: str,
        *,
        success: bool,
        message: Optional[str] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["processed_rows"] += 1
            if success:
                job["success_rows"] += 1
            else:
                job["error_rows"] += 1
                if error_detail:
                    job["errors"].append(error_detail)
                    # Keep error log short
                    job["errors"] = job["errors"][-10:]
            if message:
                job["message"] = message

    def complete_job(self, job_id: str, output_path: str, output_filename: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "completed"
            job["finished_at"] = time.time()
            job["output_path"] = output_path
            job["output_filename"] = output_filename

    def fail_job(self, job_id: str, error_detail: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "failed"
            job["finished_at"] = time.time()
            job["message"] = error_detail
            job["errors"].append(error_detail)
            job["errors"] = job["errors"][-10:]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            # Return a shallow copy to avoid accidental external mutation
            return dict(job)


