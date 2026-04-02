"""Meilisearch service for indexing and searching OSINT data"""
import meilisearch
from typing import Optional, Dict, List, Any
import logging
from app.config import settings
import time

logger = logging.getLogger(__name__)


class MeilisearchClientWrapper:
    """
    Wrapper around Meilisearch client to provide Elasticsearch-like API
    This ensures compatibility with existing code (mdm_service, routers)
    """

    def __init__(self, client: meilisearch.Client):
        self._ms_client = client

    def count(self, index: str, query: Optional[Dict] = None) -> Dict[str, int]:
        """
        Count documents in an index

        Args:
            index: Index name
            query: Optional query filter (ES format, will be converted)

        Returns:
            {'count': total_documents}
        """
        try:
            idx = self._ms_client.index(index)

            if query is None or query == {"match_all": {}}:
                # Count all documents
                stats = idx.get_stats()
                return {'count': stats.number_of_documents}

            # Convert ES query to Meilisearch filter
            ms_filter = self._convert_es_query_to_filter(query)

            # Search with filter and limit 0 to get count only
            result = idx.search('', {
                'filter': ms_filter,
                'limit': 0
            })

            # Handle both dict and object response
            if isinstance(result, dict):
                count = result.get('estimatedTotalHits', 0)
            else:
                count = getattr(result, 'estimated_total_hits', 0)

            return {'count': count}

        except Exception as e:
            logger.error(f"Count error: {e}")
            return {'count': 0}

    def delete_by_query(self, index: str, query: Dict, conflicts: str = 'abort') -> Dict[str, int]:
        """
        Delete documents matching a query

        Args:
            index: Index name
            query: ES query (will be converted to Meilisearch filter)
            conflicts: How to handle conflicts (ignored in Meilisearch)

        Returns:
            {'deleted': number_of_deleted_documents}
        """
        try:
            idx = self._ms_client.index(index)

            # Convert ES query to Meilisearch filter
            ms_filter = self._convert_es_query_to_filter(query)

            if ms_filter:
                # Delete by filter (using delete_documents with filter parameter)
                task = idx.delete_documents(filter=ms_filter)
                # Don't wait for completion - return immediately (async delete)
                # The deletion will continue in background
                logger.info(f"Delete task {task.task_uid} started for filter: {ms_filter}")
                return {'deleted': 0, 'task_uid': task.task_uid, 'status': 'processing'}
            else:
                # Delete all if no filter (match_all)
                task = idx.delete_all_documents()
                # Don't wait for completion - return immediately (async delete)
                logger.info(f"Delete all task {task.task_uid} started")
                return {'deleted': 0, 'task_uid': task.task_uid, 'status': 'processing'}

        except Exception as e:
            logger.error(f"Delete by query error: {e}")
            return {'deleted': 0}

    def update(self, index: str, id: str, doc: Dict, **kwargs) -> Dict[str, str]:
        """
        Update a document (partial update)

        Args:
            index: Index name
            id: Document ID
            doc: Fields to update

        Returns:
            {'result': 'updated'}
        """
        try:
            idx = self._ms_client.index(index)

            # Get existing document
            existing = idx.get_document(id)

            # Merge with new fields
            updated_doc = {**existing, **doc, 'id': id}

            # Update document
            task = idx.update_documents([updated_doc])
            self._ms_client.wait_for_task(task.task_uid, timeout_in_ms=30000)

            return {'result': 'updated'}

        except Exception as e:
            logger.error(f"Update error for {id}: {e}")
            return {'result': 'error'}

    def delete(self, index: str, id: str) -> Dict[str, str]:
        """
        Delete a document by ID

        Args:
            index: Index name
            id: Document ID

        Returns:
            {'result': 'deleted'}
        """
        try:
            idx = self._ms_client.index(index)
            task = idx.delete_document(id)
            self._ms_client.wait_for_task(task.task_uid, timeout_in_ms=30000)
            return {'result': 'deleted'}

        except Exception as e:
            logger.error(f"Delete error for {id}: {e}")
            return {'result': 'error'}

    def search(self, index: str, query: Optional[Dict] = None, body: Optional[Dict] = None,
               from_: int = 0, size: int = 20, sort: Optional[List] = None,
               aggs: Optional[Dict] = None, **kwargs) -> Dict:
        """
        Search documents (ES-compatible API)

        Args:
            index: Index name
            query: ES query dict
            body: ES body (alternative to query)
            from_: Offset
            size: Limit
            sort: Sort criteria
            aggs: Aggregations

        Returns:
            ES-format search results
        """
        try:
            idx = self._ms_client.index(index)

            # Extract query from body if provided
            if body:
                query = body.get('query')
                from_ = body.get('from', from_)
                size = body.get('size', size)
                sort = body.get('sort', sort)
                aggs = body.get('aggs', aggs)

            # Convert ES query to Meilisearch params
            search_params = {
                'offset': from_,
                'limit': size
            }

            # Convert query
            q = ""
            ms_filter = None

            if query:
                q, ms_filter = self._convert_es_search_query(query)

            if ms_filter:
                search_params['filter'] = ms_filter

            # Convert sort
            if sort:
                search_params['sort'] = self._convert_es_sort(sort)

            # Perform search
            result = idx.search(q, search_params)

            # Handle both dict and object response
            if isinstance(result, dict):
                result_hits = result.get('hits', [])
                result_total = result.get('estimatedTotalHits', 0)
                result_time = result.get('processingTimeMs', 0)
            else:
                result_hits = getattr(result, 'hits', [])
                result_total = getattr(result, 'estimated_total_hits', 0)
                result_time = getattr(result, 'processing_time_ms', 0)

            # Convert to ES format
            es_result = {
                'hits': {
                    'total': {'value': result_total},
                    'hits': [
                        {
                            '_source': hit,
                            '_id': hit.get('id') if isinstance(hit, dict) else getattr(hit, 'id', None),
                            '_score': 1.0
                        }
                        for hit in result_hits
                    ]
                },
                'took': result_time
            }

            # Handle aggregations if requested
            if aggs:
                es_result['aggregations'] = self._handle_aggregations(idx, aggs, ms_filter)

            return es_result

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'hits': {
                    'total': {'value': 0},
                    'hits': []
                },
                'took': 0
            }

    def _convert_es_query_to_filter(self, query: Dict) -> Optional[str]:
        """Convert Elasticsearch query to Meilisearch filter"""
        if not query or query == {"match_all": {}}:
            return None

        # Handle term query
        if 'term' in query:
            field, value_dict = next(iter(query['term'].items()))
            if isinstance(value_dict, dict):
                value = value_dict.get('value', value_dict)
            else:
                value = value_dict

            if isinstance(value, str):
                return f'{field} = "{value}"'
            else:
                return f'{field} = {value}'

        # Handle exists query
        if 'exists' in query:
            field = query['exists']['field']
            return f'{field} EXISTS'

        # Handle bool query
        if 'bool' in query:
            bool_query = query['bool']
            filters = []

            # Must clauses (AND)
            if 'must' in bool_query:
                for must_clause in bool_query['must']:
                    clause_filter = self._convert_es_query_to_filter(must_clause)
                    if clause_filter:
                        filters.append(f'({clause_filter})')

            if filters:
                return ' AND '.join(filters)

        # Handle range query
        if 'range' in query:
            field, conditions = next(iter(query['range'].items()))
            range_filters = []
            if 'gte' in conditions:
                range_filters.append(f'{field} >= {conditions["gte"]}')
            if 'lte' in conditions:
                range_filters.append(f'{field} <= {conditions["lte"]}')
            if 'gt' in conditions:
                range_filters.append(f'{field} > {conditions["gt"]}')
            if 'lt' in conditions:
                range_filters.append(f'{field} < {conditions["lt"]}')
            return ' AND '.join(range_filters)

        return None

    def _convert_es_search_query(self, query: Dict) -> tuple[str, Optional[str]]:
        """
        Convert ES search query to Meilisearch (q, filter)

        Returns:
            (search_string, filter_string)
        """
        if not query or query == {"match_all": {}}:
            return "", None

        # Handle bool query with multi_match
        if 'bool' in query:
            bool_query = query['bool']

            if 'must' in bool_query:
                search_queries = []
                filters = []

                for must_clause in bool_query['must']:
                    # Multi-match for search
                    if 'multi_match' in must_clause:
                        q = must_clause['multi_match']['query']
                        search_queries.append(q)
                    # Other clauses become filters
                    else:
                        clause_filter = self._convert_es_query_to_filter(must_clause)
                        if clause_filter:
                            filters.append(f'({clause_filter})')

                q_str = ' '.join(search_queries) if search_queries else ""
                filter_str = ' AND '.join(filters) if filters else None

                return q_str, filter_str

        # Handle direct multi_match
        if 'multi_match' in query:
            return query['multi_match']['query'], None

        return "", None

    def _convert_es_sort(self, sort: List) -> List[str]:
        """Convert ES sort to Meilisearch sort"""
        ms_sort = []
        for sort_item in sort:
            if isinstance(sort_item, dict):
                for field, order_dict in sort_item.items():
                    if isinstance(order_dict, dict):
                        order = order_dict.get('order', 'asc')
                    else:
                        order = order_dict
                    ms_sort.append(f'{field}:{order}')
            else:
                ms_sort.append(f'{sort_item}:asc')
        return ms_sort

    def _handle_aggregations(self, idx, aggs: Dict, filter_str: Optional[str]) -> Dict:
        """
        Handle ES aggregations using Meilisearch facets

        Note: Limited support - only terms aggregations
        """
        aggregations = {}

        for agg_name, agg_def in aggs.items():
            if 'terms' in agg_def:
                field = agg_def['terms']['field']
                size = agg_def['terms'].get('size', 100)

                # Perform faceted search
                search_params = {
                    'facets': [field],
                    'limit': 0
                }

                if filter_str:
                    search_params['filter'] = filter_str

                result = idx.search('', search_params)

                # Convert to ES aggregation format
                # Handle both dict and object response
                if isinstance(result, dict):
                    facet_dist = result.get('facetDistribution', {}).get(field, {})
                else:
                    facet_dist = getattr(result, 'facet_distribution', {}).get(field, {})

                aggregations[agg_name] = {
                    'buckets': [
                        {'key': key, 'doc_count': count}
                        for key, count in sorted(
                            facet_dist.items(),
                            key=lambda x: x[1],
                            reverse=True
                        )[:size]
                    ]
                }

        return aggregations


class MeilisearchService:
    """Service for managing Meilisearch indices and search operations"""

    def __init__(self):
        """Initialize Meilisearch client"""
        self._client: Optional[meilisearch.Client] = None
        self._initialized = False
        self._initialization_status = "not_started"
        self._initialization_message = ""
        self._initialization_progress = 0

    @property
    def client(self) -> MeilisearchClientWrapper:
        """Get or create Meilisearch client (lazy initialization)"""
        if self._client is None:
            ms_client = meilisearch.Client(
                f"http://{settings.meilisearch_host}:{settings.meilisearch_port}",
                settings.meilisearch_master_key
            )
            self._client = MeilisearchClientWrapper(ms_client)
        return self._client

    @property
    def _ms_client(self) -> meilisearch.Client:
        """Get raw Meilisearch client"""
        return meilisearch.Client(
            f"http://{settings.meilisearch_host}:{settings.meilisearch_port}",
            settings.meilisearch_master_key
        )

    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status"""
        return {
            "status": self._initialization_status,
            "message": self._initialization_message,
            "progress": self._initialization_progress,
            "initialized": self._initialized
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check Meilisearch server health"""
        try:
            health = self._ms_client.health()
            # health() returns a dict like {'status': 'available'}
            server_status = health.get('status') if isinstance(health, dict) else getattr(health, 'status', None)

            if server_status == 'available':
                return {"status": "healthy", "server_status": server_status}
            else:
                return {"status": "unhealthy", "server_status": server_status}
        except Exception as e:
            logger.debug(f"Meilisearch health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def initialize_collections(self) -> Dict[str, bool]:
        """Initialize required indices if they don't exist"""
        self._initialization_status = "initializing"
        self._initialization_message = "Initializing Meilisearch indices..."
        self._initialization_progress = 10

        results = {}

        # Define indices with their settings
        indices_config = {
            'silver_records': {
                'primaryKey': 'id',
                'searchableAttributes': [
                    'email', 'username', 'phone',
                    'first_name', 'last_name', 'full_name',
                    'address', 'city', 'country',
                    'company', 'job_title',
                    'social_media', 'website',
                    'domain', 'notes'
                ],
                'filterableAttributes': [
                    'source_id', 'email', 'username', 'phone',
                    'first_name', 'last_name', 'full_name',
                    'gender', 'city', 'country', 'zip_code',
                    'company', 'breach_name', 'domain',
                    'breach_date', 'imported_at', 'master_id',
                    'birth_date'
                ],
                'sortableAttributes': [
                    'imported_at', 'breach_date', 'birth_date'
                ],
                'rankingRules': [
                    'words',
                    'typo',
                    'proximity',
                    'attribute',
                    'sort',
                    'exactness'
                ],
                'typoTolerance': {
                    'enabled': True,
                    'minWordSizeForTypos': {
                        'oneTypo': 4,
                        'twoTypos': 8
                    }
                }
            },
            'master_records': {
                'primaryKey': 'id',
                'searchableAttributes': [
                    'email', 'username', 'phone',
                    'first_name', 'last_name', 'full_name',
                    'address', 'city', 'country',
                    'company', 'job_title',
                    'social_media', 'website'
                ],
                'filterableAttributes': [
                    'status', 'confidence_score', 'email_verified', 'phone_verified',
                    'email', 'username', 'phone',
                    'first_name', 'last_name', 'full_name',
                    'gender', 'city', 'country', 'company', 'job_title',
                    'breach_names', 'source_count',
                    'created_at', 'updated_at', 'birth_date',
                    'first_seen', 'last_seen'
                ],
                'sortableAttributes': [
                    'confidence_score', 'source_count', 'created_at', 'updated_at',
                    'first_seen', 'last_seen', 'birth_date'
                ],
                'rankingRules': [
                    'words',
                    'typo',
                    'proximity',
                    'attribute',
                    'sort',
                    'exactness'
                ]
            },
            'conflicts': {
                'primaryKey': 'id',
                'searchableAttributes': [
                    'field_name', 'existing_value', 'new_value'
                ],
                'filterableAttributes': [
                    'master_id', 'field_name', 'status',
                    'created_at', 'resolved_at', 'silver_id'
                ],
                'sortableAttributes': [
                    'created_at', 'resolved_at'
                ]
            }
        }

        progress_step = 80 / len(indices_config)
        current_progress = 10

        for index_name, config in indices_config.items():
            self._initialization_message = f"Creating {index_name} index..."
            self._initialization_progress = int(current_progress)

            results[index_name] = await self._ensure_index(index_name, config)
            current_progress += progress_step

        self._initialization_status = "ready"
        self._initialization_message = "Meilisearch ready!"
        self._initialization_progress = 100
        self._initialized = True
        return results

    async def _ensure_index(self, index_name: str, config: Dict) -> bool:
        """Ensure an index exists, create if it doesn't"""
        try:
            ms = self._ms_client

            # Check if index exists
            try:
                idx = ms.index(index_name)
                idx.get_stats()  # Will throw if doesn't exist
                logger.info(f"Index '{index_name}' already exists")

                # Update settings
                primary_key = config.pop('primaryKey', None)
                idx.update_settings(config)
                logger.info(f"Updated settings for '{index_name}'")

            except Exception:
                # Index doesn't exist, create it
                primary_key = config.pop('primaryKey', None)
                task = ms.create_index(index_name, {'primaryKey': primary_key})
                ms.wait_for_task(task.task_uid, timeout_in_ms=30000)

                # Set settings
                idx = ms.index(index_name)
                idx.update_settings(config)

                logger.info(f"Index '{index_name}' created successfully")

            return True

        except Exception as e:
            logger.error(f"Error creating index '{index_name}': {e}")
            return False

    async def get_collection_stats(self, collection_name: str = 'silver_records') -> Optional[Dict[str, Any]]:
        """Get statistics for an index"""
        try:
            idx = self._ms_client.index(collection_name)
            stats = idx.get_stats()

            return {
                'name': collection_name,
                'num_documents': stats.number_of_documents,
                'created_at': None,
                'num_memory_shards': 1  # Meilisearch doesn't use shards like ES
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
        Search in Meilisearch index

        Args:
            query: Search query string
            search_fields: Fields to search in (used for attribute ranking)
            filter_by: Filter expression (Typesense format: "field:value && field2:value2")
            per_page: Results per page
            page: Page number
            collection_name: Index to search in
            typo_tolerance: Enable typo tolerance
            prefix: Enable prefix search

        Returns:
            Search results with hits and facets
        """
        try:
            idx = self._ms_client.index(collection_name)

            offset = (page - 1) * per_page

            # Build search parameters
            search_params = {
                'limit': per_page,
                'offset': offset,
                'attributesToSearchOn': search_fields
            }

            # Convert filter_by (Typesense format) to Meilisearch filter
            if filter_by:
                ms_filter = self._convert_typesense_filter(filter_by)
                if ms_filter:
                    search_params['filter'] = ms_filter

            # Execute search
            start_time = time.time()
            result = idx.search(query if query != '*' else '', search_params)
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Handle both dict and object response from Meilisearch client
            if isinstance(result, dict):
                result_hits = result.get('hits', [])
                result_total = result.get('estimatedTotalHits', 0)
                result_time = result.get('processingTimeMs', elapsed_ms)
            else:
                result_hits = getattr(result, 'hits', [])
                result_total = getattr(result, 'estimated_total_hits', 0)
                result_time = getattr(result, 'processing_time_ms', elapsed_ms)

            # Format results
            hits = [
                {
                    "document": hit,
                    "highlights": None,
                    "text_match": 1.0
                }
                for hit in result_hits
            ]

            return {
                'hits': hits,
                'found': result_total,
                'out_of': result_total,
                'page': page,
                'search_time_ms': result_time,
                'facet_counts': []
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'hits': [],
                'found': 0,
                'error': str(e)
            }

    def _convert_typesense_filter(self, filter_by: str) -> str:
        """
        Convert Typesense filter format to Meilisearch filter format

        Typesense: "field:value && field2:value2"
        Meilisearch: "field = value AND field2 = value2"
        """
        parts = filter_by.split(' && ')
        ms_filters = []

        for part in parts:
            if ':' in part:
                field, value = part.split(':', 1)
                field = field.strip()
                value = value.strip()

                # Build Meilisearch filter with partial matching
                # Use OR for exact, starts_with, and contains
                sub_filters = []

                # Exact match
                if value.replace('"', '').replace("'", ""):
                    clean_value = value.replace('"', '').replace("'", "")
                    sub_filters.append(f'{field} = "{clean_value}"')

                # If more sophisticated matching is needed, Meilisearch handles it via search
                # For now, use simple equality

                if sub_filters:
                    if len(sub_filters) == 1:
                        ms_filters.append(sub_filters[0])
                    else:
                        ms_filters.append(f'({" OR ".join(sub_filters)})')

        return ' AND '.join(ms_filters) if ms_filters else ""

    async def multi_search(self, searches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple searches in a single request
        """
        try:
            # Meilisearch supports multi-search via POST /multi-search
            ms = self._ms_client

            # Format searches for Meilisearch
            ms_searches = []
            for search in searches:
                collection = search.get('collection', 'silver_records')
                query = search.get('query', '')
                query_by = search.get('query_by', 'email')

                ms_searches.append({
                    'indexUid': collection,
                    'q': query,
                    'attributesToSearchOn': query_by.split(',') if isinstance(query_by, str) else query_by,
                    'limit': search.get('per_page', 20)
                })

            # Execute multi-search
            results = ms.multi_search(ms_searches)

            return [r.get('hits', []) for r in results.get('results', [])]

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
        Import documents in batch

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
            idx = self._ms_client.index(collection_name)

            # Ensure all documents have an 'id' field
            for doc in documents:
                if 'id' not in doc and 'source_id' in doc:
                    doc['id'] = doc['source_id']
                elif 'id' not in doc:
                    # Generate ID if missing
                    import uuid
                    doc['id'] = str(uuid.uuid4())

            # Add/update documents
            task = idx.add_documents(documents)

            # Async mode: don't wait for indexing (much faster)
            if settings.meilisearch_async_mode:
                # Return immediately, indexing happens in background
                return {
                    'success': len(documents),
                    'failed': 0,
                    'errors': [],
                    'task_uid': task.task_uid  # Can be checked later if needed
                }

            # Sync mode: wait for task completion (slower but safer)
            self._ms_client.wait_for_task(task.task_uid, timeout_in_ms=settings.meilisearch_timeout * 1000)

            # Get task result
            task_info = self._ms_client.get_task(task.task_uid)

            if task_info.status == 'succeeded':
                return {
                    'success': len(documents),
                    'failed': 0,
                    'errors': []
                }
            else:
                error_msg = task_info.error if hasattr(task_info, 'error') else 'Unknown error'
                return {
                    'success': 0,
                    'failed': len(documents),
                    'errors': [error_msg]
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
            task = self._ms_client.delete_index(collection_name)
            self._ms_client.wait_for_task(task.task_uid, timeout_in_ms=30000)
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
        Get facet counts using Meilisearch faceted search

        Args:
            collection_name: Index to query
            facet_fields: Fields to get facets for

        Returns:
            Dictionary of facet counts by field
        """
        if facet_fields is None:
            facet_fields = ['breach_name', 'domain', 'breach_date']

        try:
            idx = self._ms_client.index(collection_name)

            # Perform faceted search
            result = idx.search('', {
                'facets': facet_fields,
                'limit': 0
            })

            # Handle both dict and object response
            if isinstance(result, dict):
                facet_dist = result.get('facetDistribution', {})
            else:
                facet_dist = getattr(result, 'facet_distribution', {})

            facets = {}
            for field in facet_fields:
                if field in facet_dist:
                    facets[field] = [
                        {"value": key, "count": count}
                        for key, count in sorted(
                            facet_dist[field].items(),
                            key=lambda x: x[1],
                            reverse=True
                        )[:100]
                    ]

            return facets

        except Exception as e:
            logger.error(f"Error getting facets: {e}")
            return {}


# Singleton instance
meilisearch_service = MeilisearchService()
