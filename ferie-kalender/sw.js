/* Service worker – gør appen installerbar og brugbar offline.
   App-skallen caches; Firebase/netværkskald får altid lov at gå til nettet. */
const CACHE = "korfu-ferie-v2";
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
  // App-skal: cache-first, fald tilbage til netværk
  e.respondWith(
    caches.match(e.request).then((r) => r || fetch(e.request).catch(() => caches.match("./index.html")))
  );
});
