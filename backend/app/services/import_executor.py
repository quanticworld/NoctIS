"""Import job executor - runs import jobs in background"""
import asyncio
import logging
from typing import Optional
from app.services.background_import_service import background_import_service, ImportStatus
from app.services.import_service import import_service

logger = logging.getLogger(__name__)


class ImportExecutor:
    """Executes import jobs in the background"""

    def __init__(self):
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None

    async def execute_job(self, job_id: str, resume: bool = False):
        """Execute a single import job"""
        job = background_import_service.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            # Mark job as started (only if not already running)
            if not resume and job.status != ImportStatus.RUNNING:
                await background_import_service.start_job(job_id)

            logger.info(f"{'Resuming' if resume else 'Executing'} import job {job_id}: {job.file_path} -> {job.breach_name}")

            # Calculate skip_lines for resume (use processed_lines from job)
            skip_lines = job.processed_lines if job.processed_lines > 0 else 0

            if skip_lines > 0:
                logger.info(f"Resuming job {job_id} from line {skip_lines:,}")

            # Run the import and process progress updates
            async for progress in import_service.import_csv(
                file_path=job.file_path,
                breach_name=job.breach_name,
                column_mapping=job.column_mapping,
                breach_date=job.breach_date,
                batch_size=job.batch_size,
                import_id=job_id,
                skip_lines=skip_lines
            ):
                # Update job progress
                await background_import_service.update_progress(
                    job_id=job_id,
                    total_lines=progress.get('total_lines'),
                    processed_lines=progress.get('processed'),
                    imported_count=progress.get('imported'),
                    error_count=progress.get('errors'),
                    current_batch=progress.get('current_batch'),
                    total_batches=progress.get('total_batches')
                )

                # Check if job was cancelled
                current_job = background_import_service.get_job(job_id)
                if current_job and current_job.status == ImportStatus.CANCELLED:
                    logger.info(f"Job {job_id} was cancelled, stopping execution")
                    break

            # Mark as completed
            await background_import_service.complete_job(job_id)
            logger.info(f"Job {job_id} completed successfully")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            await background_import_service.complete_job(
                job_id,
                error_message="Job was cancelled"
            )
            raise

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            await background_import_service.complete_job(
                job_id,
                error_message=str(e)
            )

    def submit_job(self, job_id: str) -> asyncio.Task:
        """Submit a job for execution and return the task"""
        task = asyncio.create_task(self.execute_job(job_id))

        # Store task reference in the job for cancellation
        job = background_import_service.get_job(job_id)
        if job:
            job.task = task

        return task

    async def start(self):
        """Start the executor (for future use if we want a job queue)"""
        self._running = True
        logger.info("Import executor started")

    async def stop(self):
        """Stop the executor"""
        self._running = False
        if self._executor_task:
            self._executor_task.cancel()
            try:
                await self._executor_task
            except asyncio.CancelledError:
                pass
        logger.info("Import executor stopped")


# Global singleton instance
import_executor = ImportExecutor()
