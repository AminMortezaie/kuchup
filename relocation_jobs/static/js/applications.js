/** Position-centric application queue — active queue + applied history. */

import { $, finishLoadingProgress, setLoadingProgress, toast } from "./utils.js";
import { initAppShell } from "./app-shell.js";

let activeTab = "queue";
let queueJobs = [];
let appliedJobs = [];

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

function jobKey(job) {
  return [
    (job.country || "").toLowerCase(),
    job.company || "",
    job.idempotency_key || job.url || "",
  ].join("|");
}

function isActiveQueueJob(job) {
  if (!job || job.applied) return false;
  return Boolean(job.pinned || job.looking_to_apply);
}

function positionCardVariant(job) {
  if (job.not_for_me) return "not_for_me";
  if (job.rejected) return "rejected";
  return "open";
}

function renderList() {
  const list = $("applicationsList");
  if (!list) return;
  const jobs = activeTab === "applied" ? appliedJobs : queueJobs;
  const empty = activeTab === "applied"
    ? "No applied positions yet."
    : "No positions in your queue. Pin a role or mark Want to apply on the job board.";

  list.replaceChildren();
  if (!jobs.length) {
    setStatus(empty);
    return;
  }
  setStatus("");

  for (const job of jobs) {
    const row = document.createElement("article");
    row.className = "applications-row";
    row.dataset.jobKey = jobKey(job);

    const meta = document.createElement("div");
    meta.className = "applications-row-meta";
    const company = document.createElement("a");
    company.className = "applications-company";
    company.href = job.workspace_path
      || `/company/${encodeURIComponent(job.country || "")}/${encodeURIComponent(String(job.company || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""))}`;
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
}

function syncTabUi() {
  document.querySelectorAll("[data-applications-tab]").forEach((btn) => {
    const selected = btn.dataset.applicationsTab === activeTab;
    btn.classList.toggle("is-active", selected);
    btn.setAttribute("aria-selected", selected ? "true" : "false");
  });
  const queueCount = $("applicationsQueueCount");
  const appliedCount = $("applicationsAppliedCount");
  if (queueCount) queueCount.textContent = String(queueJobs.length);
  if (appliedCount) appliedCount.textContent = String(appliedJobs.length);
}

async function loadQueue() {
  const data = await api("/api/applications/queue");
  queueJobs = Array.isArray(data.jobs) ? data.jobs : [];
}

async function loadApplied() {
  const data = await api("/api/applications/applied");
  appliedJobs = Array.isArray(data.jobs) ? data.jobs : [];
}

async function refreshAll({ quiet = false } = {}) {
  showError("");
  if (!quiet) setLoadingProgress(20);
  try {
    await Promise.all([loadQueue(), loadApplied()]);
    syncTabUi();
    renderList();
  } catch (err) {
    if (err.message !== "Authentication required") {
      showError(err.message || "Failed to load applications");
    }
  } finally {
    if (!quiet) finishLoadingProgress();
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
  if (detail.type !== "mutated") return;

  const job = detail.job || {};
  const key = jobKey(job);
  queueJobs = queueJobs.filter((item) => jobKey(item) !== key);
  appliedJobs = appliedJobs.filter((item) => jobKey(item) !== key);
  if (isActiveQueueJob(job)) queueJobs.unshift(job);
  if (job.applied) appliedJobs.unshift(job);
  syncTabUi();
  renderList();
}

function bindTabs() {
  document.querySelectorAll("[data-applications-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.applicationsTab;
      if (!next || next === activeTab) return;
      activeTab = next;
      syncTabUi();
      renderList();
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
  setLoadingProgress(10);
  const ok = await refreshAuth();
  if (!ok) {
    finishLoadingProgress();
    return;
  }
  await refreshAll();
}

void init();
