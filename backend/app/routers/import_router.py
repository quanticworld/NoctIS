"""Import API endpoints with WebSocket progress"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.services.import_service import import_service
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
    batch_size: Optional[int] = Field(None, ge=100, le=50000, description="Batch size")


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
            import_id=import_id
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
