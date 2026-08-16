import { escapeHtml } from "./utils.js";


function ensureDialog() {
  let dialog = document.getElementById("creditsDialog");
  if (dialog) return dialog;
  dialog = document.createElement("dialog");
  dialog.id = "creditsDialog";
  dialog.className = "preferences-dialog credits-dialog";
  dialog.innerHTML = `
    <div class="preferences-form">
      <div class="credits-heading">
        <div>
          <h2>Credits</h2>
          <p class="credits-subtitle">Free credits reset monthly. Purchased credits never expire.</p>
        </div>
        <button type="button" class="secondary-btn" data-credit-close>Close</button>
      </div>
      <div id="creditsDialogBody" class="credits-dialog-body">Loading wallet…</div>
    </div>
  `;
  dialog.querySelector("[data-credit-close]")?.addEventListener("click", () => dialog.close());
  document.body.appendChild(dialog);
  return dialog;
}


function money(minor, currency) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
  }).format((Number(minor) || 0) / 100);
}


function renderWallet(body, wallet) {
  const balance = wallet.balance || {};
  const packs = Array.isArray(wallet.packs) ? wallet.packs : [];
  const ledger = Array.isArray(wallet.ledger) ? wallet.ledger : [];
  const reset = balance.next_reset_at
    ? new Date(balance.next_reset_at).toLocaleDateString()
    : "next month";
  body.innerHTML = `
    <div class="credits-balance-card">
      <strong>${escapeHtml(String(balance.total ?? 0))} credits</strong>
      <span>${escapeHtml(String(balance.promotional ?? 0))} free · ${escapeHtml(String(balance.purchased ?? 0))} purchased</span>
      <small>Free balance resets ${escapeHtml(reset)}</small>
    </div>
    <div class="credits-pack-grid">
      ${packs.map((pack) => `
        <button type="button" class="credits-pack" data-pack="${escapeHtml(pack.key)}">
          <strong>${escapeHtml(String(pack.credits))} credits</strong>
          <span>${escapeHtml(money(pack.price_minor, pack.currency))}</span>
        </button>
      `).join("")}
    </div>
    <p class="credits-note">One credit is used only when Kuchup successfully delivers a new matched role. Tracking actions remain free.</p>
    ${ledger.length ? `
      <div class="credits-history">
        <h3>Recent activity</h3>
        ${ledger.slice(0, 8).map((entry) => `
          <div><span>${escapeHtml(entry.operation)}</span><strong>${Number(entry.amount) > 0 ? "+" : ""}${escapeHtml(String(entry.amount))}</strong></div>
        `).join("")}
      </div>
    ` : ""}
  `;
  body.querySelectorAll("[data-pack]").forEach((button) => {
    button.addEventListener("click", () => startCheckout(button.dataset.pack, button));
  });
}


async function startCheckout(packKey, button) {
  button.disabled = true;
  const previous = button.textContent;
  button.textContent = "Opening checkout…";
  try {
    const response = await fetch("/api/credits/checkout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack_key: packKey }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Checkout could not start");
    window.location.assign(data.checkout_url);
  } catch (error) {
    button.disabled = false;
    button.textContent = previous;
    window.relocationJobs?.toast?.(error.message);
  }
}


export async function openCreditsDialog() {
  const dialog = ensureDialog();
  const body = dialog.querySelector("#creditsDialogBody");
  body.textContent = "Loading wallet…";
  dialog.showModal();
  const response = await fetch("/api/credits?history=1", { credentials: "same-origin" });
  const wallet = await response.json().catch(() => ({}));
  if (!response.ok) {
    body.textContent = wallet.error || "Wallet could not be loaded.";
    return;
  }
  renderWallet(body, wallet);
}
