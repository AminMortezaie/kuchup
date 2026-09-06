from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from relocation_jobs.mcp.names import (
    interview_note_pdf_filename,
    master_pdf_filename,
    project_pdf_filename,
)

_FRAGMENT_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{xcolor}
\pagestyle{empty}
\begin{document}
"""
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_TEX_SPECIALS = str.maketrans(
    {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "#": r"\#",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
)


def _escape_tex_text(text: str) -> str:
    return text.replace("—", "---").replace("–", "--").translate(_TEX_SPECIALS)


def _looks_like_markdown(body: str) -> bool:
    return any(_MD_HEADING_RE.match(line) for line in body.splitlines())


def _markdown_fragment_to_tex(markdown: str) -> str:
    lines: list[str] = []
    for line in markdown.splitlines():
        match = _MD_HEADING_RE.match(line)
        if match is None:
            lines.append(_escape_tex_text(line))
            continue
        level = len(match.group(1))
        title = _escape_tex_text(match.group(2).strip())
        command = r"\section*" if level <= 2 else r"\subsection*"
        lines.append(f"{command}{{{title}}}")
    return "\n".join(lines)


def wrap_fragment_for_pdf(content: str) -> str:
    body = (content or "").strip()
    if not body:
        raise ValueError("project content is empty")
    if r"\documentclass" in body:
        return body
    if _looks_like_markdown(body):
        body = _markdown_fragment_to_tex(body)
    return f"{_FRAGMENT_PREAMBLE}{body}\n\\end{{document}}\n"


class SlugDocumentKind(Protocol):
    table: str
    slug_kind: str
    missing_label: str

    def pdf_filename(self, full_name: str, slug: str) -> str: ...

    def tex_for_render(self, content: str) -> str: ...


@dataclass(frozen=True)
class _SlugDocumentKind:
    table: str
    slug_kind: str
    missing_label: str
    _pdf_filename: Callable[[str, str], str]
    wrap_fragment: bool = False

    def pdf_filename(self, full_name: str, slug: str) -> str:
        return self._pdf_filename(full_name, slug)

    def tex_for_render(self, content: str) -> str:
        if self.wrap_fragment:
            return wrap_fragment_for_pdf(content)
        return content


MASTER_RESUME = _SlugDocumentKind(
    table="mcp_master_resumes",
    slug_kind="master resume slug",
    missing_label="Master resume",
    _pdf_filename=master_pdf_filename,
)
PROJECT_MASTER = _SlugDocumentKind(
    table="mcp_project_masters",
    slug_kind="project master slug",
    missing_label="Project master",
    _pdf_filename=project_pdf_filename,
    wrap_fragment=True,
)
INTERVIEW_NOTE = _SlugDocumentKind(
    table="mcp_interview_notes",
    slug_kind="interview note slug",
    missing_label="Interview note",
    _pdf_filename=interview_note_pdf_filename,
    wrap_fragment=True,
)

SLUG_DOCUMENT_KINDS = (MASTER_RESUME, PROJECT_MASTER, INTERVIEW_NOTE)
SLUG_DOCUMENT_TABLES = frozenset(kind.table for kind in SLUG_DOCUMENT_KINDS)
