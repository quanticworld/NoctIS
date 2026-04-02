"""Pydantic models for API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class RegexTemplate(str, Enum):
    """Pre-defined regex templates"""

    NAME_SEARCH = "name_search"
    EMAIL = "email"
    PHONE_FR = "phone_fr"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


class SearchRequest(BaseModel):
    """Search request model"""

    template: RegexTemplate = Field(..., description="Regex template to use")
    pattern: Optional[str] = Field(None, description="Custom regex pattern (required if template=custom)")
    first_name: Optional[str] = Field(None, description="First name for name_search template")
    last_name: Optional[str] = Field(None, description="Last name for name_search template")
    search_path: str = Field(..., description="Path to search in")
    threads: int = Field(8, ge=1, le=16, description="Number of threads")
    max_filesize: str = Field("100M", description="Maximum file size to search")
    case_insensitive: bool = Field(True, description="Case insensitive search")
    file_types: Optional[list[str]] = Field(None, description="File types to include (e.g., ['txt', 'log'])")
    exclude_types: Optional[list[str]] = Field(None, description="File types to exclude (e.g., ['pdf', 'zip'])")


class SearchMatch(BaseModel):
    """Single search match result"""

    file_path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int


class SearchProgress(BaseModel):
    """Search progress update"""

    type: Literal["progress"] = "progress"
    files_scanned: int
    total_files: Optional[int] = None
    current_file: str
    matches_found: int
    speed: float  # files per second
    eta_seconds: Optional[float] = None


class SearchResult(BaseModel):
    """Search result update"""

    type: Literal["result"] = "result"
    match: SearchMatch


class SearchComplete(BaseModel):
    """Search completion message"""

    type: Literal["complete"] = "complete"
    total_matches: int
    files_scanned: int
    duration_seconds: float


class SearchError(BaseModel):
    """Search error message"""

    type: Literal["error"] = "error"
    message: str


class StatsRequest(BaseModel):
    """Stats calculation request"""

    path: str = Field(..., description="Path to analyze")


class StatsResponse(BaseModel):
    """Stats response"""

    total_files: int
    total_lines: int
    total_size_bytes: int
    file_types: dict[str, int]  # extension -> count
    largest_files: list[dict[str, str | int]]  # [{path, size, lines}]


class ConfigResponse(BaseModel):
    """Configuration response"""

    search_path: str
    threads: int
    max_filesize: str
    available_templates: list[dict]  # Allow any dict structure
