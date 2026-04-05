"""Background import service for managing long-running imports"""
import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Persistent storage path
JOBS_STORAGE_PATH = Path("/app/data/import_jobs.json")


class ImportStatus(str, Enum):
    """Import job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportJob:
    """Represents a background import job"""

    def __init__(
        self,
        job_id: str,
        file_path: str,
        breach_name: str,
        column_mapping: Dict[str, str],
        breach_date: Optional[int] = None,
        batch_size: int = 1000,
        turbo_mode: bool = False
    ):
        self.job_id = job_id
        self.file_path = file_path
        self.breach_name = breach_name
        self.column_mapping = column_mapping
        self.breach_date = breach_date
        self.batch_size = batch_size
        self.turbo_mode = turbo_mode

        # Status tracking
        self.status = ImportStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

        # Progress tracking
        self.total_lines = 0
        self.processed_lines = 0
        self.imported_count = 0
        self.error_count = 0
        self.current_batch = 0
        self.total_batches = 0

        # Error tracking
        self.error_message: Optional[str] = None

        # Task reference for cancellation
        self.task: Optional[asyncio.Task] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for API response"""
        elapsed_time = None
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            elapsed_time = (end_time - self.started_at).total_seconds()

        # Calculate progress percentage
        progress = 0
        if self.total_lines > 0:
            progress = (self.processed_lines / self.total_lines) * 100

        # Calculate speed (lines/sec)
        speed = 0
        if elapsed_time and elapsed_time > 0:
            speed = self.processed_lines / elapsed_time

        # Estimate remaining time
        eta_seconds = None
        if speed > 0 and self.total_lines > 0:
            remaining_lines = self.total_lines - self.processed_lines
            eta_seconds = remaining_lines / speed

        return {
            "job_id": self.job_id,
            "file_path": self.file_path,
            "breach_name": self.breach_name,
            "column_mapping": self.column_mapping,
            "breach_date": self.breach_date,
            "batch_size": self.batch_size,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": {
                "total_lines": self.total_lines,
                "processed_lines": self.processed_lines,
                "imported_count": self.imported_count,
                "error_count": self.error_count,
                "current_batch": self.current_batch,
                "total_batches": self.total_batches,
                "percentage": round(progress, 2),
                "speed_lines_per_sec": round(speed, 2) if speed else 0,
                "eta_seconds": round(eta_seconds) if eta_seconds else None,
                "elapsed_seconds": round(elapsed_time) if elapsed_time else 0
            },
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImportJob':
        """Create job from dictionary"""
        job = cls(
            job_id=data['job_id'],
            file_path=data['file_path'],
            breach_name=data['breach_name'],
            column_mapping=data['column_mapping'],
            breach_date=data.get('breach_date'),
            batch_size=data.get('batch_size', 1000)
        )

        job.status = ImportStatus(data['status'])
        job.created_at = datetime.fromisoformat(data['created_at'])
        job.started_at = datetime.fromisoformat(data['started_at']) if data.get('started_at') else None
        job.completed_at = datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None

        progress = data.get('progress', {})
        job.total_lines = progress.get('total_lines', 0)
        job.processed_lines = progress.get('processed_lines', 0)
        job.imported_count = progress.get('imported_count', 0)
        job.error_count = progress.get('error_count', 0)
        job.current_batch = progress.get('current_batch', 0)
        job.total_batches = progress.get('total_batches', 0)

        job.error_message = data.get('error_message')

        return job


class BackgroundImportService:
    """Service for managing background import jobs"""

    def __init__(self):
        self.jobs: Dict[str, ImportJob] = {}
        self._lock = asyncio.Lock()
        self._load_jobs()

    def create_job(
        self,
        file_path: str,
        breach_name: str,
        column_mapping: Dict[str, str],
        breach_date: Optional[int] = None,
        batch_size: int = 1000,
        turbo_mode: bool = False
    ) -> ImportJob:
        """Create a new import job"""
        job_id = str(uuid.uuid4())
        job = ImportJob(
            job_id=job_id,
            file_path=file_path,
            breach_name=breach_name,
            column_mapping=column_mapping,
            breach_date=breach_date,
            batch_size=batch_size,
            turbo_mode=turbo_mode
        )
        self.jobs[job_id] = job
        self._save_jobs()
        logger.info(f"Created import job {job_id} for breach {breach_name}")
        return job

    def get_job(self, job_id: str) -> Optional[ImportJob]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> Dict[str, ImportJob]:
        """Get all jobs"""
        return self.jobs

    async def start_job(self, job_id: str) -> bool:
        """Start a job (called by the job executor)"""
        job = self.get_job(job_id)
        if not job:
            return False

        async with self._lock:
            if job.status != ImportStatus.PENDING:
                logger.warning(f"Job {job_id} is not pending, cannot start")
                return False

            job.status = ImportStatus.RUNNING
            job.started_at = datetime.now()
            logger.info(f"Started import job {job_id}")
            return True

    async def update_progress(
        self,
        job_id: str,
        total_lines: int = None,
        processed_lines: int = None,
        imported_count: int = None,
        error_count: int = None,
        current_batch: int = None,
        total_batches: int = None
    ):
        """Update job progress"""
        job = self.get_job(job_id)
        if not job:
            return

        if total_lines is not None:
            job.total_lines = total_lines
        if processed_lines is not None:
            job.processed_lines = processed_lines
        if imported_count is not None:
            job.imported_count = imported_count
        if error_count is not None:
            job.error_count = error_count
        if current_batch is not None:
            job.current_batch = current_batch
        if total_batches is not None:
            job.total_batches = total_batches

        # Save every 10 batches to avoid too frequent disk writes
        if current_batch and current_batch % 10 == 0:
            self._save_jobs()

    async def complete_job(self, job_id: str, error_message: Optional[str] = None):
        """Mark job as completed or failed"""
        job = self.get_job(job_id)
        if not job:
            return

        async with self._lock:
            job.completed_at = datetime.now()
            if error_message:
                job.status = ImportStatus.FAILED
                job.error_message = error_message
                logger.error(f"Import job {job_id} failed: {error_message}")
            else:
                job.status = ImportStatus.COMPLETED
                logger.info(f"Import job {job_id} completed successfully")

            self._save_jobs()

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        job = self.get_job(job_id)
        if not job:
            return False

        async with self._lock:
            if job.status != ImportStatus.RUNNING:
                return False

            job.status = ImportStatus.CANCELLED
            job.completed_at = datetime.now()

            # Cancel the asyncio task if it exists
            if job.task and not job.task.done():
                job.task.cancel()

            self._save_jobs()
            logger.info(f"Cancelled import job {job_id}")
            return True

    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed/failed jobs"""
        async with self._lock:
            now = datetime.now()
            to_delete = []

            for job_id, job in self.jobs.items():
                if job.status in [ImportStatus.COMPLETED, ImportStatus.FAILED, ImportStatus.CANCELLED]:
                    if job.completed_at:
                        age_hours = (now - job.completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            to_delete.append(job_id)

            for job_id in to_delete:
                del self.jobs[job_id]
                logger.info(f"Cleaned up old job {job_id}")

            self._save_jobs()

    def _load_jobs(self):
        """Load jobs from persistent storage"""
        try:
            if not JOBS_STORAGE_PATH.exists():
                logger.info("No existing jobs file found")
                return

            with open(JOBS_STORAGE_PATH, 'r') as f:
                data = json.load(f)

            for job_data in data.get('jobs', []):
                try:
                    job = ImportJob.from_dict(job_data)
                    self.jobs[job.job_id] = job
                    logger.info(f"Loaded job {job.job_id} with status {job.status}")
                except Exception as e:
                    logger.error(f"Failed to load job: {e}")

            logger.info(f"Loaded {len(self.jobs)} jobs from storage")

        except Exception as e:
            logger.error(f"Failed to load jobs: {e}")

    def _save_jobs(self):
        """Save jobs to persistent storage"""
        try:
            # Create directory if needed
            JOBS_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Convert all jobs to dict
            jobs_data = {
                'jobs': [job.to_dict() for job in self.jobs.values()],
                'last_updated': datetime.now().isoformat()
            }

            # Write to file
            with open(JOBS_STORAGE_PATH, 'w') as f:
                json.dump(jobs_data, f, indent=2)

            logger.debug(f"Saved {len(self.jobs)} jobs to storage")

        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")

    def get_resumable_jobs(self) -> Dict[str, ImportJob]:
        """Get jobs that can be resumed (running jobs from before restart)"""
        return {
            job_id: job for job_id, job in self.jobs.items()
            if job.status == ImportStatus.RUNNING
        }


# Global singleton instance
background_import_service = BackgroundImportService()
