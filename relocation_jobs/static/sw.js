self.addEventListener("push", (event) => {
  let title = "Kuchup";
  let body = "New jobs found!";
  if (event.data) {
    try {
      const payload = event.data.json();
      if (payload.title) title = payload.title;
      if (payload.body) body = payload.body;
    } catch (_err) {
      body = event.data.text() || body;
    }
  }
  event.waitUntil(self.registration.showNotification(title, { body, tag: "kuchup-new-jobs" }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow("/panel");
      }
      return undefined;
    }),
  );
});

self.addEventListener("fetch", () => {});
