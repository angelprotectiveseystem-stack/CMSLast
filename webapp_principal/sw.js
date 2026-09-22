// Service worker پنل مدیر مدرسه — فقط برای دریافتِ اعلان (Web Push).
// هیچ کش/آفلاینی نداره و به fetch دست نمی‌زنه؛ پس روی رفتارِ بقیه‌ی پنل اثری نداره.
// از مسیر /principal-sw.js سرو می‌شه (scope = /principal)، نه از /principal-assets/.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "" };
  }

  const title = data.title || "پنل مدیر مدرسه";
  const options = {
    body: data.body || "",
    icon: "/principal-icon.webp",
    dir: "rtl",
    lang: "fa",
    // هر اعلان یک tag ِ ثابت دارد؛ اگر همان اعلان از مسیرِ دیگری (مثلاً پولینگِ صفحه)
    // هم برسد، اعلانِ تکراری ساخته نمی‌شود و همان قبلی جایگزین می‌شود.
    tag: data.id ? "pn-" + data.id : "pn",
    data: { url: data.url || "/principal#notifications" },
  };

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(title, options),
      // اگر پنل همین لحظه باز است، زنگوله و فهرست را بی‌درنگ به‌روز کند.
      self.clients
        .matchAll({ type: "window", includeUncontrolled: true })
        .then((list) => list.forEach((c) => c.postMessage({ type: "notif-refresh" }))),
    ])
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/principal#notifications";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) {
          client.postMessage({ type: "open-notifications" });
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
