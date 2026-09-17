export function isHistoryPosition(position) {
  if (!position || typeof position !== "object") return false;
  if (position.rejected) return true;
  return Boolean(String(position.closed_at || "").trim());
}

export function partitionCompanyPositions(positions) {
  const active = [];
  const history = [];
  for (const position of positions || []) {
    if (isHistoryPosition(position)) history.push(position);
    else active.push(position);
  }
  return { active, history };
}

export function preferredWorkspacePosition(positions) {
  const { active, history } = partitionCompanyPositions(positions);
  const pool = active.length ? active : history;
  return pool.find((p) => p.has_pdf)
    || pool.find((p) => p.has_tailored_tex)
    || pool.find((p) => p.has_cover_letter_pdf)
    || pool.find((p) => p.has_cover_letter_tex)
    || pool.find((p) => p.looking_to_apply || p.pinned)
    || pool[0];
}
