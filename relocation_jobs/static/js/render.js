/** HTML rendering for stats, companies, and job rows. */

import { state, findCompany } from "./state.js";
import { applyPanelFilters } from "./board-filter.js";
import { $, escapeHtml, escapeAttr, formatAppliedLabel, formatAppliedHistoryTitle, formatActivityBadge, formatFetchDuration, parseFetchTimestamp, elapsedSecondsBetween, elapsedSecondsSince, atsScoreTone } from "./utils.js";
import {
  saveCollapsedCompanies,
  saveShowNotForMeCompanies,
  saveShowRejectedCompanies,
} from "./storage.js";
import { syncBoardView } from "./board-view.js";
import { updateFetchHeaderUI } from "./fetch-render.js";
import {
  buildFrozenOrderMap,
  companyActivityTs,
  companySortKey,
  compareDateDesc,
  maxJobFetchedTs,
  normalizeTsForSort,
  recomputeNewestJobFetched,
  sortCompaniesNewest,
} from "./company-display-order.js";

export { maxJobFetchedTs, normalizeTsForSort, recomputeNewestJobFetched };

function jobActivityTs(job) {
  return (job?.fetched || job?.last_seen || "").trim();
}

function fetchRunScopeLabel(run) {
  if (run?.company_name) return run.company_name;
  const done = Number(run?.companies_done) || 0;
  const total = Number(run?.companies_total) || 0;
  if (total > 0) return `${done}/${total} companies`;
  return "All companies";
}

function fetchRunStatusLabel(run) {
  if (run?.cancelled) return "Cancelled";
  const code = run?.exit_code;
  if (code === 0 || code == null) return "Complete";
  return `Exit ${code}`;
}

function renderFetchRunsTable(runs) {
  const items = Array.isArray(runs) ? runs : [];
  if (!items.length) {
    return `<p class="stats-fetch-runs-empty">No fetch runs recorded yet.</p>`;
  }
  const rows = items.map((run) => {
    const finished = escapeHtml(formatActivityBadge(run.finished_at || run.started_at || ""));
    const scope = escapeHtml(fetchRunScopeLabel(run));
    const duration = escapeHtml(formatFetchDuration(run.duration_seconds));
    const newJobs = Number(run.new_jobs) || 0;
    const status = escapeHtml(fetchRunStatusLabel(run));
    const statusClass = run.cancelled
      ? "stats-fetch-run-status--cancelled"
      : (run.exit_code === 0 || run.exit_code == null
        ? "stats-fetch-run-status--ok"
        : "stats-fetch-run-status--error");
    return `<tr>
      <td>${finished}</td>
      <td>${scope}</td>
      <td>${duration}</td>
      <td>${newJobs}</td>
      <td><span class="stats-fetch-run-status ${statusClass}">${status}</span></td>
    </tr>`;
  }).join("");
  return `
    <table class="stats-fetch-runs-table">
      <thead>
        <tr>
          <th>Finished</th>
          <th>Scope</th>
          <th>Duration</th>
          <th>New</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function isFetchingCompany(company) {
  return state.fetchBusy && state.fetchingCompanyKey === companySortKey(company);
}

function comparePriorityCompanies(a, b) {
  const aPri = isFetchingCompany(a);
  const bPri = isFetchingCompany(b);
  if (aPri !== bPri) return aPri ? -1 : 1;
  return 0;
}

function compareCompaniesDefault(a, b) {
  const priority = comparePriorityCompanies(a, b);
  if (priority !== 0) return priority;
  if ($("sortNewestFetch")?.checked) {
    return compareDateDesc(companyActivityTs(a), companyActivityTs(b));
  }
  const byCountry = (a.country_label || a.country || "").localeCompare(
    b.country_label || b.country || "",
    undefined,
    { sensitivity: "base" }
  );
  if (byCountry !== 0) return byCountry;
  return (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" });
}

function serverBoardOrderMap() {
  return buildFrozenOrderMap(state.boardCatalog);
}

export function sortCompaniesList(companies) {
  const list = [...companies];
  list.sort(compareCompaniesDefault);
  return list;
}

export function freezeCompanyOrder() {
  if (state.frozenCompanyOrder) return;
  // ponytail: freeze map is catalog indices; snapshot getDisplayCompanies() if catalog/display drift appears
  state.frozenCompanyOrder = buildFrozenOrderMap(state.boardCatalog);
}

export function releaseCompanyOrder() {
  state.frozenCompanyOrder = null;
}

function companyHasNoVisibleJobs(company) {
  const jobCount = company.job_count ?? (company.jobs || []).length ?? 0;
  return jobCount === 0;
}

function companyHasCollapsedPositions(company) {
  return state.collapsedCompanies.has(companySortKey(company));
}

function companyCityLabels(company) {
  const splitJoined = (text) => {
    const trimmed = (text || "").trim();
    if (!trimmed) return [];
    if (trimmed.includes(" · ")) {
      return trimmed.split(" · ").map((part) => part.trim()).filter(Boolean);
    }
    return trimmed.split(",").map((part) => part.trim()).filter(Boolean);
  };
  if (Array.isArray(company.cities) && company.cities.length) {
    const labels = [];
    for (const city of company.cities) {
      labels.push(...splitJoined(city));
    }
    if (labels.length) return labels;
  }
  const single = (company.city || "").trim();
  if (!single) return [];
  return splitJoined(single);
}

function companyLocationLabels(company) {
  const dedupe = (labels) => {
    const seen = new Set();
    const out = [];
    for (const label of labels) {
      const trimmed = (label || "").trim();
      if (!trimmed) continue;
      const key = trimmed.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(trimmed);
    }
    return out;
  };
  if (Array.isArray(company.locations) && company.locations.length) {
    const labels = company.locations.map(
      (loc) => loc.label || `${loc.city} (${loc.country_label || loc.country})`
    );
    const out = [];
    for (const label of labels) {
      const trimmed = (label || "").trim();
      if (!trimmed) continue;
      if (trimmed.includes(" · ")) {
        out.push(...trimmed.split(" · ").map((part) => part.trim()).filter(Boolean));
      } else {
        out.push(trimmed);
      }
    }
    return dedupe(out);
  }
  return dedupe(companyCityLabels(company));
}

function formatCompanyCities(company) {
  const labels = companyLocationLabels(company);
  return labels.length ? labels.join(" · ") : "Set locations";
}

export function filterCompanies() {
  return state.allCompanies.filter((c) => {
    if ($("hideCollapsedCompanies")?.checked && companyHasCollapsedPositions(c)) return false;
    return true;
  });
}

export function getDisplayCompanies() {
  const filtered = applyPanelFilters(filterCompanies());
  if (!$("sortNewestFetch")?.checked) {
    return [...filtered].sort((a, b) => {
      const priority = comparePriorityCompanies(a, b);
      if (priority !== 0) return priority;
      return compareCompaniesDefault(a, b);
    });
  }
  return sortCompaniesNewest(filtered, {
    frozenOrder: state.frozenCompanyOrder,
    serverOrder: serverBoardOrderMap(),
    isPriority: isFetchingCompany,
  });
}

function hasAtsScore(job) {
  return job?.ats_score != null && job?.ats_score !== "";
}

export function sortJobsForDisplay(jobs) {
  const list = jobs || [];
  if (!list.length) return list;

  const scored = [];
  const unscored = [];
  for (const job of list) {
    if (hasAtsScore(job)) scored.push(job);
    else unscored.push(job);
  }

  scored.sort((a, b) => Number(b.ats_score) - Number(a.ats_score));
  return [...scored, ...unscored];
}

export const HIDE_REASONS = [
  { id: "not_for_me", label: "Not for me", desc: "Role doesn't fit your goals", tone: "not-for-me" },
  { id: "expired", label: "Expired", desc: "Posting closed or no longer available", tone: "expired" },
  { id: "wrong_location", label: "Wrong location", desc: "City or region isn't relevant", tone: "wrong-location" },
  { id: "no_relocation", label: "No relocation", desc: "No visa or relocation support", tone: "no-relocation" },
];

export function notForMeReasonMeta(reason) {
  const hit = HIDE_REASONS.find((r) => r.id === reason);
  if (hit) return { label: hit.label, badgeCls: hit.tone };
  return { label: HIDE_REASONS[0].label, badgeCls: HIDE_REASONS[0].tone };
}

export function renderCompanies() {
  syncBoardView();
}
export function toggleCompanyCollapse(key) {
  if (state.collapsedCompanies.has(key)) {
    state.collapsedCompanies.delete(key);
  } else {
    state.collapsedCompanies.add(key);
  }
  saveCollapsedCompanies();
  renderCompanies();
}

export function toggleShowNotForMe(key) {
  if (state.showNotForMeCompanies.has(key)) {
    state.showNotForMeCompanies.delete(key);
  } else {
    state.showNotForMeCompanies.add(key);
    state.collapsedCompanies.delete(key);
    saveCollapsedCompanies();
  }
  saveShowNotForMeCompanies();
  renderCompanies();
}

export function toggleShowRejected(key) {
  if (state.showRejectedCompanies.has(key)) {
    state.showRejectedCompanies.delete(key);
  } else {
    state.showRejectedCompanies.add(key);
    state.collapsedCompanies.delete(key);
    saveCollapsedCompanies();
  }
  saveShowRejectedCompanies();
  renderCompanies();
}

function touchFetchingCompanyTimestamp(companyKey) {
  if (!companyKey) return;
  const company = state.boardCatalog.find((c) => companySortKey(c) === companyKey);
  if (!company) return;
  const ts = new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
  company.updated = ts;
}

export function setFetchBusy(busy, companyKey = null, { countryScope = false, syncBoard = true } = {}) {
  if (!busy) {
    state.fetchBusy = false;
    state.countryFetchActive = false;
    state.fetchingCompanyKey = null;
    state.fetchJobSummary = null;
    state.serverFetchRunning = false;
    $("addCompanyBtn").disabled = false;
    updateFetchHeaderUI();
    if (syncBoard) syncBoardView();
    return;
  }

  freezeCompanyOrder();
  if (busy && companyKey) {
    touchFetchingCompanyTimestamp(companyKey);
  }
  if (countryScope) {
    state.countryFetchActive = true;
    state.fetchBusy = false;
    state.fetchingCompanyKey = null;
  } else {
    state.fetchBusy = true;
    state.countryFetchActive = false;
    state.fetchingCompanyKey = companyKey || null;
  }
  state.serverFetchRunning = true;
  $("addCompanyBtn").disabled = !countryScope && state.fetchBusy;
  updateFetchHeaderUI();
  if (syncBoard) syncBoardView();
}

export function syncFetchJobSummary(st) {
  state.serverFetchRunning = Boolean(st?.running);
  const progress = st?.progress || {};
  state.fetchJobSummary = {
    current: progress.current || 0,
    total: progress.total || (st?.company ? 1 : 0),
    company: progress.company || st?.company || null,
    country: st?.country || null,
    countryLabel: st?.country ? countryLabelFromId(st.country) : "",
    activityMessage: (st?.activity?.message || "").trim(),
    newJobs: Math.max(0, Number(st?.new_jobs_total) || 0),
  };
  state.lastFetchStatus = st;
  // Only refresh the header chip on each poll tick. The board data does not
  // change during polling (it reloads once at completion), so re-rendering the
  // whole company list here just replays the card entrance animation and makes
  // cards visibly jump. The board is re-rendered by setFetchBusy / loadJobs.
  updateFetchHeaderUI();
}

function countryLabelFromId(countryId) {
  const opt = [...($("country")?.options || [])].find((o) => o.value === countryId);
  return opt?.textContent?.trim() || countryId || "";
}

export {
  updateFetchHeaderUI,
  openFetchPanel,
  hideFetchPanel,
  showFetchPanel,
  updateFetchProgress,
  setFetchPanelRunning,
  hideFetchCompletion,
  updateFetchRunMeta,
  showFetchCompletion,
  finishFetchPanel,
  appendFetchLog,
  updateFetchActivity,
  clearFetchReviewContent,
  clearFetchReview,
  setFetchReviewFeedbackDone,
  setFetchReviewFooterPending,
  showFetchReviewFeedback,
  renderFetchReview,
  toggleFetchReviewFilteredExpanded,
  setFetchLogMode,
  normalizeReviewJobs,
  setFetchCancelPending,
  patchRunningFetchPanel,
  showFetchNotice,
  updateFetchCountryResults,
} from "./fetch-render.js";
