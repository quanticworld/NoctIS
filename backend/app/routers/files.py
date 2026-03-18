"""File browsing and analysis API endpoints"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from app.services.file_service import file_service

router = APIRouter(prefix="/files", tags=["files"])


class FileInfo(BaseModel):
    """File information response"""
    name: str
    path: str
    absolute_path: str
    size: int
    modified: int
    extension: str
    is_directory: bool


class DirectoryTree(BaseModel):
    """Directory tree response"""
    name: str
    path: str
    children: List['DirectoryTree'] = []


class ColumnInfo(BaseModel):
    """CSV column information"""
    name: str
    detected_type: str
    non_null_count: int
    null_count: int
    unique_count: int
    sample_values: List


class CSVAnalysis(BaseModel):
    """CSV file analysis response"""
    file_path: str
    encoding: str
    delimiter: str
    total_rows: int
    total_columns: int
    columns: List[ColumnInfo]
    sample_data: List[dict]
    file_size: int


class ColumnMappingSuggestions(BaseModel):
    """Column mapping suggestions response"""
    suggestions: dict


@router.get("/browse")
async def browse_files(
    path: str = Query("/home/quantic/tmp", description="Absolute path to browse"),
    mode: str = Query("directory", description="Browse mode: 'directory' or 'file'")
):
    """
    Browse files and directories for UI file picker

    Returns list of files/directories for user selection
    """
    from pathlib import Path
    import os

    try:
        # Resolve path - handle mounted /host prefix
        browse_path = Path(path)
        if browse_path.is_absolute():
            # Try with /host prefix first (for Docker mount)
            host_path = Path('/host') / str(browse_path).lstrip('/')
            if host_path.exists():
                browse_path = host_path

        if not browse_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

        items = []

        if browse_path.is_file():
            # Return parent directory contents with current file highlighted
            browse_path = browse_path.parent

        # List directory contents
        try:
            for entry in sorted(browse_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files
                if entry.name.startswith('.'):
                    continue

                items.append({
                    'name': entry.name,
                    'path': str(entry).replace('/host', ''),  # Remove /host prefix for display
                    'is_directory': entry.is_dir(),
                    'size': entry.stat().st_size if entry.is_file() else 0,
                    'modified': int(entry.stat().st_mtime)
                })
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        return {
            'current_path': str(browse_path).replace('/host', ''),
            'parent_path': str(browse_path.parent).replace('/host', '') if browse_path.parent != browse_path else None,
            'items': items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[FileInfo])
async def list_files(
    directory: str = Query("", description="Directory to list (relative to base path)"),
    extensions: Optional[str] = Query(None, description="Comma-separated file extensions (e.g., .csv,.txt)"),
    recursive: bool = Query(False, description="Include subdirectories")
):
    """List files in a directory"""
    ext_list = None
    if extensions:
        ext_list = [ext.strip() for ext in extensions.split(",")]

    files = await file_service.list_files(directory, ext_list, recursive)
    return files


@router.get("/tree", response_model=DirectoryTree)
async def get_directory_tree(
    directory: str = Query("", description="Starting directory"),
    max_depth: int = Query(3, ge=1, le=10, description="Maximum depth to traverse")
):
    """Get directory tree structure"""
    tree = await file_service.get_directory_tree(directory, max_depth)
    if not tree:
        raise HTTPException(status_code=404, detail="Directory not found")
    return tree


@router.get("/analyze", response_model=CSVAnalysis)
async def analyze_csv(
    file_path: str = Query(..., description="Path to CSV file (relative to base path)"),
    sample_rows: int = Query(100, ge=10, le=1000, description="Number of rows to sample"),
    delimiter: Optional[str] = Query(None, description="CSV delimiter (auto-detected if not provided)"),
    encoding: Optional[str] = Query(None, description="File encoding (auto-detected if not provided)")
):
    """Analyze CSV file structure and content"""
    analysis = await file_service.analyze_csv(file_path, sample_rows, delimiter, encoding)
    if not analysis:
        raise HTTPException(status_code=404, detail="File not found or invalid CSV format")
    return analysis


@router.post("/suggest-mapping", response_model=ColumnMappingSuggestions)
async def suggest_column_mapping(
    source_columns: List[str]
):
    """Get column mapping suggestions for import"""
    suggestions = await file_service.get_column_mapping_suggestions(source_columns)
    return {"suggestions": suggestions}
