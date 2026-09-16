from pathlib import Path


def test_light_worker_dockerfile_has_no_chromium():
    text = Path("Dockerfile.ec2-worker").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "playwright" not in lowered
    assert "chromium" not in lowered
    assert "requirements-playwright" not in lowered
    assert "FETCH_WORKER_KIND=http" in text


def test_playwright_worker_dockerfile_installs_chromium():
    text = Path("Dockerfile.ec2-worker-playwright").read_text(encoding="utf-8")
    assert "playwright install" in text
    assert "chromium" in text
    assert "requirements-playwright.txt" in text
    assert "FETCH_WORKER_KIND=playwright" in text
    assert "apps/playwright-worker/run.py" in text
