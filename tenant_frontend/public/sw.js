/* EduSekai service worker: shows push notifications and opens the right page when one is tapped.
   It does not cache pages (the app always loads fresh data), so nothing here can serve stale school data. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch {
        data = { title: "EduSekai", body: event.data ? event.data.text() : "" };
    }
    const title = data.title || "EduSekai";
    event.waitUntil(
        self.registration.showNotification(title, {
            body: data.body || "",
            icon: "/icons/icon-192.png",
            badge: "/icons/icon-192.png",
            tag: data.tag || "edusekai",
            data: { link: data.link || "/dashboard" },
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const link = (event.notification.data && event.notification.data.link) || "/dashboard";
    // Only open pages of this site, never an outside address a payload might carry.
    const target = new URL(link.startsWith("/") ? link : "/dashboard", self.location.origin).href;
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            for (const client of windows) {
                if (client.url.startsWith(self.location.origin) && "focus" in client) {
                    client.navigate(target);
                    return client.focus();
                }
            }
            return self.clients.openWindow(target);
        })
    );
});
