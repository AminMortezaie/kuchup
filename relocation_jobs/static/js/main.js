/** Application entry point. */

import { setOnUnauthorized, state } from "./state.js";
import { showLogin, refreshAuth, setAdminNavVisible } from "./auth.js";
import { loadConfig, loadCountries, loadAtsTypes, loadBoardWithLocations, showJobsLoading, setLoadingProgress, finishLoadingProgress } from "./data.js";
import { beginScreenLoad } from "./screen-loader.js";
import { bindDialogEvents } from "./dialogs.js";
import { bindEvents, closePanelPopovers } from "./events.js";
import { bindFilterBar, refreshFilterBar } from "./filters.js";
import { bindHeaderBar } from "./header.js";
import { registerFetchActions } from "./fetch-actions.js";
import { publishFetchUi } from "./fetch-ui.js";
import { goToBoardPage } from "./board.js";
import { saveWaitingReferral, markJobSeen } from "./api.js";
import { toast, $ } from "./utils.js";
import { resumeFetchIfRunning, syncFetchStateFromServer } from "./scrape.js";
import { applyPanelChrome } from "./panel-mode.js";
import { initAppShell } from "./app-shell.js";
import { openPreferencesDialog } from "./preferences.js";
import { openCreditsDialog } from "./credits.js";
import {
  loadCollapsedCompanies,
  loadShowNotForMeCompanies,
  loadShowRejectedCompanies,
  loadFilterPreferences,
  loadSortPreference,
} from "./storage.js";

window.relocationJobs = window.relocationJobs || {};
window.relocationJobs.goToBoardPage = goToBoardPage;
window.relocationJobs.saveWaitingReferral = saveWaitingReferral;
window.relocationJobs.markJobSeen = markJobSeen;
window.relocationJobs.closePanelPopovers = closePanelPopovers;
window.relocationJobs.toast = toast;

async function init() {
  setOnUnauthorized(() => showLogin("session"));
  applyPanelChrome();
  initAppShell();

  loadCollapsedCompanies();
  loadShowNotForMeCompanies();
  loadShowRejectedCompanies();
  loadSortPreference();
  loadFilterPreferences();
  applyPanelChrome();

  bindEvents();
  bindDialogEvents();
  bindFilterBar();
  bindHeaderBar();
  registerFetchActions();
  publishFetchUi();
  $("preferencesLink")?.addEventListener("click", () => openPreferencesDialog());
  $("creditsLink")?.addEventListener("click", () => openCreditsDialog());
  document.querySelectorAll("[data-open-credits]").forEach((el) => {
    el.addEventListener("click", () => openCreditsDialog());
  });

  const ok = await refreshAuth();
  if (!ok) return;
  const params = new URLSearchParams(window.location.search);
  const checkoutState = params.get("credits") || params.get("upgrade");
  if (params.has("credits") || params.has("upgrade")) {
    if (checkoutState === "success") {
      toast("Checkout complete. Credits and Full Access apply after the payment confirms.");
    } else if (checkoutState === "cancelled") {
      toast("Checkout cancelled.");
    }
    void openCreditsDialog();
  }

  beginScreenLoad("Loading panel…");
  showJobsLoading();
  setLoadingProgress(10);
  await Promise.all([loadConfig(), loadAtsTypes()]);
  try {
    const { fetchPreferences } = await import("./preferences.js");
    await fetchPreferences();
  } catch {
    /* board still works with defaults */
  }
  await loadCountries();
  setAdminNavVisible(Boolean(state.authState.user?.is_admin));
  setLoadingProgress(40);
  refreshFilterBar();
  await loadBoardWithLocations();
  finishLoadingProgress();
  await resumeFetchIfRunning();
  await syncFetchStateFromServer();
}

init();
