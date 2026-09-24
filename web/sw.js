/* Service Worker — funciona OFFLINE (clave en zonas altas sin señal) */
const CACHE = 'muevecb-v2';
const RUNTIME = 'muevecb-rt-v2';
const ASSETS = [
  './', './index.html', './simulador.html',
  './css/styles.css',
  './js/data.js', './js/engine.js', './js/datasources.js', './js/realtime.js',
  './js/reports.js', './js/edge.js', './js/ai.js', './js/app.js', './js/sim.js',
  './manifest.webmanifest',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(
    ks.filter((k) => k !== CACHE && k !== RUNTIME).map((k) => caches.delete(k))
  )).then(() => self.clients.claim()));
});

// Estrategia: cache-first para lo propio; stale-while-revalidate para CDN y tiles.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  const esExterno = url.origin !== self.location.origin;
  if (esExterno) {
    // Librerías (cdnjs, jsdelivr), tiles de OSM, ArcGIS → cachear al vuelo
    e.respondWith(
      caches.open(RUNTIME).then((cache) =>
        cache.match(e.request).then((hit) => {
          const red = fetch(e.request).then((res) => {
            if (res && res.status === 200) cache.put(e.request, res.clone());
            return res;
          }).catch(() => hit);
          return hit || red;
        })
      )
    );
    return;
  }
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request).catch(() => caches.match('./index.html'))));
});
