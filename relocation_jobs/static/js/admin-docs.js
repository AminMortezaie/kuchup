import { $, escapeHtml, toast } from "./utils.js";

let tree = { folders: [] };
let selected = { folder: null, docId: null };
let bound = false;

async function apiJson(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function selectedFolder() {
  return tree.folders.find((folder) => folder.slug === selected.folder) || null;
}

function renderTree(folders) {
  return (folders || []).map((folder) => {
    const activeFolder = selected.folder === folder.slug && !selected.docId;
    const docs = (folder.docs || []).map((doc) => {
      const active = selected.docId === doc.id;
      return `
        <button type="button" class="admin-docs-item${active ? " is-active" : ""}" data-doc-id="${doc.id}" data-folder="${escapeHtml(folder.slug)}">
          ${escapeHtml(doc.title)}
        </button>`;
    }).join("");
    return `
      <div class="admin-docs-folder">
        <div class="admin-docs-folder-row">
          <button type="button" class="admin-docs-folder-btn${activeFolder ? " is-active" : ""}" data-folder="${escapeHtml(folder.slug)}">
            ${escapeHtml(folder.path)}
          </button>
          <button type="button" class="secondary-btn admin-docs-new" data-folder="${escapeHtml(folder.slug)}">New</button>
        </div>
        <div class="admin-docs-children">
          ${docs || `<p class="hint admin-docs-empty">Empty folder</p>`}
        </div>
      </div>`;
  }).join("");
}

function editorHtml() {
  const folder = selectedFolder();
  const folderOptions = tree.folders.map((item) => (
    `<option value="${escapeHtml(item.slug)}" ${item.slug === selected.folder ? "selected" : ""}>${escapeHtml(item.path)}</option>`
  )).join("");
  if (!folder) {
    return `<p class="hint">Select a folder to add a markdown doc, or open an existing one.</p>`;
  }
  const creating = !selected.docId;
  return `
    <form class="admin-docs-form" id="adminDocsForm">
      <label>
        <span>Folder</span>
        <select name="folder">${folderOptions}</select>
      </label>
      <label>
        <span>Title</span>
        <input name="title" type="text" maxlength="200" required placeholder="Doc title" />
      </label>
      <label>
        <span>Slug</span>
        <input name="slug" type="text" maxlength="80" placeholder="auto-from-title" ${creating ? "" : "required"} />
      </label>
      <label class="admin-docs-body-label">
        <span>Markdown</span>
        <textarea name="body" rows="18" spellcheck="false" placeholder="# Heading&#10;&#10;Write markdown…"></textarea>
      </label>
      <div class="admin-docs-actions">
        <button type="submit" class="primary">${creating ? "Create" : "Save"}</button>
        <button type="button" class="secondary-btn" id="adminDocsDelete" ${creating ? "hidden" : ""}>Delete</button>
        <p class="hint" id="adminDocsPath"></p>
      </div>
    </form>`;
}

function fillForm(doc) {
  const form = $("adminDocsForm");
  if (!form) return;
  form.title.value = doc?.title || "";
  form.slug.value = doc?.slug || "";
  form.body.value = doc?.body || "";
  if (doc?.folder) form.folder.value = doc.folder;
  const path = $("adminDocsPath");
  if (path) path.textContent = doc?.path || selectedFolder()?.path || "";
}

function bindMount(mount) {
  if (bound) return;
  bound = true;
  mount.addEventListener("click", async (event) => {
    if (event.target.id === "adminDocsDelete") {
      await deleteSelected();
      return;
    }
    const newBtn = event.target.closest(".admin-docs-new");
    if (newBtn) {
      selected = { folder: newBtn.dataset.folder, docId: null };
      render();
      return;
    }
    const docBtn = event.target.closest("[data-doc-id]");
    if (docBtn) {
      selected = { folder: docBtn.dataset.folder, docId: Number(docBtn.dataset.docId) };
      await loadSelected();
      return;
    }
    const folderBtn = event.target.closest("[data-folder].admin-docs-folder-btn");
    if (folderBtn) {
      selected = { folder: folderBtn.dataset.folder, docId: null };
      render();
    }
  });
  mount.addEventListener("submit", async (event) => {
    if (event.target.id !== "adminDocsForm") return;
    event.preventDefault();
    await saveForm(event.target);
  });
}

async function loadSelected() {
  const mount = $("adminTeamDocs");
  if (!selected.docId) {
    render();
    return;
  }
  try {
    const data = await apiJson(`/api/admin/team-docs/${selected.docId}`);
    selected.folder = data.doc.folder;
    render();
    fillForm(data.doc);
  } catch (err) {
    render();
    toast(err.message || "Could not load document");
  }
  mount?.querySelector("#adminDocsForm input[name='title']")?.focus();
}

async function saveForm(form) {
  const payload = {
    folder: form.folder.value,
    title: form.title.value,
    slug: form.slug.value.trim(),
    body: form.body.value,
  };
  if (!payload.slug) delete payload.slug;
  try {
    const creating = !selected.docId;
    const saved = creating
      ? await apiJson("/api/admin/team-docs", {
        method: "POST",
        body: JSON.stringify(payload),
      })
      : await apiJson(`/api/admin/team-docs/${selected.docId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    selected = { folder: saved.doc.folder, docId: saved.doc.id };
    tree = await apiJson("/api/admin/team-docs");
    render();
    fillForm(saved.doc);
    toast(creating ? "Created" : "Saved");
  } catch (err) {
    toast(err.message || "Could not save");
  }
}

async function deleteSelected() {
  if (!selected.docId) return;
  if (!window.confirm("Delete this document?")) return;
  try {
    await apiJson(`/api/admin/team-docs/${selected.docId}`, { method: "DELETE" });
    const folder = selected.folder;
    selected = { folder, docId: null };
    tree = await apiJson("/api/admin/team-docs");
    render();
    toast("Deleted");
  } catch (err) {
    toast(err.message || "Could not delete");
  }
}

function render() {
  const mount = $("adminTeamDocs");
  if (!mount) return;
  mount.innerHTML = `
    <section class="admin-panel admin-docs">
      <div class="admin-docs-tree">
        <h2 class="admin-panel-title">Folders</h2>
        <p class="hint">Staff-only markdown. Empty folders are expected until you add docs.</p>
        ${renderTree(tree.folders) || `<p class="hint">No folders yet.</p>`}
      </div>
      <div class="admin-docs-editor">
        <h2 class="admin-panel-title">${selected.docId ? "Edit markdown" : "New markdown"}</h2>
        ${editorHtml()}
      </div>
    </section>`;
  bindMount(mount);
}

export async function loadTeamDocsPane() {
  tree = await apiJson("/api/admin/team-docs");
  if (!selected.folder && tree.folders[0]) {
    selected = { folder: tree.folders[0].slug, docId: null };
  }
  render();
  if (selected.docId) await loadSelected();
}
