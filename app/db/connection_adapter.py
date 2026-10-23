"""
PostgreSQL DB-API Connection Adapter for NexusAI

Provides a thread-safe, pool-backed DB-API connection object that translates
parameter markers and executes directly against PostgreSQL.
Eliminates all SQLite file database access from application routes.
"""
import re
import logging
from typing import Any, List, Optional, Sequence, Tuple
from app.db.session import get_database_urls, get_sync_engine, get_psycopg_conninfo

logger = logging.getLogger(__name__)

_pool = None


def get_connection_pool():
    """Get or create singleton psycopg connection pool."""
    global _pool
    if _pool is None or getattr(_pool, "closed", False):
        import os
        from psycopg_pool import ConnectionPool

        conninfo = get_psycopg_conninfo()
        _pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=int(os.getenv("DB_POOL_SIZE", "20")),
            kwargs={"autocommit": False},
        )
    return _pool


def _adapt_sqlite_sql(sql: str) -> str:
    """
    Translate SQLite SQL dialects to standard PostgreSQL syntax.
    - Replaces '?' with '%s'
    - Replaces 'INSERT OR IGNORE INTO' with 'INSERT INTO ... ON CONFLICT DO NOTHING'
    """
    adapted = sql.strip()

    # Replace INSERT OR IGNORE INTO table (...) VALUES (...)
    # with INSERT INTO table (...) VALUES (...) ON CONFLICT DO NOTHING
    if re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", adapted, re.IGNORECASE):
        adapted = re.sub(
            r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
            "INSERT INTO",
            adapted,
            flags=re.IGNORECASE,
        )
        if not re.search(r"\bON\s+CONFLICT\b", adapted, re.IGNORECASE):
            adapted = f"{adapted} ON CONFLICT DO NOTHING"

    # Replace parameter placeholders '?' with '%s'
    # Avoid replacing ? inside string literals
    parts = []
    in_quote = False
    quote_char = None
    i = 0
    while i < len(adapted):
        ch = adapted[i]
        if ch in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif quote_char == ch:
                in_quote = False
                quote_char = None
            parts.append(ch)
        elif ch == "?" and not in_quote:
            parts.append("%s")
        else:
            parts.append(ch)
        i += 1

    return "".join(parts)


class PostgresCursorAdapter:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None):
        adapted_sql = _adapt_sqlite_sql(sql)
        try:
            if params is not None:
                # Convert list to tuple or None
                p = tuple(params) if isinstance(params, (list, tuple)) else params
                return self._cursor.execute(adapted_sql, p)
            return self._cursor.execute(adapted_sql)
        except Exception as e:
            logger.error(f"PostgreSQL query execution failed: {e} | SQL: {adapted_sql}")
            raise

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]):
        adapted_sql = _adapt_sqlite_sql(sql)
        return self._cursor.executemany(adapted_sql, seq_of_params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size: int = 1):
        return self._cursor.fetchmany(size)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Optional[int]:
        # In psycopg, lastrowid is not always populated unless RETURNING was used,
        # but for compatibility we return None or cursor info
        return getattr(self._cursor, "lastrowid", None)

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PostgresConnectionAdapter:
    def __init__(self):
        self._conn = None

    def _get_raw_conn(self):
        if self._conn is None or self._conn.closed:
            pool = get_connection_pool()
            self._conn = pool.getconn()
        return self._conn

    def cursor(self) -> PostgresCursorAdapter:
        raw_conn = self._get_raw_conn()
        return PostgresCursorAdapter(raw_conn.cursor())

    def commit(self):
        if self._conn and not self._conn.closed:
            self._conn.commit()

    def rollback(self):
        if self._conn and not self._conn.closed:
            self._conn.rollback()

    def close(self):
        if self._conn and not self._conn.closed:
            try:
                pool = get_connection_pool()
                pool.putconn(self._conn)
            except Exception:
                pass
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_db_connection() -> PostgresConnectionAdapter:
    """Return an active connection adapter to PostgreSQL."""
    return PostgresConnectionAdapter()

