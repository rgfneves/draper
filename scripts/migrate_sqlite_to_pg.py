#!/usr/bin/env python3
"""
One-shot migration script: reads all data from an existing SQLite database
and inserts it into PostgreSQL (configured via DATABASE_URL).

Usage:
    python -m scripts.migrate_sqlite_to_pg [--sqlite-path draper.db]
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABLES_IN_ORDER = [
    "search_configs",
    "creators",
    "posts",
    "pipeline_runs",
    "score_history",
    "outreach",
]


def _migrate_table(sqlite_conn: sqlite3.Connection, pg_conn, table: str) -> int:
    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        logger.info("  %s: 0 rows (skipped)", table)
        return 0

    cols = [desc[0] for desc in sqlite_conn.execute(f"SELECT * FROM {table} LIMIT 1").description]
    # Exclude 'id' — let PostgreSQL SERIAL generate new ids
    non_id_cols = [c for c in cols if c != "id"]

    placeholders = ", ".join(["%s"] * len(non_id_cols))
    col_names = ", ".join(non_id_cols)
    insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

    cur = pg_conn.cursor()
    count = 0
    for row in rows:
        d = dict(zip(cols, row))
        values = []
        for c in non_id_cols:
            v = d[c]
            # SQLite stores booleans as 0/1 — convert for PG
            if isinstance(v, int) and c in ("active", "verified", "business_account", "is_private", "ai_filter_pass", "is_active", "is_lead"):
                v = bool(v)
            values.append(v)
        try:
            cur.execute(insert_sql, values)
            count += 1
        except psycopg2.IntegrityError:
            pg_conn.rollback()
            logger.warning("  %s: duplicate skipped for row %s", table, d.get("id"))
            continue

    pg_conn.commit()
    cur.close()

    # Reset the serial sequence to max(id)+1
    cur2 = pg_conn.cursor()
    cur2.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
    pg_conn.commit()
    cur2.close()

    logger.info("  %s: %d rows migrated", table, count)
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument("--sqlite-path", default="draper.db", help="Path to SQLite file")
    parser.add_argument("--pg-dsn", default=None, help="PostgreSQL DSN (default: DATABASE_URL env)")
    args = parser.parse_args(argv)

    from config.settings import DATABASE_URL
    pg_dsn = args.pg_dsn or DATABASE_URL

    logger.info("Source: %s", args.sqlite_path)
    logger.info("Target: %s", pg_dsn.split("@")[-1] if "@" in pg_dsn else pg_dsn)

    # Open SQLite
    sqlite_conn = sqlite3.connect(args.sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Open PostgreSQL and apply schema
    from db.connection import get_connection
    pg_wrapper = get_connection(pg_dsn)

    total = 0
    for table in TABLES_IN_ORDER:
        total += _migrate_table(sqlite_conn, pg_wrapper.raw, table)

    sqlite_conn.close()
    pg_wrapper.close()
    logger.info("Migration complete: %d total rows migrated.", total)


if __name__ == "__main__":
    main()
