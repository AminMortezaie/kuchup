from pathlib import Path


def _instruction_text(dockerfile: str) -> str:
    lines = []
    for line in Path(dockerfile).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines).lower()


def test_light_worker_dockerfile_has_no_chromium():
    text = Path("Dockerfile.ec2-worker").read_text(encoding="utf-8")
    instructions = _instruction_text("Dockerfile.ec2-worker")
    assert "requirements-playwright" not in instructions
    assert "playwright" not in instructions
    assert "chromium" not in instructions
    assert "FETCH_WORKER_KIND=http" in text


def test_playwright_worker_dockerfile_installs_chromium():
    text = Path("Dockerfile.ec2-worker-playwright").read_text(encoding="utf-8")
    assert "playwright install" in text
    assert "chromium" in text
    assert "requirements-playwright.txt" in text
    assert "FETCH_WORKER_KIND=playwright" in text
    assert "apps/playwright-worker/run.py" in text
