/** Preferences onboarding / settings dialog. */

import { state } from "./state.js";
import { $, escapeHtml } from "./utils.js";
import { loadBoard } from "./board.js";
import { isRemotePanel, panelStorageKey } from "./panel-mode.js";

const PREF_COUNTRY_OPTIONS = [
  ["germany", "Germany"],
  ["netherlands", "Netherlands"],
  ["uk", "United Kingdom"],
  ["portugal", "Portugal"],
  ["ireland", "Ireland"],
];

let dialogBound = false;
let dialogRequired = false;

function dialogEl() {
  return $("preferencesDialog");
}

function selectedCountries() {
  return [...document.querySelectorAll("#preferencesCountryList input[type=checkbox]:checked")]
    .map((el) => el.value);
}

function renderCountryChecks(selected) {
  const list = $("preferencesCountryList");
  if (!list) return;
  const picked = new Set(selected || []);
  list.innerHTML = PREF_COUNTRY_OPTIONS.map(([id, label]) => `
    <label class="pref-check">
      <input type="checkbox" value="${escapeHtml(id)}" ${picked.has(id) ? "checked" : ""} />
      <span>${escapeHtml(label)}</span>
    </label>
  `).join("");
}

export async function fetchPreferences() {
  const res = await fetch("/api/preferences", { credentials: "same-origin" });
  if (!res.ok) throw new Error("Failed to load preferences");
  const data = await res.json();
  state.preferences = data.preferences || {};
  return state.preferences;
}

export async function openPreferencesDialog({ required = false } = {}) {
  ensureDialog();
  const dialog = dialogEl();
  if (!dialog) return;
  dialogRequired = Boolean(required);
  let prefs = state.preferences;
  try {
    prefs = await fetchPreferences();
  } catch {
    prefs = prefs || {};
  }
  const targets = prefs.target_countries?.length
    ? prefs.target_countries
    : ["germany"];
  renderCountryChecks(targets);
  const remoteOk = $("preferencesRemoteOk");
  if (remoteOk) remoteOk.checked = Boolean(prefs.remote_ok);
  const err = $("preferencesError");
  if (err) err.textContent = "";
  const title = $("preferencesTitle");
  if (title) {
    title.textContent = required
      ? "Choose where you want to relocate"
      : "Search preferences";
  }
  const hint = $("preferencesHint");
  if (hint) {
    hint.textContent = required
      ? "We’ll match companies for these countries. You can change this later from the account menu."
      : "Your board filters to matched companies in these countries. Free accounts include a company cap.";
  }
  const cancelBtn = $("preferencesCancelBtn");
  if (cancelBtn) cancelBtn.hidden = dialogRequired;
  dialog.showModal();
}

async function savePreferences(event) {
  event.preventDefault();
  const countries = selectedCountries();
  const err = $("preferencesError");
  if (!countries.length) {
    if (err) err.textContent = "Pick at least one country.";
    return;
  }
  const remoteOk = Boolean($("preferencesRemoteOk")?.checked);
  const saveBtn = $("preferencesSaveBtn");
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = "Matching companies…";
  }
  try {
    const res = await fetch("/api/preferences", {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_countries: countries,
        remote_ok: remoteOk,
        seniority: state.preferences?.seniority || "",
        keywords: state.preferences?.keywords || [],
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || "Could not save preferences");
    }
    state.preferences = data.preferences || {
      target_countries: countries,
      remote_ok: remoteOk,
      preferences_confirmed: true,
    };
    dialogRequired = false;
    dialogEl()?.close();
    const countrySel = $("country");
    if (countrySel && !isRemotePanel() && countries.length) {
      const preferred = countries[0];
      if ([...countrySel.options].some((o) => o.value === preferred)) {
        countrySel.value = preferred;
        localStorage.setItem(panelStorageKey("country"), preferred);
      }
    }
    await loadBoard({ page: 1, requestChanged: true, overlayLabel: "Matching companies…" });
  } catch (exc) {
    if (err) err.textContent = exc.message || "Could not save preferences";
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save preferences";
    }
  }
}

function ensureDialog() {
  if (dialogBound) return;
  const dialog = dialogEl();
  if (!dialog) return;
  dialogBound = true;
  $("preferencesForm")?.addEventListener("submit", savePreferences);
  $("preferencesCancelBtn")?.addEventListener("click", () => {
    if (!dialogRequired) dialog.close();
  });
  dialog.addEventListener("cancel", (event) => {
    if (dialogRequired) event.preventDefault();
  });
}

export async function maybeShowPreferencesOnboarding() {
  if (isRemotePanel()) return;
  try {
    const prefs = await fetchPreferences();
    if (!prefs.preferences_confirmed) {
      await openPreferencesDialog({ required: true });
    }
  } catch {
    /* ignore — board still loads with defaults */
  }
}
