from __future__ import annotations

import re

from relocation_jobs.team_docs import repo
from relocation_jobs.users.repo import get_user_by_id

_TITLE_MAX = 200
_SLUG_MAX = 80
_BODY_MAX = 200_000

FOLDERS = {
    "product": "Product",
    "business": "Business",
    "marketing": "Marketing",
    "tech": "Tech",
}


def _clean_title(title: str) -> str:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        raise ValueError("Title is required")
    if len(cleaned) > _TITLE_MAX:
        raise ValueError(f"Title must be at most {_TITLE_MAX} characters")
    return cleaned


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    cleaned = cleaned[:_SLUG_MAX].strip("-")
    if not cleaned:
        raise ValueError("A URL-safe slug is required")
    return cleaned


def _clean_body(body) -> str:
    text = "" if body is None else str(body)
    if len(text) > _BODY_MAX:
        raise ValueError(f"Body must be at most {_BODY_MAX} characters")
    return text


def _allocate_slug(folder: str, slug: str) -> str:
    if not repo.find_doc_in_folder(folder, slug):
        return slug
    index = 2
    while True:
        candidate = f"{slug}-{index}"
        if not repo.find_doc_in_folder(folder, candidate):
            return candidate
        index += 1


def _require_folder(folder: str) -> str:
    slug = (folder or "").strip()
    if slug not in FOLDERS:
        raise LookupError("Folder not found")
    return slug


def _editor_label(user_id: int | None) -> str:
    if not user_id:
        return ""
    user = get_user_by_id(int(user_id))
    if not user:
        return ""
    display_name = (user.get("display_name") or "").strip()
    if display_name:
        return display_name
    email = (user.get("email") or "").strip()
    if email:
        return email
    return (user.get("username") or "").strip()


def _with_path(doc: dict) -> dict:
    folder = doc["folder"]
    return {**doc, "path": f"/{folder}/{doc['slug']}", "folder_path": f"/{folder}"}


def _public_doc(doc: dict) -> dict:
    payload = _with_path(doc)
    payload["created_by"] = _editor_label(doc.get("created_by_user_id"))
    payload["updated_by"] = _editor_label(doc.get("updated_by_user_id"))
    payload.pop("created_by_user_id", None)
    payload.pop("updated_by_user_id", None)
    return payload


def list_folder_tree() -> dict:
    by_folder: dict[str, list[dict]] = {}
    for doc in repo.list_doc_summaries():
        by_folder.setdefault(doc["folder"], []).append(_public_doc(doc))
    return {
        "folders": [
            {
                "slug": slug,
                "title": title,
                "path": f"/{slug}",
                "docs": by_folder.get(slug, []),
            }
            for slug, title in FOLDERS.items()
        ]
    }


def get_document(doc_id: int) -> dict:
    doc = repo.get_doc(doc_id)
    if not doc:
        raise LookupError("Document not found")
    return _public_doc(doc)


def create_document(
    *,
    folder: str,
    title: str,
    body: str = "",
    slug: str | None = None,
    editor_user_id: int,
) -> dict:
    folder = _require_folder(folder)
    clean_title = _clean_title(title)
    requested = (slug or "").strip()
    base = _slugify(requested or clean_title)
    allocated = _allocate_slug(folder, base) if not requested else base
    if requested and repo.find_doc_in_folder(folder, allocated):
        raise ValueError("A document with that slug already exists in this folder")
    saved = repo.insert_doc(
        folder=folder,
        slug=allocated,
        title=clean_title,
        body=_clean_body(body),
        editor_user_id=editor_user_id,
    )
    return _public_doc(saved)


def update_document(
    doc_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    slug: str | None = None,
    folder: str | None = None,
    editor_user_id: int,
) -> dict:
    current = repo.get_doc(doc_id)
    if not current:
        raise LookupError("Document not found")
    next_folder = _require_folder(folder) if folder is not None else current["folder"]
    next_title = _clean_title(title) if title is not None else current["title"]
    next_body = _clean_body(body) if body is not None else current["body"]
    requested = None if slug is None else str(slug).strip()
    if requested == "":
        raise ValueError("A URL-safe slug is required")
    next_slug = _slugify(requested) if requested else current["slug"]
    clash = repo.find_doc_in_folder(next_folder, next_slug)
    if clash and clash["id"] != current["id"]:
        raise ValueError("A document with that slug already exists in this folder")
    saved = repo.update_doc(
        current["id"],
        folder=next_folder,
        slug=next_slug,
        title=next_title,
        body=next_body,
        editor_user_id=editor_user_id,
    )
    if not saved:
        raise LookupError("Document not found")
    return _public_doc(saved)


def delete_document(doc_id: int) -> None:
    if not repo.delete_doc(doc_id):
        raise LookupError("Document not found")
