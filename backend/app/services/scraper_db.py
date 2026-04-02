"""SQLite database for scrapers, executions, and findings"""
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path("/home/quantic/NoctIS/data/scrapers.db")


class ScraperDatabase:
    """SQLite database for scrapers"""

    def __init__(self):
        """Initialize database"""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scrapers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    code TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'python',
                    cron_expression TEXT,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    keywords TEXT,  -- JSON array
                    auto_import INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_run_at INTEGER,
                    last_run_status TEXT,
                    next_run_at INTEGER
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    scraper_id TEXT NOT NULL,
                    status TEXT NOT NULL,  -- running, success, error
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER,
                    duration_seconds REAL,
                    stdout TEXT,
                    stderr TEXT,
                    findings_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    scraper_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    data TEXT NOT NULL,  -- JSON
                    matched_keywords TEXT,  -- JSON array
                    created_at INTEGER NOT NULL,
                    imported_to_typesense INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_scrapers_enabled ON scrapers(enabled);
                CREATE INDEX IF NOT EXISTS idx_executions_scraper ON executions(scraper_id);
                CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
                CREATE INDEX IF NOT EXISTS idx_findings_scraper ON findings(scraper_id);
                CREATE INDEX IF NOT EXISTS idx_findings_execution ON findings(execution_id);
            """)

    # SCRAPERS CRUD
    def create_scraper(self, name: str, code: str, **kwargs) -> str:
        """Create a new scraper"""
        scraper_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())

        keywords = json.dumps(kwargs.get('keywords', []))

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO scrapers (
                    id, name, description, code, language, cron_expression,
                    enabled, keywords, auto_import, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scraper_id, name, kwargs.get('description'), code,
                kwargs.get('language', 'python'), kwargs.get('cron_expression'),
                int(kwargs.get('enabled', False)), keywords,
                int(kwargs.get('auto_import', False)), now, now
            ))

        return scraper_id

    def get_scraper(self, scraper_id: str) -> Optional[Dict[str, Any]]:
        """Get scraper by ID"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM scrapers WHERE id = ?", (scraper_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_scrapers(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all scrapers"""
        with self.get_connection() as conn:
            query = "SELECT * FROM scrapers"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY created_at DESC"

            rows = conn.execute(query).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_scraper(self, scraper_id: str, **updates) -> bool:
        """Update scraper"""
        if 'keywords' in updates:
            updates['keywords'] = json.dumps(updates['keywords'])

        updates['updated_at'] = int(datetime.now().timestamp())

        # Convert bool to int for SQLite
        if 'enabled' in updates:
            updates['enabled'] = int(updates['enabled'])
        if 'auto_import' in updates:
            updates['auto_import'] = int(updates['auto_import'])

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [scraper_id]

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE scrapers SET {set_clause} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0

    def delete_scraper(self, scraper_id: str) -> bool:
        """Delete scraper"""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM scrapers WHERE id = ?", (scraper_id,))
            return cursor.rowcount > 0

    # EXECUTIONS
    def create_execution(self, scraper_id: str) -> str:
        """Create execution"""
        execution_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO executions (id, scraper_id, status, started_at, stdout, stderr)
                VALUES (?, ?, 'running', ?, '', '')
            """, (execution_id, scraper_id, now))

        return execution_id

    def update_execution(self, execution_id: str, **updates) -> bool:
        """Update execution"""
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [execution_id]

        with self.get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE executions SET {set_clause} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_executions(self, scraper_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List executions"""
        with self.get_connection() as conn:
            if scraper_id:
                rows = conn.execute("""
                    SELECT * FROM executions
                    WHERE scraper_id = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (scraper_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM executions
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()

            return [self._row_to_dict(row) for row in rows]

    # FINDINGS
    def create_finding(self, scraper_id: str, execution_id: str, data: dict, matched_keywords: List[str] = None) -> str:
        """Create finding"""
        finding_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp())

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO findings (id, scraper_id, execution_id, data, matched_keywords, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                finding_id, scraper_id, execution_id,
                json.dumps(data),
                json.dumps(matched_keywords or []),
                now
            ))

        return finding_id

    def list_findings(self, scraper_id: Optional[str] = None, execution_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List findings"""
        with self.get_connection() as conn:
            query = "SELECT * FROM findings WHERE 1=1"
            params = []

            if scraper_id:
                query += " AND scraper_id = ?"
                params.append(scraper_id)
            if execution_id:
                query += " AND execution_id = ?"
                params.append(execution_id)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert SQLite Row to dict"""
        d = dict(row)

        # Parse JSON fields
        if 'keywords' in d and d['keywords']:
            d['keywords'] = json.loads(d['keywords'])
        if 'matched_keywords' in d and d['matched_keywords']:
            d['matched_keywords'] = json.loads(d['matched_keywords'])
        if 'data' in d and d['data']:
            d['data'] = json.loads(d['data'])

        # Convert SQLite int to bool
        if 'enabled' in d:
            d['enabled'] = bool(d['enabled'])
        if 'auto_import' in d:
            d['auto_import'] = bool(d['auto_import'])
        if 'imported_to_typesense' in d:
            d['imported_to_typesense'] = bool(d['imported_to_typesense'])

        return d


# Singleton instance
scraper_db = ScraperDatabase()
