from pathlib import Path


def test_panel_and_add_company_dialog_keep_shell_and_input_responsive():
    root = Path(__file__).resolve().parents[2]
    index = (root / "relocation_jobs/static/index.html").read_text(encoding="utf-8")
    admin = (root / "relocation_jobs/static/admin.html").read_text(encoding="utf-8")
    main_js = (root / "relocation_jobs/static/js/main.js").read_text(encoding="utf-8")
    dialogs = (root / "relocation_jobs/static/js/dialogs.js").read_text(encoding="utf-8")
    data_js = (root / "relocation_jobs/static/js/data.js").read_text(encoding="utf-8")

    assert 'id="mainContent" class="main-content app-shell"' in index
    assert "main-content hidden" not in index
    assert 'id="adminContent" class="admin-content app-shell"' in admin
    assert "admin-content hidden" not in admin

    assert "beginScreenLoad" not in main_js
    assert "noOverlay: true" in main_js
    assert "noOverlay: true" in data_js

    assert "isAddCompanyLocationsPanelOpen" in dialogs
    assert "setTimeout(() => {" in dialogs
    assert "void populateAddCompanyAtsPicker();" in dialogs
    assert "debounce(() => renderAddCompanyLocationOptions()" in dialogs
