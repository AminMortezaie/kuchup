from __future__ import annotations

import json
from pathlib import Path

from relocation_jobs.mcp import service
from relocation_jobs.mcp.server import get_agent_skill as mcp_get_agent_skill
from relocation_jobs.mcp.server import list_agent_skills as mcp_list_agent_skills
from relocation_jobs.mcp.server import mcp as stdio_mcp


def test_tailor_skill_seeded():
    items = service.list_agent_skills()
    slugs = {item.slug for item in items}
    assert "tailor" in slugs
    tailor = next(item for item in items if item.slug == "tailor")
    assert tailor.title
    assert tailor.summary
    assert "save_tailored_tex" in tailor.summary


def test_get_agent_skill_tailor_body():
    skill = service.get_agent_skill("tailor")
    assert skill.slug == "tailor"
    assert skill.body.strip().startswith("# Agent playbook: tailor")
    tailor_md = (
        Path(__file__).resolve().parents[2]
        / "relocation_jobs"
        / "mcp"
        / "agent_skills"
        / "tailor.md"
    )
    assert skill.body == tailor_md.read_text(encoding="utf-8").strip() + "\n"
    for needle in (
        "get_job_context",
        "list_looking_to_apply_jobs",
        "get_reframe_pipeline",
        "save_tailored_tex",
        "validate_tex",
    ):
        assert needle in skill.body


def test_get_agent_skill_unknown_raises():
    try:
        service.get_agent_skill("not-a-real-playbook")
    except LookupError as exc:
        assert "not-a-real-playbook" in str(exc)
    else:
        raise AssertionError("expected LookupError")


def test_mcp_tools_return_tailor_playbook():
    listed = json.loads(mcp_list_agent_skills())
    assert any(row.get("slug") == "tailor" for row in listed)
    payload = json.loads(mcp_get_agent_skill("tailor"))
    assert payload["slug"] == "tailor"
    assert "Agent playbook" in payload["body"]


def test_stdio_mcp_registers_agent_skill_tools():
    names = {tool.name for tool in stdio_mcp._tool_manager.list_tools()}
    assert {"list_agent_skills", "get_agent_skill"} <= names
