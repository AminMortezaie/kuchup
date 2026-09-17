from __future__ import annotations

from pathlib import Path

from relocation_jobs.core.paths import STATIC_DIR
from relocation_jobs.team_docs.service import ROOT_FOLDER_PATHS


def _folder_by_slug(tree: dict, slug: str) -> dict:
    for folder in tree["folders"]:
        if folder["slug"] == slug:
            return folder
    raise AssertionError(f"missing folder {slug}")


def test_admin_docs_pane_is_private_shell():
    html = (Path(STATIC_DIR) / "admin.html").read_text(encoding="utf-8")
    admin_js = (Path(STATIC_DIR) / "js" / "admin.js").read_text(encoding="utf-8")
    shell_js = (Path(STATIC_DIR) / "js" / "app-shell.js").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex, nofollow"' in html
    assert 'data-admin-nav="docs"' in html
    assert 'data-admin-pane="docs"' in html
    assert 'id="adminTeamDocs"' in html
    assert "./admin-docs.js" in admin_js
    assert '"docs"' in shell_js


def test_team_docs_not_on_sitemap_or_homepage(v2_client):
    sitemap = v2_client.get("/sitemap.xml").get_data(as_text=True)
    robots = v2_client.get("/robots.txt").get_data(as_text=True)
    home = v2_client.get("/").get_data(as_text=True)
    assert "team-docs" not in sitemap
    assert "/admin" not in sitemap
    assert "Disallow: /admin" in robots
    assert "Disallow: /api/" in robots
    assert "/api/admin/team-docs" not in home


def test_team_docs_require_auth(v2_client):
    assert v2_client.get("/api/admin/team-docs").status_code == 401
    assert v2_client.post("/api/admin/team-docs", json={"title": "Nope"}).status_code == 401
    assert v2_client.get("/api/admin/team-docs/1").status_code == 401
    assert v2_client.patch("/api/admin/team-docs/1", json={"title": "Nope"}).status_code == 401
    assert v2_client.delete("/api/admin/team-docs/1").status_code == 401


def test_team_docs_require_admin(v2_client, test_user, db):
    del db
    with v2_client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = test_user["id"]
        sess["username"] = test_user["username"]
        sess.permanent = True
    assert v2_client.get("/api/admin/team-docs").status_code == 403
    created = v2_client.post(
        "/api/admin/team-docs",
        json={"folder_id": 1, "title": "Secret", "body": "nope"},
    )
    assert created.status_code == 403
    assert created.get_json()["error"] == "Admin access required"


def test_team_docs_seed_root_folders(v2_auth_client, db):
    del db
    tree = v2_auth_client.get("/api/admin/team-docs")
    assert tree.status_code == 200
    folders = tree.get_json()["folders"]
    assert [folder["path"] for folder in folders] == list(ROOT_FOLDER_PATHS)
    assert all(folder["docs"] == [] for folder in folders)
    assert all(folder["folders"] == [] for folder in folders)


def test_team_docs_crud_happy_path(v2_auth_client, db):
    del db
    tree = v2_auth_client.get("/api/admin/team-docs").get_json()
    product = _folder_by_slug(tree, "product")
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={
            "folder_id": product["id"],
            "title": "Launch checklist",
            "body": "# Launch\n\n- [ ] ship docs",
        },
    )
    assert created.status_code == 201
    doc = created.get_json()["doc"]
    assert doc["slug"] == "launch-checklist"
    assert doc["path"] == "/product/launch-checklist"
    assert doc["body"] == "# Launch\n\n- [ ] ship docs"

    listed = v2_auth_client.get("/api/admin/team-docs").get_json()
    product_docs = _folder_by_slug(listed, "product")["docs"]
    assert [item["title"] for item in product_docs] == ["Launch checklist"]
    assert "body" not in product_docs[0]

    fetched = v2_auth_client.get(f"/api/admin/team-docs/{doc['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["doc"]["body"] == doc["body"]

    updated = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc['id']}",
        json={"title": "Launch checklist v2", "body": "shipped", "slug": "launch-v2"},
    )
    assert updated.status_code == 200
    saved = updated.get_json()["doc"]
    assert saved["title"] == "Launch checklist v2"
    assert saved["slug"] == "launch-v2"
    assert saved["path"] == "/product/launch-v2"
    assert saved["body"] == "shipped"

    deleted = v2_auth_client.delete(f"/api/admin/team-docs/{doc['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    missing = v2_auth_client.get(f"/api/admin/team-docs/{doc['id']}")
    assert missing.status_code == 404
    empty = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "product")
    assert empty["docs"] == []


def test_team_docs_move_between_seeded_folders(v2_auth_client, db):
    del db
    tree = v2_auth_client.get("/api/admin/team-docs").get_json()
    product = _folder_by_slug(tree, "product")
    tech = _folder_by_slug(tree, "tech")
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "API notes", "body": "wip"},
    )
    doc_id = created.get_json()["doc"]["id"]
    moved = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"folder_id": tech["id"]},
    )
    assert moved.status_code == 200
    assert moved.get_json()["doc"]["path"] == "/tech/api-notes"
    listed = v2_auth_client.get("/api/admin/team-docs").get_json()
    assert _folder_by_slug(listed, "product")["docs"] == []
    assert _folder_by_slug(listed, "tech")["docs"][0]["title"] == "API notes"


def test_team_docs_duplicate_slug_rejected(v2_auth_client, db):
    del db
    product = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "product")
    first = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "Roadmap", "slug": "roadmap"},
    )
    assert first.status_code == 201
    clash = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "Other", "slug": "roadmap"},
    )
    assert clash.status_code == 400
    assert "already exists" in clash.get_json()["error"]


def test_team_docs_auto_slug_suffix_and_validation(v2_auth_client, db):
    del db
    product = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "product")
    first = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "Hello"},
    )
    second = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "Hello"},
    )
    assert first.get_json()["doc"]["slug"] == "hello"
    assert second.status_code == 201
    assert second.get_json()["doc"]["slug"] == "hello-2"
    missing_title = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "  "},
    )
    assert missing_title.status_code == 400
    missing_folder = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": 999999, "title": "Nope"},
    )
    assert missing_folder.status_code == 404
    missing_folder_id = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"title": "Nope"},
    )
    assert missing_folder_id.status_code == 400


def test_team_docs_patch_and_delete_missing(v2_auth_client, db):
    del db
    product = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "product")
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder_id": product["id"], "title": "Patch me"},
    )
    doc_id = created.get_json()["doc"]["id"]
    bad_slug = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"slug": "!!!"},
    )
    assert bad_slug.status_code == 400
    empty_folder = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"folder_id": ""},
    )
    assert empty_folder.status_code == 200
    assert empty_folder.get_json()["doc"]["folder_id"] == product["id"]
    missing = v2_auth_client.patch("/api/admin/team-docs/999999", json={"title": "Gone"})
    assert missing.status_code == 404
    deleted = v2_auth_client.delete("/api/admin/team-docs/999999")
    assert deleted.status_code == 404
