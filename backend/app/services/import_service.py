"""Import service for ingesting CSV files into Meilisearch"""
import pandas as pd
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import logging
from app.config import settings
from app.services.file_service import file_service
from app.services.meilisearch_service import meilisearch_service
from app.services.mdm_service import mdm_service

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing CSV data into Meilisearch"""

    def __init__(self):
        self.active_imports: Dict[str, bool] = {}  # Track active imports for cancellation

    async def import_csv(
        self,
        file_path: str,
        breach_name: str,
        column_mapping: Dict[str, str],
        breach_date: Optional[int] = None,
        batch_size: int = None,
        import_id: str = None,
        skip_lines: int = 0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Import CSV file into Typesense with progress updates

        Args:
            file_path: Path to CSV file
            breach_name: Name of the breach
            column_mapping: Mapping of source columns to target fields
            breach_date: Unix timestamp of breach date
            batch_size: Number of rows per batch
            import_id: Unique import ID for cancellation
            skip_lines: Number of lines to skip (for resuming imports)

        Yields:
            Progress updates with status and statistics
        """
        if batch_size is None:
            batch_size = settings.meilisearch_batch_size

        import_id = import_id or f"import_{datetime.now().timestamp()}"
        self.active_imports[import_id] = True

        full_path = file_service._resolve_file_path(file_path)
        imported_at = int(datetime.now().timestamp())
        logger.info(f"Starting import from: {full_path}")

        try:
            # Analyze CSV first
            yield {
                'status': 'analyzing',
                'message': 'Analyzing CSV file...',
                'progress': 0
            }

            analysis = await file_service.analyze_csv(file_path, sample_rows=10)
            if not analysis:
                yield {
                    'status': 'error',
                    'message': 'Failed to analyze CSV file',
                    'error': 'Invalid CSV format'
                }
                return

            total_rows = analysis['total_rows']
            encoding = analysis['encoding']
            delimiter = analysis['delimiter']

            # Extract domain from breach name (optional)
            domain = self._extract_domain(breach_name)

            # DEBUG: Log column mapping received
            logger.info(f"DEBUG: ========== IMPORT STARTED ==========")
            logger.info(f"DEBUG: Column mapping received (RAW): {column_mapping}")
            logger.info(f"DEBUG: Column mapping type: {type(column_mapping)}")
            logger.info(f"DEBUG: Number of mappings: {len(column_mapping)}")
            logger.info(f"DEBUG: Mapped fields (non-None): {[(k, v) for k, v in column_mapping.items() if v]}")
            logger.info(f"DEBUG: All keys: {list(column_mapping.keys())}")
            logger.info(f"DEBUG: col_5 in mapping? {('col_5' in column_mapping)}")
            if 'col_5' in column_mapping:
                logger.info(f"DEBUG: col_5 maps to: {column_mapping.get('col_5')}")
            logger.info(f"DEBUG: ======================================")

            # Start import
            yield {
                'status': 'importing',
                'message': f'Starting import of {total_rows:,} rows...',
                'progress': 0,
                'imported': 0,
                'failed': 0,
                'total_rows': total_rows
            }

            # Process with ultra-robust line-by-line parsing using native csv module
            errors = []

            with open(full_path, 'r', encoding=encoding, errors='replace') as csvfile:
                # Read multiple lines to determine expected field count (take the mode)
                sample_lines = []
                for _ in range(min(100, total_rows)):
                    line = csvfile.readline()
                    if not line:
                        break
                    sample_lines.append(line.strip())

                # Reset to beginning
                csvfile.seek(0)

                # Detect most common field count after fixing
                field_counts = {}
                for line in sample_lines:
                    fixed = self._fix_malformed_csv_line(line, 14, delimiter)
                    count = fixed.count(delimiter) + 1
                    field_counts[count] = field_counts.get(count, 0) + 1

                # Use most common field count as expected
                expected_fields = max(field_counts.items(), key=lambda x: x[1])[0]

                logger.info(f"Detected {expected_fields} fields in CSV (from {len(sample_lines)} sample lines)")
                logger.info(f"Field count distribution: {field_counts}")
                logger.info(f"Using delimiter: '{delimiter}'")

                # Read first line for header detection
                first_line = csvfile.readline().strip()
                first_line_fixed = self._fix_malformed_csv_line(first_line, expected_fields, delimiter)

                # Parse first line as header (or first data row if no header)
                first_line_parts = first_line_fixed.split(delimiter)

                # Strip whitespace
                first_line_parts = [h.strip() for h in first_line_parts]

                # Detect if first line is a header or data
                has_real_header = not first_line_parts[0].replace('.', '').replace(',', '').isdigit()

                if not has_real_header:
                    logger.info("No header detected, using col_0, col_1, ... as column names")
                    # Use consistent column names: col_0, col_1, etc. (same as analyze_csv)
                    header = [f"col_{i}" for i in range(expected_fields)]
                    # Reset file to read first line as data
                    csvfile.seek(0)
                    csvfile.readline()  # Skip BOM but keep first line for processing
                else:
                    logger.info("Header detected in first line, normalizing to col_N format")
                    # CRITICAL: Always normalize to col_0, col_1, etc. for consistency with frontend
                    # This ensures column_mapping keys always match
                    original_header = first_line_parts[:expected_fields]
                    header = [f"col_{i}" for i in range(expected_fields)]
                    logger.info(f"Original header: {original_header[:5]}... -> Normalized: {header[:5]}...")

                logger.info(f"Using {len(header)} columns: {header[:10]}...")

                # DEBUG: Log header structure for city debugging
                if 'col_5' in header:
                    logger.info(f"DEBUG: col_5 found at position {header.index('col_5')} in header")

                # COMPATIBILITY FIX DISABLED
                # The frontend should ALWAYS send col_0, col_1, col_2, etc.
                # If it doesn't, that's a frontend bug that needs to be fixed
                mapping_keys = list(column_mapping.keys())
                if mapping_keys and not mapping_keys[0].startswith('col_'):
                    logger.error(f"❌ FRONTEND BUG: Received non-col_N column names: {mapping_keys[:5]}")
                    logger.error(f"   Frontend must send column_mapping with keys like 'col_0', 'col_1', etc.")
                    logger.error(f"   Received keys: {list(column_mapping.keys())}")
                    # Don't try to fix it - fail fast so the bug gets fixed
                    raise ValueError(f"Invalid column mapping format. Expected col_0, col_1, etc. Got: {mapping_keys[:3]}")

                # Skip lines if resuming (skip_lines doesn't count header)
                if skip_lines > 0:
                    logger.info(f"Resuming import: skipping first {skip_lines:,} lines")
                    for i in range(skip_lines):
                        csvfile.readline()
                        if (i + 1) % 100000 == 0:
                            logger.info(f"Skipped {i + 1:,} / {skip_lines:,} lines...")
                    logger.info(f"Finished skipping {skip_lines:,} lines, starting import")

                # Process rows in batches with intelligent fixing
                batch = []
                row_num = 1 + skip_lines  # Start counting from after skipped lines
                fixed_count = 0
                last_progress_update = 0
                total_imported = skip_lines  # Count skipped lines as already imported
                total_failed = 0

                for raw_line in csvfile:
                    row_num += 1

                    # Check for cancellation every 1000 rows
                    if row_num % 1000 == 0 and not self.active_imports.get(import_id, False):
                        yield {
                            'status': 'cancelled',
                            'message': 'Import cancelled by user',
                            'imported': total_imported,
                            'failed': total_failed
                        }
                        return

                    # Apply intelligent fixing to the line
                    fixed_line = self._fix_malformed_csv_line(raw_line.strip(), expected_fields, delimiter)

                    # Parse the fixed line
                    row = fixed_line.split(delimiter)

                    # Track if we fixed this line
                    if fixed_line != raw_line.strip():
                        fixed_count += 1

                    # Skip rows that still don't match after fixing
                    if len(row) != len(header):
                        total_failed += 1
                        if len(errors) < 100:
                            errors.append(f"Row {row_num}: Expected {len(header)} fields, got {len(row)} (even after fixing)")
                        continue

                    # Create row dict and add to batch
                    try:
                        row_dict = dict(zip(header, row))

                        # DEBUG: Log first row_dict to verify structure
                        if row_num == 2:  # First data row (row 1 is header)
                            logger.info(f"DEBUG: First row_dict keys: {list(row_dict.keys())[:10]}")
                            if 'col_5' in row_dict:
                                logger.info(f"DEBUG: First row col_5 value: {row_dict.get('col_5')}")

                        batch.append(row_dict)
                    except Exception as e:
                        total_failed += 1
                        if len(errors) < 100:
                            errors.append(f"Row {row_num}: {str(e)[:100]}")
                        continue

                    # Send progress update every 1000 rows (even if batch not full)
                    if row_num % 1000 == 0 and row_num != last_progress_update:
                        last_progress_update = row_num
                        progress = int((row_num / total_rows) * 100) if total_rows > 0 else 0
                        yield {
                            'status': 'importing',
                            'message': f'Processing {row_num:,} / {total_rows:,} rows...',
                            'progress': min(progress, 95),
                            'imported': total_imported,
                            'failed': total_failed,
                            'total_rows': total_rows,
                            'rows_processed': row_num
                        }
                        await asyncio.sleep(0.001)  # Tiny delay to let WebSocket send

                    # Process batch when full
                    if len(batch) >= batch_size:
                        # Transform batch to documents
                        documents = []
                        for idx, row_data in enumerate(batch):
                            try:
                                doc = self._transform_row(
                                    pd.Series(row_data),  # Convert dict to Series for compatibility
                                    column_mapping,
                                    breach_name,
                                    file_path,
                                    domain,
                                    breach_date,
                                    imported_at
                                )
                                if doc:
                                    documents.append(doc)
                                elif idx == 0:  # Log first row of first batch for debugging
                                    logger.warning(f"First row produced no data. Row keys: {list(row_data.keys())[:5]}, Mapping: {list(column_mapping.keys())[:5]}")
                            except Exception as e:
                                total_failed += 1
                                if len(errors) < 100:
                                    errors.append(f"Transform error: {str(e)[:100]}")
                                if idx == 0:
                                    logger.error(f"Transform error on first row: {e}")
                                continue

                        # Import to SILVER
                        if documents:
                            result = await mdm_service.import_to_silver(
                                documents=documents,
                                breach_name=breach_name,
                                source_file=file_path
                            )
                            total_imported += result.get('imported', 0)
                            total_failed += result.get('failed', 0)

                        # Calculate progress
                        progress = int((row_num / total_rows) * 100) if total_rows > 0 else 0

                        # Yield progress update
                        yield {
                            'status': 'importing',
                            'message': f'Imported {total_imported:,} / {total_rows:,} rows',
                            'progress': min(progress, 95),  # Cap at 95% to leave room for dedup
                            'imported': total_imported,
                            'failed': total_failed,
                            'total_rows': total_rows,
                            'rows_processed': row_num
                        }

                        # Clear batch and allow WebSocket to send
                        batch = []
                        await asyncio.sleep(0.01)

                # Process remaining rows in final batch
                if batch:
                    documents = []
                    for row_data in batch:
                        try:
                            doc = self._transform_row(
                                pd.Series(row_data),
                                column_mapping,
                                breach_name,
                                file_path,
                                domain,
                                breach_date,
                                imported_at
                            )
                            if doc:
                                documents.append(doc)
                        except Exception as e:
                            total_failed += 1
                            continue

                    if documents:
                        result = await mdm_service.import_to_silver(
                            documents=documents,
                            breach_name=breach_name,
                            source_file=file_path
                        )
                        total_imported += result.get('imported', 0)
                        total_failed += result.get('failed', 0)

            # DEDUPLICATION DISABLED - Run manually from MDM view if needed
            # Automatic dedup is too heavy for large datasets (19M+ docs)
            # Use MDM view to run deduplication on-demand instead

            # # Run deduplication after import
            # yield {
            #     'status': 'deduplicating',
            #     'message': 'Running deduplication and master creation...',
            #     'progress': 95,
            #     'imported': total_imported,
            #     'total_rows': total_rows
            # }
            #
            # try:
            #     # Process deduplication on newly imported silver records
            #     dedup_stats = await mdm_service.process_silver_deduplication(batch_size=500)
            #     logger.info(f"Deduplication stats: {dedup_stats}")
            # except Exception as e:
            #     logger.error(f"Deduplication failed: {e}")
            #     # Continue anyway

            # Final status with auto-fix stats
            message_parts = [f'Import completed: {total_imported:,} rows imported']
            if fixed_count > 0:
                message_parts.append(f'{fixed_count:,} rows auto-fixed')
            if total_failed > 0:
                message_parts.append(f'{total_failed:,} rows skipped')

            yield {
                'status': 'completed',
                'message': ', '.join(message_parts),
                'progress': 100,
                'imported': total_imported,
                'failed': total_failed,
                'fixed': fixed_count,
                'total_rows': total_rows,
                'errors': errors[:10] if errors else []
            }

        except Exception as e:
            logger.error(f"Import error: {e}", exc_info=True)
            yield {
                'status': 'error',
                'message': f'Import failed: {str(e)}',
                'error': str(e)
            }

        finally:
            # Cleanup
            if import_id in self.active_imports:
                del self.active_imports[import_id]

    def _transform_row(
        self,
        row: pd.Series,
        column_mapping: Dict[str, str],
        breach_name: str,
        source_file: str,
        domain: Optional[str],
        breach_date: Optional[int],
        imported_at: int
    ) -> Optional[Dict[str, Any]]:
        """
        Transform a CSV row to Typesense document

        Args:
            row: Pandas series (CSV row)
            column_mapping: Column mapping
            breach_name: Breach name
            source_file: Source file path
            domain: Extracted domain
            breach_date: Breach date
            imported_at: Import timestamp

        Returns:
            Typesense document or None if invalid
        """
        doc = {
            'breach_name': breach_name,
            'source_file': source_file,
            'imported_at': imported_at
        }

        # Add breach date if provided
        if breach_date:
            doc['breach_date'] = breach_date

        # Add domain if available
        if domain:
            doc['domain'] = domain

        # Map columns
        has_data = False
        for source_col, target_field in column_mapping.items():
            if target_field and source_col in row.index:
                value = row[source_col]

                # Skip null values
                if pd.isna(value):
                    continue

                # Convert to string and clean
                value = str(value).strip()
                if not value:
                    continue

                # DEBUG: Log city mapping
                if target_field == 'city':
                    logger.info(f"DEBUG: Mapping city - source_col={source_col}, value={value}")

                doc[target_field] = value
                has_data = True

                # Auto-extract domain from email if not set
                if target_field == 'email' and not domain and '@' in value:
                    try:
                        doc['domain'] = value.split('@')[1].lower()
                    except Exception:
                        pass

        # Only return document if it has at least one data field
        return doc if has_data else None

    def _fix_malformed_csv_line(self, line: str, expected_fields: int, delimiter: str = ',') -> str:
        """
        Intelligent heuristic to fix malformed CSV lines

        Common issues:
        1. Dates with commas/delimiters: "1/1/2001 12,00,00 AM" -> "1/1/2001 12:00:00 AM"
        2. Unescaped delimiters in addresses: "City, Country" should be one field

        Args:
            line: Raw CSV line
            expected_fields: Expected number of fields
            delimiter: Field delimiter (default: ',')

        Returns:
            Fixed CSV line
        """
        import re

        # Only apply date/time fixing for comma delimiters
        # Fix 1: Replace commas in date/time patterns with colons
        # Pattern: date followed by time with commas like "12,00,00 AM"
        # Match: "10/9/2013 12,00,00 AM" or "1/1/0001 12,00,00 AM"
        if delimiter == ',':
            line = re.sub(
                r'(\d{1,2}/\d{1,2}/\d{4}\s+)(\d{1,2}),(\d{2}),(\d{2})(\s+[AP]M)',
                r'\1\2:\3:\4\5',
                line
            )

        # Check if we still have too many fields
        current_fields = line.count(delimiter) + 1

        if current_fields > expected_fields:
            # Fix 2: Try to merge address fields intelligently
            parts = line.split(delimiter)
            excess = current_fields - expected_fields

            # Identify location keywords that indicate end of address
            location_keywords = ['Hungary', 'France', 'Paris']

            fixed_parts = []
            i = 0
            merged_count = 0

            while i < len(parts) and merged_count < excess:
                part = parts[i].strip()

                # Look for pattern: "X, keyword" where keyword is a country
                if i < len(parts) - 1:
                    next_part = parts[i + 1].strip()

                    # If next part is a location keyword, merge current with next
                    if next_part in location_keywords and i > 5 and i < len(parts) - 3:
                        merged = f"{part} {next_part}".strip()
                        fixed_parts.append(merged)
                        merged_count += 1
                        i += 2
                        continue

                fixed_parts.append(part)
                i += 1

            # Add remaining parts
            while i < len(parts):
                fixed_parts.append(parts[i].strip())
                i += 1

            # Rebuild line
            line = delimiter.join(fixed_parts)

            # If still too many fields, try a more aggressive merge
            current_fields = line.count(delimiter) + 1
            if current_fields > expected_fields:
                # Last resort: merge excess middle fields
                parts = line.split(delimiter)
                excess = current_fields - expected_fields

                # Merge around the middle (likely address area)
                if len(parts) > 10:
                    middle_start = 5
                    middle_end = middle_start + excess + 1

                    before = parts[:middle_start]
                    middle = [' '.join(parts[middle_start:middle_end])]
                    after = parts[middle_end:]

                    line = delimiter.join(before + middle + after)

        return line

    def _extract_domain(self, breach_name: str) -> Optional[str]:
        """
        Extract domain from breach name

        Args:
            breach_name: Breach name (e.g., "LinkedIn 2021", "adobe.com")

        Returns:
            Domain or None
        """
        breach_lower = breach_name.lower().strip()

        # Common domain patterns
        if '.' in breach_lower and ' ' not in breach_lower:
            return breach_lower

        # Extract from common patterns
        common_sites = {
            'linkedin': 'linkedin.com',
            'facebook': 'facebook.com',
            'twitter': 'twitter.com',
            'adobe': 'adobe.com',
            'yahoo': 'yahoo.com',
            'myspace': 'myspace.com',
            'dropbox': 'dropbox.com',
        }

        for name, domain in common_sites.items():
            if name in breach_lower:
                return domain

        return None

    async def cancel_import(self, import_id: str) -> bool:
        """
        Cancel an active import

        Args:
            import_id: Import ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        if import_id in self.active_imports:
            self.active_imports[import_id] = False
            logger.info(f"Import {import_id} cancelled")
            return True
        return False

    async def get_import_preview(
        self,
        file_path: str,
        column_mapping: Dict[str, str],
        breach_name: str,
        rows: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Preview how data will be imported

        Args:
            file_path: Path to CSV file
            column_mapping: Column mapping
            breach_name: Breach name
            rows: Number of rows to preview

        Returns:
            Preview data with transformed documents
        """
        try:
            analysis = await file_service.analyze_csv(file_path, sample_rows=rows)
            if not analysis:
                return None

            full_path = file_service._resolve_file_path(file_path)
            encoding = analysis['encoding']
            delimiter = analysis['delimiter']
            logger.info(f"Generating preview for: {full_path}")

            # Detect if file has header (same logic as file_service)
            with open(full_path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()
                first_col = first_line.split(delimiter)[0].strip()
                has_header = not first_col.replace('.', '').replace(',', '').isdigit()

            # Read CSV with error handling for malformed files
            df = pd.read_csv(
                full_path,
                encoding=encoding,
                sep=delimiter,
                nrows=rows,
                on_bad_lines='skip',  # Skip problematic lines
                engine='python',  # More flexible parser
                quoting=1,  # QUOTE_ALL mode
                skipinitialspace=True,  # Skip spaces after delimiter
                header=0 if has_header else None  # Use header detection
            )

            # CRITICAL: Normalize column names to col_0, col_1, etc. (same as file_service)
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
            logger.info(f"Preview columns normalized to: {df.columns.tolist()}")

            domain = self._extract_domain(breach_name)
            imported_at = int(datetime.now().timestamp())

            preview_docs = []
            for _, row in df.iterrows():
                doc = self._transform_row(
                    row,
                    column_mapping,
                    breach_name,
                    file_path,
                    domain,
                    None,
                    imported_at
                )
                if doc:
                    preview_docs.append(doc)

            return {
                'total_rows': analysis['total_rows'],
                'preview_count': len(preview_docs),
                'sample_documents': preview_docs,
                'mapped_fields': list(set(column_mapping.values()) - {None})
            }

        except Exception as e:
            logger.error(f"Preview error: {e}")
            return None


# Singleton instance
import_service = ImportService()
