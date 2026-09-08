/** Board capacity / plan strip from API meta. */

import { $, escapeHtml } from "./utils.js";
import { isRemotePanel } from "./panel-mode.js";

const COUNTRY_LABELS = {
  germany: "Germany",
  netherlands: "Netherlands",
  uk: "United Kingdom",
  portugal: "Portugal",
  ireland: "Ireland",
};

function countryLabel(id) {
  return COUNTRY_LABELS[id] || String(id);
}

function hideBanner(el) {
  el.hidden = true;
  el.replaceChildren();
}

function paintBanner(el, text, actionHtml = "") {
  el.hidden = false;
  el.innerHTML = `
    <p class="board-scope-text">${text}</p>
    ${actionHtml ? `<div class="board-scope-actions">${actionHtml}</div>` : ""}
  `;
}

function unconfirmedCopy(targets) {
  const names = (targets.length ? targets : ["germany"]).map((id) => countryLabel(String(id)));
  return `Matching ${escapeHtml(names.join(", "))}. Change countries from your account menu.`;
}

export function renderBoardScopeBanner(meta = {}) {
  const el = $("boardScopeBanner");
  if (!el) return;
  const remote = isRemotePanel() || meta.catalog_kind === "remote";
  const targets = Array.isArray(meta.target_countries) ? meta.target_countries : [];

  if (!remote && Boolean(meta.board_capped)) {
    paintBanner(
      el,
      "Company board is full",
      `<button type="button" class="board-scope-btn" id="boardScopeUpgradeBtn">Unlock Full Access — $29</button>
       <a class="board-scope-link" href="/pricing">See plans</a>`,
    );
    $("boardScopeUpgradeBtn")?.addEventListener("click", () => {
      import("./credits.js").then((mod) => mod.openCreditsDialog());
    });
    return;
  }
  if (Boolean(meta.positions_capped)) {
    paintBanner(
      el,
      "Next new matched role needs credits",
      `<button type="button" class="board-scope-btn" id="boardScopeCreditsBtn">Add credits</button>
       <button type="button" class="board-scope-btn" id="boardScopeUpgradeBtn">Unlock Full Access — $29</button>`,
    );
    $("boardScopeCreditsBtn")?.addEventListener("click", () => {
      import("./credits.js").then((mod) => mod.openCreditsDialog());
    });
    $("boardScopeUpgradeBtn")?.addEventListener("click", () => {
      import("./credits.js").then((mod) => mod.openCreditsDialog());
    });
    return;
  }
  if (!remote && Boolean(meta.needs_preferences)) {
    paintBanner(el, unconfirmedCopy(targets));
    return;
  }
  hideBanner(el);
}
