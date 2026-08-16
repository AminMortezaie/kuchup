from __future__ import annotations


def test_health_ok_when_postgres_up_and_redis_unset(v2_client, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_postgres",
        lambda: True,
    )
    resp = v2_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "ok": True,
        "postgres": "ok",
        "redis": "ok",
    }


def test_health_503_when_postgres_down(v2_client, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_postgres",
        lambda: False,
    )
    resp = v2_client.get("/api/health")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["ok"] is False
    assert payload["postgres"] == "fail"
    assert payload["redis"] == "ok"


def test_health_503_when_redis_configured_and_down(v2_client, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://:x@127.0.0.1:6379/0")
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_postgres",
        lambda: True,
    )
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_redis",
        lambda: False,
    )
    monkeypatch.setattr(
        "relocation_jobs.core.health.redis_enabled",
        lambda: True,
    )
    resp = v2_client.get("/api/health")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["ok"] is False
    assert payload["postgres"] == "ok"
    assert payload["redis"] == "fail"


def test_health_ok_when_postgres_and_redis_up(v2_client, monkeypatch):
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_postgres",
        lambda: True,
    )
    monkeypatch.setattr(
        "relocation_jobs.core.health.ping_redis",
        lambda: True,
    )
    monkeypatch.setattr(
        "relocation_jobs.core.health.redis_enabled",
        lambda: True,
    )
    resp = v2_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
