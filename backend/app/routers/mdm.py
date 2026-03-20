"""MDM API endpoints for master data management"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.services.mdm_service import mdm_service
import logging
import json
from pathlib import Path

router = APIRouter(prefix="/mdm", tags=["mdm"])
logger = logging.getLogger(__name__)

# Configuration file for correlation rules
RULES_CONFIG_PATH = Path("/app/data/correlation_rules.json")


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
    has_more: bool = False


class ResolveConflictRequest(BaseModel):
    """Request to resolve a conflict"""
    conflict_id: str
    chosen_value: str
    resolved_by: str = Field("manual", description="Who resolved")


class ImportToSilverRequest(BaseModel):
    """Request to import documents to silver layer"""
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to import")
    breach_name: str = Field(..., description="Name of the breach/source")
    source_file: str = Field(..., description="Source file path or identifier")


class CorrelationRule(BaseModel):
    """Correlation rule definition"""
    name: str
    confidence: float = Field(..., ge=0, le=100)
    keys: List[str] = Field(..., min_items=1)


class CorrelationRulesRequest(BaseModel):
    """Request to update correlation rules"""
    rules: List[CorrelationRule]


@router.get("/masters", response_model=List[MasterRecord])
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
        # Build filter
        filters = []
        if status:
            filters.append(f"status:={status}")
        if min_confidence is not None:
            filters.append(f"confidence_score:>={min_confidence}")
        if min_sources is not None:
            filters.append(f"source_count:>={min_sources}")

        # Handle breach filtering with AND logic
        if breaches:
            breach_list = [b.strip() for b in breaches.split(',')]
            # For AND logic, we need masters that contain ALL specified breaches
            # Typesense array filters: breach_names:=[value] checks if value exists in array
            for breach in breach_list:
                escaped_breach = breach.replace(':', '\\:')
                filters.append(f"breach_names:=[{escaped_breach}]")
            # Also require source_count >= number of breaches
            filters.append(f"source_count:>={len(breach_list)}")

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

        # Extract documents from Typesense hits structure
        # Typesense returns {'hits': [{'document': {...}}, ...]}
        # We need to extract just the documents
        documents = [hit['document'] for hit in results['hits']]

        return documents

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


@router.post("/masters/{master_id}/demote")
async def demote_from_golden(master_id: str):
    """
    Demote a master record from golden to silver status

    Removes golden validation status
    """
    try:
        master = mdm_service.client.collections['master_records'].documents[master_id].retrieve()

        import time
        updates = {
            'status': 'silver',
            'validated_by': None,
            'updated_at': int(time.time())
        }

        mdm_service.client.collections['master_records'].documents[master_id].update(updates)

        return {'status': 'success', 'master_id': master_id}

    except Exception as e:
        logger.error(f"Demote failed: {e}")
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


@router.get("/correlation-rules")
async def get_correlation_rules():
    """
    Get current correlation rules configuration

    Returns the matching strategies used for deduplication
    """
    try:
        # Try to load from file first
        if RULES_CONFIG_PATH.exists():
            with open(RULES_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config

        # Fall back to hardcoded defaults from mdm_service
        default_rules = {
            'rules': [
                {'name': name, 'confidence': strategy['confidence'], 'keys': strategy['keys']}
                for name, strategy in mdm_service.MATCH_STRATEGIES.items()
            ]
        }
        return default_rules

    except Exception as e:
        logger.error(f"Failed to get correlation rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation-rules")
async def update_correlation_rules(request: CorrelationRulesRequest):
    """
    Update correlation rules configuration

    Saves new matching strategies to be used in deduplication
    """
    try:
        # Validate rules
        if not request.rules:
            raise HTTPException(status_code=400, detail="At least one rule is required")

        # Convert to mdm_service format
        new_strategies = {}
        for rule in request.rules:
            new_strategies[rule.name] = {
                'confidence': rule.confidence,
                'keys': rule.keys
            }

        # Save to file
        RULES_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RULES_CONFIG_PATH, 'w') as f:
            json.dump({'rules': [r.model_dump() for r in request.rules]}, f, indent=2)

        # Update mdm_service MATCH_STRATEGIES
        mdm_service.MATCH_STRATEGIES = new_strategies

        logger.info(f"Updated correlation rules: {len(request.rules)} rules")

        return {
            'status': 'success',
            'rules_count': len(request.rules)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update correlation rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breaches")
async def get_breaches():
    """
    Get list of unique breach names from silver records

    Returns list of breach names with count of records per breach
    """
    try:
        # Typesense doesn't have a direct aggregation API, so we'll do a faceted search
        # Get all unique breach names by fetching facet counts
        results = mdm_service.client.collections['silver_records'].documents.search({
            'q': '*',
            'facet_by': 'breach_name',
            'per_page': 0,
            'max_facet_values': 1000  # Support up to 1000 different breaches
        })

        # Extract facet counts
        breaches = []
        if 'facet_counts' in results:
            for facet in results['facet_counts']:
                if facet['field_name'] == 'breach_name':
                    for count in facet['counts']:
                        breaches.append({
                            'name': count['value'],
                            'count': count['count']
                        })
                    break

        # Sort by count descending
        breaches.sort(key=lambda x: x['count'], reverse=True)

        return breaches

    except Exception as e:
        logger.error(f"Failed to get breaches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/breaches/{breach_name}")
async def delete_breach(breach_name: str):
    """
    Delete all data from a specific breach

    - Deletes all silver records from this breach
    - Removes breach from masters' breach_names array
    - Deletes masters that only had this breach (orphaned masters)
    - Updates source_count for remaining masters
    """
    try:
        deleted_silver = 0
        deleted_masters = 0
        updated_masters = 0

        # Step 1: Find all silver records for this breach
        logger.info(f"Finding silver records for breach: {breach_name}")
        silver_results = mdm_service.client.collections['silver_records'].documents.search({
            'q': '*',
            'filter_by': f'breach_name:={breach_name}',
            'per_page': 250
        })

        total_silver = silver_results['found']
        logger.info(f"Found {total_silver} silver records for {breach_name}")

        # Step 2: Get all master_ids from these silver records
        master_ids_to_check = set()

        # Fetch all silver records (paginated)
        page = 1
        while True:
            results = mdm_service.client.collections['silver_records'].documents.search({
                'q': '*',
                'filter_by': f'breach_name:={breach_name}',
                'per_page': 250,
                'page': page
            })

            if not results['hits']:
                break

            for hit in results['hits']:
                silver_doc = hit['document']
                if silver_doc.get('master_id'):
                    master_ids_to_check.add(silver_doc['master_id'])

            page += 1
            if page > results.get('out_of', page) / 250:
                break

        logger.info(f"Found {len(master_ids_to_check)} masters to check")

        # Step 3: Delete all silver records from this breach
        logger.info(f"Deleting silver records for {breach_name}")
        try:
            mdm_service.client.collections['silver_records'].documents.delete({
                'filter_by': f'breach_name:={breach_name}'
            })
            deleted_silver = total_silver
        except Exception as e:
            logger.error(f"Failed to delete silver records: {e}")

        # Step 4: Update or delete affected masters
        logger.info(f"Updating/deleting affected masters")
        for master_id in master_ids_to_check:
            try:
                master = mdm_service.client.collections['master_records'].documents[master_id].retrieve()
                breach_names = master.get('breach_names', [])

                # Remove this breach from the list
                if breach_name in breach_names:
                    breach_names.remove(breach_name)

                # If no breaches left, delete the master
                if not breach_names:
                    mdm_service.client.collections['master_records'].documents[master_id].delete()
                    deleted_masters += 1
                else:
                    # Update master: remove breach, update source_count
                    # Recalculate source_count by counting remaining silver records
                    silver_ids = master.get('silver_ids', [])
                    remaining_silver = []

                    for silver_id in silver_ids:
                        try:
                            silver = mdm_service.client.collections['silver_records'].documents[silver_id].retrieve()
                            if silver.get('breach_name') != breach_name:
                                remaining_silver.append(silver_id)
                        except:
                            # Silver was deleted or doesn't exist
                            pass

                    import time
                    mdm_service.client.collections['master_records'].documents[master_id].update({
                        'breach_names': breach_names,
                        'silver_ids': remaining_silver,
                        'source_count': len(remaining_silver),
                        'updated_at': int(time.time())
                    })
                    updated_masters += 1

            except Exception as e:
                logger.error(f"Error processing master {master_id}: {e}")

        return {
            'status': 'success',
            'message': f'Breach "{breach_name}" deleted',
            'deleted_silver': deleted_silver,
            'deleted_masters': deleted_masters,
            'updated_masters': updated_masters
        }

    except Exception as e:
        logger.error(f"Delete breach failed: {e}")
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
            mdm_service.client.collections['silver_records'].documents.delete({'filter_by': 'id:!=null'})
            logger.info("Deleted all silver records")
        except Exception as e:
            logger.error(f"Failed to delete silver records: {e}")

        # Delete all master records
        try:
            mdm_service.client.collections['master_records'].documents.delete({'filter_by': 'id:!=null'})
            logger.info("Deleted all master records")
        except Exception as e:
            logger.error(f"Failed to delete master records: {e}")

        # Get final counts
        silver_stats = mdm_service.client.collections['silver_records'].retrieve()
        master_stats = mdm_service.client.collections['master_records'].retrieve()

        return {
            'status': 'success',
            'message': 'All data cleared',
            'remaining': {
                'silver': silver_stats.get('num_documents', 0),
                'master': master_stats.get('num_documents', 0)
            }
        }

    except Exception as e:
        logger.error(f"Clear all failed: {e}")
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


@router.get("/conflicts")
async def get_conflicts(
    master_id: Optional[str] = Query(None, description="Filter by master ID"),
    status: str = Query("pending", description="Filter by status (pending/resolved/ignored)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200)
):
    """
    Get conflicts for manual resolution

    Returns conflicts grouped by master record, showing field-level
    differences between sources that need user decision.
    """
    try:
        conflicts = await mdm_service.get_conflicts(
            master_id=master_id,
            status=status,
            page=page,
            per_page=per_page
        )
        return conflicts

    except Exception as e:
        logger.error(f"Failed to get conflicts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conflicts/resolve")
async def resolve_conflict(request: ResolveConflictRequest):
    """
    Resolve a conflict by choosing which value to keep

    The chosen_value should be either the existing_value or new_value
    from the conflict record. This will update the master record and
    mark the conflict as resolved.
    """
    try:
        success = await mdm_service.resolve_conflict(
            conflict_id=request.conflict_id,
            chosen_value=request.chosen_value,
            resolved_by=request.resolved_by
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to resolve conflict")

        return {
            'status': 'success',
            'message': 'Conflict resolved successfully',
            'conflict_id': request.conflict_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve conflict: {e}")
        raise HTTPException(status_code=500, detail=str(e))
