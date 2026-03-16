from __future__ import annotations

import psycopg2
import pytest

import testing.postgresql

from db.connection import PgConnection, _apply_schema
from db.repository import seed_default_search_configs


# One shared Postgresql factory for the entire test session (faster startup)
_pg_factory = testing.postgresql.PostgresqlFactory(cache_initialized_db=True)


def teardown_module():
    _pg_factory.clear_cache()


@pytest.fixture
def pg_conn():
    """Yields a PgConnection backed by an ephemeral PostgreSQL instance."""
    pg = _pg_factory()
    raw = psycopg2.connect(**pg.dsn())
    raw.autocommit = False
    conn = PgConnection(raw)
    _apply_schema(conn)
    seed_default_search_configs(conn)
    yield conn
    conn.close()
    pg.stop()
