from __future__ import annotations

import logging
import os
from typing import Any, Sequence

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


# ---------------------------------------------------------------------------
# PgCursor — wraps psycopg2 cursor to return dict-like rows (row["col"])
# ---------------------------------------------------------------------------

class _DictRow(dict):
    """Dict subclass that also supports integer indexing like sqlite3.Row."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PgCursor:
    """Thin wrapper around psycopg2 RealDictCursor that returns _DictRow objects."""

    def __init__(self, pg_cursor):
        self._cur = pg_cursor

    # --- Delegate common attributes ---
    @property
    def lastrowid(self):
        return None  # Not used — we rely on RETURNING id

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def fetchone(self):
        row = self._cur.fetchone()
        return _DictRow(row) if row is not None else None

    def fetchall(self):
        return [_DictRow(r) for r in self._cur.fetchall()]

    def close(self):
        self._cur.close()

    def __iter__(self):
        return self

    def __next__(self):
        row = self._cur.fetchone()
        if row is None:
            raise StopIteration
        return _DictRow(row)


# ---------------------------------------------------------------------------
# PgConnection — provides conn.execute() / conn.commit() API like sqlite3
# ---------------------------------------------------------------------------

class PgConnection:
    """
    Wraps a psycopg2 connection to provide the same conn.execute(sql, params)
    interface used throughout the codebase (dashboard, pipeline, tests).
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> PgCursor:
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return PgCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self, **kwargs):
        return self._conn.cursor(**kwargs)

    @property
    def raw(self):
        """Access to the underlying psycopg2 connection."""
        return self._conn


# ---------------------------------------------------------------------------
# Schema & migrations
# ---------------------------------------------------------------------------

def _apply_schema(conn: PgConnection) -> None:
    with open(_SCHEMA_PATH, "r") as fh:
        sql = fh.read()
    # psycopg2 can run multiple statements in one execute()
    raw_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    raw_cur.execute(sql)
    raw_cur.close()
    conn.commit()
    logger.debug("Schema applied.")
    _apply_migrations(conn)


def _column_exists(conn: PgConnection, table: str, column: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    result = cur.fetchone()
    cur.close()
    return result is not None


def _apply_migrations(conn: PgConnection) -> None:
    """Adds columns introduced after initial schema without breaking existing DBs."""
    creator_migrations = [
        ("discovered_via_type",  "TEXT"),
        ("discovered_via_value", "TEXT"),
        ("is_private",           "BOOLEAN"),
        ("profile_pic_url",      "TEXT"),
        ("email",                "TEXT"),
        ("category",             "TEXT"),
        ("is_lead",              "BOOLEAN NOT NULL DEFAULT FALSE"),
    ]
    for col, definition in creator_migrations:
        if not _column_exists(conn, "creators", col):
            raw_cur = conn.cursor()
            raw_cur.execute(f"ALTER TABLE creators ADD COLUMN {col} {definition}")
            raw_cur.close()
            logger.info("Migration: added column creators.%s", col)

    if not _column_exists(conn, "posts", "post_url"):
        raw_cur = conn.cursor()
        raw_cur.execute("ALTER TABLE posts ADD COLUMN post_url TEXT")
        raw_cur.close()
        logger.info("Migration: added column posts.post_url")

    if not _column_exists(conn, "search_configs", "tags"):
        raw_cur = conn.cursor()
        raw_cur.execute("ALTER TABLE search_configs ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        raw_cur.close()
        logger.info("Migration: added column search_configs.tags")

    conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_connection(dsn: str | None = None) -> PgConnection:
    """Opens a PostgreSQL connection and ensures schema exists."""
    if dsn is None:
        from config.settings import DATABASE_URL
        dsn = DATABASE_URL

    pg_conn = psycopg2.connect(dsn)
    pg_conn.autocommit = False
    conn = PgConnection(pg_conn)

    _apply_schema(conn)
    from db.repository import seed_default_search_configs
    seed_default_search_configs(conn)
    logger.debug("Database connection opened.")
    return conn
