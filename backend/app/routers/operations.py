"""Operations tracking API - Global status of all background operations"""
from fastapi import APIRouter
from typing import Dict, Any, List
from app.services.background_import_service import background_import_service
from app.services.clickhouse_service import clickhouse_service
import logging

router = APIRouter(prefix="/operations", tags=["operations"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_operations_status() -> Dict[str, Any]:
    """
    Get status of all background operations (imports, etc.)

    Returns:
        {
            "imports": [...],
            "clickhouse_health": {...}
        }
    """
    try:
        # Get all import jobs
        all_import_jobs = background_import_service.get_all_jobs()

        # Filter active imports (not completed/failed/cancelled)
        active_imports = []
        for job_id, job in all_import_jobs.items():
            if job.status in ['pending', 'running']:
                active_imports.append({
                    "type": "import",
                    "job_id": job_id,
                    "status": job.status,
                    "breach_name": job.breach_name,
                    "progress": {
                        "processed": job.processed_lines,
                        "total": job.total_lines,
                        "percentage": (job.processed_lines / job.total_lines * 100) if job.total_lines > 0 else 0
                    },
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None
                })

        # Get ClickHouse health status
        clickhouse_health = await clickhouse_service.health_check()

        return {
            "imports": active_imports,
            "clickhouse_health": clickhouse_health,
            "has_active_operations": len(active_imports) > 0
        }

    except Exception as e:
        logger.error(f"Error getting operations status: {e}")
        return {
            "imports": [],
            "clickhouse_health": {"status": "unknown"},
            "has_active_operations": False,
            "error": str(e)
        }
