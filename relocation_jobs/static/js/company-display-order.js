/** Calculated company rank vs visible Panel order. */

export function companySortKey(company) {
  return `${company.country}:${company.name}`;
}

export function normalizeTsForSort(ts) {
  const value = (ts || "").trim();
  if (!value) return "0000-00-00T00:00:00";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T00:00:00`;
  return value.replace(/Z$/, "+00:00");
}

export function compareDateDesc(a, b) {
  const av = normalizeTsForSort(a);
  const bv = normalizeTsForSort(b);
  if (av === bv) return 0;
  if (av === "0000-00-00T00:00:00") return 1;
  if (bv === "0000-00-00T00:00:00") return -1;
  return bv.localeCompare(av);
}

export function companyActivityTs(company) {
  return (company?.newest_job_fetched || company?.latest_fetched || "").trim();
}

export function maxJobFetchedTs(jobs) {
  let best = "";
  for (const job of jobs || []) {
    const ts = (job?.fetched || "").trim();
    if (!ts) continue;
    if (!best || compareDateDesc(ts, best) < 0) best = ts;
  }
  return best;
}

/** Match server sort: max job.fetched over open-board roles only. */
export function recomputeNewestJobFetched(company) {
  if (!company) return;
  const ts = maxJobFetchedTs(company.jobs);
  company.newest_job_fetched = ts;
  company.latest_fetched = ts;
}

export function buildFrozenOrderMap(companies) {
  const map = new Map();
  (companies || []).forEach((company, index) => {
    map.set(companySortKey(company), index);
  });
  return map;
}

/**
 * Newest-first visible order.
 * When frozenOrder is set, known companies keep that layout while
 * newest_job_fetched may still change on the company objects.
 */
export function sortCompaniesNewest(companies, {
  frozenOrder = null,
  serverOrder = null,
  isPriority = null,
} = {}) {
  const list = [...(companies || [])];
  list.sort((a, b) => {
    if (isPriority) {
      const aPri = Boolean(isPriority(a));
      const bPri = Boolean(isPriority(b));
      if (aPri !== bPri) return aPri ? -1 : 1;
    }
    if (frozenOrder) {
      const ai = frozenOrder.get(companySortKey(a));
      const bi = frozenOrder.get(companySortKey(b));
      const aKnown = ai !== undefined;
      const bKnown = bi !== undefined;
      if (aKnown && bKnown) return ai - bi;
      if (aKnown !== bKnown) return aKnown ? -1 : 1;
    }
    const byActivity = compareDateDesc(companyActivityTs(a), companyActivityTs(b));
    if (byActivity !== 0) return byActivity;
    if (serverOrder) {
      const ai = serverOrder.get(companySortKey(a));
      const bi = serverOrder.get(companySortKey(b));
      if (ai != null && bi != null) return ai - bi;
    }
    return (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" });
  });
  return list;
}

export function companyHasOpenRoles(company) {
  const open = (company?.jobs || []).length;
  const more = Math.max(0, Number(company?.jobs_more) || 0);
  return open + more > 0;
}
