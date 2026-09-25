/** Position-centric application states — Apply / Applied / Rejected (paginated). */

import {
  $,
  beginTopLoadingProgress,
  finishLoadingProgress,
  toast,
} from "./utils.js";
import { beginScreenLoad, endScreenLoad } from "./screen-loader.js";
import { initAppShell } from "./app-shell.js";
import { companyWorkspacePath } from "./company-workspace.js";

const PAGE_SIZE = 20;
const TABS = ["queue", "applied", "rejected"];

const EMPTY_COPY = {
  queue: "No positions waiting for application. Pin a role on the job board.",
  applied: "No active applications.",
  rejected: "No rejected applications.",
};

const LIST_PATH = {
  queue: "/api/applications/queue",
  applied: "/api/applications/applied",
  rejected: "/api/applications/rejected",
};

let activeTab = "queue";
const tabState = {
  queue: emptyTabState(),
  applied: emptyTabState(),
  rejected: emptyTabState(),
};
let counts = { apply: 0, applied: 0, rejected: 0 };
let countsLoaded = false;

function emptyTabState() {
  return {
    jobs: [],
    page: 1,
    total: 0,
    totalPages: 1,
    loaded: false,
    loading: false,
    error: "",
  };
}

function showLogin() {
  const content = $("applicationsContent");
  if (content) content.hidden = true;
  $("applicationsLoginPanel").hidden = false;
  const params = new URLSearchParams(window.location.search);
  const err = $("applicationsLoginError");
  if (err) err.textContent = params.get("error") || "";
}

function showApp() {
  $("applicationsLoginPanel").hidden = true;
  const content = $("applicationsContent");
  if (content) content.hidden = false;
}

function showError(message) {
  const el = $("applicationsError");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function setStatus(message) {
  const el = $("applicationsStatus");
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

async function api(path) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (res.status === 401) {
    showLogin();
    throw new Error("Authentication required");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function positionCardVariant(job) {
  if (job.not_for_me) return "not_for_me";
  if (job.rejected) return "rejected";
  return "open";
}

function syncTabUi() {
  document.querySelectorAll("[data-applications-tab]").forEach((btn) => {
    const selected = btn.dataset.applicationsTab === activeTab;
    btn.classList.toggle("is-active", selected);
    btn.setAttribute("aria-selected", selected ? "true" : "false");
  });
  const queueCount = $("applicationsQueueCount");
  const appliedCount = $("applicationsAppliedCount");
  const rejectedCount = $("applicationsRejectedCount");
  if (queueCount) {
    queueCount.textContent = countsLoaded ? String(counts.apply) : "—";
  }
  if (appliedCount) {
    appliedCount.textContent = countsLoaded ? String(counts.applied) : "—";
  }
  if (rejectedCount) {
    rejectedCount.textContent = countsLoaded ? String(counts.rejected) : "—";
  }
}

/** Same window as frontend/src/BoardPagination.jsx — Prev + ≤5 slots + Next. */
function pageRange(current, total) {
  if (total <= 5) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  if (current <= 3) return [1, 2, 3, "…", total];
  if (current >= total - 2) return [1, "…", total - 2, total - 1, total];
  return [1, "…", current, "…", total];
}

function goToPage(page) {
  void loadTab(activeTab, { page, force: true });
}

function renderPagination(state) {
  const root = $("applicationsPagination");
  if (!root) return;
  root.replaceChildren();
  if (!state.loaded || state.totalPages <= 1) return;

  const nav = document.createElement("nav");
  nav.className = "board-pagination applications-pagination";
  nav.setAttribute("aria-label", "Application pages");

  const summary = document.createElement("p");
  summary.className = "board-pagination-summary";
  const start = state.total ? (state.page - 1) * PAGE_SIZE + 1 : 0;
  const end = state.total ? Math.min(state.page * PAGE_SIZE, state.total) : 0;
  summary.textContent = `Page ${state.page} of ${state.totalPages} · ${start}–${end} of ${state.total}`;

  const controls = document.createElement("div");
  controls.className = "board-pagination-controls";

  const prev = document.createElement("button");
  prev.type = "button";
  prev.className = "filter-btn board-page-nav";
  prev.textContent = "Previous";
  prev.disabled = state.loading || state.page <= 1;
  prev.addEventListener("click", () => goToPage(state.page - 1));

  const pages = document.createElement("div");
  pages.className = "board-pagination-pages";
  for (const item of pageRange(state.page, state.totalPages)) {
    if (typeof item === "number") {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `filter-btn board-page-num${item === state.page ? " is-active" : ""}`;
      btn.textContent = String(item);
      btn.disabled = state.loading || item === state.page;
      if (item === state.page) btn.setAttribute("aria-current", "page");
      btn.addEventListener("click", () => goToPage(item));
      pages.appendChild(btn);
    } else {
      const gap = document.createElement("span");
      gap.className = "board-page-gap";
      gap.setAttribute("aria-hidden", "true");
      gap.textContent = item;
      pages.appendChild(gap);
    }
  }

  const next = document.createElement("button");
  next.type = "button";
  next.className = "filter-btn board-page-nav";
  next.textContent = "Next";
  next.disabled = state.loading || state.page >= state.totalPages;
  next.addEventListener("click", () => goToPage(state.page + 1));

  controls.append(prev, pages, next);
  nav.append(summary, controls);
  root.appendChild(nav);
}

function renderList() {
  const list = $("applicationsList");
  if (!list) return;
  const state = tabState[activeTab];
  list.replaceChildren();
  showError(state.error || "");

  if (state.loading && !state.loaded) {
    setStatus("");
    renderPagination(state);
    return;
  }
  if (!state.jobs.length) {
    setStatus(EMPTY_COPY[activeTab] || "Nothing here yet.");
    renderPagination(state);
    return;
  }
  setStatus("");

  for (const job of state.jobs) {
    const row = document.createElement("article");
    row.className = "applications-row";

    const meta = document.createElement("div");
    meta.className = "applications-row-meta";
    const company = document.createElement("a");
    company.className = "applications-company";
    company.href = job.workspace_path || companyWorkspacePath(job.country, job.company);
    company.textContent = job.company || "Company";
    const place = document.createElement("span");
    place.className = "applications-place";
    place.textContent = [job.country_label || job.country, job.job_city || job.location]
      .filter(Boolean)
      .join(" · ");
    meta.append(company, place);

    const cardHost = document.createElement("div");
    cardHost.className = "applications-card-host";
    const card = document.createElement("position-card");
    card.job = job;
    card.variant = positionCardVariant(job);
    cardHost.appendChild(card);

    row.append(meta, cardHost);
    list.appendChild(row);
  }
  renderPagination(state);
}

async function loadCounts() {
  const data = await api("/api/applications/counts");
  counts = {
    apply: Number(data.apply) || 0,
    applied: Number(data.applied) || 0,
    rejected: Number(data.rejected) || 0,
  };
  countsLoaded = true;
  syncTabUi();
}

async function loadTab(tab, { page = 1, force = false, quiet = false } = {}) {
  if (!TABS.includes(tab)) return;
  const state = tabState[tab];
  if (state.loading) return;
  if (state.loaded && !force && state.page === page) {
    if (tab === activeTab) renderList();
    return;
  }
  state.loading = true;
  state.error = "";
  if (tab === activeTab) renderList();

  let useOverlay = false;
  let useBar = false;
  if (!quiet && tab === activeTab) {
    if (!state.loaded) {
      beginScreenLoad();
      useOverlay = true;
    } else {
      beginTopLoadingProgress();
      useBar = true;
    }
  }

  let finishedLoading = false;
  const finishLoading = () => {
    if (finishedLoading) return;
    finishedLoading = true;
    if (useOverlay) endScreenLoad();
    else if (useBar) finishLoadingProgress();
  };

  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    const data = await api(`${LIST_PATH[tab]}?${params}`);
    const meta = data.meta || {};
    state.jobs = Array.isArray(data.jobs) ? data.jobs : [];
    state.page = Number(meta.page) || page;
    state.total = Number(meta.total) || 0;
    state.totalPages = Number(meta.total_pages) || 1;
    state.loaded = true;
    if (!state.jobs.length && state.page > 1) {
      const fallback = Math.max(1, Math.min(state.page - 1, state.totalPages));
      if (fallback !== state.page) {
        state.loading = false;
        finishLoading();
        await loadTab(tab, { page: fallback, force: true, quiet });
        return;
      }
    }
  } catch (err) {
    if (err.message !== "Authentication required") {
      state.error = err.message || "Failed to load applications";
    }
  } finally {
    state.loading = false;
    finishLoading();
    if (tab === activeTab) {
      renderList();
      const body = document.querySelector(".applications-page-body");
      if (body && force) body.scrollTop = 0;
    }
  }
}

async function refreshAfterMutation() {
  showError("");
  for (const tab of TABS) {
    tabState[tab] = emptyTabState();
  }
  try {
    beginTopLoadingProgress();
    await loadCounts();
    await loadTab(activeTab, { page: 1, force: true, quiet: true });
    finishLoadingProgress();
  } catch (err) {
    finishLoadingProgress();
    if (err.message !== "Authentication required") {
      showError(err.message || "Failed to refresh applications");
    }
  }
}

function onPositionStateChanged(event) {
  const detail = event.detail || {};
  if (detail.type === "auth-required") {
    showLogin();
    return;
  }
  if (detail.type === "toast" && detail.message) {
    toast(detail.message);
    return;
  }
  if (detail.type === "error" && detail.message) {
    showError(detail.message);
    return;
  }
  if (detail.type === "mutated") void refreshAfterMutation();
}

function bindTabs() {
  document.querySelectorAll("[data-applications-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.applicationsTab;
      if (!next || next === activeTab || !TABS.includes(next)) return;
      activeTab = next;
      syncTabUi();
      void loadTab(activeTab, { page: tabState[activeTab].page || 1 });
    });
  });
}

async function refreshAuth() {
  const res = await fetch("/api/auth/status", { credentials: "same-origin" });
  const data = await res.json().catch(() => ({}));
  if (!data.authenticated) {
    showLogin();
    return false;
  }
  showApp();
  return true;
}

async function init() {
  initAppShell();
  bindTabs();
  document.addEventListener("position-state-changed", onPositionStateChanged);
  beginScreenLoad();
  const ok = await refreshAuth();
  if (!ok) {
    endScreenLoad();
    return;
  }
  syncTabUi();
  try {
    await loadCounts();
    await loadTab(activeTab, { page: 1, force: true, quiet: true });
  } catch (err) {
    if (err.message !== "Authentication required") {
      showError(err.message || "Failed to load applications");
    }
  } finally {
    endScreenLoad();
  }
}

void init();
