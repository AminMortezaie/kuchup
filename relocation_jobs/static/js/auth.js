/** Login and session UI (Google-only). */

import { state } from "./state.js";
import { $ } from "./utils.js";
import { updateFetchHeaderUI } from "./render.js";
import { applyPanelChrome, isRemotePanel } from "./panel-mode.js";

export function showLogin(message = "") {
  $("mainContent").classList.add("hidden");
  $("loginPanel").hidden = false;
  const params = new URLSearchParams(window.location.search);
  const error = message || params.get("error") || "";
  $("loginError").textContent = error === "session"
    ? "Your session expired — sign in again."
    : error;
  if (params.get("error") && window.history.replaceState) {
    const url = new URL(window.location.href);
    url.searchParams.delete("error");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }
  $("loginHint").textContent = isRemotePanel()
    ? "Track remote roles from aggregator boards."
    : "Track applications and relocation-friendly roles per country.";
  const google = $("googleSignIn");
  if (google && isRemotePanel()) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    google.href = `/api/auth/google?next=${next}`;
  }
}

export function setAdminNavVisible(visible) {
  const adminLink = $("adminLink");
  const adminPanelBtn = $("adminPanelBtn");
  state.fetchControlsEnabled = Boolean(visible) && state.scrapeConfig?.scrape_enabled !== false;
  if (adminLink) adminLink.hidden = !visible;
  if (adminPanelBtn) adminPanelBtn.hidden = !visible;
  updateFetchHeaderUI();
}

export function showApp() {
  $("loginPanel").hidden = true;
  $("mainContent").classList.remove("hidden");
  applyPanelChrome();
  const user = state.authState.user;
  const entitlements = state.authState.entitlements || {};
  const creditBalance = state.authState.credits?.balance;
  const creditsLink = $("creditsLink");
  if (creditsLink) {
    creditsLink.textContent = creditBalance
      ? `Credits · ${creditBalance.total ?? 0}`
      : "Credits";
  }
  if (user) {
    const label = user.email || user.username || "?";
    const initial = label.charAt(0).toUpperCase();
    $("userAvatar").textContent = initial;
    const plan = entitlements.plan || user.plan || "";
    $("userName").textContent = plan ? `${label} · ${plan}` : label;
    $("userMenuBtn").title = label;
    setAdminNavVisible(Boolean(user.is_admin));
  } else {
    $("userAvatar").textContent = "?";
    $("userName").textContent = "Account";
    $("userMenuBtn").title = "Account";
    setAdminNavVisible(false);
  }
}

export async function refreshAuth() {
  const res = await fetch("/api/auth/status", { credentials: "same-origin" });
  state.authState = await res.json();
  const hint = $("loginRegisterHint");
  if (hint) hint.hidden = !state.authState.allow_register;
  if (state.authState.authenticated) {
    showApp();
    return true;
  }
  showLogin();
  return false;
}

export async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  state.authState = { authenticated: false };
  showLogin();
}
