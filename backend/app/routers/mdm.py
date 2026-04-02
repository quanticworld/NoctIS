"""MDM API endpoints for master data management"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.services.mdm_service import mdm_service
import logging

router = APIRouter(prefix="/mdm", tags=["mdm"])
logger = logging.getLogger(__name__)


class ImportToSilverRequest(BaseModel):
    """Request to import documents to silver layer"""
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to import")
    breach_name: str = Field(..., description="Name of the breach/source")
    source_file: str = Field(..., description="Source file path or identifier")


class DeduplicationStats(BaseModel):
    """Deduplication process statistics"""
    processed: int
    new_masters: int
    merged: int
    errors: int
    has_more: bool = False


@router.get("/stats")
async def get_mdm_stats():
    """
    Get MDM statistics

    Returns overall statistics about silver/master records
    """
    try:
        # Get collection stats from Elasticsearch
        silver_count = mdm_service.client.count(index='silver_records')
        master_count = mdm_service.client.count(index='master_records')

        # Count by status
        golden_count = mdm_service.client.count(
            index='master_records',
            query={"term": {"status": "golden"}}
        )

        silver_status_count = mdm_service.client.count(
            index='master_records',
            query={"term": {"status": "silver"}}
        )

        # Count unlinked silver records
        total_silver = silver_count['count']
        try:
            linked_count = mdm_service.client.count(
                index='silver_records',
                query={"exists": {"field": "master_id"}}
            )
            unlinked_count = total_silver - linked_count['count']
        except:
            unlinked_count = total_silver

        return {
            'silver_records': {
                'total': total_silver,
                'unlinked': unlinked_count
            },
            'master_records': {
                'total': master_count['count'],
                'golden': golden_count['count'],
                'silver': silver_status_count['count']
            }
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_to_silver(request: ImportToSilverRequest):
    """
    Import documents to silver layer (raw data)

    This endpoint allows you to import documents directly without using the UI.
    The documents will be stored in the silver_records collection and can then
    be processed through deduplication to create master records.

    Example:
        POST /api/v1/mdm/import
        {
            "documents": [
                {"email": "test@example.com", "first_name": "John", "last_name": "Doe"},
                {"phone": "1234567890", "first_name": "Jane", "city": "Paris"}
            ],
            "breach_name": "TestBreach",
            "source_file": "manual_import.json"
        }
    """
    try:
        result = await mdm_service.import_to_silver(
            documents=request.documents,
            breach_name=request.breach_name,
            source_file=request.source_file
        )

        return {
            'status': 'success',
            'imported': result.get('imported', 0),
            'failed': result.get('failed', 0),
            'breach_name': request.breach_name
        }

    except Exception as e:
        logger.error(f"Failed to import to silver: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deduplicate", response_model=DeduplicationStats)
async def run_deduplication(
    batch_size: int = Query(100, ge=10, le=250, description="Records per batch (max 250)"),
    max_batches: Optional[int] = Query(None, ge=1, description="Max batches to process (None = all)")
):
    """
    Run deduplication process on silver records

    Processes unlinked silver records and creates/merges masters.
    Set max_batches to limit processing (useful for large datasets).
    """
    try:
        stats = await mdm_service.process_silver_deduplication(batch_size, max_batches)
        return stats
    except Exception as e:
        logger.error(f"Deduplication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breaches")
async def get_breaches():
    """
    Get list of unique breach names from silver records

    Returns list of breach names with count of records per breach
    """
    try:
        # Use Elasticsearch aggregations to get breach counts
        response = mdm_service.client.search(
            index='silver_records',
            size=0,
            aggs={
                "breaches": {
                    "terms": {
                        "field": "breach_name",
                        "size": 1000
                    }
                }
            }
        )

        # Extract aggregation results
        breaches = []
        if 'aggregations' in response and 'breaches' in response['aggregations']:
            for bucket in response['aggregations']['breaches']['buckets']:
                breaches.append({
                    'name': bucket['key'],
                    'count': bucket['doc_count']
                })

        return breaches

    except Exception as e:
        logger.error(f"Failed to get breaches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/breaches/{breach_name}")
async def delete_breach(breach_name: str):
    """
    Delete all records from a specific breach

    This will:
    - Delete all silver records from this breach
    - Remove the breach from masters' breach_names
    - Delete masters that only had this breach
    """
    try:
        logger.info(f"Deleting breach: {breach_name}")

        # Count records before deletion
        silver_count_before = mdm_service.client.count(
            index='silver_records',
            query={"term": {"breach_name": breach_name}}
        )

        # Delete all silver records from this breach
        delete_response = mdm_service.client.delete_by_query(
            index='silver_records',
            query={"term": {"breach_name": breach_name}},
            conflicts='proceed'
        )

        deleted_silver = delete_response.get('deleted', 0)
        logger.info(f"Deleted {deleted_silver} silver records from breach: {breach_name}")

        # Update masters: remove this breach from breach_names array
        # Find all masters that have this breach
        masters_with_breach = mdm_service.client.search(
            index='master_records',
            query={"term": {"breach_names": breach_name}},
            size=10000
        )

        deleted_masters = 0
        updated_masters = 0

        for hit in masters_with_breach.get('hits', {}).get('hits', []):
            master = hit['_source']
            master_id = hit['_id']
            breach_names = master.get('breach_names', [])

            if breach_name in breach_names:
                breach_names.remove(breach_name)

                # If no more breaches, delete the master
                if len(breach_names) == 0:
                    mdm_service.client.delete(
                        index='master_records',
                        id=master_id
                    )
                    deleted_masters += 1
                else:
                    # Otherwise, update the master
                    mdm_service.client.update(
                        index='master_records',
                        id=master_id,
                        doc={'breach_names': breach_names}
                    )
                    updated_masters += 1

        logger.info(f"Breach deletion complete: {breach_name}")
        logger.info(f"  - Silver records deleted: {deleted_silver}")
        logger.info(f"  - Masters deleted: {deleted_masters}")
        logger.info(f"  - Masters updated: {updated_masters}")

        return {
            'status': 'success',
            'breach_name': breach_name,
            'deleted_silver': deleted_silver,
            'deleted_masters': deleted_masters,
            'updated_masters': updated_masters
        }

    except Exception as e:
        logger.error(f"Failed to delete breach {breach_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/masters")
async def list_masters(
    status: Optional[str] = Query(None, description="Filter by status (silver/golden)"),
    min_confidence: Optional[float] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    min_sources: Optional[int] = Query(None, ge=1, description="Minimum source count"),
    breaches: Optional[str] = Query(None, description="Comma-separated breach names (AND logic - must be in ALL)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=250)
):
    """
    List master records with filtering

    Returns paginated list of master records.
    When multiple breaches are specified, returns masters found in ALL breaches (AND logic).
    """
    try:
        # Build Elasticsearch query
        must_clauses = []
        if status:
            must_clauses.append({"term": {"status": status}})
        if min_confidence is not None:
            must_clauses.append({"range": {"confidence_score": {"gte": min_confidence}}})
        if min_sources is not None:
            must_clauses.append({"range": {"source_count": {"gte": min_sources}}})

        # Handle breach filtering with AND logic
        if breaches:
            breach_list = [b.strip() for b in breaches.split(',')]
            for breach in breach_list:
                must_clauses.append({"term": {"breach_names": breach}})
            must_clauses.append({"range": {"source_count": {"gte": len(breach_list)}}})

        es_query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

        # Search with Elasticsearch
        from_ = (page - 1) * per_page
        response = mdm_service.client.search(
            index='master_records',
            query=es_query,
            from_=from_,
            size=per_page,
            sort=[{"updated_at": {"order": "desc"}}]
        )

        documents = [hit['_source'] for hit in response['hits']['hits']]
        return documents

    except Exception as e:
        logger.error(f"Failed to list masters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-all")
async def clear_all_data():
    """
    Delete ALL data from silver and master collections

    WARNING: This is destructive and cannot be undone!
    """
    try:
        # Delete all silver records
        try:
            mdm_service.client.delete_by_query(
                index='silver_records',
                query={"match_all": {}}
            )
            logger.info("Deleted all silver records")
        except Exception as e:
            logger.error(f"Failed to delete silver records: {e}")

        # Delete all master records
        try:
            mdm_service.client.delete_by_query(
                index='master_records',
                query={"match_all": {}}
            )
            logger.info("Deleted all master records")
        except Exception as e:
            logger.error(f"Failed to delete master records: {e}")

        # Get final counts
        silver_count = mdm_service.client.count(index='silver_records')
        master_count = mdm_service.client.count(index='master_records')

        return {
            'status': 'success',
            'message': 'All data cleared',
            'remaining': {
                'silver': silver_count['count'],
                'master': master_count['count']
            }
        }

    except Exception as e:
        logger.error(f"Clear all failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
