/* Behavioral Auth PWA service worker.
 * Network-first for HTML so new builds always load; cache-first for static
 * assets. Queues telemetry POSTs while offline and replays on reconnect.
 */
const CACHE = "bas-static-v1";
const STATIC = [
  "/",
  "/static/css/styles.css",
  "/static/js/telemetry.js",
  "/static/js/auth.js",
  "/static/js/enrollment.js",
  "/sensors/sensor_bridge.js",
  "/mobile/pwa/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Telemetry POSTs: try network, queue on failure.
  if (req.method === "POST" && url.pathname.startsWith("/api/v2/telemetry")) {
    event.respondWith((async () => {
      try { return await fetch(req.clone()); }
      catch (e) {
        const body = await req.clone().text();
        const queue = await caches.open("bas-queue-v1");
        await queue.put(new Request(`/__queued/${Date.now()}`),
                        new Response(body, { headers: { "X-Url": req.url } }));
        return new Response(JSON.stringify({ queued: true }),
                            { headers: { "Content-Type": "application/json" } });
      }
    })());
    return;
  }

  // HTML navigations: network-first.
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/")));
    return;
  }

  // Static: cache-first.
  event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
});

self.addEventListener("sync", (e) => {
  if (e.tag === "bas-flush") e.waitUntil(replayQueue());
});

async function replayQueue() {
  const cache = await caches.open("bas-queue-v1");
  const keys = await cache.keys();
  for (const k of keys) {
    const res = await cache.match(k);
    const url = res.headers.get("X-Url");
    const body = await res.text();
    try {
      await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body });
      await cache.delete(k);
    } catch (e) { /* still offline */ }
  }
}
