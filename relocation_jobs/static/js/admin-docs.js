import { $, escapeAttr, escapeHtml, formatLocalDateTime, toast } from "./utils.js";

let tree = { folders: [] };
let selected = { folder: null, docId: null };
let mode = "index";
let currentDoc = null;
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

function docIdFromHash() {
  const raw = (window.location.hash || "").replace(/^#/, "");
  const [pane, id] = raw.split("/");
  if (pane !== "docs" || !/^[1-9]\d*$/.test(id || "")) return null;
  return Number(id);
}

function folderTitle(slug) {
  const folder = tree.folders.find((item) => item.slug === slug);
  return folder?.title || slug || "";
}

function whenHtml(value) {
  const label = formatLocalDateTime(value || "");
  if (!label) return "";
  return `<time datetime="${escapeAttr(value || "")}">${escapeHtml(label)}</time>`;
}

function indexHtml() {
  const sections = (tree.folders || []).map((folder) => {
    const docs = folder.docs || [];
    const items = docs.map((doc) => `
      <li>
        <button type="button" class="admin-docs-row" data-doc-id="${Number(doc.id)}">
          ${whenHtml(doc.updated_at)}
          <span class="admin-docs-row-title">${escapeHtml(doc.title)}</span>
        </button>
      </li>`).join("");
    const list = items
      ? `<ol class="admin-docs-index">${items}</ol>`
      : `<p class="admin-docs-empty">No docs yet</p>`;
    return `
      <section class="admin-docs-section">
        <div class="admin-docs-section-head">
          <h2 class="admin-docs-section-label">${escapeHtml(folder.title)}</h2>
          <span class="admin-docs-count">${docs.length}</span>
          <button type="button" class="secondary-btn admin-docs-new" data-folder="${escapeAttr(folder.slug)}">New</button>
        </div>
        ${list}
      </section>`;
  }).join("");
  return `
    <div class="admin-docs-index-page">
      <p class="hint admin-docs-lead">Staff-only notes, grouped by section.</p>
      ${sections || `<p class="hint">No sections yet.</p>`}
    </div>`;
}

function articleHtml(doc) {
  return `
    <article class="admin-docs-article">
      <div class="admin-docs-article-bar">
        <button type="button" class="admin-docs-back" id="adminDocsBack">All docs</button>
        <div class="admin-docs-actions">
          <button type="button" class="primary" id="adminDocsEdit">Edit</button>
        </div>
      </div>
      <p class="admin-docs-kicker">${escapeHtml(folderTitle(doc.folder))}</p>
      <h2 class="admin-docs-title">${escapeHtml(doc.title)}</h2>
      <p class="admin-docs-byline">${whenHtml(doc.updated_at)}</p>
      <div class="admin-docs-prose" id="adminDocsProse"></div>
    </article>`;
}

function editorHtml() {
  const creating = !currentDoc;
  const folderOptions = (tree.folders || []).map((item) => `
    <option value="${escapeAttr(item.slug)}" ${item.slug === (currentDoc?.folder || selected.folder) ? "selected" : ""}>${escapeHtml(item.path)}</option>`).join("");
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
      <label>
        <span>Markdown</span>
        <textarea name="body" rows="18" spellcheck="false" placeholder="# Heading&#10;&#10;Write markdown…"></textarea>
      </label>
      <div class="admin-docs-actions">
        <button type="submit" class="primary">${creating ? "Create" : "Save"}</button>
        <button type="button" class="secondary-btn admin-docs-cancel">Cancel</button>
        <button type="button" class="secondary-btn" id="adminDocsDelete" ${creating ? "hidden" : ""}>Delete</button>
        <p class="hint" id="adminDocsPath"></p>
      </div>
    </form>`;
}

function editorShell() {
  const creating = !currentDoc;
  const kicker = creating ? (folderTitle(selected.folder) || "New") : "Edit";
  const title = creating ? "New doc" : currentDoc.title;
  return `
    <section class="admin-docs-read">
      <p class="admin-docs-kicker">${escapeHtml(kicker)}</p>
      <h2 class="admin-docs-title">${escapeHtml(title)}</h2>
      ${editorHtml()}
    </section>`;
}

function fillForm(doc) {
  const form = $("adminDocsForm");
  if (!form) return;
  form.title.value = doc?.title || "";
  form.slug.value = doc?.slug || "";
  form.body.value = doc?.body || "";
  const folder = doc?.folder || selected.folder;
  if (folder) form.folder.value = folder;
  const path = $("adminDocsPath");
  if (path) path.textContent = doc?.path || "";
}

function bindMount(mount) {
  if (bound) return;
  bound = true;
  mount.addEventListener("click", (event) => {
    if (event.target.closest("#adminDocsDelete")) {
      void deleteSelected();
      return;
    }
    if (event.target.closest(".admin-docs-cancel")) {
      cancelEdit();
      return;
    }
    if (event.target.closest("#adminDocsEdit")) {
      mode = "edit";
      render();
      return;
    }
    if (event.target.closest("#adminDocsBack")) {
      window.location.hash = "docs";
      return;
    }
    const newBtn = event.target.closest(".admin-docs-new");
    if (newBtn) {
      currentDoc = null;
      selected = { folder: newBtn.dataset.folder, docId: null };
      mode = "edit";
      render();
      return;
    }
    const docBtn = event.target.closest("[data-doc-id]");
    if (docBtn) window.location.hash = `docs/${docBtn.dataset.docId}`;
  });
  mount.addEventListener("submit", (event) => {
    if (event.target.id !== "adminDocsForm") return;
    event.preventDefault();
    void saveForm(event.target);
  });
}

function cancelEdit() {
  if (currentDoc) {
    mode = "read";
    render();
    return;
  }
  mode = "index";
  selected = { folder: null, docId: null };
  render();
}

function render() {
  const mount = $("adminTeamDocs");
  if (!mount) return;
  if (mode === "edit") mount.innerHTML = editorShell();
  else if (mode === "read" && currentDoc) mount.innerHTML = articleHtml(currentDoc);
  else mount.innerHTML = indexHtml();
  if (mode === "read" && currentDoc) {
    const prose = $("adminDocsProse");
    if (prose) prose.innerHTML = currentDoc.html || `<p class="hint">This doc is empty.</p>`;
  }
  if (mode === "edit") {
    fillForm(currentDoc);
    mount.querySelector("#adminDocsForm input[name='title']")?.focus();
  }
  bindMount(mount);
}

async function loadSelected() {
  try {
    const data = await apiJson(`/api/admin/team-docs/${selected.docId}`);
    currentDoc = data.doc;
    selected = { folder: data.doc.folder, docId: data.doc.id };
    mode = "read";
    render();
  } catch (err) {
    currentDoc = null;
    selected = { folder: null, docId: null };
    mode = "index";
    render();
    if ((window.location.hash || "") !== "#docs") window.location.hash = "docs";
    toast(err.message || "Could not load document");
  }
}

async function openFromHash() {
  const id = docIdFromHash();
  if (!id) {
    currentDoc = null;
    selected = { folder: null, docId: null };
    mode = "index";
    render();
    return;
  }
  selected.docId = id;
  await loadSelected();
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
    currentDoc = saved.doc;
    selected = { folder: saved.doc.folder, docId: saved.doc.id };
    mode = "read";
    tree = await apiJson("/api/admin/team-docs");
    render();
    const next = `#docs/${saved.doc.id}`;
    if (window.location.hash !== next) window.location.hash = `docs/${saved.doc.id}`;
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
    tree = await apiJson("/api/admin/team-docs");
    currentDoc = null;
    selected = { folder: null, docId: null };
    mode = "index";
    render();
    if (window.location.hash !== "#docs") window.location.hash = "docs";
    toast("Deleted");
  } catch (err) {
    toast(err.message || "Could not delete");
  }
}

export async function syncTeamDocsHash() {
  const id = docIdFromHash();
  if (id && mode === "read" && currentDoc?.id === id) return;
  if (!id && mode === "index") return;
  await openFromHash();
}

export async function loadTeamDocsPane() {
  tree = await apiJson("/api/admin/team-docs");
  await openFromHash();
}
