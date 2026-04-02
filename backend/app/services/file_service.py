"""File browsing and CSV parsing service"""
import os
import csv
import chardet
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)


class FileService:
    """Service for browsing files and parsing CSV data"""

    def __init__(self, base_path: str = None):
        """Initialize with base path"""
        self.base_path = Path(base_path or settings.default_search_path)

    def _resolve_file_path(self, file_path: str) -> Path:
        """
        Resolve file path, handling spaces and special characters
        In Docker, the host filesystem is mounted at /host

        Args:
            file_path: User-provided file path (can be absolute or relative)

        Returns:
            Resolved Path object
        """
        # Strip whitespace
        file_path = file_path.strip()

        logger.info(f"Resolving file path: '{file_path}'")
        logger.info(f"Base path: {self.base_path}")

        # Handle absolute paths with /host prefix (for Docker mount)
        if os.path.isabs(file_path):
            resolved = Path(file_path)
            # Try with /host prefix first (for Docker mount)
            host_path = Path('/host') / str(resolved).lstrip('/')
            if host_path.exists():
                logger.info(f"Resolved with /host prefix: {host_path}")
                return host_path
            logger.info(f"Resolved as absolute path: {resolved}")
            return resolved

        # Handle relative paths from base_path
        resolved = self.base_path / file_path
        logger.info(f"Resolved as relative path: {resolved}")
        return resolved

    async def list_files(
        self,
        directory: str = "",
        extensions: List[str] = None,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List files in a directory

        Args:
            directory: Relative directory path from base_path
            extensions: Filter by file extensions (e.g., ['.csv', '.txt'])
            recursive: Include subdirectories

        Returns:
            List of file information dictionaries
        """
        if extensions is None:
            extensions = ['.csv', '.txt', '.json', '.tsv']

        target_path = self.base_path / directory

        # Security check: ensure path doesn't escape base_path
        try:
            target_path = target_path.resolve()
            if not str(target_path).startswith(str(self.base_path.resolve())):
                raise ValueError("Access denied: path outside base directory")
        except Exception as e:
            logger.error(f"Path resolution error: {e}")
            return []

        if not target_path.exists() or not target_path.is_dir():
            return []

        files = []
        try:
            pattern = "**/*" if recursive else "*"
            for item in target_path.glob(pattern):
                if item.is_file() and (not extensions or item.suffix.lower() in extensions):
                    stat = item.stat()
                    files.append({
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'absolute_path': str(item),
                        'size': stat.st_size,
                        'modified': int(stat.st_mtime),
                        'extension': item.suffix.lower(),
                        'is_directory': False
                    })
                elif item.is_dir() and recursive:
                    stat = item.stat()
                    files.append({
                        'name': item.name,
                        'path': str(item.relative_to(self.base_path)),
                        'absolute_path': str(item),
                        'size': 0,
                        'modified': int(stat.st_mtime),
                        'extension': '',
                        'is_directory': True
                    })

            # Sort: directories first, then by name
            files.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))
            return files

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

    async def get_directory_tree(
        self,
        directory: str = "",
        max_depth: int = 3,
        current_depth: int = 0
    ) -> Dict[str, Any]:
        """
        Get directory tree structure

        Args:
            directory: Starting directory
            max_depth: Maximum depth to traverse
            current_depth: Current recursion depth

        Returns:
            Tree structure with nested directories
        """
        target_path = self.base_path / directory

        # Security check
        try:
            target_path = target_path.resolve()
            if not str(target_path).startswith(str(self.base_path.resolve())):
                raise ValueError("Access denied")
        except Exception as e:
            logger.error(f"Path error: {e}")
            return {}

        if not target_path.exists() or not target_path.is_dir():
            return {}

        tree = {
            'name': target_path.name or 'root',
            'path': str(target_path.relative_to(self.base_path)),
            'children': []
        }

        if current_depth >= max_depth:
            return tree

        try:
            for item in sorted(target_path.iterdir(), key=lambda x: x.name.lower()):
                if item.is_dir():
                    child = await self.get_directory_tree(
                        str(item.relative_to(self.base_path)),
                        max_depth,
                        current_depth + 1
                    )
                    tree['children'].append(child)

            return tree

        except Exception as e:
            logger.error(f"Error building tree: {e}")
            return tree

    async def detect_encoding(self, file_path: str) -> str:
        """
        Detect file encoding

        Args:
            file_path: Path to file (relative to base_path or absolute)

        Returns:
            Detected encoding (default: utf-8)
        """
        full_path = self._resolve_file_path(file_path)
        logger.info(f"Detecting encoding for: {full_path}")

        try:
            # Read first 100KB for detection
            with open(full_path, 'rb') as f:
                raw_data = f.read(100000)
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
                logger.info(f"Detected encoding: {encoding} (confidence: {result['confidence']})")
                return encoding
        except Exception as e:
            logger.error(f"Encoding detection error: {e}")
            return 'utf-8'

    async def analyze_csv(
        self,
        file_path: str,
        sample_rows: int = 100,
        custom_delimiter: Optional[str] = None,
        custom_encoding: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze CSV file structure and content

        Args:
            file_path: Path to CSV file (relative to base_path or absolute)
            sample_rows: Number of rows to sample

        Returns:
            CSV analysis with columns, sample data, and statistics
        """
        full_path = self._resolve_file_path(file_path)
        logger.info(f"Analyzing CSV file: {full_path}")

        if not full_path.exists():
            logger.error(f"File not found: {full_path}")
            return None

        try:
            # Detect or use custom encoding
            if custom_encoding:
                encoding = custom_encoding
                logger.info(f"Using custom encoding: {encoding}")
            else:
                encoding = await self.detect_encoding(file_path)

            # Detect or use custom delimiter
            if custom_delimiter:
                delimiter = custom_delimiter
                logger.info(f"Using custom delimiter: '{delimiter}'")
            else:
                # Detect CSV dialect with multiple strategies
                delimiter = ','
                with open(full_path, 'r', encoding=encoding) as f:
                    sample = f.read(10000)

                    # Strategy 1: Try csv.Sniffer
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|:')
                        delimiter = dialect.delimiter
                    except Exception:
                        pass

                    # Strategy 2: Count delimiter occurrences on first lines
                    if delimiter == ',':
                        lines = sample.split('\n')[:5]
                        candidates = {',': 0, ';': 0, '\t': 0, '|': 0, ':': 0}

                        for line in lines:
                            if line.strip():
                                for delim in candidates.keys():
                                    candidates[delim] += line.count(delim)

                        # Pick the most common delimiter with consistent count
                        if candidates:
                            max_delim = max(candidates, key=candidates.get)
                            if candidates[max_delim] > 0:
                                delimiter = max_delim

            # Read with pandas for analysis
            # First check if file has a header by reading first line
            with open(full_path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()
                first_col = first_line.split(delimiter)[0].strip()
                has_header = not first_col.replace('.', '').replace(',', '').isdigit()

            try:
                # Read CSV with or without header
                df = pd.read_csv(
                    full_path,
                    encoding=encoding,
                    sep=delimiter,
                    nrows=sample_rows,
                    on_bad_lines='skip',  # Skip malformed lines
                    engine='python',  # More flexible parser
                    header=0 if has_header else None  # Use first row as header only if it's actually a header
                )

                # CRITICAL: If no header, pandas will use integers as column names
                # We MUST convert them to "col_0", "col_1", etc. for consistency
                if not has_header:
                    df.columns = [f"col_{i}" for i in range(len(df.columns))]
                    logger.info(f"No header detected, using column indices: {df.columns.tolist()}")
                else:
                    # IMPORTANT: Even with header, normalize to col_N format for consistency
                    # This ensures frontend always uses col_0, col_1, etc.
                    original_columns = df.columns.tolist()
                    df.columns = [f"col_{i}" for i in range(len(df.columns))]
                    logger.info(f"Header detected: {original_columns[:5]}... -> normalized to: {df.columns.tolist()}")

            except Exception as parse_error:
                logger.error(f"Failed to parse with delimiter '{delimiter}': {parse_error}")
                # Fallback: try with comma
                df = pd.read_csv(
                    full_path,
                    encoding=encoding,
                    sep=',',
                    nrows=sample_rows,
                    on_bad_lines='skip',
                    engine='python'
                )
                delimiter = ','

            # Analyze columns
            columns = []
            for col in df.columns:
                col_data = df[col]

                # Calculate statistics safely (handle NaN/inf)
                try:
                    non_null = int(col_data.notna().sum())
                except (ValueError, OverflowError):
                    non_null = 0

                try:
                    null_count = int(len(col_data) - non_null)
                except (ValueError, OverflowError):
                    null_count = 0

                try:
                    unique_count = int(col_data.nunique())
                except (ValueError, OverflowError):
                    unique_count = 0

                # Detect column type
                detected_type = self._detect_column_type(col, col_data)

                # Get sample values safely
                try:
                    sample_values = col_data.dropna().astype(str).head(5).tolist()
                except Exception:
                    sample_values = []

                columns.append({
                    'name': str(col),
                    'detected_type': detected_type,
                    'non_null_count': non_null,
                    'null_count': null_count,
                    'unique_count': unique_count,
                    'sample_values': sample_values
                })

            # Get total row count using wc -l (fast and accurate)
            total_rows = len(df)
            try:
                import subprocess
                # Use wc -l for fast line counting
                result = subprocess.run(
                    ['wc', '-l', str(full_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    # wc -l output: "12345 /path/to/file.csv"
                    line_count = int(result.stdout.strip().split()[0])
                    total_rows = max(0, line_count - 1)  # Subtract header, ensure >= 0
                    logger.info(f"Total rows counted with wc: {total_rows:,}")
            except Exception as e:
                logger.warning(f"Could not count rows with wc: {e}, using sample count")
                # Fallback: use sample count
                total_rows = len(df)

            # Clean sample_data to avoid JSON serialization issues
            try:
                sample_data = df.head(10).fillna('').to_dict(orient='records')
            except Exception as e:
                logger.warning(f"Could not generate sample data: {e}")
                sample_data = []

            return {
                'file_path': file_path,
                'encoding': encoding,
                'delimiter': delimiter,
                'total_rows': int(total_rows),
                'total_columns': int(len(columns)),
                'columns': columns,
                'sample_data': sample_data,
                'file_size': int(full_path.stat().st_size)
            }

        except Exception as e:
            logger.error(f"CSV analysis error: {e}")
            return None

    def _detect_column_type(self, column_name: str, data: pd.Series) -> str:
        """
        Detect column semantic type

        Args:
            column_name: Column name
            data: Column data

        Returns:
            Detected type (email, phone, ip_address, username, password, etc.)
        """
        col_lower = column_name.lower()
        sample = data.dropna().astype(str).head(20)

        # Email detection
        if 'email' in col_lower or 'mail' in col_lower:
            return 'email'
        if len(sample) > 0 and sample.str.contains('@', na=False).sum() > len(sample) * 0.5:
            return 'email'

        # Phone detection
        if 'phone' in col_lower or 'tel' in col_lower or 'mobile' in col_lower or 'gsm' in col_lower:
            return 'phone'
        if len(sample) > 0 and sample.str.match(r'^\+?[\d\s\-\(\)]{8,}$', na=False).sum() > len(sample) * 0.3:
            return 'phone'

        # IP address detection
        if 'ip' in col_lower and 'zip' not in col_lower:
            if len(sample) > 0 and sample.str.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', na=False).sum() > len(sample) * 0.3:
                return 'ip_address'

        # Password/hash detection
        if 'pass' in col_lower or 'pwd' in col_lower or 'hash' in col_lower:
            # Check for hash-like patterns (long hex strings)
            if len(sample) > 0 and sample.str.match(r'^[a-fA-F0-9]{32,}$', na=False).sum() > len(sample) * 0.3:
                return 'password_hash'
            return 'password'

        # Username detection
        if 'user' in col_lower or 'login' in col_lower or 'account' in col_lower or 'pseudo' in col_lower:
            return 'username'

        # Name detection (specific to general)
        if 'firstname' in col_lower or 'first_name' in col_lower or 'prenom' in col_lower or 'prénom' in col_lower:
            return 'first_name'
        if 'lastname' in col_lower or 'last_name' in col_lower or ('nom' in col_lower and 'prenom' not in col_lower):
            return 'last_name'
        if 'fullname' in col_lower or 'full_name' in col_lower:
            return 'full_name'
        if 'name' in col_lower and 'user' not in col_lower and 'file' not in col_lower:
            return 'full_name'

        # Gender detection
        if 'gender' in col_lower or 'sex' in col_lower or 'sexe' in col_lower or 'genre' in col_lower:
            return 'gender'

        # Birth date detection
        if 'birth' in col_lower or 'dob' in col_lower or 'naissance' in col_lower or 'birthday' in col_lower:
            return 'birth_date'

        # Address fields
        if 'city' in col_lower or 'ville' in col_lower or 'town' in col_lower:
            return 'city'
        if 'country' in col_lower or 'pays' in col_lower:
            return 'country'
        if 'zip' in col_lower or 'postal' in col_lower or col_lower == 'cp':
            return 'zip_code'
        if 'address' in col_lower or 'adresse' in col_lower or 'street' in col_lower or 'rue' in col_lower:
            return 'address'

        # Professional info
        if 'company' in col_lower or 'entreprise' in col_lower or 'société' in col_lower or 'societe' in col_lower:
            return 'company'
        if 'job' in col_lower or 'title' in col_lower or 'poste' in col_lower or 'profession' in col_lower:
            return 'job_title'

        # Social media & web
        if any(x in col_lower for x in ['facebook', 'twitter', 'instagram', 'linkedin', 'social']):
            return 'social_media'
        if 'website' in col_lower or 'site' in col_lower or ('url' in col_lower and 'email' not in col_lower):
            return 'website'

        # Notes
        if 'note' in col_lower or 'comment' in col_lower or 'description' in col_lower:
            return 'notes'

        # Date detection
        if 'date' in col_lower or 'time' in col_lower or 'created' in col_lower:
            return 'date'

        # Default to text
        return 'text'

    async def get_column_mapping_suggestions(
        self,
        source_columns: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        Suggest mappings from source columns to target schema

        Args:
            source_columns: List of source column names

        Returns:
            Mapping suggestions {source_column: target_field}
        """
        target_schema = [
            'email', 'username', 'password', 'password_hash',
            'phone', 'ip_address',
            'full_name', 'first_name', 'last_name', 'gender', 'birth_date',
            'address', 'city', 'country', 'zip_code',
            'company', 'job_title', 'social_media', 'website', 'notes'
        ]

        suggestions = {}
        used_targets = set()

        for col in source_columns:
            col_lower = col.lower()
            best_match = None

            # Direct name matching
            for target in target_schema:
                if target in used_targets:
                    continue

                if target in col_lower:
                    best_match = target
                    break

            # Fuzzy matching
            if not best_match:
                if '@' in col_lower or 'mail' in col_lower:
                    best_match = 'email'
                elif 'user' in col_lower or 'login' in col_lower:
                    best_match = 'username'
                elif 'pass' in col_lower or 'pwd' in col_lower:
                    if 'hash' in col_lower:
                        best_match = 'password_hash'
                    else:
                        best_match = 'password'
                elif 'phone' in col_lower or 'tel' in col_lower:
                    best_match = 'phone'
                elif 'ip' in col_lower:
                    best_match = 'ip_address'
                elif 'name' in col_lower and 'user' not in col_lower:
                    best_match = 'name'

            suggestions[col] = best_match
            if best_match:
                used_targets.add(best_match)

        return suggestions


# Singleton instance
file_service = FileService()
