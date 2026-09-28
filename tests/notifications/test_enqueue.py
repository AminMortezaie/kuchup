from __future__ import annotations

from relocation_jobs.notifications import enqueue as notify_enqueue


def test_enqueue_country_notify_wave_publishes_sqs(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setenv(
        "SQS_JOB_NOTIFY_QUEUE_URL",
        "https://sqs.eu-central-1.amazonaws.com/123/job-notify",
    )
    monkeypatch.setattr(
        "relocation_jobs.notifications.enqueue.send_json_message",
        lambda url, payload: sent.append({"url": url, "payload": payload}) or "msg-1",
    )

    result = notify_enqueue.enqueue_country_notify_wave(country="uk", fetch_run_id=42)

    assert result["queued"] is True
    assert sent[0]["payload"] == {
        "type": "country_wave",
        "country": "uk",
        "fetch_run_id": 42,
    }


def test_enqueue_country_notify_wave_skips_without_config(monkeypatch):
    monkeypatch.delenv("SQS_JOB_NOTIFY_QUEUE_URL", raising=False)
    monkeypatch.delenv("NOTIFICATION_WORKER_BIN", raising=False)
    result = notify_enqueue.enqueue_country_notify_wave(country="uk", fetch_run_id=7)
    assert result["queued"] is False
    assert result["reason"] == "notify_queue_unconfigured"
