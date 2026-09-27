/** Login and session UI (email/password + Google). */

import { state } from "./state.js";
import { $ } from "./utils.js";
import { updateFetchHeaderUI } from "./render.js";
import { applyPanelChrome, isRemotePanel } from "./panel-mode.js";

let panelAuthMode = "signin";

function panelAuthEndpoint() {
  return panelAuthMode === "signup" ? "/api/auth/register" : "/api/auth/login";
}

function applyPanelAuthMode() {
  const title = $("loginTitle");
  const submit = $("panelAuthSubmit");
  const toggle = $("panelAuthModeToggle");
  const password = $("panelAuthPassword");
  const modeHint = $("panelAuthModeHint");
  const allowRegister = Boolean(state.authState?.allow_register);
  if (panelAuthMode === "signup") {
    if (title) title.textContent = "Create account";
    if (submit) submit.textContent = "Sign up";
    if (toggle) toggle.textContent = "Already have an account? Sign in";
    if (password) password.autocomplete = "new-password";
  } else {
    if (title) title.textContent = "Sign in";
    if (submit) submit.textContent = "Sign in";
    if (toggle) toggle.textContent = "Create an account";
    if (password) password.autocomplete = "current-password";
  }
  if (modeHint) modeHint.hidden = !allowRegister;
  if (toggle && !allowRegister) {
    panelAuthMode = "signin";
    if (toggle) toggle.hidden = true;
  } else if (toggle) {
    toggle.hidden = false;
  }
}

function showCheckEmail(message) {
  const form = $("panelEmailAuthForm");
  const confirmHint = $("panelAuthConfirmHint");
  const modeHint = $("panelAuthModeHint");
  const divider = document.querySelector("#loginPanel .login-divider");
  const googleActions = $("googleSignIn")?.closest(".login-actions");
  if (form) form.hidden = true;
  if (modeHint) modeHint.hidden = true;
  if (divider) divider.hidden = true;
  if (googleActions) googleActions.hidden = true;
  if (confirmHint) {
    confirmHint.hidden = false;
    confirmHint.textContent = message || "Check your email for a confirmation link before signing in.";
  }
  const title = $("loginTitle");
  if (title) title.textContent = "Confirm your email";
}

async function submitPanelEmailAuth(event) {
  event.preventDefault();
  const error = $("loginError");
  const email = ($("panelAuthEmail")?.value || "").trim();
  const password = $("panelAuthPassword")?.value || "";
  if (error) error.textContent = "";
  const res = await fetch(panelAuthEndpoint(), {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (error) error.textContent = data.error || "Sign-in failed";
    return;
  }
  if (panelAuthMode === "signup" && data.confirm_email_sent) {
    showCheckEmail(data.message);
    return;
  }
  state.authState = data;
  if (state.authState.authenticated) {
    window.location.reload();
  }
}

export function bindPanelAuth() {
  $("panelEmailAuthForm")?.addEventListener("submit", submitPanelEmailAuth);
  $("panelAuthModeToggle")?.addEventListener("click", () => {
    panelAuthMode = panelAuthMode === "signin" ? "signup" : "signin";
    applyPanelAuthMode();
    const error = $("loginError");
    if (error) error.textContent = "";
  });
}

export function showLogin(message = "") {
  $("mainContent").classList.add("hidden");
  $("loginPanel").hidden = false;
  const form = $("panelEmailAuthForm");
  const confirmHint = $("panelAuthConfirmHint");
  const modeHint = $("panelAuthModeHint");
  const divider = document.querySelector("#loginPanel .login-divider");
  const googleActions = $("googleSignIn")?.closest(".login-actions");
  if (form) form.hidden = false;
  if (confirmHint) confirmHint.hidden = true;
  if (modeHint) modeHint.hidden = false;
  if (divider) divider.hidden = false;
  if (googleActions) googleActions.hidden = false;
  applyPanelAuthMode();
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
  applyPanelAuthMode();
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
