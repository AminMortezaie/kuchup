/** Board capacity / plan strip from API meta. */

import { $, escapeHtml } from "./utils.js";

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

export function renderBoardScopeBanner(meta = {}) {
  const el = $("boardScopeBanner");
  if (!el) return;

  if (Boolean(meta.board_capped)) {
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
  hideBanner(el);
}
