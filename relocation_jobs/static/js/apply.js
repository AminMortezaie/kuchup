/** Application data — profile + master resumes + project masters + interview notes for MCP (per logged-in user). */

import { createSlugDocumentEditor } from "./apply-documents.js";
import { $, escapeHtml, finishLoadingProgress, setLoadingProgress } from "./utils.js";

const MAX_PIPELINE_PROMPTS = 5;

function showLogin() {
  const content = $("applyContent");
  if (content) content.hidden = true;
  $("applyLoginPanel").hidden = false;
  const params = new URLSearchParams(window.location.search);
  const err = $("applyLoginError");
  if (err) err.textContent = params.get("error") || "";
}

function showApp() {
  $("applyLoginPanel").hidden = true;
  const content = $("applyContent");
  if (content) content.hidden = false;
}

function showError(message) {
  const el = $("applyError");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function showToast(message) {
  const toast = $("applyToast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...options });
  if (res.status === 401) {
    showLogin();
    throw new Error("Authentication required");
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/pdf")) {
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    return res;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

const editorDeps = { api, showError, showToast };

const masterEditor = createSlugDocumentEditor({
  apiBase: "/api/mcp/master-resumes",
  ids: {
    list: "applyMasterList",
    slug: "applyMasterSlug",
    label: "applyMasterLabel",
    content: "applyMasterContent",
    updated: "applyMasterUpdated",
    downloadPdf: "applyMasterDownloadPdf",
    openPdf: "applyMasterOpenPdf",
    pdfFrame: "applyMasterPdfFrame",
    pdfMissing: "applyMasterPdfMissing",
    renderBtn: "applyMasterRenderBtn",
    saveBtn: "applyMasterSaveBtn",
    newBtn: "applyNewMasterBtn",
  },
  copy: {
    emptyList: "No master resumes yet — create one.",
    slugRequired: "Slug is required (e.g. go, java, fullstack)",
    contentRequired: "LaTeX content cannot be empty",
    renderRequired: "Select or save a master resume before rendering PDF",
    saveFailed: "Failed to save master resume",
    renderFailed: "Failed to re-render PDF",
  },
  defaultPdfFilename: "resume.pdf",
  ...editorDeps,
});

const projectEditor = createSlugDocumentEditor({
  apiBase: "/api/mcp/project-masters",
  ids: {
    list: "applyProjectList",
    slug: "applyProjectSlug",
    label: "applyProjectLabel",
    content: "applyProjectContent",
    updated: "applyProjectUpdated",
    downloadPdf: "applyProjectDownloadPdf",
    openPdf: "applyProjectOpenPdf",
    pdfFrame: "applyProjectPdfFrame",
    pdfMissing: "applyProjectPdfMissing",
    renderBtn: "applyProjectRenderBtn",
    saveBtn: "applyProjectSaveBtn",
    newBtn: "applyNewProjectBtn",
  },
  copy: {
    emptyList: "No project masters yet — create one.",
    slugRequired: "Slug is required (e.g. relocation-jobs)",
    contentRequired: "Project content cannot be empty",
    renderRequired: "Select or save a project master before rendering PDF",
    saveFailed: "Failed to save project master",
    renderFailed: "Failed to re-render PDF",
  },
  defaultPdfFilename: "project.pdf",
  ...editorDeps,
});

const noteEditor = createSlugDocumentEditor({
  apiBase: "/api/mcp/interview-notes",
  ids: {
    list: "applyNoteList",
    slug: "applyNoteSlug",
    label: "applyNoteLabel",
    content: "applyNoteContent",
    updated: "applyNoteUpdated",
    downloadPdf: "applyNoteDownloadPdf",
    openPdf: "applyNoteOpenPdf",
    pdfFrame: "applyNotePdfFrame",
    pdfMissing: "applyNotePdfMissing",
    renderBtn: "applyNoteRenderBtn",
    saveBtn: "applyNoteSaveBtn",
    newBtn: "applyNewNoteBtn",
  },
  copy: {
    emptyList: "No interview notes yet — create one.",
    slugRequired: "Slug is required (e.g. adyen)",
    contentRequired: "Interview notes cannot be empty",
    renderRequired: "Select or save interview notes before rendering PDF",
    saveFailed: "Failed to save interview notes",
    renderFailed: "Failed to re-render PDF",
  },
  defaultPdfFilename: "interview.pdf",
  ...editorDeps,
});

function setTab(tab) {
  for (const btn of document.querySelectorAll(".apply-tab")) {
    btn.classList.toggle("apply-tab--active", btn.dataset.tab === tab);
  }
  const profile = $("applyProfilePanel");
  const masters = $("applyMastersPanel");
  const projects = $("applyProjectsPanel");
  const notes = $("applyNotesPanel");
  const connect = $("applyConnectPanel");
  if (profile) profile.hidden = tab !== "profile";
  if (masters) masters.hidden = tab !== "masters";
  if (projects) projects.hidden = tab !== "projects";
  if (notes) notes.hidden = tab !== "notes";
  if (connect) connect.hidden = tab !== "connect";

  const active = document.querySelector(`.apply-tab[data-tab="${tab}"]`);
  const rail = active?.closest(".tab-rail");
  if (active && rail) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const railRect = rail.getBoundingClientRect();
    const btnRect = active.getBoundingClientRect();
    if (btnRect.left < railRect.left || btnRect.right > railRect.right) {
      rail.scrollBy({
        left: btnRect.left - railRect.left - 12,
        behavior: reduceMotion ? "auto" : "smooth",
      });
    }
  }

  if (tab === "connect") {
    loadConnectPanel().catch((err) => showError(err.message || "Failed to load MCP connect info"));
  }

  if (tab === "masters") masterEditor.resyncPreview();
  if (tab === "projects") projectEditor.resyncPreview();
  if (tab === "notes") noteEditor.resyncPreview();
}

function fillProfileForm(profile) {
  $("profileFullName").value = profile.full_name || "";
  $("profileEmail").value = profile.email || "";
  $("profilePhone").value = profile.phone || "";
  $("profileLinkedin").value = profile.linkedin_url || "";
  $("profileLocation").value = profile.location || "";
  $("profileWorkAuth").value = profile.work_authorization || "";
  $("profileNotice").value = profile.notice_period || "";
  $("profileSummary").value = profile.summary || "";
  renderPipelineList(Array.isArray(profile.pipeline) ? profile.pipeline : []);
}

function pipelineFromForm({ includeEmpty = false } = {}) {
  const items = document.querySelectorAll(".apply-pipeline-item textarea");
  const values = Array.from(items).map((el) => el.value.trim());
  return includeEmpty ? values : values.filter(Boolean);
}

function renderPipelineList(prompts) {
  const list = $("applyPipelineList");
  const addBtn = $("applyPipelineAddBtn");
  if (!list) return;

  const items = prompts.slice(0, MAX_PIPELINE_PROMPTS);
  if (!items.length) {
    list.innerHTML = `<p class="apply-pipeline-empty">No pipeline prompts yet.</p>`;
  } else {
    list.innerHTML = items.map((text, index) => `
      <div class="apply-pipeline-item">
        <div class="apply-pipeline-item-header">
          <label for="applyPipeline${index}">Prompt ${index + 1}</label>
          <div class="apply-pipeline-item-actions">
            <div class="apply-pipeline-reorder">
              <button type="button" class="apply-pipeline-move" data-index="${index}" data-dir="-1" aria-label="Move prompt ${index + 1} up"${index === 0 ? " disabled" : ""}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="18 15 12 9 6 15"/></svg>
              </button>
              <button type="button" class="apply-pipeline-move" data-index="${index}" data-dir="1" aria-label="Move prompt ${index + 1} down"${index === items.length - 1 ? " disabled" : ""}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
              </button>
            </div>
            <button type="button" class="link-btn apply-pipeline-remove" data-index="${index}" aria-label="Remove prompt ${index + 1}">Remove</button>
          </div>
        </div>
        <textarea id="applyPipeline${index}" class="apply-pipeline-textarea" rows="3" placeholder="Instructions for Claude before reframing">${escapeHtml(text)}</textarea>
      </div>
    `).join("");
  }

  if (addBtn) {
    addBtn.disabled = items.length >= MAX_PIPELINE_PROMPTS;
    addBtn.hidden = items.length >= MAX_PIPELINE_PROMPTS;
  }
}

function addPipelinePrompt() {
  const prompts = pipelineFromForm({ includeEmpty: true });
  if (prompts.length >= MAX_PIPELINE_PROMPTS) return;
  prompts.push("");
  renderPipelineList(prompts);
  const textareas = document.querySelectorAll(".apply-pipeline-item textarea");
  textareas[textareas.length - 1]?.focus();
}

function removePipelinePrompt(index) {
  const prompts = pipelineFromForm({ includeEmpty: true });
  prompts.splice(index, 1);
  renderPipelineList(prompts);
}

function movePipelinePrompt(index, delta) {
  const prompts = pipelineFromForm({ includeEmpty: true });
  const target = index + delta;
  if (target < 0 || target >= prompts.length) return;
  [prompts[index], prompts[target]] = [prompts[target], prompts[index]];
  renderPipelineList(prompts);
}

function profilePayload() {
  return {
    full_name: $("profileFullName").value.trim(),
    email: $("profileEmail").value.trim(),
    phone: $("profilePhone").value.trim(),
    linkedin_url: $("profileLinkedin").value.trim(),
    location: $("profileLocation").value.trim(),
    work_authorization: $("profileWorkAuth").value.trim(),
    notice_period: $("profileNotice").value.trim(),
    summary: $("profileSummary").value.trim(),
    pipeline: pipelineFromForm(),
  };
}

async function saveProfile(event) {
  event.preventDefault();
  showError("");
  const btn = $("applyProfileSaveBtn");
  btn.disabled = true;
  try {
    await api("/api/mcp/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profilePayload()),
    });
    showToast("Profile saved");
  } catch (err) {
    showError(err.message || "Failed to save profile");
  } finally {
    btn.disabled = false;
  }
}

async function loadData() {
  showError("");
  setLoadingProgress(15);
  try {
    const [profileData, mastersData, projectsData, notesData] = await Promise.all([
      api("/api/mcp/profile"),
      api("/api/mcp/master-resumes"),
      api("/api/mcp/project-masters"),
      api("/api/mcp/interview-notes"),
    ]);
    fillProfileForm(profileData.profile || {});
    masterEditor.replaceItems(mastersData.items || []);
    projectEditor.replaceItems(projectsData.items || []);
    noteEditor.replaceItems(notesData.items || []);
    await masterEditor.loadFirstIfNeeded();
    await projectEditor.loadFirstIfNeeded();
    await noteEditor.loadFirstIfNeeded();
  } finally {
    finishLoadingProgress();
  }
}

async function refreshAuth() {
  const res = await fetch("/api/auth/status", { credentials: "same-origin" });
  const data = await res.json();
  if (!data.authenticated) {
    showLogin();
    return false;
  }
  showApp();
  return true;
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  masterEditor.reset();
  projectEditor.reset();
  noteEditor.reset();
  showLogin();
}

async function loadConnectPanel() {
  const info = await api("/api/mcp/connect-info");
  const urlInput = $("applyMcpUrl");
  if (urlInput) urlInput.value = info.mcp_url || "";
  const quota = $("applyMcpQuotaHint");
  const ent = info.entitlements || {};
  if (quota) {
    if (ent.mcp_daily_limit == null) {
      quota.textContent = "MCP write/render quota: unlimited on your plan.";
    } else {
      const remaining = ent.mcp_daily_remaining ?? 0;
      const limit = ent.mcp_daily_limit;
      const plan = ent.plan || "free";
      quota.innerHTML =
        `Free/Full MCP quota: <strong>${remaining}</strong> of ${limit} write/render requests left today (plan: ${escapeHtml(plan)}). `
        + `Saving masters and rendering PDFs consume this budget. `
        + `<a href="/pricing">See plans</a> · <a href="/mcp">How MCP works</a>`;
    }
  }
  await refreshTokenList();
}

async function refreshTokenList() {
  const data = await api("/api/mcp/tokens");
  const list = $("applyTokenList");
  if (!list) return;
  const items = data.items || [];
  if (!items.length) {
    list.innerHTML = '<li class="apply-pipeline-empty">No API tokens yet.</li>';
    return;
  }
  list.innerHTML = items
    .map((item) => {
      const status = item.revoked ? "Revoked" : "Active";
      const revoke = item.revoked
        ? ""
        : `<button type="button" class="link-btn apply-token-revoke" data-id="${item.id}">Revoke</button>`;
      return `<li class="apply-token-item">
        <span class="apply-token-meta">${escapeHtml(item.label || "Untitled")} · ${escapeHtml(status)} · ${escapeHtml(item.created_at || "")}</span>
        ${revoke}
      </li>`;
    })
    .join("");
}

async function createApiToken() {
  const label = ($("applyTokenLabel")?.value || "").trim();
  const data = await api("/api/mcp/tokens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const once = $("applyTokenOnce");
  const value = $("applyTokenOnceValue");
  if (once && value) {
    value.textContent = data.token || "";
    once.hidden = false;
  }
  if ($("applyTokenLabel")) $("applyTokenLabel").value = "";
  await refreshTokenList();
  showToast("Token created — copy it now");
}

async function revokeApiToken(tokenId) {
  await api(`/api/mcp/tokens/${tokenId}`, { method: "DELETE" });
  showToast("Token revoked");
  await refreshTokenList();
}

async function copyText(value, okMessage) {
  if (!value) return;
  await navigator.clipboard.writeText(value);
  showToast(okMessage);
}

function bindEvents() {
  $("applyLogoutBtn")?.addEventListener("click", logout);
  $("applyProfileForm")?.addEventListener("submit", saveProfile);
  $("applyPipelineAddBtn")?.addEventListener("click", addPipelinePrompt);
  $("applyPipelineList")?.addEventListener("click", (e) => {
    const removeBtn = e.target.closest(".apply-pipeline-remove");
    if (removeBtn) {
      removePipelinePrompt(Number(removeBtn.dataset.index));
      return;
    }
    const moveBtn = e.target.closest(".apply-pipeline-move");
    if (!moveBtn || moveBtn.disabled) return;
    movePipelinePrompt(Number(moveBtn.dataset.index), Number(moveBtn.dataset.dir));
  });
  masterEditor.bind();
  projectEditor.bind();
  noteEditor.bind();

  for (const tabBtn of document.querySelectorAll(".apply-tab")) {
    tabBtn.addEventListener("click", () => setTab(tabBtn.dataset.tab));
  }

  $("applyMcpUrlCopyBtn")?.addEventListener("click", () => {
    copyText($("applyMcpUrl")?.value || "", "MCP URL copied");
  });
  $("applyTokenCreateBtn")?.addEventListener("click", () => {
    createApiToken().catch((err) => showError(err.message || "Failed to create token"));
  });
  $("applyTokenOnceCopyBtn")?.addEventListener("click", () => {
    copyText($("applyTokenOnceValue")?.textContent || "", "Token copied");
  });
  $("applyTokenList")?.addEventListener("click", (e) => {
    const btn = e.target.closest(".apply-token-revoke");
    if (!btn) return;
    revokeApiToken(Number(btn.dataset.id)).catch((err) => showError(err.message || "Failed to revoke token"));
  });
}

async function init() {
  bindEvents();
  if (await refreshAuth()) {
    try {
      await loadData();
      const tab = new URLSearchParams(window.location.search).get("tab");
      if (tab === "connect" || tab === "masters" || tab === "projects" || tab === "notes" || tab === "profile") {
        setTab(tab);
      }
    } catch (err) {
      showError(err.message || "Failed to load application data");
    }
  }
}

init();
