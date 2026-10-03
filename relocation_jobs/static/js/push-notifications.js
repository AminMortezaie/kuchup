import { state } from "./state.js";

function isStandalonePwa() {
  return (
    window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true
  );
}

function planEligible() {
  const plan = (state.authState?.entitlements?.plan || state.authState?.user?.plan || "").toLowerCase();
  return plan === "full" || plan === "grandfathered";
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    out[i] = raw.charCodeAt(i);
  }
  return out;
}

async function fetchVapidPublicKey() {
  const res = await fetch("/api/notifications/vapid-public-key", { credentials: "same-origin" });
  if (!res.ok) return null;
  const body = await res.json();
  return body.public_key || null;
}

export async function initPushNotifications() {
  if (!isStandalonePwa()) return;
  if (!planEligible()) return;
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  if (Notification.permission === "denied") return;

  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    await fetch("/api/notifications/subscribe", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(existing.toJSON()),
    });
    return;
  }

  if (Notification.permission === "default") {
    const granted = await Notification.requestPermission();
    if (granted !== "granted") return;
  }

  const publicKey = await fetchVapidPublicKey();
  if (!publicKey) return;

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });

  await fetch("/api/notifications/subscribe", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription.toJSON()),
  });
}
