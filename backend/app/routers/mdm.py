"""MDM API endpoints for master data management"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.services.mdm_service import mdm_service
import logging

router = APIRouter(prefix="/mdm", tags=["mdm"])
logger = logging.getLogger(__name__)


class MasterRecord(BaseModel):
    """Master record response model"""
    id: str
    status: str
    confidence_score: float
    source_count: int
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    breach_names: List[str]
    created_at: int
    updated_at: int


class MasterWithSources(BaseModel):
    """Master record with linked silver sources"""
    master: Dict[str, Any]
    sources: List[Dict[str, Any]]


class MergeRequest(BaseModel):
    """Request to merge multiple masters"""
    master_ids: List[str] = Field(..., min_items=2, description="Master IDs to merge")
    keep_master_id: Optional[str] = Field(None, description="Which master to keep (optional)")


class PromoteRequest(BaseModel):
    """Request to promote master to golden"""
    master_id: str
    validated_by: Optional[str] = Field("manual", description="Who validated")


class SplitRequest(BaseModel):
    """Request to split silver records from master"""
    master_id: str
    silver_ids: List[str] = Field(..., min_items=1, description="Silver IDs to split out")


class DeduplicationStats(BaseModel):
    """Deduplication process statistics"""
    processed: int
    new_masters: int
    merged: int
    errors: int


@router.get("/masters", response_model=List[MasterRecord])
async def list_masters(
    status: Optional[str] = Query(None, description="Filter by status (silver/golden)"),
    min_confidence: Optional[float] = Query(None, ge=0, le=100, description="Minimum confidence score"),
    min_sources: Optional[int] = Query(None, ge=1, description="Minimum source count"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=250)
):
    """
    List master records with filtering

    Returns paginated list of master records
    """
    try:
        # Build filter
        filters = []
        if status:
            filters.append(f"status:={status}")
        if min_confidence is not None:
            filters.append(f"confidence_score:>={min_confidence}")
        if min_sources is not None:
            filters.append(f"source_count:>={min_sources}")

        filter_query = ' && '.join(filters) if filters else None

        # Search masters
        search_params = {
            'q': '*',
            'per_page': per_page,
            'page': page,
            'sort_by': 'updated_at:desc'
        }

        # Only add filter_by if we have filters (Typesense doesn't accept None)
        if filter_query:
            search_params['filter_by'] = filter_query

        results = mdm_service.client.collections['master_records'].documents.search(search_params)

        return results['hits']

    except Exception as e:
        logger.error(f"Failed to list masters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/masters/{master_id}", response_model=MasterWithSources)
async def get_master(master_id: str):
    """
    Get master record with all linked silver sources

    Returns master record with full source details
    """
    result = await mdm_service.get_master_with_sources(master_id)

    if not result:
        raise HTTPException(status_code=404, detail="Master not found")

    return {
        'master': result,
        'sources': result.get('sources', [])
    }


@router.post("/deduplicate", response_model=DeduplicationStats)
async def run_deduplication(
    batch_size: int = Query(100, ge=10, le=1000, description="Batch size")
):
    """
    Run deduplication process on silver records

    Processes unlinked silver records and creates/merges masters
    """
    try:
        stats = await mdm_service.process_silver_deduplication(batch_size)
        return stats
    except Exception as e:
        logger.error(f"Deduplication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/masters/merge")
async def merge_masters(request: MergeRequest):
    """
    Manually merge multiple master records

    Combines multiple masters into one, preserving all source links
    """
    try:
        # Validate all masters exist
        masters = []
        for master_id in request.master_ids:
            try:
                master = mdm_service.client.collections['master_records'].documents[master_id].retrieve()
                masters.append(master)
            except Exception:
                raise HTTPException(status_code=404, detail=f"Master {master_id} not found")

        # Determine which master to keep
        if request.keep_master_id:
            if request.keep_master_id not in request.master_ids:
                raise HTTPException(status_code=400, detail="keep_master_id must be in master_ids")
            keep_master = next(m for m in masters if m['id'] == request.keep_master_id)
        else:
            # Keep the one with highest confidence
            keep_master = max(masters, key=lambda m: m.get('confidence_score', 0))

        # Merge all silver_ids and data
        all_silver_ids = []
        all_breach_names = set()
        all_passwords = []
        all_password_hashes = []

        for master in masters:
            all_silver_ids.extend(master.get('silver_ids', []))
            all_breach_names.update(master.get('breach_names', []))
            all_passwords.extend(master.get('passwords', []))
            all_password_hashes.extend(master.get('password_hashes', []))

        # Remove duplicates
        all_silver_ids = list(set(all_silver_ids))
        all_passwords = list(set(all_passwords))
        all_password_hashes = list(set(all_password_hashes))

        # Calculate new confidence (average weighted by source count)
        total_sources = sum(m.get('source_count', 1) for m in masters)
        new_confidence = sum(
            m.get('confidence_score', 50) * m.get('source_count', 1)
            for m in masters
        ) / total_sources

        # Update keep_master
        import time
        updates = {
            'silver_ids': all_silver_ids,
            'source_count': len(all_silver_ids),
            'breach_names': list(all_breach_names),
            'passwords': all_passwords,
            'password_hashes': all_password_hashes,
            'confidence_score': new_confidence,
            'updated_at': int(time.time()),
            'status': 'golden' if new_confidence >= 90 else 'silver'
        }

        # Merge data fields from other masters (fill missing fields)
        for master in masters:
            if master['id'] == keep_master['id']:
                continue
            for field in ['email', 'username', 'phone', 'full_name', 'first_name',
                          'last_name', 'gender', 'birth_date', 'address', 'city',
                          'country', 'company', 'job_title', 'social_media', 'website']:
                if not keep_master.get(field) and master.get(field):
                    updates[field] = master[field]

        mdm_service.client.collections['master_records'].documents[keep_master['id']].update(updates)

        # Update all silver records to point to keep_master
        for silver_id in all_silver_ids:
            try:
                mdm_service.client.collections['silver_records'].documents[silver_id].update({
                    'master_id': keep_master['id']
                })
            except Exception as e:
                logger.warning(f"Failed to update silver {silver_id}: {e}")

        # Delete other masters
        for master in masters:
            if master['id'] != keep_master['id']:
                try:
                    mdm_service.client.collections['master_records'].documents[master['id']].delete()
                except Exception as e:
                    logger.warning(f"Failed to delete master {master['id']}: {e}")

        return {
            'status': 'success',
            'master_id': keep_master['id'],
            'merged_count': len(request.master_ids) - 1,
            'total_sources': len(all_silver_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/masters/{master_id}/promote")
async def promote_to_golden(master_id: str, request: PromoteRequest):
    """
    Manually promote a master record to golden status

    Marks a master as validated and high-quality
    """
    try:
        master = mdm_service.client.collections['master_records'].documents[master_id].retrieve()

        import time
        updates = {
            'status': 'golden',
            'confidence_score': max(master.get('confidence_score', 50), 90.0),
            'validated_by': request.validated_by,
            'updated_at': int(time.time())
        }

        mdm_service.client.collections['master_records'].documents[master_id].update(updates)

        return {'status': 'success', 'master_id': master_id}

    except Exception as e:
        logger.error(f"Promote failed: {e}")
        raise HTTPException(status_code=404, detail="Master not found")


@router.post("/masters/{master_id}/split")
async def split_master(master_id: str, request: SplitRequest):
    """
    Split silver records out from a master

    Creates new masters for the split records
    """
    try:
        master = mdm_service.client.collections['master_records'].documents[master_id].retrieve()

        # Validate silver_ids belong to this master
        current_silver_ids = master.get('silver_ids', [])
        invalid_ids = [sid for sid in request.silver_ids if sid not in current_silver_ids]

        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Silver IDs not in this master: {invalid_ids}"
            )

        # Remove silver_ids from this master
        remaining_silver_ids = [sid for sid in current_silver_ids if sid not in request.silver_ids]

        if not remaining_silver_ids:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove all silver records from master"
            )

        import time
        mdm_service.client.collections['master_records'].documents[master_id].update({
            'silver_ids': remaining_silver_ids,
            'source_count': len(remaining_silver_ids),
            'updated_at': int(time.time())
        })

        # Create new master for split records or unlink them
        new_master_ids = []
        for silver_id in request.silver_ids:
            try:
                silver = mdm_service.client.collections['silver_records'].documents[silver_id].retrieve()

                # Unlink from current master
                mdm_service.client.collections['silver_records'].documents[silver_id].update({
                    'master_id': None
                })

                # Create new master
                new_master_id = await mdm_service.create_master_from_silver(silver, strategy='manual_split', confidence=50.0)
                new_master_ids.append(new_master_id)

            except Exception as e:
                logger.error(f"Failed to split silver {silver_id}: {e}")

        return {
            'status': 'success',
            'master_id': master_id,
            'new_masters': new_master_ids,
            'split_count': len(new_master_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Split failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_mdm_stats():
    """
    Get MDM statistics

    Returns overall statistics about silver/master records
    """
    try:
        # Get collection stats
        silver_stats = mdm_service.client.collections['silver_records'].retrieve()
        master_stats = mdm_service.client.collections['master_records'].retrieve()

        # Count by status
        golden_results = mdm_service.client.collections['master_records'].documents.search({
            'q': '*',
            'filter_by': 'status:=golden',
            'per_page': 0
        })

        silver_status_results = mdm_service.client.collections['master_records'].documents.search({
            'q': '*',
            'filter_by': 'status:=silver',
            'per_page': 0
        })

        # Count unlinked silver records (those without master_id or with empty master_id)
        # Note: Since master_id is optional, we need to count total and subtract linked
        total_silver = silver_stats.get('num_documents', 0)

        # Try to count linked (with master_id set)
        try:
            linked_results = mdm_service.client.collections['silver_records'].documents.search({
                'q': '*',
                'filter_by': 'master_id:!=""',
                'per_page': 0
            })
            unlinked_count = total_silver - linked_results['found']
        except:
            # If filter fails, assume all are unlinked (no masters created yet)
            unlinked_count = total_silver

        return {
            'silver_records': {
                'total': silver_stats.get('num_documents', 0),
                'unlinked': unlinked_count
            },
            'master_records': {
                'total': master_stats.get('num_documents', 0),
                'golden': golden_results['found'],
                'silver': silver_status_results['found']
            }
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
