/* Service worker – gør appen installerbar og brugbar offline.
   App-skallen caches; Firebase/netværkskald får altid lov at gå til nettet. */
const CACHE = "korfu-ferie-v4";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = e.request.url;
  // Lad alle eksterne/Firebase-kald gå direkte til nettet
  if (
    url.includes("gstatic.com") ||
    url.includes("googleapis.com") ||
    url.includes("firebase") ||
    e.request.method !== "GET"
  ) {
    return;
  }
  // App-skal: netværk-først (så opdateringer altid kommer igennem),
  // fald tilbage til cache når man er offline.
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return resp;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("./index.html")))
  );
});
