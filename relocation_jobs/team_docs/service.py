from __future__ import annotations

import re

from relocation_jobs.team_docs import repo

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TITLE_MAX = 200
_SLUG_MAX = 80
_BODY_MAX = 200_000

ROOT_FOLDER_PATHS = ("/product", "/business", "/marketing", "/tech")


def _clean_title(title: str) -> str:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        raise ValueError("Title is required")
    if len(cleaned) > _TITLE_MAX:
        raise ValueError(f"Title must be at most {_TITLE_MAX} characters")
    return cleaned


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not cleaned or not _SLUG_RE.match(cleaned):
        raise ValueError("A URL-safe slug is required")
    if len(cleaned) > _SLUG_MAX:
        cleaned = cleaned[:_SLUG_MAX].strip("-")
    if not cleaned or not _SLUG_RE.match(cleaned):
        raise ValueError("A URL-safe slug is required")
    return cleaned


def _clean_body(body) -> str:
    text = "" if body is None else str(body)
    if len(text) > _BODY_MAX:
        raise ValueError(f"Body must be at most {_BODY_MAX} characters")
    return text


def _allocate_slug(folder_id: int, slug: str, *, exclude_id: int | None = None) -> str:
    existing = repo.find_doc_in_folder(folder_id, slug)
    if not existing or existing["id"] == exclude_id:
        return slug
    index = 2
    while True:
        candidate = f"{slug}-{index}"
        found = repo.find_doc_in_folder(folder_id, candidate)
        if not found or found["id"] == exclude_id:
            return candidate
        index += 1


def _require_folder(folder_id: int) -> dict:
    folder = repo.get_folder(folder_id)
    if not folder:
        raise LookupError("Folder not found")
    return folder


def _with_path(doc: dict, folder: dict | None = None) -> dict:
    resolved = folder or repo.get_folder(int(doc["folder_id"]))
    path = f"{resolved['path']}/{doc['slug']}" if resolved else f"/{doc['slug']}"
    return {**doc, "path": path, "folder_path": resolved["path"] if resolved else ""}


def list_folder_tree() -> dict:
    folders = repo.list_folders()
    docs = repo.list_doc_summaries()
    children: dict[int | None, list[dict]] = {}
    for folder in folders:
        children.setdefault(folder["parent_id"], []).append(folder)
    docs_by_folder: dict[int, list[dict]] = {}
    folders_by_id = {folder["id"]: folder for folder in folders}
    for doc in docs:
        folder = folders_by_id.get(doc["folder_id"])
        docs_by_folder.setdefault(doc["folder_id"], []).append(_with_path(doc, folder))

    def attach(folder: dict) -> dict:
        return {
            **folder,
            "docs": docs_by_folder.get(folder["id"], []),
            "folders": [attach(child) for child in children.get(folder["id"], [])],
        }

    return {"folders": [attach(folder) for folder in children.get(None, [])]}


def get_document(doc_id: int) -> dict:
    doc = repo.get_doc(doc_id)
    if not doc:
        raise LookupError("Document not found")
    return _with_path(doc)


def create_document(
    *,
    folder_id: int,
    title: str,
    body: str = "",
    slug: str | None = None,
) -> dict:
    folder = _require_folder(folder_id)
    clean_title = _clean_title(title)
    requested = (slug or "").strip()
    base = _slugify(requested or clean_title)
    allocated = _allocate_slug(folder["id"], base) if not requested else base
    if requested and repo.find_doc_in_folder(folder["id"], allocated):
        raise ValueError("A document with that slug already exists in this folder")
    saved = repo.insert_doc(
        folder_id=folder["id"],
        slug=allocated,
        title=clean_title,
        body=_clean_body(body),
    )
    return _with_path(saved, folder)


def update_document(
    doc_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    slug: str | None = None,
    folder_id: int | None = None,
) -> dict:
    current = repo.get_doc(doc_id)
    if not current:
        raise LookupError("Document not found")
    next_folder_id = int(folder_id) if folder_id is not None else int(current["folder_id"])
    folder = _require_folder(next_folder_id)
    next_title = _clean_title(title) if title is not None else current["title"]
    next_body = _clean_body(body) if body is not None else current["body"]
    requested = None if slug is None else str(slug).strip()
    if requested == "":
        raise ValueError("A URL-safe slug is required")
    base = _slugify(requested) if requested else current["slug"]
    next_slug = base if requested else current["slug"]
    clash = repo.find_doc_in_folder(folder["id"], next_slug)
    if clash and clash["id"] != current["id"]:
        raise ValueError("A document with that slug already exists in this folder")
    saved = repo.update_doc(
        current["id"],
        folder_id=folder["id"],
        slug=next_slug,
        title=next_title,
        body=next_body,
    )
    if not saved:
        raise LookupError("Document not found")
    return _with_path(saved, folder)


def delete_document(doc_id: int) -> None:
    if not repo.delete_doc(doc_id):
        raise LookupError("Document not found")
