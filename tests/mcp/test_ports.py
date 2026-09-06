from __future__ import annotations

from relocation_jobs.mcp.ports import INTERVIEW_NOTE, wrap_fragment_for_pdf


def test_wrap_fragment_converts_markdown_headings():
    tex = wrap_fragment_for_pdf(
        "## Creative Fabrica\n\n### 1. Tell me about yourself.\nI am a backend engineer.\n"
    )
    assert r"\documentclass" in tex
    assert "##" not in tex
    assert r"\section*{Creative Fabrica}" in tex
    assert r"\subsection*{1. Tell me about yourself.}" in tex
    assert "I am a backend engineer." in tex
    assert tex.strip().endswith(r"\end{document}")


def test_wrap_fragment_keeps_latex_subsection():
    tex = wrap_fragment_for_pdf(r"\subsection*{STAR}" "\nSituation, Task.")
    assert r"\subsection*{STAR}" in tex
    assert r"\section*" not in tex


def test_wrap_fragment_returns_full_document():
    source = r"\documentclass{article}\begin{document}Hi\end{document}"
    assert wrap_fragment_for_pdf(source) == source


def test_interview_note_tex_for_render_strips_hash():
    tex = INTERVIEW_NOTE.tex_for_render("## Title\n### Q1\nAnswer")
    lines = tex.splitlines()
    assert lines[9] == r"\section*{Title}"
    assert "#" not in tex
