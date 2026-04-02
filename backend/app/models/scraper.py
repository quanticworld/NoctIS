"""Scraper models for database"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ScraperCreate(BaseModel):
    """Create a new scraper"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    code: str = Field(..., min_length=1)
    language: str = Field(default="python", pattern="^(python|bash)$")
    cron_expression: Optional[str] = None  # e.g., "0 * * * *" for hourly
    enabled: bool = Field(default=False)
    keywords: List[str] = Field(default_factory=list)  # Alert keywords
    auto_import: bool = Field(default=False)  # Auto-import findings to Typesense


class ScraperUpdate(BaseModel):
    """Update scraper"""
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    language: Optional[str] = None
    cron_expression: Optional[str] = None
    enabled: Optional[bool] = None
    keywords: Optional[List[str]] = None
    auto_import: Optional[bool] = None


class ScraperResponse(BaseModel):
    """Scraper response"""
    id: str
    name: str
    description: Optional[str]
    code: str
    language: str
    cron_expression: Optional[str]
    enabled: bool
    keywords: List[str]
    auto_import: bool
    created_at: int
    updated_at: int
    last_run_at: Optional[int] = None
    last_run_status: Optional[str] = None  # success, error, running
    next_run_at: Optional[int] = None


class ExecutionCreate(BaseModel):
    """Start a scraper execution"""
    scraper_id: str


class ExecutionResponse(BaseModel):
    """Scraper execution response"""
    id: str
    scraper_id: str
    status: str  # running, success, error
    started_at: int
    finished_at: Optional[int] = None
    duration_seconds: Optional[float] = None
    stdout: str = ""
    stderr: str = ""
    findings_count: int = 0
    error_message: Optional[str] = None


class FindingResponse(BaseModel):
    """Scraper finding/result"""
    id: str
    scraper_id: str
    execution_id: str
    data: dict  # Flexible structure
    matched_keywords: List[str] = []
    created_at: int
    imported_to_typesense: bool = False
