"""Master Data Management service for entity resolution and deduplication"""
import hashlib
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
from app.services.typesense_service import typesense_service

logger = logging.getLogger(__name__)


class MDMService:
    """Service for Master Data Management: deduplication, entity resolution, and data quality"""

    # Matching strategies with confidence scores
    MATCH_STRATEGIES = {
        'email_exact': {'confidence': 95, 'keys': ['email']},
        'phone_firstname': {'confidence': 85, 'keys': ['phone', 'first_name']},
        'phone_lastname': {'confidence': 85, 'keys': ['phone', 'last_name']},
        'email_username': {'confidence': 80, 'keys': ['email', 'username']},
        'fullname_birthdate': {'confidence': 75, 'keys': ['full_name', 'birth_date']},
        'username_breach': {'confidence': 50, 'keys': ['username', 'breach_name']},
    }

    def __init__(self):
        self.client = typesense_service.client

    async def import_to_silver(
        self,
        documents: List[Dict[str, Any]],
        breach_name: str,
        source_file: str
    ) -> Dict[str, int]:
        """
        Import raw data to silver_records collection

        Args:
            documents: List of raw documents to import
            breach_name: Name of the breach
            source_file: Source file path

        Returns:
            Stats: {imported: count, failed: count}
        """
        silver_docs = []

        for idx, doc in enumerate(documents):
            # Generate unique source_id (deterministic based on content)
            content_hash = self._generate_content_hash(doc)
            source_id = f"{breach_name}_{content_hash}_{idx}"

            silver_doc = {
                'id': source_id,  # Typesense will use this as ID
                'source_id': source_id,
                'breach_name': breach_name,
                'source_file': source_file,
                'imported_at': int(datetime.now().timestamp()),
                **doc  # All fields from original document
            }

            silver_docs.append(silver_doc)

        # Import to Typesense (upsert mode - will update if source_id exists)
        try:
            result = self.client.collections['silver_records'].documents.import_(
                silver_docs,
                {'action': 'upsert'}  # Update if exists, insert if not
            )

            success = sum(1 for r in result if 'success' in str(r).lower())
            failed = len(result) - success

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

            # Build search query
            filter_conditions = []
            for key in keys:
                value = silver_doc[key]
                # Escape special characters for Typesense
                escaped_value = value.replace(':', '\\:')
                filter_conditions.append(f"{key}:={escaped_value}")

            filter_query = ' && '.join(filter_conditions)

            try:
                # Search for matching master
                results = self.client.collections['master_records'].documents.search({
                    'q': '*',
                    'filter_by': filter_query,
                    'per_page': 1
                })

                if results['found'] > 0:
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
            self.client.collections['master_records'].documents.create(master_doc)
            logger.info(f"Created master record: {master_id} from silver {silver_doc['source_id']}")
            return master_id
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
            # Fetch current master
            master = self.client.collections['master_records'].documents[master_id].retrieve()

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

            # Merge data fields (only update if missing in master)
            for field in ['email', 'username', 'phone', 'full_name', 'first_name',
                          'last_name', 'gender', 'birth_date', 'address', 'city',
                          'country', 'company', 'job_title', 'social_media', 'website']:
                if not master.get(field) and silver_doc.get(field):
                    updates[field] = silver_doc[field]

            # Update master
            self.client.collections['master_records'].documents[master_id].update(updates)
            logger.info(f"Merged silver {silver_doc['source_id']} into master {master_id}")

            # Update silver with master_id link
            self.client.collections['silver_records'].documents[silver_doc['id']].update({
                'master_id': master_id
            })

            return True

        except Exception as e:
            logger.error(f"Failed to merge silver to master: {e}")
            return False

    async def process_silver_deduplication(self, batch_size: int = 100) -> Dict[str, int]:
        """
        Process silver records for deduplication and master creation/merge

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Stats: {processed, new_masters, merged, errors}
        """
        stats = {'processed': 0, 'new_masters': 0, 'merged': 0, 'errors': 0}

        try:
            # Find silver records without master_id
            # Note: Typesense doesn't support filtering by empty values
            # So we fetch all and filter in Python (or use NOT operator)
            results = self.client.collections['silver_records'].documents.search({
                'q': '*',
                'per_page': batch_size
            })

            # Filter out records that already have a master_id
            unlinked_hits = [hit for hit in results['hits'] if not hit['document'].get('master_id')]

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
                        self.client.collections['silver_records'].documents[silver_doc['id']].update({
                            'master_id': master_id
                        })

                except Exception as e:
                    logger.error(f"Error processing silver {silver_doc['id']}: {e}")
                    stats['errors'] += 1

            logger.info(f"Deduplication stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Deduplication batch failed: {e}")
            return stats

    def _generate_content_hash(self, doc: Dict[str, Any]) -> str:
        """Generate deterministic hash from document content"""
        # Sort keys for deterministic hash
        content = '|'.join(str(doc.get(k, '')) for k in sorted(doc.keys()))
        return hashlib.md5(content.encode()).hexdigest()[:12]

    async def get_master_with_sources(self, master_id: str) -> Optional[Dict[str, Any]]:
        """
        Get master record with all linked silver sources

        Args:
            master_id: Master record ID

        Returns:
            Master record with 'sources' field containing all silver records
        """
        try:
            master = self.client.collections['master_records'].documents[master_id].retrieve()

            # Fetch all linked silver records
            silver_ids = master.get('silver_ids', [])
            sources = []

            for silver_id in silver_ids:
                try:
                    silver = self.client.collections['silver_records'].documents[silver_id].retrieve()
                    sources.append(silver)
                except Exception as e:
                    logger.warning(f"Failed to fetch silver {silver_id}: {e}")

            master['sources'] = sources
            return master

        except Exception as e:
            logger.error(f"Failed to get master with sources: {e}")
            return None


# Singleton instance
mdm_service = MDMService()
