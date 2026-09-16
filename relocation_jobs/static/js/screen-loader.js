/** Full-screen branded loader — mark + dots, no fake percentage. */

let depth = 0;
let showRaf = null;
let finishTimer = null;

function elements() {
  return {
    root: document.getElementById("screenLoader"),
    label: document.getElementById("screenLoaderLabel"),
  };
}

export function isScreenLoadActive() {
  return depth > 0;
}

export function beginScreenLoad(label = "Loading…") {
  const { root, label: labelEl } = elements();
  if (!root) return;
  if (labelEl) labelEl.textContent = label;
  if (depth > 0) return;

  depth = 1;
  if (finishTimer) {
    clearTimeout(finishTimer);
    finishTimer = null;
  }
  root.hidden = false;
  root.classList.remove("is-done");
  root.setAttribute("aria-hidden", "false");
  document.body.classList.add("screen-loading");
  if (showRaf) cancelAnimationFrame(showRaf);
  showRaf = requestAnimationFrame(() => {
    showRaf = null;
    if (depth > 0) root.classList.add("is-visible");
  });
}

export function endScreenLoad() {
  if (depth === 0) return;
  depth = 0;

  if (showRaf) {
    cancelAnimationFrame(showRaf);
    showRaf = null;
  }
  const { root } = elements();
  if (!root) return;
  root.classList.add("is-done");
  root.classList.remove("is-visible");
  root.hidden = true;
  root.setAttribute("aria-hidden", "true");
  document.body.classList.remove("screen-loading");
  if (finishTimer) clearTimeout(finishTimer);
  finishTimer = window.setTimeout(() => {
    root.classList.remove("is-done");
    finishTimer = null;
  }, 400);
}
