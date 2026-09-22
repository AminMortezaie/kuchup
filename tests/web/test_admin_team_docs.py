from __future__ import annotations

from pathlib import Path

from relocation_jobs.core.paths import STATIC_DIR
from relocation_jobs.team_docs.service import FOLDERS


def _folder_by_slug(tree: dict, slug: str) -> dict:
    for folder in tree["folders"]:
        if folder["slug"] == slug:
            return folder
    raise AssertionError(f"missing folder {slug}")


def test_admin_docs_pane_is_private_shell():
    html = (Path(STATIC_DIR) / "admin.html").read_text(encoding="utf-8")
    admin_js = (Path(STATIC_DIR) / "js" / "admin.js").read_text(encoding="utf-8")
    shell_js = (Path(STATIC_DIR) / "js" / "app-shell.js").read_text(encoding="utf-8")
    docs_js = (Path(STATIC_DIR) / "js" / "admin-docs.js").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex, nofollow"' in html
    assert 'data-admin-nav="docs"' in html
    assert 'data-admin-pane="docs"' in html
    assert 'id="adminTeamDocs"' in html
    assert ">Admin Docs</span>" in html
    assert ">Admin Docs</h1>" in html
    assert "./admin-docs.js" in admin_js
    assert '"docs"' in shell_js
    assert 'raw.split("/")[0]' in shell_js
    assert "admin-docs-index" in docs_js
    assert "admin-docs-row" in docs_js
    assert "No docs yet" in docs_js
    assert "admin-docs-new" in docs_js
    assert 'data-folder="${escapeAttr(folder.slug)}"' in docs_js
    assert "admin-docs-prose" in docs_js
    assert 'id="adminDocsEdit"' in docs_js
    assert "admin-docs-cancel" in docs_js


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
        json={"folder": "product", "title": "Secret", "body": "nope"},
    )
    assert created.status_code == 403
    assert created.get_json()["error"] == "Admin access required"


def test_team_docs_seed_root_folders(v2_auth_client, db):
    del db
    tree = v2_auth_client.get("/api/admin/team-docs")
    assert tree.status_code == 200
    folders = tree.get_json()["folders"]
    assert [folder["path"] for folder in folders] == [f"/{slug}" for slug in FOLDERS]
    assert all(folder["docs"] == [] for folder in folders)


def test_team_docs_crud_happy_path(v2_auth_client, db):
    del db
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={
            "folder": "product",
            "title": "Launch checklist",
            "body": "# Launch\n\n- [ ] ship docs",
        },
    )
    assert created.status_code == 201
    doc = created.get_json()["doc"]
    assert doc["slug"] == "launch-checklist"
    assert doc["path"] == "/product/launch-checklist"
    assert doc["body"] == "# Launch\n\n- [ ] ship docs"
    assert "<h1>Launch</h1>" in doc["html"]
    assert "<li>[ ] ship docs</li>" in doc["html"]

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
    assert saved["html"] == "<p>shipped</p>"

    deleted = v2_auth_client.delete(f"/api/admin/team-docs/{doc['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    missing = v2_auth_client.get(f"/api/admin/team-docs/{doc['id']}")
    assert missing.status_code == 404
    empty = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "product")
    assert empty["docs"] == []


def test_team_docs_reader_html_is_admin_only(v2_auth_client, test_user, db):
    del db
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={
            "folder": "tech",
            "title": "Launch note",
            "body": (
                "# Hello\n\n**safe**\n\n<script>alert(1)</script>\n\n"
                "[bad](javascript:alert(1))\n\n"
                '<img src=x onerror="alert(1)">'
            ),
        },
    )
    assert created.status_code == 201
    doc = created.get_json()["doc"]
    html = doc["html"]
    assert "<h1>Hello</h1>" in html
    assert "<strong>safe</strong>" in html
    assert "<script>" not in html
    assert "<img" not in html
    assert "javascript:" not in html
    assert "&lt;img" in html

    fetched = v2_auth_client.get(f"/api/admin/team-docs/{doc['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["doc"]["html"] == html

    summary = _folder_by_slug(v2_auth_client.get("/api/admin/team-docs").get_json(), "tech")["docs"][0]
    assert "html" not in summary
    assert "body" not in summary

    with v2_auth_client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = test_user["id"]
        sess["username"] = test_user["username"]
        sess.permanent = True
    assert v2_auth_client.get("/api/admin/team-docs").status_code == 403
    blocked = v2_auth_client.get(f"/api/admin/team-docs/{doc['id']}")
    assert blocked.status_code == 403
    assert blocked.get_json()["error"] == "Admin access required"
    patched = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc['id']}",
        json={"body": "hijack"},
    )
    assert patched.status_code == 403


def test_team_docs_move_between_seeded_folders(v2_auth_client, db):
    del db
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "API notes", "body": "wip"},
    )
    doc_id = created.get_json()["doc"]["id"]
    moved = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"folder": "tech"},
    )
    assert moved.status_code == 200
    assert moved.get_json()["doc"]["path"] == "/tech/api-notes"
    listed = v2_auth_client.get("/api/admin/team-docs").get_json()
    assert _folder_by_slug(listed, "product")["docs"] == []
    assert _folder_by_slug(listed, "tech")["docs"][0]["title"] == "API notes"


def test_team_docs_duplicate_slug_rejected(v2_auth_client, db):
    del db
    first = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "Roadmap", "slug": "roadmap"},
    )
    assert first.status_code == 201
    clash = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "Other", "slug": "roadmap"},
    )
    assert clash.status_code == 400
    assert "already exists" in clash.get_json()["error"]


def test_team_docs_folder_docs_sorted_by_slug(v2_auth_client, db):
    del db
    specs = [
        ("zebra-note", "Zebra note"),
        ("alpha-note", "Alpha note"),
        ("middle-note", "Middle note"),
    ]
    for slug, title in specs:
        res = v2_auth_client.post(
            "/api/admin/team-docs",
            json={"folder": "product", "title": title, "slug": slug},
        )
        assert res.status_code == 201

    listed = v2_auth_client.get("/api/admin/team-docs").get_json()
    product_docs = _folder_by_slug(listed, "product")["docs"]
    assert [item["slug"] for item in product_docs] == ["alpha-note", "middle-note", "zebra-note"]

    alpha_id = next(item["id"] for item in product_docs if item["slug"] == "alpha-note")
    updated = v2_auth_client.patch(
        f"/api/admin/team-docs/{alpha_id}",
        json={"title": "ZZZ renamed — sorts last by title"},
    )
    assert updated.status_code == 200

    relisted = v2_auth_client.get("/api/admin/team-docs").get_json()
    slugs = [item["slug"] for item in _folder_by_slug(relisted, "product")["docs"]]
    assert slugs == ["alpha-note", "middle-note", "zebra-note"]


def test_team_docs_auto_slug_suffix_and_validation(v2_auth_client, db):
    del db
    first = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "Hello"},
    )
    second = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "Hello"},
    )
    assert first.get_json()["doc"]["slug"] == "hello"
    assert second.status_code == 201
    assert second.get_json()["doc"]["slug"] == "hello-2"
    missing_title = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "  "},
    )
    assert missing_title.status_code == 400
    missing_folder = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "nope", "title": "Nope"},
    )
    assert missing_folder.status_code == 404
    missing_folder_name = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"title": "Nope"},
    )
    assert missing_folder_name.status_code == 400


def test_team_docs_patch_and_delete_missing(v2_auth_client, db):
    del db
    created = v2_auth_client.post(
        "/api/admin/team-docs",
        json={"folder": "product", "title": "Patch me"},
    )
    doc_id = created.get_json()["doc"]["id"]
    bad_slug = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"slug": "!!!"},
    )
    assert bad_slug.status_code == 400
    empty_folder = v2_auth_client.patch(
        f"/api/admin/team-docs/{doc_id}",
        json={"folder": ""},
    )
    assert empty_folder.status_code == 200
    assert empty_folder.get_json()["doc"]["folder"] == "product"
    missing = v2_auth_client.patch("/api/admin/team-docs/999999", json={"title": "Gone"})
    assert missing.status_code == 404
    deleted = v2_auth_client.delete("/api/admin/team-docs/999999")
    assert deleted.status_code == 404
