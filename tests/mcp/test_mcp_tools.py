from mcp.server.fastmcp import FastMCP

from relocation_jobs.mcp.http_app import _copy_tools
from relocation_jobs.mcp.server import mcp as stdio_mcp

INTERVIEW_NOTE_TOOLS = frozenset(
    {
        "list_interview_notes",
        "get_interview_note",
        "save_interview_note",
    }
)


def _tool_names(server: FastMCP) -> set[str]:
    return {tool.name for tool in server._tool_manager.list_tools()}


def test_stdio_mcp_registers_interview_note_tools():
    assert INTERVIEW_NOTE_TOOLS <= _tool_names(stdio_mcp)


def test_http_mcp_copies_interview_note_tools():
    http_mcp = FastMCP("relocation-jobs-test")
    _copy_tools(stdio_mcp, http_mcp)
    assert INTERVIEW_NOTE_TOOLS <= _tool_names(http_mcp)
