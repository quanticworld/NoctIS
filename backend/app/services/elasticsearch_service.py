"""Elasticsearch service for indexing and searching OSINT data"""
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
from typing import Optional, Dict, List, Any
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Service for managing Elasticsearch indices and search operations"""

    def __init__(self):
        """Initialize Elasticsearch client"""
        self._client: Optional[Elasticsearch] = None
        self._initialized = False
        self._initialization_status = "not_started"
        self._initialization_message = ""
        self._initialization_progress = 0

    @property
    def client(self) -> Elasticsearch:
        """Get or create Elasticsearch client (lazy initialization)"""
        if self._client is None:
            self._client = Elasticsearch(
                [f"{settings.elasticsearch_scheme}://{settings.elasticsearch_host}:{settings.elasticsearch_port}"],
                request_timeout=settings.elasticsearch_timeout
            )
        return self._client

    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status"""
        return {
            "status": self._initialization_status,
            "message": self._initialization_message,
            "progress": self._initialization_progress,
            "initialized": self._initialized
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check Elasticsearch server health"""
        try:
            health = self.client.cluster.health()
            status = health['status']
            if status in ['green', 'yellow']:
                return {"status": "healthy", "cluster_status": status}
            else:
                return {"status": "unhealthy", "cluster_status": status}
        except Exception as e:
            logger.debug(f"Elasticsearch health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def initialize_collections(self) -> Dict[str, bool]:
        """Initialize required indices if they don't exist"""
        self._initialization_status = "initializing"
        self._initialization_message = "Initializing Elasticsearch indices..."
        self._initialization_progress = 10

        results = {}

        # Silver Data: Raw imports (immutable, source of truth)
        silver_mappings = {
            "properties": {
                "source_id": {"type": "keyword"},
                # Core identifiers
                "email": {"type": "keyword"},
                "username": {"type": "keyword"},
                "password": {"type": "keyword"},
                "password_hash": {"type": "keyword"},
                "phone": {"type": "keyword"},
                "ip_address": {"type": "ip"},
                # Personal info
                "full_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "first_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "last_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "gender": {"type": "keyword"},
                "birth_date": {"type": "date", "format": "yyyy-MM-dd||yyyy/MM/dd||epoch_millis"},
                # Location info
                "address": {"type": "text"},
                "city": {"type": "keyword"},
                "country": {"type": "keyword"},
                "zip_code": {"type": "keyword"},
                # Professional info
                "company": {"type": "keyword"},
                "job_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                # Online presence
                "social_media": {"type": "text"},
                "website": {"type": "keyword"},
                # Additional
                "notes": {"type": "text"},
                # Source metadata
                "breach_name": {"type": "keyword"},
                "breach_date": {"type": "date", "format": "epoch_millis"},
                "source_file": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "imported_at": {"type": "date", "format": "epoch_millis"},
                # MDM linkage
                "master_id": {"type": "keyword"}
            }
        }

        silver_settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "30s",
            "index.translog.durability": "async"
        }

        # Master Data: Consolidated entities (deduplicated)
        master_mappings = {
            "properties": {
                "status": {"type": "keyword"},
                "confidence_score": {"type": "float"},
                "created_at": {"type": "date", "format": "epoch_millis"},
                "updated_at": {"type": "date", "format": "epoch_millis"},
                "validated_by": {"type": "keyword"},
                "matching_keys": {"type": "keyword"},
                "silver_ids": {"type": "keyword"},
                "source_count": {"type": "integer"},
                # Consolidated data
                "email": {"type": "keyword"},
                "email_verified": {"type": "boolean"},
                "username": {"type": "keyword"},
                "phone": {"type": "keyword"},
                "phone_verified": {"type": "boolean"},
                "ip_address": {"type": "ip"},
                "full_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "first_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "last_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "gender": {"type": "keyword"},
                "birth_date": {"type": "date", "format": "yyyy-MM-dd||yyyy/MM/dd||epoch_millis"},
                "address": {"type": "text"},
                "city": {"type": "keyword"},
                "country": {"type": "keyword"},
                "zip_code": {"type": "keyword"},
                "company": {"type": "keyword"},
                "job_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "social_media": {"type": "text"},
                "website": {"type": "keyword"},
                "breach_names": {"type": "keyword"},
                "first_seen": {"type": "date", "format": "epoch_millis"},
                "last_seen": {"type": "date", "format": "epoch_millis"},
                "passwords": {"type": "keyword"},
                "password_hashes": {"type": "keyword"}
            }
        }

        master_settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }

        # Conflicts
        conflicts_mappings = {
            "properties": {
                "master_id": {"type": "keyword"},
                "field_name": {"type": "keyword"},
                "status": {"type": "keyword"},
                "existing_value": {"type": "text"},
                "new_value": {"type": "text"},
                "existing_source": {"type": "keyword"},
                "new_source": {"type": "keyword"},
                "resolved_value": {"type": "text"},
                "resolved_by": {"type": "keyword"},
                "resolved_at": {"type": "date", "format": "epoch_millis"},
                "created_at": {"type": "date", "format": "epoch_millis"},
                "silver_id": {"type": "keyword"}
            }
        }

        conflicts_settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }

        self._initialization_message = "Creating silver_records index..."
        self._initialization_progress = 30
        results['silver_records'] = await self._ensure_index('silver_records', silver_settings, silver_mappings)

        self._initialization_message = "Creating master_records index..."
        self._initialization_progress = 60
        results['master_records'] = await self._ensure_index('master_records', master_settings, master_mappings)

        self._initialization_message = "Creating conflicts index..."
        self._initialization_progress = 90
        results['conflicts'] = await self._ensure_index('conflicts', conflicts_settings, conflicts_mappings)

        self._initialization_status = "ready"
        self._initialization_message = "Elasticsearch ready!"
        self._initialization_progress = 100
        self._initialized = True
        return results

    async def _ensure_index(self, index_name: str, settings: Dict, mappings: Dict) -> bool:
        """Ensure an index exists, create if it doesn't"""
        try:
            if self.client.indices.exists(index=index_name):
                logger.info(f"Index '{index_name}' already exists")
                return True
            else:
                self.client.indices.create(
                    index=index_name,
                    body={"settings": settings, "mappings": mappings}
                )
                logger.info(f"Index '{index_name}' created successfully")
                return True
        except Exception as e:
            logger.error(f"Error creating index '{index_name}': {e}")
            return False

    async def get_collection_stats(self, collection_name: str = 'silver_records') -> Optional[Dict[str, Any]]:
        """Get statistics for an index"""
        try:
            if not self.client.indices.exists(index=collection_name):
                return None

            stats = self.client.indices.stats(index=collection_name)
            count_result = self.client.count(index=collection_name)

            return {
                'name': collection_name,
                'num_documents': count_result['count'],
                'created_at': None,
                'num_memory_shards': stats['_all']['total']['segments']['count']
            }
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return None

    async def search(
        self,
        query: str,
        search_fields: List[str],
        filter_by: Optional[str] = None,
        per_page: int = 20,
        page: int = 1,
        collection_name: str = 'silver_records',
        typo_tolerance: bool = True,
        prefix: bool = True
    ) -> Dict[str, Any]:
        """
        Search in Elasticsearch index

        Args:
            query: Search query string
            search_fields: Fields to search in
            filter_by: Filter expression (Typesense format: "field:value && field2:value2")
            per_page: Results per page
            page: Page number
            collection_name: Index to search in
            typo_tolerance: Enable fuzzy search
            prefix: Enable prefix search

        Returns:
            Search results with hits and facets
        """
        try:
            from_offset = (page - 1) * per_page

            # Build must clauses
            must_clauses = []

            # Add main search query if not wildcard
            if query != '*':
                query_clause = {
                    "multi_match": {
                        "query": query,
                        "fields": search_fields,
                        "type": "best_fields"
                    }
                }
                if typo_tolerance:
                    query_clause["multi_match"]["fuzziness"] = "AUTO"
                must_clauses.append(query_clause)

            # Parse filter_by (Typesense format: "field:value && field2:value2")
            # Filters are EXACT partial matches (no typo tolerance, no fuzzy)
            # Use should clauses for better scoring: exact match > starts with > contains
            if filter_by:
                filter_parts = filter_by.split(' && ')
                for filter_part in filter_parts:
                    if ':' in filter_part:
                        field, value = filter_part.split(':', 1)
                        field = field.strip()
                        value = value.strip()

                        # Build a bool query with multiple should clauses for better scoring
                        # Higher boost = higher relevance
                        should_clauses = []

                        # For fields with .keyword mapping
                        if field in ['first_name', 'last_name', 'full_name', 'job_title']:
                            keyword_field = f"{field}.keyword"
                            # Exact match (highest score)
                            should_clauses.append({
                                "term": {
                                    keyword_field: {
                                        "value": value,
                                        "case_insensitive": True,
                                        "boost": 10
                                    }
                                }
                            })
                            # Starts with (high score)
                            should_clauses.append({
                                "wildcard": {
                                    keyword_field: {
                                        "value": f"{value}*",
                                        "case_insensitive": True,
                                        "boost": 5
                                    }
                                }
                            })
                            # Contains (normal score)
                            should_clauses.append({
                                "wildcard": {
                                    keyword_field: {
                                        "value": f"*{value}*",
                                        "case_insensitive": True,
                                        "boost": 1
                                    }
                                }
                            })
                        else:
                            # Pure keyword fields
                            # Exact match
                            should_clauses.append({
                                "term": {
                                    field: {
                                        "value": value,
                                        "case_insensitive": True,
                                        "boost": 10
                                    }
                                }
                            })
                            # Starts with
                            should_clauses.append({
                                "wildcard": {
                                    field: {
                                        "value": f"{value}*",
                                        "case_insensitive": True,
                                        "boost": 5
                                    }
                                }
                            })
                            # Contains
                            should_clauses.append({
                                "wildcard": {
                                    field: {
                                        "value": f"*{value}*",
                                        "case_insensitive": True,
                                        "boost": 1
                                    }
                                }
                            })

                        # At least one should clause must match (minimum_should_match: 1)
                        must_clauses.append({
                            "bool": {
                                "should": should_clauses,
                                "minimum_should_match": 1
                            }
                        })

            # Build final query
            if must_clauses:
                body = {
                    "query": {"bool": {"must": must_clauses}},
                    "from": from_offset,
                    "size": per_page
                }
            else:
                # Match all if no query and no filters
                body = {
                    "query": {"match_all": {}},
                    "from": from_offset,
                    "size": per_page
                }

            response = self.client.search(index=collection_name, body=body)

            hits = [
                {
                    "document": hit["_source"],
                    "highlights": hit.get("highlight"),
                    "text_match": hit["_score"]
                }
                for hit in response["hits"]["hits"]
            ]

            return {
                'hits': hits,
                'found': response['hits']['total']['value'],
                'out_of': response['hits']['total']['value'],
                'page': page,
                'search_time_ms': response['took'],
                'facet_counts': []
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'hits': [],
                'found': 0,
                'error': str(e)
            }

    async def multi_search(self, searches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple searches in a single request using _msearch
        """
        try:
            requests = []
            for search in searches:
                index = search.get('collection', 'silver_records')
                query = search.get('query', '')
                query_by = search.get('query_by', 'email')

                requests.append({"index": index})
                requests.append({
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": query_by.split(',') if isinstance(query_by, str) else query_by
                        }
                    },
                    "size": search.get('per_page', 20)
                })

            response = self.client.msearch(body=requests)
            return [r.get('hits', {}) for r in response.get('responses', [])]

        except Exception as e:
            logger.error(f"Multi-search error: {e}")
            return []

    async def import_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str = 'silver_records',
        action: str = 'index'
    ) -> Dict[str, Any]:
        """
        Import documents in batch using bulk API

        Args:
            documents: List of documents to import
            collection_name: Target index
            action: Import action (index, create, update)

        Returns:
            Import results with success/failure counts
        """
        if not documents:
            return {'success': 0, 'failed': 0, 'errors': []}

        try:
            actions = [
                {
                    "_op_type": action,
                    "_index": collection_name,
                    "_id": doc.get('source_id') or doc.get('id'),
                    "_source": doc
                }
                for doc in documents
            ]

            success_count, errors = bulk(self.client, actions, raise_on_error=False, stats_only=False)
            failed_count = len(errors)

            return {
                'success': success_count,
                'failed': failed_count,
                'errors': [str(e) for e in errors[:10]]
            }

        except Exception as e:
            logger.error(f"Import error: {e}")
            return {
                'success': 0,
                'failed': len(documents),
                'error': str(e)
            }

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete an index"""
        try:
            self.client.indices.delete(index=collection_name)
            logger.info(f"Index '{collection_name}' deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            return False

    async def get_facets(
        self,
        collection_name: str = 'silver_records',
        facet_fields: List[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get facet counts using aggregations

        Args:
            collection_name: Index to query
            facet_fields: Fields to get facets for

        Returns:
            Dictionary of facet counts by field
        """
        if facet_fields is None:
            facet_fields = ['breach_name', 'domain', 'breach_date']

        try:
            aggs = {
                field: {"terms": {"field": field, "size": 100}}
                for field in facet_fields
            }

            response = self.client.search(
                index=collection_name,
                body={"size": 0, "aggs": aggs}
            )

            facets = {}
            for field in facet_fields:
                if field in response['aggregations']:
                    facets[field] = [
                        {"value": bucket["key"], "count": bucket["doc_count"]}
                        for bucket in response['aggregations'][field]['buckets']
                    ]

            return facets

        except Exception as e:
            logger.error(f"Error getting facets: {e}")
            return {}


# Singleton instance
elasticsearch_service = ElasticsearchService()
