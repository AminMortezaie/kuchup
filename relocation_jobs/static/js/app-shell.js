const ADMIN_PANES = ["home", "catalog", "problems", "users", "jobs", "runs", "config"];
const MENU_MQ = "(max-width: 900px)";

export function initAppShell() {
  const shell = document.querySelector(".app-shell");
  const rail = document.getElementById("appRail");
  const menuBtn = document.getElementById("appMenuBtn");
  const backdrop = document.getElementById("appMenuBackdrop");
  if (!shell || !rail) return;

  const mq = window.matchMedia(MENU_MQ);
  shell.classList.remove("is-rail-collapsed");
  window.localStorage.removeItem("kuchup-app-rail-collapsed");

  const setMenu = (open) => {
    shell.classList.toggle("is-menu-open", open);
    if (menuBtn) menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (menuBtn) menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    if (backdrop) backdrop.hidden = !open;
    document.documentElement.classList.toggle("app-menu-locked", open && mq.matches);
  };

  menuBtn?.addEventListener("click", () => setMenu(!shell.classList.contains("is-menu-open")));
  backdrop?.addEventListener("click", () => setMenu(false));
  rail.addEventListener("click", (event) => {
    if (!mq.matches) return;
    if (event.target.closest("a.app-rail-item")) setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (document.querySelector("dialog[open]")) return;
    setMenu(false);
  });
  mq.addEventListener("change", () => {
    if (!mq.matches) setMenu(false);
  });
}

export function showAdminPane(name) {
  const pane = ADMIN_PANES.includes(name) ? name : "home";
  document.querySelectorAll("[data-admin-pane]").forEach((el) => {
    el.hidden = el.dataset.adminPane !== pane;
  });
  document.querySelectorAll("[data-admin-nav]").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.adminNav === pane);
  });
}

export function adminPaneFromHash() {
  const name = (window.location.hash || "#home").slice(1);
  return ADMIN_PANES.includes(name) ? name : "home";
}

export function initAdminPanes(onChange) {
  if (!document.querySelector("[data-admin-pane]")) return;
  const fromHash = () => {
    const pane = adminPaneFromHash();
    showAdminPane(pane);
    onChange?.(pane);
  };
  window.addEventListener("hashchange", fromHash);
  fromHash();
}
