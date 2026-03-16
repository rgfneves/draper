# Migration: SQLite → PostgreSQL (COMPLETED)

## Overview

This document details the migration from SQLite to PostgreSQL for the Draper project. The current codebase uses `sqlite3` (stdlib) with a thin custom abstraction (`db/connection.py`, `db/repository.py`). The migration replaces only the database layer — all business logic in `pipeline/`, `dashboard/`, and `config/` remains untouched.

---

## Scope of Changes

| File | Change |
|------|--------|
| `requirements.txt` | Add `psycopg2-binary` (or `psycopg[binary]`) |
| `.env.example` | Replace `DB_PATH` with `DATABASE_URL` |
| `config/settings.py` | Replace `DB_PATH` with `DATABASE_URL` |
| `db/connection.py` | Full rewrite: `sqlite3` → `psycopg2`, new schema/migration logic |
| `db/repository.py` | Paramstyle `?` → `%s`, `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL`, `lastrowid` → `RETURNING id`, `PRAGMA`-based migrations removed |
| `db/schema.sql` | SQLite DDL → PostgreSQL DDL |
| `tests/test_db.py` | Replace `:memory:` fixture with a real PG test DB or use `testing.postgresql` |
| `tests/test_runner.py` | Same fixture update |

**Not touched:** `pipeline/`, `dashboard/`, `config/seeds.py`, `config/filters.py`, `models.py`

---

## Step-by-Step Plan

### Step 1 — Add `psycopg2` dependency

**File:** `requirements.txt`

```diff
+ psycopg2-binary>=2.9
```

> Use `psycopg2-binary` for dev/heroku. For production containers with compiled drivers use `psycopg2>=2.9` instead.

---

### Step 2 — Update environment config

**File:** `.env.example`

```diff
- DB_PATH=draper.db
+ DATABASE_URL=postgresql://draper:draper@localhost:5432/draper
```

**File:** `config/settings.py`

```diff
- DB_PATH: str = os.getenv("DB_PATH", "draper.db")
+ DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://draper:draper@localhost:5432/draper")
```

---

### Step 3 — Rewrite `db/connection.py`

**Key differences from SQLite:**

| SQLite | PostgreSQL |
|--------|------------|
| `sqlite3.connect(path)` | `psycopg2.connect(dsn)` |
| `conn.row_factory = sqlite3.Row` | `cursor_factory = psycopg2.extras.RealDictCursor` |
| `PRAGMA foreign_keys = ON` | Not needed (FK enforced by default) |
| `conn.executescript(sql)` | `conn.cursor().execute(sql)` (no multi-statement support; split by `;`) |
| `_apply_migrations` via `PRAGMA table_info` | Query `information_schema.columns` |
| `get_connection(":memory:")` in tests | Use a real test DB or `testing.postgresql` |

**New `connection.py`:**

```python
from __future__ import annotations

import logging
import os

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def _apply_schema(conn) -> None:
    with open(_SCHEMA_PATH, "r") as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.debug("Schema applied.")
    _apply_migrations(conn)


def _column_exists(conn, table: str, column: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            """,
            (table, column),
        )
        return cur.fetchone() is not None


def _apply_migrations(conn) -> None:
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
            with conn.cursor() as cur:
                cur.execute(f"ALTER TABLE creators ADD COLUMN {col} {definition}")
            logger.info("Migration: added column creators.%s", col)

    if not _column_exists(conn, "posts", "post_url"):
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE posts ADD COLUMN post_url TEXT")
        logger.info("Migration: added column posts.post_url")

    if not _column_exists(conn, "search_configs", "tags"):
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE search_configs ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        logger.info("Migration: added column search_configs.tags")

    conn.commit()


def get_connection(dsn: str | None = None):
    """Opens a PostgreSQL connection and ensures schema exists."""
    if dsn is None:
        from config.settings import DATABASE_URL
        dsn = DATABASE_URL

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    _apply_schema(conn)

    from db.repository import seed_default_search_configs
    seed_default_search_configs(conn)
    logger.debug("Database connection opened.")
    return conn
```

---

### Step 4 — Rewrite `db/schema.sql`

**Key differences:**

| SQLite | PostgreSQL |
|--------|------------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `BOOLEAN` | `BOOLEAN` (native, no change) |
| `REAL` | `REAL` or `DOUBLE PRECISION` |
| `DATETIME DEFAULT CURRENT_TIMESTAMP` | `TIMESTAMPTZ DEFAULT NOW()` |
| `PRAGMA foreign_keys = ON` | Remove (PG default) |
| `CREATE TABLE IF NOT EXISTS` | Keep (PG supports it) |

**New `schema.sql`:**

```sql
CREATE TABLE IF NOT EXISTS search_configs (
    id          SERIAL PRIMARY KEY,
    platform    TEXT NOT NULL,
    search_type TEXT NOT NULL,
    value       TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    source      TEXT NOT NULL DEFAULT 'manual',
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, search_type, value)
);

CREATE TABLE IF NOT EXISTS creators (
    id                   SERIAL PRIMARY KEY,
    platform             TEXT NOT NULL,
    username             TEXT NOT NULL,
    display_name         TEXT,
    bio                  TEXT,
    link_in_bio          TEXT,
    followers            INTEGER,
    following            INTEGER,
    total_posts          INTEGER,
    verified             BOOLEAN,
    business_account     BOOLEAN,
    is_private           BOOLEAN,
    profile_pic_url      TEXT,
    email                TEXT,
    category             TEXT,
    location             TEXT,
    niche                TEXT,
    ai_filter_pass       BOOLEAN,
    ai_filter_reason     TEXT,
    epic_trip_score      REAL,
    score_engagement     REAL,
    score_niche          REAL,
    score_followers      REAL,
    score_growth         REAL,
    score_activity       REAL,
    avg_engagement       REAL,
    posts_last_30_days   INTEGER,
    posting_frequency    REAL,
    is_active            BOOLEAN,
    discovered_via_type  TEXT,
    discovered_via_value TEXT,
    status               TEXT DEFAULT 'discovered',
    is_lead              BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at        TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(platform, username)
);

CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    creator_id      INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    post_id         TEXT NOT NULL,
    post_type       TEXT,
    post_url        TEXT,
    published_at    TIMESTAMPTZ,
    likes           INTEGER,
    comments        INTEGER,
    shares          INTEGER,
    views           INTEGER,
    engagement_rate REAL,
    caption         TEXT,
    hashtags        TEXT,
    UNIQUE(platform, post_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  SERIAL PRIMARY KEY,
    platform            TEXT,
    seeds_used          TEXT,
    creators_found      INTEGER,
    creators_qualified  INTEGER,
    apify_cost_usd      REAL,
    openai_cost_usd     REAL,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    status              TEXT DEFAULT 'running',
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS score_history (
    id              SERIAL PRIMARY KEY,
    creator_id      INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    run_id          INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    epic_trip_score REAL,
    followers       INTEGER,
    avg_engagement  REAL,
    scored_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outreach (
    id           SERIAL PRIMARY KEY,
    creator_id   INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
    contacted_at TIMESTAMPTZ,
    channel      TEXT,
    status       TEXT,
    notes        TEXT
);
```

---

### Step 5 — Update `db/repository.py`

**Three systemic changes across all functions:**

#### 5a. Paramstyle: `?` → `%s`

SQLite uses `?` as placeholder. PostgreSQL (psycopg2) uses `%s`.

```diff
- "SELECT * FROM creators WHERE platform=? AND username=?"
+ "SELECT * FROM creators WHERE platform=%s AND username=%s"
```

Named params (`:name`) also change:

```diff
- "WHERE id = :id"
+ "WHERE id = %(id)s"
```

#### 5b. Execution API: `conn.execute()` → `conn.cursor().execute()`

psycopg2 connections don't have an `.execute()` method directly.

```diff
- cur = conn.execute(sql, params)
+ cur = conn.cursor()
+ cur.execute(sql, params)
```

#### 5c. `lastrowid` → `RETURNING id`

SQLite's `cursor.lastrowid` doesn't exist in psycopg2. Use `RETURNING id` in INSERT statements.

```diff
  INSERT INTO creators (...) VALUES (...)
  ON CONFLICT(...) DO UPDATE SET ...
+ RETURNING id
```

```diff
- if cur.lastrowid:
-     return cur.lastrowid
+ row = cur.fetchone()
+ if row:
+     return row["id"]
```

#### 5d. Row access

`sqlite3.Row` supports `row["column"]` and `dict(row)`. `RealDictCursor` returns `dict` directly — `_row_to_creator` works unchanged.

#### 5e. Bulk `IN (?, ?, ?)` placeholders

```diff
- placeholders = ",".join("?" * len(creator_ids))
+ placeholders = ",".join(["%s"] * len(creator_ids))
```

---

### Step 6 — Update tests

**Current problem:** Tests use `get_connection(":memory:")` which is SQLite-only.

**Option A — Real test DB (recommended for CI):**

```python
# conftest.py
import pytest
import psycopg2
from db.connection import get_connection

TEST_DSN = "postgresql://draper:draper@localhost:5432/draper_test"

@pytest.fixture
def conn():
    c = get_connection(TEST_DSN)
    yield c
    # Truncate all tables between tests (faster than drop/recreate)
    with c.cursor() as cur:
        cur.execute("""
            TRUNCATE creators, posts, pipeline_runs, score_history,
                     outreach, search_configs RESTART IDENTITY CASCADE
        """)
    c.commit()
    c.close()
```

**Option B — `testing.postgresql` (in-process PG, no external server needed):**

```
pip install testing.postgresql
```

```python
import testing.postgresql
import pytest
from db.connection import get_connection

@pytest.fixture(scope="session")
def postgresql():
    with testing.postgresql.Postgresql() as pg:
        yield pg

@pytest.fixture
def conn(postgresql):
    c = get_connection(postgresql.url())
    yield c
    with c.cursor() as cur:
        cur.execute("TRUNCATE creators, posts, pipeline_runs, score_history, outreach, search_configs RESTART IDENTITY CASCADE")
    c.commit()
    c.close()
```

**Also update assertions that query the DB directly:**

```diff
- rows = conn.execute("SELECT count(*) FROM creators WHERE username='same_user'").fetchone()
- assert rows[0] == 1
+ with conn.cursor() as cur:
+     cur.execute("SELECT count(*) FROM creators WHERE username='same_user'")
+     assert cur.fetchone()["count"] == 1
```

---

### Step 7 — Data migration (existing SQLite data)

If there is data in the current `draper.db` to preserve:

```bash
# 1. Export from SQLite
sqlite3 draper.db .dump > draper_dump.sql

# 2. Create PG database
createdb draper

# 3. Apply new schema
psql draper < db/schema.sql

# 4. Use pgloader for clean migration (handles type differences)
brew install pgloader
pgloader draper.db postgresql://localhost/draper
```

Or use a Python script:

```python
# scripts/migrate_sqlite_to_pg.py
import sqlite3, psycopg2, json

sqlite_conn = sqlite3.connect("draper.db")
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect("postgresql://localhost/draper")

tables = ["search_configs", "creators", "posts", "pipeline_runs", "score_history", "outreach"]

for table in tables:
    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        continue
    cols = rows[0].keys()
    placeholders = ",".join(["%s"] * len(cols))
    col_names = ",".join(cols)
    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                tuple(row)
            )
pg_conn.commit()
print("Migration complete.")
```

---

## Implementation Checklist

- [x] **Step 1** — Add `psycopg2-binary>=2.9` and `testing.postgresql>=1.3` to `requirements.txt`
- [x] **Step 2** — Replace `DB_PATH` with `DATABASE_URL` in `.env`, `.env.example`, and `config/settings.py`
- [x] **Step 3** — Rewrite `db/schema.sql` (`SERIAL`, `TIMESTAMPTZ`, `DOUBLE PRECISION`, remove `PRAGMA`)
- [x] **Step 4** — Rewrite `db/connection.py` with `PgConnection`/`PgCursor`/`_DictRow` wrapper (preserves `conn.execute()` API)
- [x] **Step 5** — Update `db/repository.py` (`%s`/`%(name)s` params, `RETURNING id`, `EXCLUDED` uppercase)
- [x] **Step 6** — Update `dashboard/pages/run.py` (`?` → `%s`)
- [x] **Step 7** — Update `dashboard/pages/profiles.py` (`?` → `%s`)
- [x] **Step 8** — Update `pipeline/runner.py` (`?` → `%s`)
- [x] **Step 9** — Update tests: new `conftest.py` with `testing.postgresql` fixture (`pg_conn`), updated `test_db.py`, `test_runner.py`, `test_integration.py`
- [x] **Step 10** — Create data migration script `scripts/migrate_sqlite_to_pg.py`
- [ ] **Verify** — Run `pytest` green after all changes
- [ ] **Deploy** — Set `DATABASE_URL` in production environment (Heroku: `heroku config:set DATABASE_URL=...`)

---

## Files Changed

| File | Summary |
|------|---------|
| `requirements.txt` | Added `psycopg2-binary`, `testing.postgresql` |
| `.env`, `.env.example` | `DB_PATH` → `DATABASE_URL` |
| `config/settings.py` | `DB_PATH` → `DATABASE_URL` |
| `db/schema.sql` | Full PostgreSQL DDL rewrite |
| `db/connection.py` | Full rewrite with `PgConnection` wrapper |
| `db/repository.py` | All SQL paramstyle + `RETURNING id` |
| `dashboard/pages/run.py` | `?` → `%s` in ~15 queries |
| `dashboard/pages/profiles.py` | `?` → `%s` in 1 query |
| `pipeline/runner.py` | `?` → `%s` in 6 queries |
| `tests/conftest.py` | New — shared `pg_conn` fixture |
| `tests/test_db.py` | Use `pg_conn`, PG-compatible assertions |
| `tests/test_runner.py` | Use `pg_conn` |
| `tests/test_integration.py` | Use `pg_conn`, PG-compatible assertions |
| `scripts/migrate_sqlite_to_pg.py` | New — SQLite → PG data migration |

## Files NOT Changed

- `db/models.py` — dataclasses are DB-agnostic
- `pipeline/analysis.py`, `pipeline/scoring.py`, etc. — pure business logic
- `dashboard/app.py` — only calls `get_connection()`, no SQL
- `config/seeds.py`, `config/filters.py` — no DB interaction
- `dashboard/pages/overview.py`, `leads.py`, `seeds.py`, `search.py`, `calibration.py` — use only `db.repository` functions (no raw SQL with `?`)
