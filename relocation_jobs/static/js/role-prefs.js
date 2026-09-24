import { apiFetch } from "./api.js";
import { state } from "./state.js";
import { $, escapeAttr, escapeHtml, toast } from "./utils.js";

let tags = [];

function closeRolePrefs() {
  const dialog = $("jobPrefsDialog");
  if (!dialog) return;
  dialog.classList.remove("open");
  dialog.setAttribute("aria-hidden", "true");
  if (location.hash === "#job-preferences") {
    history.replaceState(null, "", location.pathname + location.search);
  }
}

function renderTags() {
  const list = $("jobPrefsList");
  const status = $("jobPrefsStatus");
  if (!list || !status) return;
  const admin = Boolean(state.authState?.user?.is_admin);
  const excludes = tags.filter((tag) => tag.kind === "exclude");
  const includes = tags.filter((tag) => tag.kind === "include");
  status.hidden = true;
  list.innerHTML = [
    section("Hide titles containing", excludes, admin, true),
    section("Match titles containing", includes, admin, false),
  ].join("");
  list.querySelectorAll("[data-tag-toggle]").forEach((input) => {
    input.addEventListener("change", () => saveToggle(input));
  });
  if (admin) {
    list.querySelectorAll("[data-tag-edit]").forEach((input) => {
      input.addEventListener("change", () => saveEdit(input));
    });
  }
}

function section(label, rows, admin, togglable) {
  const body = rows.map((tag) => rowHtml(tag, admin, togglable)).join("");
  return `<p class="role-prefs-group">${escapeHtml(label)}</p>${body}`;
}

function rowHtml(tag, admin, togglable) {
  const keyword = admin
    ? `<input class="role-prefs-keyword" data-tag-edit="${tag.id}" data-kind="${escapeAttr(tag.kind)}" value="${escapeAttr(tag.keyword)}" />`
    : `<span class="role-prefs-keyword">${escapeHtml(tag.keyword)}</span>`;
  const toggle = togglable
    ? `<input type="checkbox" data-tag-toggle="${tag.id}" ${tag.enabled ? "checked" : ""} aria-label="${escapeAttr("Hide " + tag.keyword)}" />`
    : "";
  return `<div class="role-prefs-row">${keyword}${toggle}</div>`;
}

async function saveToggle(input) {
  const tagId = input.getAttribute("data-tag-toggle");
  const enabled = input.checked;
  const res = await apiFetch(`/api/role-preferences/${tagId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    input.checked = !enabled;
    toast("Could not save that preference");
    return;
  }
  const tag = tags.find((item) => String(item.id) === String(tagId));
  if (tag) tag.enabled = enabled;
  const { loadJobs } = await import("./data.js");
  await loadJobs({ noOverlay: true });
}

async function saveEdit(input) {
  const tagId = input.getAttribute("data-tag-edit");
  const kind = input.getAttribute("data-kind");
  const keyword = input.value;
  const res = await apiFetch(`/api/admin/role-filter-tags/${tagId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, kind }),
  });
  if (!res.ok) {
    toast("Could not update that tag");
    await loadRolePrefs();
    return;
  }
  toast("Tag saved. The next scrape uses it.");
}

async function loadRolePrefs() {
  const status = $("jobPrefsStatus");
  if (status) {
    status.hidden = false;
    status.textContent = "Loading tags…";
  }
  const res = await apiFetch("/api/role-preferences");
  if (!res.ok) {
    if (status) status.textContent = "Could not load tags.";
    return;
  }
  const data = await res.json();
  tags = data.tags || [];
  const adminForm = $("jobPrefsAdmin");
  if (adminForm) adminForm.hidden = !state.authState?.user?.is_admin;
  renderTags();
}

export async function openRolePrefs() {
  const dialog = $("jobPrefsDialog");
  if (!dialog) {
    location.href = "/panel#job-preferences";
    return;
  }
  dialog.classList.add("open");
  dialog.setAttribute("aria-hidden", "false");
  await loadRolePrefs();
}

export function bindRolePrefs() {
  $("jobPrefsBtn")?.addEventListener("click", () => {
    void openRolePrefs();
  });
  $("jobPrefsClose")?.addEventListener("click", closeRolePrefs);
  $("jobPrefsDialog")?.addEventListener("click", (event) => {
    if (event.target === $("jobPrefsDialog")) closeRolePrefs();
  });
  $("jobPrefsAdmin")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const keyword = $("jobPrefsKeyword").value;
    const kind = $("jobPrefsKind").value;
    const res = await apiFetch("/api/admin/role-filter-tags", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword, kind }),
    });
    if (!res.ok) {
      toast("Could not add that tag");
      return;
    }
    $("jobPrefsKeyword").value = "";
    toast("Tag added. The next scrape uses it.");
    await loadRolePrefs();
  });
}

export function openRolePrefsFromHash() {
  if (location.hash === "#job-preferences") void openRolePrefs();
}
