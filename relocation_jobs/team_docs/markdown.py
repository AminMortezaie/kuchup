from __future__ import annotations

import html
import re

_FENCE_OPEN = re.compile(r"^(?P<mark>`{3,}|~{3,})")
_HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*#*\s*$")
_HR = re.compile(r"^ {0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})\s*$")
_UL = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_OL = re.compile(r"^(\s*)\d+[.)]\s+(.+)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_STRONG = re.compile(r"\*\*(.+?)\*\*|(?<![\w])__(.+?)__(?![\w])")
_EM = re.compile(r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)")
_SAFE_URL = re.compile(r"^(?:https?://|mailto:)[^\s<>\"']+$", re.IGNORECASE)
_SAFE_PATH = re.compile(r"^/(?!/)[^\s<>\"']*$")


def render_markdown(source: str | None) -> str:
    text = "" if source is None else str(source)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(_render_blocks(text.split("\n")))


def _render_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        block, index = _next_block(lines, index)
        if block:
            blocks.append(block)
    return blocks


def _block_kind(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if _FENCE_OPEN.match(stripped):
        return "fence"
    if _HR.match(line):
        return "hr"
    if _HEADING.match(line):
        return "heading"
    if _QUOTE.match(line):
        return "quote"
    if _UL.match(line):
        return "ul"
    if _OL.match(line):
        return "ol"
    return None


def _next_block(lines: list[str], index: int) -> tuple[str, int]:
    kind = _block_kind(lines[index])
    if kind == "fence":
        return _render_fence(lines, index)
    if kind == "hr":
        return "<hr>", index + 1
    if kind == "heading":
        return _render_heading(lines[index]), index + 1
    if kind == "quote":
        return _render_quote(lines, index)
    if kind in {"ul", "ol"}:
        return _render_list(lines, index, ordered=kind == "ol")
    return _render_paragraph(lines, index)


def _render_fence(lines: list[str], index: int) -> tuple[str, int]:
    token = _FENCE_OPEN.match(lines[index].strip()).group("mark")
    index += 1
    body: list[str] = []
    while index < len(lines) and not lines[index].strip().startswith(token):
        body.append(lines[index])
        index += 1
    if index < len(lines):
        index += 1
    code = html.escape("\n".join(body))
    return f"<pre><code>{code}</code></pre>", index


def _render_heading(line: str) -> str:
    match = _HEADING.match(line)
    level = len(match.group(1))
    return f"<h{level}>{_inline(match.group(2))}</h{level}>"


def _render_quote(lines: list[str], index: int) -> tuple[str, int]:
    parts: list[str] = []
    while index < len(lines) and _QUOTE.match(lines[index]):
        parts.append(_QUOTE.match(lines[index]).group(1))
        index += 1
    return f"<blockquote><p>{_inline(' '.join(parts))}</p></blockquote>", index


def _render_list(lines: list[str], index: int, *, ordered: bool) -> tuple[str, int]:
    pattern = _OL if ordered else _UL
    items: list[str] = []
    while index < len(lines) and pattern.match(lines[index]):
        items.append(f"<li>{_inline(pattern.match(lines[index]).group(2))}</li>")
        index += 1
    tag = "ol" if ordered else "ul"
    return f"<{tag}>{''.join(items)}</{tag}>", index


def _render_paragraph(lines: list[str], index: int) -> tuple[str, int]:
    parts: list[str] = []
    while index < len(lines) and lines[index].strip() and _block_kind(lines[index]) is None:
        parts.append(lines[index].strip())
        index += 1
    if not parts:
        return "", index + 1
    return f"<p>{_inline(' '.join(parts))}</p>", index


def _inline(raw: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in _CODE.finditer(raw):
        pieces.append(_format_text(raw[cursor:match.start()]))
        pieces.append(f"<code>{html.escape(match.group(1))}</code>")
        cursor = match.end()
    pieces.append(_format_text(raw[cursor:]))
    return "".join(pieces)


def _format_text(raw: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in _LINK.finditer(raw):
        pieces.append(_emphasis(html.escape(raw[cursor:match.start()])))
        pieces.append(_link(match.group(1), match.group(2)))
        cursor = match.end()
    pieces.append(_emphasis(html.escape(raw[cursor:])))
    return "".join(pieces)


def _link(label: str, href: str) -> str:
    safe = _safe_href(href)
    text = _emphasis(html.escape(label))
    if not safe:
        return text
    return f'<a href="{html.escape(safe, quote=True)}">{text}</a>'


def _safe_href(href: str) -> str | None:
    value = href.strip()
    if _SAFE_URL.match(value) or _SAFE_PATH.match(value):
        return value
    return None


def _emphasis(escaped: str) -> str:
    strong = _STRONG.sub(lambda match: f"<strong>{match.group(1) or match.group(2)}</strong>", escaped)
    return _EM.sub(r"<em>\1</em>", strong)
