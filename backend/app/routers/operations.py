"""Operations tracking API - Global status of all background operations"""
from fastapi import APIRouter
from typing import Dict, Any, List
from app.services.background_import_service import background_import_service
from app.services.meilisearch_service import meilisearch_service
import logging

router = APIRouter(prefix="/operations", tags=["operations"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_operations_status() -> Dict[str, Any]:
    """
    Get status of all background operations (imports, deletions, etc.)

    Returns:
        {
            "imports": [...],
            "meilisearch_tasks": {
                "processing": [...],
                "enqueued": [...]
            }
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

        # Get Meilisearch tasks (deletions, indexing, etc.)
        meilisearch_tasks = await get_meilisearch_active_tasks()

        return {
            "imports": active_imports,
            "meilisearch_tasks": meilisearch_tasks,
            "has_active_operations": len(active_imports) > 0 or len(meilisearch_tasks.get('processing', [])) > 0 or len(meilisearch_tasks.get('enqueued', [])) > 0
        }

    except Exception as e:
        logger.error(f"Error getting operations status: {e}")
        return {
            "imports": [],
            "meilisearch_tasks": {"processing": [], "enqueued": []},
            "has_active_operations": False,
            "error": str(e)
        }


async def get_meilisearch_active_tasks() -> Dict[str, List[Dict[str, Any]]]:
    """Get active Meilisearch tasks (processing or enqueued)"""
    try:
        ms_client = meilisearch_service._ms_client

        # Get processing and enqueued tasks
        tasks_response = ms_client.get_tasks({
            'statuses': ['processing', 'enqueued'],
            'limit': 50
        })

        # Handle both dict and object response
        if isinstance(tasks_response, dict):
            all_tasks = tasks_response.get('results', [])
        else:
            all_tasks = getattr(tasks_response, 'results', [])

        processing_tasks = []
        enqueued_tasks = []

        for task in all_tasks:
            # Handle both dict and object
            if isinstance(task, dict):
                task_info = task
            else:
                task_info = {
                    'uid': getattr(task, 'uid', None),
                    'indexUid': getattr(task, 'index_uid', None),
                    'status': getattr(task, 'status', None),
                    'type': getattr(task, 'type', None),
                    'details': getattr(task, 'details', {}),
                    'enqueuedAt': getattr(task, 'enqueued_at', None),
                    'startedAt': getattr(task, 'started_at', None),
                }

            task_data = {
                "task_uid": task_info.get('uid'),
                "index": task_info.get('indexUid'),
                "type": task_info.get('type'),
                "status": task_info.get('status'),
                "details": task_info.get('details', {}),
                "enqueued_at": task_info.get('enqueuedAt'),
                "started_at": task_info.get('startedAt')
            }

            if task_info.get('status') == 'processing':
                processing_tasks.append(task_data)
            elif task_info.get('status') == 'enqueued':
                enqueued_tasks.append(task_data)

        return {
            "processing": processing_tasks,
            "enqueued": enqueued_tasks
        }

    except Exception as e:
        logger.error(f"Error getting Meilisearch tasks: {e}")
        return {
            "processing": [],
            "enqueued": []
        }
