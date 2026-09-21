from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from relocation_jobs.core.job_identity import normalize_job_url

_PgOperationalError = psycopg.OperationalError

POOL_MIN_SIZE = 2
POOL_MAX_SIZE = 8

ConnectionPool: Any = None

_pool_lock = threading.Lock()
_pool: Any | None = None
_pg = {"conn": None, "initialized": False}
_thread_local = threading.local()


class _RetryConnection:
    def __init__(self, conn):
        self._conn = conn

    def _reconnect(self):
        self._conn = _replace_connection(self._conn)

    def execute(self, sql, params=()):
        try:
            return self._conn.execute(sql, params)
        except _PgOperationalError:
            self._reconnect()
            return self._conn.execute(sql, params)

    def executemany(self, sql, params_seq):
        try:
            return self._conn.executemany(sql, params_seq)
        except _PgOperationalError:
            self._reconnect()
            return self._conn.executemany(sql, params_seq)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        return self._conn.__exit__(*args)


def reset_db_initialized() -> None:
    _pg["initialized"] = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_url(url: str) -> str:
    return normalize_job_url(url)


def _connect_kwargs() -> dict:
    return {
        "row_factory": dict_row,
        "autocommit": True,
        "connect_timeout": 10,
        "prepare_threshold": None,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }


def _connect_postgres():
    return psycopg.connect(os.environ["DATABASE_URL"], **_connect_kwargs())


def _injected_connection():
    conn = _pg.get("conn")
    if conn is None:
        return None
    if getattr(conn, "closed", False):
        conn = _connect_postgres()
        _pg["conn"] = conn
    return conn


def close_connection_pool() -> None:
    global _pool
    with _pool_lock:
        pool = _pool
        _pool = None
    _thread_local.__dict__.clear()
    if pool is None:
        return
    try:
        pool.close()
    except Exception:
        pass


def _connection_pool_class():
    global ConnectionPool
    patched = ConnectionPool
    if patched is not None:
        return patched
    from psycopg_pool import ConnectionPool as pool_cls

    ConnectionPool = pool_cls
    return pool_cls


def init_connection_pool(*, force: bool = False) -> None:
    global _pool
    if _pg.get("conn") is not None:
        return
    conninfo = os.environ.get("DATABASE_URL", "").strip()
    if not conninfo:
        return
    with _pool_lock:
        if _pool is not None and not force:
            return
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None
        pool_cls = _connection_pool_class()
        _pool = pool_cls(
            conninfo=conninfo,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            kwargs=_connect_kwargs(),
            open=True,
            name="relocation-jobs",
        )


def reset_connection_pool_after_fork() -> None:
    global _pool
    _pool = None
    _thread_local.__dict__.clear()
    init_connection_pool()


def _get_pool():
    pool = _pool
    if pool is None:
        init_connection_pool()
        pool = _pool
    if pool is None:
        raise RuntimeError("Postgres connection pool is not available")
    return pool


def _checkout_pooled_connection():
    conn = getattr(_thread_local, "conn", None)
    if conn is not None and not getattr(conn, "closed", False):
        return conn
    conn = _get_pool().getconn()
    _thread_local.conn = conn
    _thread_local.pooled = True
    return conn


def _drop_thread_connection(conn=None) -> None:
    held = getattr(_thread_local, "conn", None)
    pooled = bool(getattr(_thread_local, "pooled", False))
    if conn is None:
        conn = held
    if held is conn:
        _thread_local.conn = None
        _thread_local.pooled = False
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass
    pool = _pool
    if pool is None or not pooled:
        return
    try:
        pool.putconn(conn)
    except Exception:
        pass


def _replace_connection(old_conn):
    if _pg.get("conn") is not None:
        fresh = _connect_postgres()
        _pg["conn"] = fresh
        return fresh
    _drop_thread_connection(old_conn)
    return _checkout_pooled_connection()


def _acquire_connection():
    injected = _injected_connection()
    if injected is not None:
        return injected
    return _checkout_pooled_connection()


def get_connection():
    return _RetryConnection(_acquire_connection())


def release_thread_connection() -> None:
    conn = getattr(_thread_local, "conn", None)
    pooled = bool(getattr(_thread_local, "pooled", False))
    _thread_local.conn = None
    _thread_local.pooled = False
    if conn is None or not pooled:
        return
    pool = _pool
    if pool is None:
        return
    try:
        pool.putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def ping_postgres() -> bool:
    try:
        get_connection().execute("SELECT 1")
        return True
    except Exception:
        return False


@contextmanager
def db_read():
    conn = get_connection()
    try:
        yield conn
    except _PgOperationalError:
        _drop_thread_connection(getattr(conn, "_conn", conn))
        raise


@contextmanager
def db_transaction():
    conn = get_connection()
    try:
        with conn.transaction():
            yield conn
    except _PgOperationalError:
        _drop_thread_connection(getattr(conn, "_conn", conn))
        raise
    except Exception:
        raw = getattr(conn, "_conn", conn)
        if getattr(raw, "closed", False):
            _drop_thread_connection(raw)
        raise


def init_db(*, force: bool = False) -> None:
    if _pg["initialized"] and not force:
        return

    from relocation_jobs.catalog.schema import init_catalog_schema
    from relocation_jobs.core.migrations import _migrate_schema

    init_connection_pool()
    init_catalog_schema()
    from relocation_jobs.catalog.custom_countries import init_countries_store

    init_countries_store()
    with db_transaction() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                google_sub TEXT UNIQUE,
                email TEXT UNIQUE,
                display_name TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                plan_updated_at TEXT,
                mcp_quota_date TEXT,
                mcp_quota_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS job_tracking (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                country TEXT NOT NULL,
                company_name TEXT NOT NULL,
                job_url TEXT NOT NULL,
                applied INTEGER NOT NULL DEFAULT 0,
                applied_date TEXT,
                not_for_me INTEGER NOT NULL DEFAULT 0,
                not_for_me_date TEXT,
                rejected INTEGER NOT NULL DEFAULT 0,
                rejected_date TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, country, company_name, job_url)
            );

            CREATE TABLE IF NOT EXISTS company_tracking (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                country TEXT NOT NULL,
                company_name TEXT NOT NULL,
                company_applied INTEGER NOT NULL DEFAULT 0,
                company_applied_date TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, country, company_name)
            );

            CREATE INDEX IF NOT EXISTS idx_job_tracking_user ON job_tracking(user_id);
            CREATE INDEX IF NOT EXISTS idx_company_tracking_user ON company_tracking(user_id);

            CREATE TABLE IF NOT EXISTS fetch_runs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                country TEXT NOT NULL,
                company_name TEXT,
                scope TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                duration_seconds REAL,
                exit_code INTEGER,
                cancelled INTEGER NOT NULL DEFAULT 0,
                new_jobs INTEGER NOT NULL DEFAULT 0,
                concurrency INTEGER,
                companies_done INTEGER,
                companies_total INTEGER,
                result_line TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_fetch_runs_user_started
                ON fetch_runs(user_id, started_at DESC);
            """
        )
        _migrate_schema(conn)
    _pg["initialized"] = True
