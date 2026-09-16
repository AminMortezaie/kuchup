from __future__ import annotations

import threading
import time
from pathlib import Path

import relocation_jobs.core.db as core
from relocation_jobs.core.paths import PROJECT_ROOT
from relocation_jobs.web import gunicorn_conf


class _FakeConn:
    def __init__(self, ident: int):
        self.ident = ident
        self.closed = False
        self.puts = 0

    def execute(self, sql, params=()):
        return self

    def close(self):
        self.closed = True


class _FakePool:
    def __init__(self):
        self.lock = threading.Lock()
        self.created = 0
        self.returned: list[_FakeConn] = []
        self.closed = False

    def getconn(self):
        with self.lock:
            self.created += 1
            ident = self.created
        time.sleep(0.02)
        return _FakeConn(ident)

    def putconn(self, conn):
        self.returned.append(conn)

    def close(self):
        self.closed = True


def _clear_thread_state() -> None:
    core._thread_local.__dict__.clear()


def _with_pool(pool, fn):
    saved_conn = core._pg["conn"]
    saved_pool = core._pool
    core._pg["conn"] = None
    core._pool = pool
    _clear_thread_state()
    try:
        return fn()
    finally:
        _clear_thread_state()
        core._pool = saved_pool
        core._pg["conn"] = saved_conn


def test_idle_ping_threshold_removed():
    assert not hasattr(core, "_IDLE_PING_THRESHOLD_S")
    assert not hasattr(core, "_db_lock")


def test_pool_constants_match_phase0():
    assert core.POOL_MIN_SIZE == 2
    assert core.POOL_MAX_SIZE == 8


def test_init_connection_pool_uses_psycopg_pool(monkeypatch):
    created = {}

    class CapturingPool:
        def __init__(self, conninfo, **kwargs):
            created.update(kwargs)
            created["conninfo"] = conninfo

        def close(self):
            pass

    saved_conn = core._pg["conn"]
    core._pg["conn"] = None
    monkeypatch.setenv("DATABASE_URL", "postgresql://relocation:PASSWORD@127.0.0.1:5432/relocation_jobs")
    monkeypatch.setattr(core, "ConnectionPool", CapturingPool)
    monkeypatch.setattr(core, "_pool", None)
    try:
        core.init_connection_pool()
        assert created["min_size"] == 2
        assert created["max_size"] == 8
        assert created["open"] is True
        assert created["conninfo"].startswith("postgresql://")
    finally:
        core._pool = None
        core._pg["conn"] = saved_conn


def test_init_connection_pool_skips_when_test_override_present():
    called = []

    class BoomPool:
        def __init__(self, *args, **kwargs):
            called.append(kwargs)
            raise AssertionError("pool must not open when tests inject a connection")

    saved_pool = core._pool
    core._pool = None
    original = core.ConnectionPool
    core.ConnectionPool = BoomPool
    try:
        core.init_connection_pool()
        assert called == []
        assert core._pool is None
    finally:
        core.ConnectionPool = original
        core._pool = saved_pool


def test_threads_checkout_distinct_pooled_connections():
    pool = _FakePool()
    results: list[int] = []

    def worker():
        conn = core.get_connection()
        results.append(conn._conn.ident)

    def run():
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    _with_pool(pool, run)
    assert len(results) == 4
    assert len(set(results)) == 4


def test_same_thread_reuses_checked_out_connection():
    pool = _FakePool()

    def run():
        first = core.get_connection()
        second = core.get_connection()
        return first._conn.ident, second._conn.ident, pool.created

    first_id, second_id, created = _with_pool(pool, run)
    assert first_id == second_id
    assert created == 1


def test_release_thread_connection_returns_to_pool():
    pool = _FakePool()

    def run():
        conn = core.get_connection()
        raw = conn._conn
        core.release_thread_connection()
        return raw

    raw = _with_pool(pool, run)
    assert pool.returned == [raw]


def test_reset_after_fork_does_not_close_inherited_pool(monkeypatch):
    inherited = _FakePool()
    created = []

    def fake_init(*, force: bool = False):
        created.append(force)
        core._pool = _FakePool()

    saved_conn = core._pg["conn"]
    saved_pool = core._pool
    core._pg["conn"] = None
    core._pool = inherited
    monkeypatch.setattr(core, "init_connection_pool", fake_init)
    try:
        core.reset_connection_pool_after_fork()
        assert inherited.closed is False
        assert created == [False]
        assert core._pool is not inherited
    finally:
        core._pool = saved_pool
        core._pg["conn"] = saved_conn


def test_gunicorn_conf_workers_and_post_fork():
    assert gunicorn_conf.workers == 2
    assert gunicorn_conf.threads == 8
    assert gunicorn_conf.preload_app is False
    assert callable(gunicorn_conf.post_fork)


def test_post_fork_hook_reinitializes_pool(monkeypatch):
    called = []
    monkeypatch.setattr(
        "relocation_jobs.core.db.reset_connection_pool_after_fork",
        lambda: called.append("reset"),
    )
    gunicorn_conf.post_fork(None, None)
    assert called == ["reset"]


def test_docker_entrypoint_uses_two_gunicorn_workers():
    text = Path(PROJECT_ROOT / "docker-entrypoint.sh").read_text()
    assert "--workers 2" in text
    assert "--workers 1" not in text
    assert "--config python:relocation_jobs.web.gunicorn_conf" in text
