"""Statistics service for analyzing directories"""
import asyncio
from pathlib import Path
from typing import Optional
from ..models import StatsResponse


class StatsService:
    """Service for calculating directory statistics"""

    @staticmethod
    async def calculate_stats(path: str, max_files: int = None) -> StatsResponse:
        """
        Calculate statistics for a given path (fast - only counts files, doesn't read content)

        Args:
            path: Directory path to analyze
            max_files: Not used anymore (kept for compatibility)
        """
        path_obj = Path(path)

        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if not path_obj.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        total_files = 0
        total_size = 0
        file_types: dict[str, int] = {}
        largest_files: list[dict] = []

        # Use asyncio to run blocking IO in thread pool
        def scan_directory():
            nonlocal total_files, total_size

            files_info = []

            for file_path in path_obj.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    # Get file stats (fast - no file reading)
                    stat = file_path.stat()
                    size = stat.st_size
                    total_files += 1
                    total_size += size

                    # Count file type
                    ext = file_path.suffix.lower() or ".no_extension"
                    file_types[ext] = file_types.get(ext, 0) + 1

                    # Track for largest files list (no line counting)
                    files_info.append({
                        "path": str(file_path),
                        "size": size,
                        "lines": 0,  # Not counted to keep it fast
                    })

                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue

            # Get top 10 largest files
            files_info.sort(key=lambda x: x["size"], reverse=True)
            return files_info[:10]

        # Run in thread pool to avoid blocking
        largest_files = await asyncio.get_event_loop().run_in_executor(
            None, scan_directory
        )

        return StatsResponse(
            total_files=total_files,
            total_lines=0,  # Not counted anymore for speed
            total_size_bytes=total_size,
            file_types=file_types,
            largest_files=largest_files,
        )
