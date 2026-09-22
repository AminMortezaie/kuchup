from pathlib import Path


def _instruction_text(dockerfile: str) -> str:
    lines = []
    for line in Path(dockerfile).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines).lower()


def _docker_run_blocks(text: str) -> list[str]:
    blocks = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if "docker run " not in lines[index]:
            index += 1
            continue
        chunk = [lines[index]]
        while chunk[-1].rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            chunk.append(lines[index])
        blocks.append("\n".join(chunk))
        index += 1
    return blocks


def test_light_worker_dockerfile_has_no_chromium():
    text = Path("Dockerfile.ec2-worker").read_text(encoding="utf-8")
    instructions = _instruction_text("Dockerfile.ec2-worker")
    assert "requirements-playwright" not in instructions
    assert "playwright" not in instructions
    assert "chromium" not in instructions
    assert "FETCH_WORKER_KIND=http" in text


def test_only_fetch_workers_have_memory_caps():
    text = Path("scripts/ec2_app_deploy.sh").read_text(encoding="utf-8")
    assert "FETCH_WORKER_MEMORY=512m" in text
    assert "PLAYWRIGHT_WORKER_MEMORY=640m" in text
    capped = [
        block
        for block in _docker_run_blocks(text)
        if "--memory=" in block or "--memory-swap=" in block
    ]
    assert len(capped) == 2
    light = next(block for block in capped if "${WORKER_CONTAINER}" in block)
    playwright = next(
        block for block in capped if "${PLAYWRIGHT_WORKER_CONTAINER}" in block
    )
    assert "--memory=${FETCH_WORKER_MEMORY}" in light
    assert "--memory-swap=${FETCH_WORKER_MEMORY}" in light
    assert "FETCH_WORKER_KIND=http" in light
    assert "--restart unless-stopped" in light
    assert "--memory=${PLAYWRIGHT_WORKER_MEMORY}" in playwright
    assert "--memory-swap=${PLAYWRIGHT_WORKER_MEMORY}" in playwright
    assert "FETCH_WORKER_KIND=playwright" in playwright
    assert "--restart unless-stopped" in playwright


def test_playwright_worker_dockerfile_installs_chromium():
    text = Path("Dockerfile.ec2-worker-playwright").read_text(encoding="utf-8")
    assert "playwright install" in text
    assert "chromium" in text
    assert "requirements-playwright.txt" in text
    assert "FETCH_WORKER_KIND=playwright" in text
    assert "apps/playwright-worker/run.py" in text
