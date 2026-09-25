"""Static layout checks for docked board/applications pagination (mobile scroll bug)."""

from __future__ import annotations

from pathlib import Path

STATIC = Path("relocation_jobs/static")


def test_board_pagination_uses_grid_shell_not_flex_auto_margin():
    shell = (STATIC / "app-shell.css").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "grid-template-rows: minmax(0, 1fr) auto" in shell
    assert ".app-shell .board-page" in shell
    assert 'id="board-pagination-root"' in index
    assert index.index("board-page-body") < index.index("board-pagination-root")
    assert "margin-top: auto" not in styles.split(".board-pagination-root")[1].split(
        ".board-pagination "
    )[0]
    assert "touch-action: none" not in styles.split(".board-pagination-root")[1].split(
        ".board-toolbar"
    )[0]
