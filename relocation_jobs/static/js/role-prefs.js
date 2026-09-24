import { apiFetch } from "./api.js";
import { initAppShell } from "./app-shell.js";
import { setOnUnauthorized } from "./state.js";
import { $, escapeAttr, escapeHtml, toast } from "./utils.js";

let tags = [];
let mine = [];

function chipLabel(keyword) {
  // Keep trailing boundary chars visible (java␠ / java, / java/ / java-).
  return String(keyword || "").replace(/ $/u, "·");
}

function chipHtml(tag, { removable = false } = {}) {
  const on = tag.enabled !== false;
  const label = chipLabel(tag.keyword);
  const remove = removable
    ? `<button type="button" class="role-prefs-chip-remove" data-tag-remove="${tag.id}" aria-label="${escapeAttr("Remove " + tag.keyword)}">×</button>`
    : "";
  if (removable) {
    return `<span class="role-prefs-chip is-on" data-kind="${escapeAttr(tag.kind)}" title="${escapeAttr(tag.keyword)}">${escapeHtml(label)}${remove}</span>`;
  }
  return `<button type="button" class="role-prefs-chip ${on ? "is-on" : "is-off"}" data-tag-toggle="${tag.id}" aria-pressed="${on ? "true" : "false"}" data-kind="${escapeAttr(tag.kind)}" title="${escapeAttr(tag.keyword)}">${escapeHtml(label)}</button>`;
}

function section(label, rows, { removable = false } = {}) {
  if (!rows.length) {
    return `<p class="role-prefs-group">${escapeHtml(label)}</p><p class="role-prefs-empty">None yet</p>`;
  }
  const body = `<div class="role-prefs-chips">${rows.map((tag) => chipHtml(tag, { removable })).join("")}</div>`;
  return `<p class="role-prefs-group">${escapeHtml(label)}</p>${body}`;
}

function renderTags() {
  const list = $("jobPrefsList");
  const status = $("jobPrefsStatus");
  if (!list || !status) return;
  const excludes = tags.filter((tag) => tag.kind === "exclude");
  const includes = tags.filter((tag) => tag.kind === "include");
  const myExcludes = mine.filter((tag) => tag.kind === "exclude");
  const myIncludes = mine.filter((tag) => tag.kind === "include");
  status.hidden = true;
  list.innerHTML = [
    section("Match titles containing", includes),
    section("Hide titles containing", excludes),
    section("My match tags", myIncludes, { removable: true }),
    section("My hide tags", myExcludes, { removable: true }),
  ].join("");
  list.querySelectorAll("[data-tag-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => void saveToggle(btn));
  });
  list.querySelectorAll("[data-tag-remove]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      void removeMine(btn.getAttribute("data-tag-remove"));
    });
  });
}

async function saveToggle(btn) {
  const tagId = btn.getAttribute("data-tag-toggle");
  const enabled = btn.getAttribute("aria-pressed") !== "true";
  const res = await apiFetch(`/api/role-preferences/${tagId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    toast("Could not save that preference");
    return;
  }
  const tag = tags.find((item) => String(item.id) === String(tagId));
  if (tag) tag.enabled = enabled;
  renderTags();
}

async function removeMine(tagId) {
  const res = await apiFetch(`/api/role-preferences/mine/${tagId}`, { method: "DELETE" });
  if (!res.ok) {
    toast("Could not remove that tag");
    return;
  }
  mine = mine.filter((item) => String(item.id) !== String(tagId));
  renderTags();
}

async function loadRolePrefs() {
  const status = $("jobPrefsStatus");
  if (status) {
    status.hidden = false;
    status.textContent = "Loading tags…";
  }
  let res;
  try {
    res = await apiFetch("/api/role-preferences");
  } catch {
    showLogin();
    return;
  }
  if (!res.ok) {
    if (status) status.textContent = "Could not load tags.";
    return;
  }
  showApp();
  const data = await res.json();
  tags = data.tags || [];
  mine = data.mine || [];
  renderTags();
}

function showLogin() {
  const content = $("jobPrefsContent");
  if (content) content.hidden = true;
  const panel = $("jobPrefsLoginPanel");
  if (panel) panel.hidden = false;
  const err = $("jobPrefsLoginError");
  if (err) {
    const params = new URLSearchParams(window.location.search);
    err.textContent = params.get("error") || "";
  }
}

function showApp() {
  const panel = $("jobPrefsLoginPanel");
  if (panel) panel.hidden = true;
  const content = $("jobPrefsContent");
  if (content) content.hidden = false;
}

function bindForm() {
  $("jobPrefsMine")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const keyword = $("jobPrefsKeyword").value;
    const kind = $("jobPrefsKind").value;
    const res = await apiFetch("/api/role-preferences/mine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, kind }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      toast(data.error || "Could not add that tag");
      return;
    }
    $("jobPrefsKeyword").value = "";
    toast("Added to your board filters");
    await loadRolePrefs();
  });
}

async function init() {
  setOnUnauthorized(showLogin);
  initAppShell();
  bindForm();
  await loadRolePrefs();
}

init();
