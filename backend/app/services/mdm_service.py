"""Master Data Management service for entity resolution and deduplication"""
import hashlib
import uuid
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import logging
from app.services.clickhouse_service import clickhouse_service

logger = logging.getLogger(__name__)

# Configuration file for correlation rules
RULES_CONFIG_PATH = Path("/app/data/correlation_rules.json")


class MDMService:
    """Service for Master Data Management: deduplication, entity resolution, and data quality"""

    # Default matching strategies with confidence scores
    DEFAULT_MATCH_STRATEGIES = {
        'email_exact': {'confidence': 95, 'keys': ['email']},
        'phone_firstname': {'confidence': 85, 'keys': ['phone', 'first_name']},
        'phone_lastname': {'confidence': 85, 'keys': ['phone', 'last_name']},
        'email_username': {'confidence': 80, 'keys': ['email', 'username']},
        'fullname_birthdate': {'confidence': 75, 'keys': ['full_name', 'birth_date']},
        'username_breach': {'confidence': 50, 'keys': ['username', 'breach_name']},
    }

    def __init__(self):
        self.client = clickhouse_service.client
        # Load strategies from config file or use defaults
        self.MATCH_STRATEGIES = self._load_match_strategies()

    def _load_match_strategies(self) -> Dict[str, Any]:
        """Load matching strategies from config file or use defaults"""
        try:
            if RULES_CONFIG_PATH.exists():
                with open(RULES_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    strategies = {}
                    for rule in config.get('rules', []):
                        strategies[rule['name']] = {
                            'confidence': rule['confidence'],
                            'keys': rule['keys']
                        }
                    logger.info(f"Loaded {len(strategies)} correlation rules from config")
                    return strategies
        except Exception as e:
            logger.warning(f"Failed to load correlation rules from file: {e}")

        logger.info("Using default correlation rules")
        return self.DEFAULT_MATCH_STRATEGIES.copy()

    async def import_to_silver(
        self,
        documents: List[Dict[str, Any]],
        breach_name: str,
        source_file: str,
        fast_mode: bool = True
    ) -> Dict[str, int]:
        """
        Import raw data to silver_records collection

        Args:
            documents: List of raw documents to import
            breach_name: Name of the breach
            source_file: Source file path
            fast_mode: Use fast hashing (UUID) instead of content hash

        Returns:
            Stats: {imported: count, failed: count}
        """
        silver_docs = []

        for idx, doc in enumerate(documents):
            # OPTIMIZATION: Use fast ID generation in fast_mode
            if fast_mode:
                # Fast: just use UUID (no deterministic dedup, but 100x faster)
                source_id = f"{breach_name}_{uuid.uuid4().hex[:12]}"
            else:
                # Slow: deterministic hash (allows dedup, but slow)
                content_hash = self._generate_content_hash(doc)
                source_id = f"{breach_name}_{content_hash}"

            silver_doc = {
                'id': source_id,  # Elasticsearch will use this as _id
                'source_id': source_id,
                'breach_name': breach_name,
                'source_file': source_file,
                'imported_at': int(datetime.now().timestamp()),
                **doc  # All fields from original document
            }

            silver_docs.append(silver_doc)

        # Import to ClickHouse (bulk API with upsert)
        try:
            result = await clickhouse_service.import_documents(
                documents=silver_docs,
                collection_name='silver_records'
            )

            success = result.get('success', 0)
            failed = result.get('failed', 0)

            logger.info(f"Imported to silver: {success} success, {failed} failed")

            return {'imported': success, 'failed': failed}

        except Exception as e:
            logger.error(f"Failed to import to silver: {e}")
            return {'imported': 0, 'failed': len(silver_docs)}

    async def find_matching_master(
        self,
        silver_doc: Dict[str, Any]
    ) -> Optional[Tuple[str, str, float]]:
        """
        Find matching master record for a silver document

        Args:
            silver_doc: Silver document to match

        Returns:
            Tuple of (master_id, strategy_used, confidence) or None
        """
        for strategy_name, strategy in self.MATCH_STRATEGIES.items():
            keys = strategy['keys']
            confidence = strategy['confidence']

            # Check if all required keys are present and not empty
            if not all(silver_doc.get(key) for key in keys):
                continue

            # Build Elasticsearch query (bool query with must clauses)
            must_clauses = []
            for key in keys:
                value = silver_doc[key]
                must_clauses.append({"term": {key: value}})

            try:
                # Search for matching master using ClickHouse
                results = await clickhouse_service.search(
                    query="*",
                    search_fields=[],
                    collection_name='master_records',
                    per_page=1,
                    page=1,
                    filter_by=None,
                    typo_tolerance=False,
                    prefix=False,
                    custom_query={
                        "bool": {
                            "must": must_clauses
                        }
                    }
                )

                if results.get('found', 0) > 0:
                    master_id = results['hits'][0]['document']['id']
                    logger.info(f"Found match using {strategy_name}: master_id={master_id}")
                    return (master_id, strategy_name, confidence)

            except Exception as e:
                logger.warning(f"Error searching with strategy {strategy_name}: {e}")
                continue

        return None

    async def create_master_from_silver(
        self,
        silver_doc: Dict[str, Any],
        strategy: str = 'auto',
        confidence: float = 50.0
    ) -> str:
        """
        Create a new master record from a silver document

        Args:
            silver_doc: Silver document
            strategy: Matching strategy used
            confidence: Initial confidence score

        Returns:
            Master ID
        """
        master_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())

        # Extract matching keys
        matching_keys = []
        if silver_doc.get('email'):
            matching_keys.append(f"email:{silver_doc['email']}")
        if silver_doc.get('phone') and silver_doc.get('first_name'):
            matching_keys.append(f"phone+fn:{silver_doc['phone']}_{silver_doc['first_name']}")
        if silver_doc.get('phone') and silver_doc.get('last_name'):
            matching_keys.append(f"phone+ln:{silver_doc['phone']}_{silver_doc['last_name']}")

        # Determine status based on confidence
        status = 'golden' if confidence >= 90 else 'silver'

        master_doc = {
            'id': master_id,
            'status': status,
            'confidence_score': confidence,
            'created_at': now,
            'updated_at': now,
            'validated_by': 'auto',
            'matching_keys': matching_keys,
            'silver_ids': [silver_doc['source_id']],
            'source_count': 1,

            # Copy all data fields
            'email': silver_doc.get('email'),
            'username': silver_doc.get('username'),
            'phone': silver_doc.get('phone'),
            'ip_address': silver_doc.get('ip_address'),
            'full_name': silver_doc.get('full_name'),
            'first_name': silver_doc.get('first_name'),
            'last_name': silver_doc.get('last_name'),
            'gender': silver_doc.get('gender'),
            'birth_date': silver_doc.get('birth_date'),
            'address': silver_doc.get('address'),
            'city': silver_doc.get('city'),
            'country': silver_doc.get('country'),
            'zip_code': silver_doc.get('zip_code'),
            'company': silver_doc.get('company'),
            'job_title': silver_doc.get('job_title'),
            'social_media': silver_doc.get('social_media'),
            'website': silver_doc.get('website'),

            # Aggregate breach info
            'breach_names': [silver_doc['breach_name']],
            'first_seen': silver_doc['imported_at'],
            'last_seen': silver_doc['imported_at'],

            # Passwords (as arrays)
            'passwords': [silver_doc['password']] if silver_doc.get('password') else [],
            'password_hashes': [silver_doc['password_hash']] if silver_doc.get('password_hash') else [],
        }

        # Remove None values
        master_doc = {k: v for k, v in master_doc.items() if v is not None}

        try:
            # Create document in ClickHouse
            result = await clickhouse_service.import_documents(
                documents=[master_doc],
                collection_name='master_records'
            )
            if result.get('imported', 0) > 0:
                logger.info(f"Created master record: {master_id} from silver {silver_doc['source_id']}")
                return master_id
            else:
                raise Exception("Failed to create master document")
        except Exception as e:
            logger.error(f"Failed to create master: {e}")
            raise

    async def merge_silver_to_master(
        self,
        silver_doc: Dict[str, Any],
        master_id: str,
        confidence: float
    ) -> bool:
        """
        Merge a silver record into an existing master

        Args:
            silver_doc: Silver document to merge
            master_id: Target master ID
            confidence: Match confidence

        Returns:
            Success status
        """
        try:
            # Fetch current master from Elasticsearch
            response = self.client.get(index='master_records', id=master_id)
            master = response['_source']

            # Update silver_ids
            silver_ids = master.get('silver_ids', [])
            if silver_doc['source_id'] not in silver_ids:
                silver_ids.append(silver_doc['source_id'])

            # Update breach names
            breach_names = master.get('breach_names', [])
            if silver_doc['breach_name'] not in breach_names:
                breach_names.append(silver_doc['breach_name'])

            # Merge passwords
            passwords = master.get('passwords', [])
            if silver_doc.get('password') and silver_doc['password'] not in passwords:
                passwords.append(silver_doc['password'])

            password_hashes = master.get('password_hashes', [])
            if silver_doc.get('password_hash') and silver_doc['password_hash'] not in password_hashes:
                password_hashes.append(silver_doc['password_hash'])

            # Update timestamps
            now = int(datetime.now().timestamp())

            # Merge fields (keep most complete/recent data)
            updates = {
                'silver_ids': silver_ids,
                'source_count': len(silver_ids),
                'breach_names': breach_names,
                'updated_at': now,
                'last_seen': now,
                'passwords': passwords,
                'password_hashes': password_hashes,
            }

            # Update confidence (weighted average)
            old_confidence = master.get('confidence_score', 50)
            old_count = master.get('source_count', 1)
            new_confidence = ((old_confidence * old_count) + confidence) / (old_count + 1)
            updates['confidence_score'] = new_confidence

            # Promote to golden if confidence is high
            if new_confidence >= 90 and master.get('status') != 'golden':
                updates['status'] = 'golden'

            # Merge data fields - detect conflicts when values differ
            conflicting_fields = []
            for field in ['email', 'username', 'phone', 'full_name', 'first_name',
                          'last_name', 'gender', 'birth_date', 'address', 'city',
                          'country', 'company', 'job_title', 'social_media', 'website']:
                master_value = master.get(field)
                silver_value = silver_doc.get(field)

                # If both exist and are different, we have a conflict
                if master_value and silver_value and master_value != silver_value:
                    conflicting_fields.append({
                        'field_name': field,
                        'existing_value': master_value,
                        'new_value': silver_value,
                        'existing_source': master.get('breach_names', ['unknown'])[0],
                        'new_source': silver_doc['breach_name']
                    })
                    logger.warning(f"Conflict detected on field '{field}': '{master_value}' vs '{silver_value}'")

                # If master is empty but silver has value, update
                elif not master_value and silver_value:
                    updates[field] = silver_value

            # Store conflicts if any were detected
            if conflicting_fields:
                await self._store_conflicts(master_id, silver_doc['source_id'], conflicting_fields)

            # Update master in Elasticsearch
            self.client.update(
                index='master_records',
                id=master_id,
                body={'doc': updates}
            )
            logger.info(f"Merged silver {silver_doc['source_id']} into master {master_id}")

            # Update silver with master_id link
            self.client.update(
                index='silver_records',
                id=silver_doc['id'],
                body={'doc': {'master_id': master_id}}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to merge silver to master: {e}")
            return False

    async def process_silver_deduplication(
        self,
        batch_size: int = 100,
        max_batches: int = None,
        page_offset: int = 1,
        progress_callback = None
    ) -> Dict[str, int]:
        """
        Process silver records for deduplication and master creation/merge

        Args:
            batch_size: Number of records to process per batch
            max_batches: Maximum number of batches to process (None = all)
            page_offset: Starting page number (for resuming)

        Returns:
            Stats: {processed, new_masters, merged, errors, has_more}
        """
        stats = {'processed': 0, 'new_masters': 0, 'merged': 0, 'errors': 0, 'has_more': False}
        batches_processed = 0

        try:
            # Process batches until no more unlinked records or max_batches reached
            page = page_offset

            while True:
                # Check if we've hit max_batches limit
                if max_batches and batches_processed >= max_batches:
                    logger.info(f"Reached max_batches limit: {max_batches}")
                    stats['has_more'] = True
                    break

                # Fetch next batch of silver records
                results = await clickhouse_service.search(
                    query="*",
                    search_fields=[],
                    collection_name='silver_records',
                    per_page=batch_size,
                    page=page,
                    filter_by=None,
                    typo_tolerance=False,
                    prefix=False
                )

                # Filter out records that already have a master_id
                unlinked_hits = [hit for hit in results.get('hits', []) if not hit['document'].get('master_id')]

                # If no unlinked records found, check if there are more pages
                if not unlinked_hits:
                    # Check if we've exhausted all pages
                    if len(results.get('hits', [])) == 0 or page > results.get('out_of', page):
                        logger.info("No more unlinked silver records to process")
                        break
                    # Otherwise, try next page
                    page += 1
                    continue

                logger.info(f"Processing batch {batches_processed + 1}: {len(unlinked_hits)} unlinked records from page {page}")

                # Send progress update at start of batch
                if progress_callback:
                    await progress_callback({
                        'type': 'progress',
                        'batch': batches_processed + 1,
                        'processed': stats['processed'],
                        'new_masters': stats['new_masters'],
                        'merged': stats['merged'],
                        'errors': stats['errors']
                    })

                for hit in unlinked_hits:
                    silver_doc = hit['document']
                    stats['processed'] += 1

                    try:
                        # Try to find matching master
                        match = await self.find_matching_master(silver_doc)

                        if match:
                            master_id, strategy, confidence = match
                            # Merge to existing master
                            success = await self.merge_silver_to_master(silver_doc, master_id, confidence)
                            if success:
                                stats['merged'] += 1
                        else:
                            # Create new master
                            master_id = await self.create_master_from_silver(silver_doc)
                            stats['new_masters'] += 1

                            # Link silver to master
                            self.client.update(
                                index='silver_records',
                                id=silver_doc['id'],
                                body={'doc': {'master_id': master_id}}
                            )

                    except Exception as e:
                        logger.error(f"Error processing silver {silver_doc.get('id', 'unknown')}: {e}")
                        stats['errors'] += 1

                batches_processed += 1
                page += 1

                # Log progress every 10 batches
                if batches_processed % 10 == 0:
                    logger.info(f"Progress: {stats}")

            logger.info(f"Deduplication complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Deduplication batch failed: {e}")
            return stats

    def _generate_content_hash(self, doc: Dict[str, Any]) -> str:
        """Generate deterministic hash from document content"""
        # Sort keys for deterministic hash
        content = '|'.join(str(doc.get(k, '')) for k in sorted(doc.keys()))
        return hashlib.md5(content.encode()).hexdigest()[:12]

    async def _store_conflicts(
        self,
        master_id: str,
        silver_id: str,
        conflicting_fields: List[Dict[str, Any]]
    ) -> None:
        """
        Store field-level conflicts for manual resolution

        Args:
            master_id: Master record ID
            silver_id: Silver record ID causing conflict
            conflicting_fields: List of conflicts with field details
        """
        now = int(datetime.now().timestamp())

        conflict_docs = []
        for conflict in conflicting_fields:
            conflict_id = str(uuid.uuid4())
            conflict_doc = {
                'id': conflict_id,
                'master_id': master_id,
                'silver_id': silver_id,
                'field_name': conflict['field_name'],
                'status': 'pending',
                'existing_value': str(conflict['existing_value']),
                'new_value': str(conflict['new_value']),
                'existing_source': conflict['existing_source'],
                'new_source': conflict['new_source'],
                'created_at': now
            }
            conflict_docs.append(conflict_doc)

        try:
            # Use clickhouse_service to import conflicts
            result = await clickhouse_service.import_documents(
                documents=conflict_docs,
                collection_name='conflicts'
            )
            logger.info(f"Stored {result.get('imported', 0)} conflicts for master {master_id}")
        except Exception as e:
            logger.error(f"Failed to store conflicts: {e}")

    async def get_master_with_sources(self, master_id: str) -> Optional[Dict[str, Any]]:
        """
        Get master record with all linked silver sources

        Args:
            master_id: Master record ID

        Returns:
            Master record with 'sources' field containing all silver records
        """
        try:
            # Fetch master from Elasticsearch
            response = self.client.get(index='master_records', id=master_id)
            master = response['_source']
            master['id'] = master_id  # Add ID to response

            # Fetch all linked silver records
            silver_ids = master.get('silver_ids', [])
            sources = []

            for silver_id in silver_ids:
                try:
                    silver_response = self.client.get(index='silver_records', id=silver_id)
                    silver = silver_response['_source']
                    silver['id'] = silver_id
                    sources.append(silver)
                except Exception as e:
                    logger.warning(f"Failed to fetch silver {silver_id}: {e}")

            master['sources'] = sources
            return master

        except Exception as e:
            logger.error(f"Failed to get master with sources: {e}")
            return None

    async def get_conflicts(
        self,
        master_id: Optional[str] = None,
        status: str = 'pending',
        page: int = 1,
        per_page: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get conflicts for resolution

        Args:
            master_id: Filter by master ID (optional)
            status: Filter by status (pending/resolved/ignored)
            page: Page number
            per_page: Results per page

        Returns:
            List of conflict records
        """
        try:
            # Build Elasticsearch bool query
            must_clauses = [{"term": {"status": status}}]
            if master_id:
                must_clauses.append({"term": {"master_id": master_id}})

            results = await clickhouse_service.search(
                query="*",
                search_fields=[],
                collection_name='conflicts',
                per_page=per_page,
                page=page,
                filter_by=None,
                typo_tolerance=False,
                prefix=False,
                custom_query={
                    "bool": {
                        "must": must_clauses
                    }
                },
                sort_by="created_at:desc"
            )

            return [hit['document'] for hit in results.get('hits', [])]

        except Exception as e:
            logger.error(f"Failed to get conflicts: {e}")
            return []

    async def resolve_conflict(
        self,
        conflict_id: str,
        chosen_value: str,
        resolved_by: str = 'manual'
    ) -> bool:
        """
        Resolve a conflict by choosing a value

        Args:
            conflict_id: Conflict ID
            chosen_value: The value to use (existing_value or new_value)
            resolved_by: Who/what resolved it (manual/auto)

        Returns:
            Success status
        """
        try:
            # Get conflict details from Elasticsearch
            conflict_response = self.client.get(index='conflicts', id=conflict_id)
            conflict = conflict_response['_source']

            # Update master record with chosen value
            master_id = conflict['master_id']
            field_name = conflict['field_name']

            now = int(datetime.now().timestamp())

            # Update master
            self.client.update(
                index='master_records',
                id=master_id,
                body={'doc': {
                    field_name: chosen_value,
                    'updated_at': now
                }}
            )

            # Mark conflict as resolved
            self.client.update(
                index='conflicts',
                id=conflict_id,
                body={'doc': {
                    'status': 'resolved',
                    'resolved_value': chosen_value,
                    'resolved_by': resolved_by,
                    'resolved_at': now
                }}
            )

            logger.info(f"Resolved conflict {conflict_id}: {field_name} = {chosen_value}")
            return True

        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
            return False


# Lazy singleton instance
_mdm_service_instance: Optional[MDMService] = None

def get_mdm_service() -> MDMService:
    """Get or create the singleton MDMService instance (lazy initialization)"""
    global _mdm_service_instance
    if _mdm_service_instance is None:
        _mdm_service_instance = MDMService()
    return _mdm_service_instance

# For backward compatibility during transition
mdm_service = None  # Will be replaced with get_mdm_service() calls
