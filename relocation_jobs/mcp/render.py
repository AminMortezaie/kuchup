from __future__ import annotations

import hmac
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_COMPILE_TIMEOUT_SEC = 60
_TECTONIC_INCOMPATIBLE_PACKAGES = ("fontawesome5", "fontawesome")
_USEPACKAGE_RE = re.compile(r"^\\usepackage(\[[^\]]*\])?\{([^}]+)\}")
_FA_CMD_RE = re.compile(r"\\fa(?:Icon|[A-Za-z]+)(?:\[[^\]]*\])?(?:\{[^}]*\})?")
_TECTONIC_SEARCH_PATHS = (
    "/opt/homebrew/bin/tectonic",
    "/usr/local/bin/tectonic",
)


@dataclass
class CompileResult:
    ok: bool
    log: str = ""
    pdf_path: str = ""


def _resolve_latex_command() -> str:
    raw = (os.environ.get("MCP_LATEX_CMD") or "tectonic").strip() or "tectonic"
    if Path(raw).is_file():
        return raw
    found = shutil.which(raw)
    if found:
        return found
    if raw == "tectonic":
        for candidate in _TECTONIC_SEARCH_PATHS:
            if Path(candidate).is_file():
                return candidate
    return raw


def sanitize_tex_for_tectonic(tex: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    kept: list[str] = []
    for line in tex.splitlines():
        match = _USEPACKAGE_RE.match(line.strip())
        if match is not None:
            packages = [part.strip() for part in match.group(2).split(",")]
            blocked = [pkg for pkg in packages if pkg in _TECTONIC_INCOMPATIBLE_PACKAGES]
            if blocked:
                removed.extend(blocked)
                continue
        kept.append(line)
    sanitized = "\n".join(kept)
    if _FA_CMD_RE.search(sanitized):
        sanitized = _FA_CMD_RE.sub("", sanitized)
        removed.append("fa-icons")
    if "—" in sanitized:
        sanitized = sanitized.replace("—", "--")
        removed.append("unicode-em-dash")
    if tex.endswith("\n"):
        sanitized += "\n"
    return sanitized, removed


def _tex_needs_tectonic_sanitize(tex: str) -> bool:
    for line in tex.splitlines():
        match = _USEPACKAGE_RE.match(line.strip())
        if match is None:
            continue
        packages = [part.strip() for part in match.group(2).split(",")]
        if any(pkg in _TECTONIC_INCOMPATIBLE_PACKAGES for pkg in packages):
            return True
    if _FA_CMD_RE.search(tex):
        return True
    return "—" in tex


def _build_command(cmd: str, tex_path: Path, out_dir: Path) -> list[str]:
    name = Path(cmd).name
    if name == "tectonic":
        return [cmd, "--outdir", str(out_dir), str(tex_path)]
    if name in ("pdflatex", "xelatex", "lualatex"):
        return [cmd, "-interaction=nonstopmode", "-output-directory", str(out_dir), str(tex_path)]
    return [cmd, str(tex_path)]


def _compile_via_mcp(tex_path: Path, out_dir: Path) -> CompileResult | None:
    if (os.environ.get("MCP_HTTP_PORT") or "").strip():
        return None
    url = (os.environ.get("MCP_COMPILE_URL") or "").strip()
    secret = (os.environ.get("PANEL_SECRET_KEY") or "").strip()
    if not url or not secret:
        return None
    pdf_path = out_dir / tex_path.with_suffix(".pdf").name
    request = urllib.request.Request(
        url,
        data=tex_path.read_bytes(),
        headers={"X-Panel-Secret": secret},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_COMPILE_TIMEOUT_SEC) as response:
            pdf_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        return CompileResult(ok=False, log=detail or f"MCP compile failed ({exc.code})")
    except urllib.error.URLError as exc:
        return CompileResult(ok=False, log=f"MCP compile unreachable: {exc.reason}")
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        return CompileResult(ok=False, log="MCP compile returned an empty PDF")
    return CompileResult(ok=True, pdf_path=str(pdf_path), log="compiled by MCP")


def compile_tex_bytes(body: bytes, secret_header: str) -> tuple[int, bytes]:
    expected = (os.environ.get("PANEL_SECRET_KEY") or "").strip()
    given = secret_header or ""
    if not expected or len(given) != len(expected) or not hmac.compare_digest(given, expected):
        return 404, b""
    if not body or len(body) > 2_000_000:
        return 400, b"tex missing or too large"
    with tempfile.TemporaryDirectory() as tmp:
        tex_path = Path(tmp) / "document.tex"
        tex_path.write_bytes(body)
        result = render_tex_to_pdf(tex_path)
        if not result.ok:
            return 400, (result.log or "compile failed").encode()
        return 200, Path(result.pdf_path).read_bytes()


def _run_compile(tex_path: Path, out_dir: Path) -> CompileResult:
    pdf_path = out_dir / tex_path.with_suffix(".pdf").name
    cmd = _resolve_latex_command()
    argv = _build_command(cmd, tex_path, out_dir)
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_COMPILE_TIMEOUT_SEC,
            cwd=str(out_dir),
            check=False,
        )
    except FileNotFoundError:
        proxied = _compile_via_mcp(tex_path, out_dir)
        if proxied is not None:
            return proxied
        return CompileResult(
            ok=False,
            log=(
                f"LaTeX compiler not found: {cmd}. "
                "Install tectonic, set MCP_LATEX_CMD to its full path in Claude Desktop MCP env, "
                "or use pdflatex."
            ),
        )
    except subprocess.TimeoutExpired:
        return CompileResult(ok=False, log=f"LaTeX compile timed out after {_COMPILE_TIMEOUT_SEC}s")

    log = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if completed.returncode == 0 and pdf_path.is_file():
        return CompileResult(ok=True, pdf_path=str(pdf_path), log=log)
    return CompileResult(
        ok=False,
        log=log or f"Compile failed (exit {completed.returncode})",
    )


def render_tex_to_pdf(tex_path: Path) -> CompileResult:
    if not tex_path.is_file():
        return CompileResult(ok=False, log=f"Tex file not found: {tex_path}")

    out_dir = tex_path.parent
    original = tex_path.read_text(encoding="utf-8")
    to_compile = original
    note = ""

    if Path(_resolve_latex_command()).name == "tectonic" and _tex_needs_tectonic_sanitize(original):
        to_compile, removed = sanitize_tex_for_tectonic(original)
        if removed:
            pkgs = ", ".join(sorted(set(removed)))
            note = f"Omitted tectonic-incompatible: {pkgs}"

    if to_compile != original:
        tex_path.write_text(to_compile, encoding="utf-8")

    result = _run_compile(tex_path, out_dir)

    if to_compile != original:
        tex_path.write_text(original, encoding="utf-8")

    if result.ok and note:
        result.log = f"{note}\n\n{result.log}".strip() if result.log else note
    return result
