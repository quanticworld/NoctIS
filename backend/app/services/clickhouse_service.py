"""ClickHouse service for ultra-fast data ingestion and search"""
import clickhouse_connect
from clickhouse_driver import Client as ClickHouseDriverClient
from typing import Optional, Dict, List, Any
import logging
from app.config import settings
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def _retry_connect(func, max_retries=5, base_delay=1.0):
    """Retry helper for ClickHouse connection with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to ClickHouse after {max_retries} attempts: {e}")
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"ClickHouse connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)


class ClickHouseClientWrapper:
    """
    Wrapper around ClickHouse client to provide Elasticsearch/Meilisearch-like API
    This ensures compatibility with existing code (mdm_service, routers)
    """

    def __init__(self, client: clickhouse_connect.driver.Client, driver_client: ClickHouseDriverClient):
        self._ch_client = client  # HTTP client (clickhouse-connect)
        self._ch_driver = driver_client  # Native client (clickhouse-driver) for bulk inserts
        self._database = settings.clickhouse_database

    def count(self, index: str, query: Optional[Dict] = None) -> Dict[str, int]:
        """
        Count documents in a table

        Args:
            index: Table name
            query: Optional query filter (ES format, will be converted)

        Returns:
            {'count': total_documents}
        """
        try:
            where_clause = self._convert_es_query_to_where(query) if query else ""
            where_sql = f"WHERE {where_clause}" if where_clause else ""

            sql = f"SELECT count() AS count FROM {self._database}.{index} {where_sql}"
            result = self._ch_client.query(sql)

            return {'count': result.result_rows[0][0] if result.result_rows else 0}

        except Exception as e:
            logger.error(f"Count error: {e}")
            return {'count': 0}

    def delete_by_query(self, index: str, query: Dict, conflicts: str = 'abort') -> Dict[str, int]:
        """
        Delete documents matching a query

        Args:
            index: Table name
            query: ES query (will be converted to ClickHouse WHERE)
            conflicts: How to handle conflicts (ignored in ClickHouse)

        Returns:
            {'deleted': number_of_deleted_documents}
        """
        try:
            where_clause = self._convert_es_query_to_where(query)
            if not where_clause:
                # Delete all (dangerous!)
                logger.warning(f"DELETE ALL requested for {index}")
                where_clause = "1=1"

            # Count before delete
            count_sql = f"SELECT count() FROM {self._database}.{index} WHERE {where_clause}"
            count_before = self._ch_client.command(count_sql)

            # ClickHouse uses ALTER TABLE ... DELETE for mutations
            sql = f"ALTER TABLE {self._database}.{index} DELETE WHERE {where_clause}"
            self._ch_client.command(sql)

            logger.info(f"Delete mutation started for {index} WHERE {where_clause} (estimated: {count_before} rows)")

            # Wait for mutations to complete (synchronous mode)
            import time
            max_wait = 30  # 30 seconds max
            waited = 0
            while waited < max_wait:
                # Check if mutations are still running
                mutations_sql = f"""
                    SELECT count() FROM system.mutations
                    WHERE database = '{self._database}'
                    AND table = '{index}'
                    AND is_done = 0
                """
                running_mutations = self._ch_client.command(mutations_sql)
                if running_mutations == 0:
                    logger.info(f"Delete mutation completed for {index}")
                    break
                time.sleep(0.5)
                waited += 0.5

            if waited >= max_wait:
                logger.warning(f"Delete mutation timeout for {index} after {max_wait}s")

            return {'deleted': count_before}

        except Exception as e:
            logger.error(f"Delete by query error: {e}")
            return {'deleted': 0}

    def update(self, index: str, id: str, doc: Dict, **kwargs) -> Dict[str, str]:
        """
        Update a document (partial update)

        Note: ClickHouse doesn't support direct updates well (it's append-only).
        We'll use ALTER TABLE ... UPDATE (mutation) which is async.

        Args:
            index: Table name
            id: Document ID
            doc: Fields to update

        Returns:
            {'result': 'updated'}
        """
        try:
            # Build SET clause from doc
            set_clauses = []
            for key, value in doc.items():
                if isinstance(value, str):
                    set_clauses.append(f"{key} = '{value}'")
                elif value is None:
                    set_clauses.append(f"{key} = NULL")
                else:
                    set_clauses.append(f"{key} = {value}")

            set_sql = ", ".join(set_clauses)
            sql = f"ALTER TABLE {self._database}.{index} UPDATE {set_sql} WHERE id = '{id}'"

            self._ch_client.command(sql)
            logger.info(f"Update mutation started for {index} id={id}")

            return {'result': 'updated'}

        except Exception as e:
            logger.error(f"Update error for {id}: {e}")
            return {'result': 'error'}

    def delete(self, index: str, id: str) -> Dict[str, str]:
        """
        Delete a document by ID

        Args:
            index: Table name
            id: Document ID

        Returns:
            {'result': 'deleted'}
        """
        try:
            sql = f"ALTER TABLE {self._database}.{index} DELETE WHERE id = '{id}'"
            self._ch_client.command(sql)
            return {'result': 'deleted'}

        except Exception as e:
            logger.error(f"Delete error for {id}: {e}")
            return {'result': 'error'}

    def get(self, index: str, id: str) -> Dict[str, Any]:
        """
        Get a document by ID

        Args:
            index: Table name
            id: Document ID

        Returns:
            {'_source': document_dict, '_id': id}
        """
        try:
            sql = f"SELECT * FROM {self._database}.{index} WHERE id = '{id}' LIMIT 1"
            result = self._ch_client.query(sql)

            if not result.result_rows:
                raise Exception(f"Document {id} not found")

            # Convert row to dict
            columns = result.column_names
            row = result.result_rows[0]
            doc = dict(zip(columns, row))

            return {'_source': doc, '_id': id}

        except Exception as e:
            logger.error(f"Get error for {id}: {e}")
            raise

    def search(self, index: str, query: Optional[Dict] = None, body: Optional[Dict] = None,
               from_: int = 0, size: int = 20, sort: Optional[List] = None,
               aggs: Optional[Dict] = None, **kwargs) -> Dict:
        """
        Search documents (ES-compatible API)

        Args:
            index: Table name
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
            # Extract query from body if provided
            if body:
                query = body.get('query')
                from_ = body.get('from', from_)
                size = body.get('size', size)
                sort = body.get('sort', sort)
                aggs = body.get('aggs', aggs)

            # Build SQL query
            where_clause = self._convert_es_query_to_where(query) if query else ""
            where_sql = f"WHERE {where_clause}" if where_clause else ""

            order_by_clause = self._convert_es_sort(sort) if sort else ""
            order_by_sql = f"ORDER BY {order_by_clause}" if order_by_clause else ""

            sql = f"""
                SELECT *
                FROM {self._database}.{index}
                {where_sql}
                {order_by_sql}
                LIMIT {size} OFFSET {from_}
            """

            start_time = time.time()
            result = self._ch_client.query(sql)
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Convert rows to dicts
            columns = result.column_names
            hits = []
            for row in result.result_rows:
                doc = dict(zip(columns, row))
                hits.append({
                    '_source': doc,
                    '_id': doc.get('id'),
                    '_score': 1.0
                })

            # Get total count
            count_sql = f"SELECT count() FROM {self._database}.{index} {where_sql}"
            count_result = self._ch_client.query(count_sql)
            total = count_result.result_rows[0][0] if count_result.result_rows else 0

            # ES-format response
            es_result = {
                'hits': {
                    'total': {'value': total},
                    'hits': hits
                },
                'took': elapsed_ms
            }

            # Handle aggregations if requested
            if aggs:
                es_result['aggregations'] = self._handle_aggregations(index, aggs, where_sql)

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

    def _convert_es_query_to_where(self, query: Dict) -> str:
        """Convert Elasticsearch query to ClickHouse WHERE clause"""
        if not query or query == {"match_all": {}}:
            return ""

        # Handle term query
        if 'term' in query:
            field, value_dict = next(iter(query['term'].items()))
            if isinstance(value_dict, dict):
                value = value_dict.get('value', value_dict)
            else:
                value = value_dict

            if isinstance(value, str):
                return f"{field} = '{value}'"
            else:
                return f"{field} = {value}"

        # Handle exists query
        if 'exists' in query:
            field = query['exists']['field']
            return f"{field} IS NOT NULL"

        # Handle bool query
        if 'bool' in query:
            bool_query = query['bool']
            conditions = []

            # Must clauses (AND)
            if 'must' in bool_query:
                for must_clause in bool_query['must']:
                    clause = self._convert_es_query_to_where(must_clause)
                    if clause:
                        conditions.append(f'({clause})')

            if conditions:
                return ' AND '.join(conditions)

        # Handle range query
        if 'range' in query:
            field, conditions_dict = next(iter(query['range'].items()))
            range_conditions = []
            if 'gte' in conditions_dict:
                range_conditions.append(f'{field} >= {conditions_dict["gte"]}')
            if 'lte' in conditions_dict:
                range_conditions.append(f'{field} <= {conditions_dict["lte"]}')
            if 'gt' in conditions_dict:
                range_conditions.append(f'{field} > {conditions_dict["gt"]}')
            if 'lt' in conditions_dict:
                range_conditions.append(f'{field} < {conditions_dict["lt"]}')
            return ' AND '.join(range_conditions)

        # Handle multi_match (fuzzy search with ngramDistance)
        if 'multi_match' in query:
            search_query = query['multi_match']['query']
            fields = query['multi_match'].get('fields', [])

            # Build fuzzy match conditions for each field
            fuzzy_conditions = []
            for field in fields:
                # Use ngramDistance for fuzzy matching (threshold: 0.3)
                fuzzy_conditions.append(f"ngramDistance(lowerUTF8({field}), lowerUTF8('{search_query}')) < 0.3")

            if fuzzy_conditions:
                return '(' + ' OR '.join(fuzzy_conditions) + ')'

        return ""

    def _convert_es_sort(self, sort: List) -> str:
        """Convert ES sort to ClickHouse ORDER BY"""
        if not sort:
            return ""

        order_clauses = []
        for sort_item in sort:
            if isinstance(sort_item, dict):
                for field, order_dict in sort_item.items():
                    if isinstance(order_dict, dict):
                        order = order_dict.get('order', 'asc').upper()
                    else:
                        order = order_dict.upper()
                    order_clauses.append(f'{field} {order}')
            else:
                order_clauses.append(f'{sort_item} ASC')

        return ', '.join(order_clauses)

    def _handle_aggregations(self, index: str, aggs: Dict, where_sql: str) -> Dict:
        """
        Handle ES aggregations using ClickHouse GROUP BY

        Note: Limited support - only terms aggregations
        """
        aggregations = {}

        for agg_name, agg_def in aggs.items():
            if 'terms' in agg_def:
                field = agg_def['terms']['field']
                size = agg_def['terms'].get('size', 100)

                # Execute aggregation query
                sql = f"""
                    SELECT {field}, count() AS count
                    FROM {self._database}.{index}
                    {where_sql}
                    GROUP BY {field}
                    ORDER BY count DESC
                    LIMIT {size}
                """

                result = self._ch_client.query(sql)

                # Convert to ES aggregation format
                buckets = []
                for row in result.result_rows:
                    buckets.append({
                        'key': row[0],
                        'doc_count': row[1]
                    })

                aggregations[agg_name] = {'buckets': buckets}

        return aggregations


class ClickHouseService:
    """Service for managing ClickHouse tables and search operations"""

    def __init__(self):
        """Initialize ClickHouse clients"""
        self._client: Optional[ClickHouseClientWrapper] = None
        self._initialized = False
        self._initialization_status = "not_started"
        self._initialization_message = ""
        self._initialization_progress = 0

    @property
    def client(self) -> ClickHouseClientWrapper:
        """Get or create ClickHouse client (lazy initialization with retry logic)"""
        if self._client is None:
            # Create HTTP client (for queries) with retry logic
            ch_client = _retry_connect(lambda: clickhouse_connect.get_client(
                host=settings.clickhouse_host,
                port=settings.clickhouse_http_port,
                username=settings.clickhouse_user,
                password=settings.clickhouse_password,
                database=settings.clickhouse_database
            ))

            # Create native client (for bulk inserts) with retry logic
            ch_driver = _retry_connect(lambda: ClickHouseDriverClient(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password,
                database=settings.clickhouse_database,
                settings={
                    'use_numpy': False,
                    'max_insert_block_size': settings.clickhouse_batch_size
                }
            ))

            self._client = ClickHouseClientWrapper(ch_client, ch_driver)
            logger.info("Successfully connected to ClickHouse")

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
        """Check ClickHouse server health"""
        try:
            result = self.client._ch_client.ping()
            if result:
                return {"status": "healthy", "server_status": "available"}
            else:
                return {"status": "unhealthy", "server_status": "unavailable"}
        except Exception as e:
            logger.debug(f"ClickHouse health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def initialize_collections(self) -> Dict[str, bool]:
        """
        Initialize required tables if they don't exist

        Note: Tables are created via SQL scripts on container startup.
        This method just verifies they exist.
        """
        self._initialization_status = "initializing"
        self._initialization_message = "Verifying ClickHouse tables..."
        self._initialization_progress = 10

        results = {}
        tables = ['silver_records', 'master_records', 'conflicts']

        for idx, table in enumerate(tables):
            try:
                # Check if table exists
                sql = f"EXISTS TABLE {settings.clickhouse_database}.{table}"
                result = self.client._ch_client.query(sql)
                exists = result.result_rows[0][0] if result.result_rows else 0

                if exists:
                    logger.info(f"✅ Table '{table}' exists")
                    results[table] = True
                else:
                    logger.warning(f"⚠️  Table '{table}' not found")
                    results[table] = False

                self._initialization_progress = 10 + int((idx + 1) / len(tables) * 80)

            except Exception as e:
                logger.error(f"Error checking table '{table}': {e}")
                results[table] = False

        self._initialization_status = "ready"
        self._initialization_message = "ClickHouse ready!"
        self._initialization_progress = 100
        self._initialized = True

        return results

    async def get_collection_stats(self, collection_name: str = 'silver_records') -> Optional[Dict[str, Any]]:
        """Get statistics for a table"""
        try:
            # Get document count
            count_result = self.client._ch_client.query(
                f"SELECT count() FROM {settings.clickhouse_database}.{collection_name}"
            )
            num_docs = count_result.result_rows[0][0] if count_result.result_rows else 0

            # Get table size
            size_result = self.client._ch_client.query(f"""
                SELECT
                    formatReadableSize(sum(bytes)) AS size,
                    sum(rows) AS rows
                FROM system.parts
                WHERE database = '{settings.clickhouse_database}'
                  AND table = '{collection_name}'
                  AND active
            """)

            size_info = size_result.result_rows[0] if size_result.result_rows else ("0 B", 0)

            return {
                'name': collection_name,
                'num_documents': num_docs,
                'size': size_info[0],
                'rows': size_info[1],
                'created_at': None,
                'num_memory_shards': 1
            }

        except Exception as e:
            logger.error(f"Error getting table stats: {e}")
            return None

    async def import_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str = 'silver_records',
        action: str = 'insert'
    ) -> Dict[str, Any]:
        """
        Import documents in bulk (ultra-fast native protocol)

        Args:
            documents: List of documents to import
            collection_name: Target table
            action: Import action (insert, replace)

        Returns:
            Import results with success/failure counts
        """
        if not documents:
            return {'success': 0, 'failed': 0, 'errors': []}

        try:
            # Prepare data for bulk insert
            columns = list(documents[0].keys())
            rows = []

            for doc in documents:
                row = []
                for col in columns:
                    value = doc.get(col)
                    # Convert datetime objects to strings (handle both aware and naive)
                    if isinstance(value, datetime):
                        # Remove timezone info if present (ClickHouse DateTime doesn't support tz)
                        if value.tzinfo is not None:
                            value = value.replace(tzinfo=None)
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row.append(value)
                rows.append(row)

            # Bulk insert using native protocol (much faster than HTTP)
            table_name = f"{settings.clickhouse_database}.{collection_name}"
            self.client._ch_driver.execute(
                f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES",
                rows
            )

            logger.info(f"✅ Bulk inserted {len(documents)} documents into {collection_name}")

            return {
                'success': len(documents),
                'failed': 0,
                'errors': []
            }

        except Exception as e:
            logger.error(f"Import error: {e}")
            return {
                'success': 0,
                'failed': len(documents),
                'error': str(e)
            }

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
        Search in ClickHouse table with fuzzy matching

        Args:
            query: Search query string
            search_fields: Fields to search in
            filter_by: Filter expression (Typesense format: "field:value && field2:value2")
            per_page: Results per page
            page: Page number
            collection_name: Table to search in
            typo_tolerance: Enable fuzzy matching (ngramDistance)
            prefix: Enable prefix search

        Returns:
            Search results with hits and facets
        """
        try:
            offset = (page - 1) * per_page

            # Build fuzzy search conditions
            search_conditions = []
            if query and query != '*':
                # Split query into words for better multi-word matching
                query_words = [w.strip() for w in query.split() if w.strip()]

                for field in search_fields:
                    if typo_tolerance:
                        # For each word, create fuzzy conditions
                        word_conditions = []
                        for word in query_words:
                            # Escape single quotes in word
                            escaped_word = word.replace("'", "\\'")
                            # Use ngramDistance for fuzzy matching (0.4 = 40% tolerance)
                            word_conditions.append(
                                f"ngramDistance(lowerUTF8({field}), lowerUTF8('{escaped_word}')) < 0.4"
                            )
                        # Field matches if ANY word matches (OR)
                        if word_conditions:
                            search_conditions.append('(' + ' OR '.join(word_conditions) + ')')
                    else:
                        # Exact match (any word must match exactly)
                        word_conditions = []
                        for word in query_words:
                            escaped_word = word.replace("'", "\\'")
                            word_conditions.append(f"lowerUTF8({field}) = lowerUTF8('{escaped_word}')")
                        if word_conditions:
                            search_conditions.append('(' + ' OR '.join(word_conditions) + ')')

            # Build filter conditions
            filter_conditions = []
            if filter_by:
                filter_conditions = self._parse_typesense_filter(filter_by)

            # Combine all conditions
            all_conditions = []
            if search_conditions:
                all_conditions.append('(' + ' OR '.join(search_conditions) + ')')
            if filter_conditions:
                all_conditions.extend(filter_conditions)

            where_clause = ' AND '.join(all_conditions) if all_conditions else "1=1"
            where_sql = f"WHERE {where_clause}"

            # Execute search
            start_time = time.time()
            sql = f"""
                SELECT *
                FROM {settings.clickhouse_database}.{collection_name}
                {where_sql}
                LIMIT {per_page} OFFSET {offset}
            """

            result = self.client._ch_client.query(sql)
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Get total count
            count_sql = f"SELECT count() FROM {settings.clickhouse_database}.{collection_name} {where_sql}"
            count_result = self.client._ch_client.query(count_sql)
            total = count_result.result_rows[0][0] if count_result.result_rows else 0

            # Format results
            columns = result.column_names
            hits = []
            for row in result.result_rows:
                doc = dict(zip(columns, row))
                hits.append({
                    "document": doc,
                    "highlights": None,
                    "text_match": 1.0
                })

            return {
                'hits': hits,
                'found': total,
                'out_of': total,
                'page': page,
                'search_time_ms': elapsed_ms,
                'facet_counts': []
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'hits': [],
                'found': 0,
                'error': str(e)
            }

    def _parse_typesense_filter(self, filter_by: str) -> List[str]:
        """
        Convert Typesense filter format to ClickHouse WHERE conditions

        Typesense: "field:value && field2:value2"
        ClickHouse: ["lowerUTF8(field) = lowerUTF8('value')", ...]

        Uses case-insensitive matching for better UX
        """
        parts = filter_by.split(' && ')
        conditions = []

        for part in parts:
            if ':' in part:
                field, value = part.split(':', 1)
                field = field.strip()
                value = value.strip().strip('"').strip("'")
                # Case-insensitive matching
                escaped_value = value.replace("'", "\\'")
                conditions.append(f"lowerUTF8({field}) = lowerUTF8('{escaped_value}')")

        return conditions


# Singleton instance
clickhouse_service = ClickHouseService()
