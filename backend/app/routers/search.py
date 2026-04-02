"""ClickHouse search API endpoints"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.clickhouse_service import clickhouse_service

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., min_length=1, description="Search query")
    search_fields: List[str] = Field(
        default=[
            "email", "username", "phone",
            "first_name", "last_name", "full_name", "gender",
            "address", "city", "country", "zip_code",
            "company", "job_title",
            "social_media", "website",
            "domain", "notes"
        ],
        description="Fields to search in"
    )
    filter_by: Optional[str] = Field(None, description="Filter expression")
    per_page: int = Field(20, ge=1, le=250, description="Results per page")
    page: int = Field(1, ge=1, description="Page number")
    typo_tolerance: bool = Field(True, description="Enable typo tolerance")
    prefix: bool = Field(True, description="Enable prefix search")


class SearchHit(BaseModel):
    """Search result hit"""
    document: dict
    highlights: Optional[dict] = None
    text_match: Optional[int] = None


class SearchResponse(BaseModel):
    """Search response model"""
    hits: List[dict]
    found: int
    out_of: int
    page: int
    search_time_ms: int
    facet_counts: List[dict] = []


class MultiSearchRequest(BaseModel):
    """Multi-search request"""
    searches: List[dict]


class CollectionStats(BaseModel):
    """Collection statistics"""
    name: str
    num_documents: int
    created_at: Optional[int] = None
    num_memory_shards: int


class FacetsResponse(BaseModel):
    """Facets response"""
    facets: dict


@router.post("/query", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search in Meilisearch collection

    Supports:
    - Multi-field search
    - Typo tolerance
    - Prefix matching
    - Filtering
    - Pagination
    """
    results = await clickhouse_service.search(
        query=request.query,
        search_fields=request.search_fields,
        filter_by=request.filter_by,
        per_page=request.per_page,
        page=request.page,
        collection_name='silver_records',
        typo_tolerance=request.typo_tolerance,
        prefix=request.prefix
    )

    if 'error' in results:
        raise HTTPException(status_code=500, detail=results['error'])

    return results


@router.post("/multi-query")
async def multi_search(request: MultiSearchRequest):
    """Execute multiple searches in a single request"""
    results = await clickhouse_service.multi_search(request.searches)
    return {"results": results}


@router.get("/stats", response_model=CollectionStats)
async def get_collection_stats(
    collection: str = Query("silver_records", description="Collection name")
):
    """Get collection statistics"""
    stats = await clickhouse_service.get_collection_stats(collection)
    if not stats:
        raise HTTPException(status_code=404, detail="Collection not found")
    return stats


@router.get("/facets", response_model=FacetsResponse)
async def get_facets(
    collection: str = Query("silver_records", description="Collection name"),
    fields: Optional[str] = Query(None, description="Comma-separated facet fields")
):
    """Get facet counts for specified fields"""
    facet_fields = None
    if fields:
        facet_fields = [f.strip() for f in fields.split(",")]

    facets = await clickhouse_service.get_facets(collection, facet_fields)
    return {"facets": facets}


@router.get("/health")
async def health_check():
    """Check ClickHouse server health"""
    return await clickhouse_service.health_check()


@router.get("/initialization-status")
async def get_initialization_status():
    """Get ClickHouse initialization status"""
    return clickhouse_service.get_initialization_status()


@router.post("/initialize")
async def initialize_collections():
    """Initialize required ClickHouse tables"""
    results = await clickhouse_service.initialize_collections()
    return {"collections": results}
