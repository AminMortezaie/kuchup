/** Board capacity / plan strip from API meta. */

import { $, escapeHtml } from "./utils.js";
import { isRemotePanel } from "./panel-mode.js";

export function renderBoardScopeBanner(meta = {}) {
  const el = $("boardScopeBanner");
  if (!el) return;
  const plan = meta.plan || "";
  const upgrade = Boolean(meta.upgrade_available);
  const needsPrefs = Boolean(meta.needs_preferences);
  const targets = Array.isArray(meta.target_countries) ? meta.target_countries : [];
  const remote = isRemotePanel() || meta.catalog_kind === "remote";
  const slotsUsed = meta.company_slots_used;
  const slotsCap = meta.company_slots_cap;
  const creditsTotal = meta.credits_total;
  const creditsFree = meta.credits_promotional;
  const creditsPurchased = meta.credits_purchased;
  const peek = meta.jobs_per_company_peek;
  const positionsCapped = Boolean(meta.positions_capped);
  const boardCapped = Boolean(meta.board_capped);

  const parts = [];
  if (needsPrefs) {
    parts.push("Confirm your target countries so we can match open roles.");
  } else if (!remote && targets.length) {
    parts.push(`Countries: ${targets.map((t) => escapeHtml(String(t))).join(", ")} (any of these).`);
  }
  if (!remote && slotsCap != null && slotsUsed != null) {
    parts.push(
      `Free · ${escapeHtml(String(slotsUsed))}/${escapeHtml(String(slotsCap))} company slots`
      + (peek != null ? ` · up to ${escapeHtml(String(peek))} roles each` : "")
      + (creditsTotal != null
        ? ` · ${escapeHtml(String(creditsTotal))} credits left (${escapeHtml(String(creditsFree || 0))} free + ${escapeHtml(String(creditsPurchased || 0))} purchased)`
        : "")
      + ".",
    );
  } else if (!remote && plan === "free" && slotsCap != null) {
    parts.push(`Free plan · ${escapeHtml(String(slotsCap))} company slots with open roles.`);
  }
  if (remote) {
    parts.push("Remote board is separate from relocation country preferences.");
  }
  if (positionsCapped) {
    parts.push("Tracking still works. Add credits to receive the next matched role.");
  } else if (boardCapped && upgrade) {
    parts.push("Company slots full — Full Access unlocks more companies.");
  } else if (upgrade) {
    parts.push("Full Access removes Free slot and position limits.");
  }

  if (!parts.length) {
    el.hidden = true;
    el.replaceChildren();
    return;
  }

  el.hidden = false;
  el.innerHTML = `
    <p class="board-scope-text">${parts.join(" ")}</p>
    <div class="board-scope-actions">
      <button type="button" class="board-scope-btn" id="boardScopePrefsBtn">Preferences</button>
      ${plan === "free" ? `<button type="button" class="board-scope-btn" id="boardScopeCreditsBtn">Add credits</button>` : ""}
      ${upgrade ? `<a class="board-scope-link" href="/pricing">See plans</a>` : ""}
    </div>
  `;
  $("boardScopePrefsBtn")?.addEventListener("click", () => {
    import("./preferences.js").then((mod) => mod.openPreferencesDialog());
  });
  $("boardScopeCreditsBtn")?.addEventListener("click", () => {
    import("./credits.js").then((mod) => mod.openCreditsDialog());
  });
}
