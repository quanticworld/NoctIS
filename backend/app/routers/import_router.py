"""Import API endpoints with WebSocket progress"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from app.services.import_service import import_service
from app.services.background_import_service import background_import_service
from app.services.import_executor import import_executor
import json
import logging

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    """Import request model"""
    file_path: str = Field(..., description="Path to CSV file")
    breach_name: str = Field(..., min_length=1, description="Name of the breach")
    column_mapping: Dict[str, Optional[str]] = Field(..., description="Column mapping")
    breach_date: Optional[int] = Field(None, description="Breach date (Unix timestamp)")
    batch_size: Optional[int] = Field(None, ge=100, le=100000, description="Batch size")
    turbo_mode: bool = Field(False, description="🚀 TURBO: Skip MDM, 50k batches, minimal updates (10-20x faster)")


class PreviewRequest(BaseModel):
    """Preview request model"""
    file_path: str
    column_mapping: Dict[str, Optional[str]]
    breach_name: str
    rows: int = Field(10, ge=1, le=100)


class PreviewResponse(BaseModel):
    """Preview response model"""
    total_rows: int
    preview_count: int
    sample_documents: list
    mapped_fields: list


@router.websocket("/stream")
async def import_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming import progress

    Protocol:
    1. Client connects
    2. Client sends ImportRequest as JSON
    3. Server streams progress updates
    4. Connection closes on completion/error

    Progress messages:
    - {"status": "analyzing", "message": "...", "progress": 0}
    - {"status": "importing", "message": "...", "progress": 50, "imported": 1000, ...}
    - {"status": "completed", "message": "...", "progress": 100, "imported": 2000}
    - {"status": "error", "message": "...", "error": "..."}
    - {"status": "cancelled", "message": "..."}
    """
    await websocket.accept()

    try:
        # Receive import request
        data = await websocket.receive_text()
        request_data = json.loads(data)

        # Validate request
        try:
            import_request = ImportRequest(**request_data)
        except Exception as e:
            await websocket.send_json({
                'status': 'error',
                'message': 'Invalid request',
                'error': str(e)
            })
            await websocket.close()
            return

        # Generate unique import ID
        import_id = f"import_{websocket.client.host}_{id(websocket)}"

        # Stream progress updates
        async for progress in import_service.import_csv(
            file_path=import_request.file_path,
            breach_name=import_request.breach_name,
            column_mapping=import_request.column_mapping,
            breach_date=import_request.breach_date,
            batch_size=import_request.batch_size,
            import_id=import_id,
            turbo_mode=import_request.turbo_mode
        ):
            try:
                await websocket.send_json(progress)

                # Close on completion or error
                if progress['status'] in ['completed', 'error', 'cancelled']:
                    break

            except WebSocketDisconnect:
                # Client disconnected, cancel import
                await import_service.cancel_import(import_id)
                logger.info(f"Client disconnected, import {import_id} cancelled")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during import")
    except Exception as e:
        logger.error(f"Import stream error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'status': 'error',
                'message': 'Import failed',
                'error': str(e)
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/preview", response_model=PreviewResponse)
async def preview_import(request: PreviewRequest):
    """Preview how data will be imported"""
    preview = await import_service.get_import_preview(
        file_path=request.file_path,
        column_mapping=request.column_mapping,
        breach_name=request.breach_name,
        rows=request.rows
    )

    if not preview:
        raise HTTPException(status_code=404, detail="File not found or invalid format")

    return preview


@router.post("/cancel")
async def cancel_import(
    import_id: str = Query(..., description="Import ID to cancel")
):
    """Cancel an active import"""
    cancelled = await import_service.cancel_import(import_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Import not found or already completed")

    return {"status": "cancelled", "import_id": import_id}


# ============================================================================
# Background Import API (REST endpoints for imports without WebSocket)
# ============================================================================


@router.post("/background/start")
async def start_background_import(request: ImportRequest):
    """
    Start an import job in the background

    Returns a job_id that can be used to track progress.
    The import will continue even if the client disconnects.
    """
    # Create the job
    job = background_import_service.create_job(
        file_path=request.file_path,
        breach_name=request.breach_name,
        column_mapping=request.column_mapping,
        breach_date=request.breach_date,
        batch_size=request.batch_size or 1000,
        turbo_mode=request.turbo_mode
    )

    # Submit the job for execution
    import_executor.submit_job(job.job_id)

    logger.info(f"Started background import job {job.job_id}")

    return {
        "job_id": job.job_id,
        "status": "submitted",
        "message": "Import job started in background"
    }


@router.get("/background/status/{job_id}")
async def get_import_status(job_id: str):
    """
    Get the status and progress of a background import job

    Returns detailed progress information including:
    - Status (pending, running, completed, failed, cancelled)
    - Progress percentage
    - Lines processed
    - Speed (lines/sec)
    - ETA
    """
    job = background_import_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@router.get("/background/jobs")
async def list_import_jobs(
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    List all import jobs

    Optionally filter by status: pending, running, completed, failed, cancelled
    """
    jobs = background_import_service.get_all_jobs()

    # Filter by status if provided
    if status:
        jobs = {
            job_id: job for job_id, job in jobs.items()
            if job.status == status
        }

    # Convert to list and sort by creation time (newest first)
    job_list = [job.to_dict() for job in jobs.values()]
    job_list.sort(key=lambda x: x['created_at'], reverse=True)

    return {
        "total": len(job_list),
        "jobs": job_list
    }


@router.post("/background/cancel/{job_id}")
async def cancel_background_import(job_id: str):
    """
    Cancel a running background import job
    """
    cancelled = await background_import_service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail="Job not found or not in a cancellable state"
        )

    return {
        "status": "cancelled",
        "job_id": job_id,
        "message": "Job cancelled successfully"
    }


@router.delete("/background/cleanup")
async def cleanup_old_jobs(
    max_age_hours: int = Query(24, ge=1, le=168, description="Max age in hours")
):
    """
    Clean up old completed/failed jobs

    Default: removes jobs older than 24 hours
    """
    await background_import_service.cleanup_old_jobs(max_age_hours)

    return {
        "status": "success",
        "message": f"Cleaned up jobs older than {max_age_hours} hours"
    }
