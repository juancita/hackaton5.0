/* Service Worker — funciona OFFLINE (clave en zonas altas sin señal) */
const CACHE = 'muevecb-v30';
const RUNTIME = 'muevecb-rt-v11';
const ASSETS = [
  './', './index.html', './simulador.html',
  './css/styles.css?v=22',
  './js/data.js', './js/icons.js', './js/engine.js', './js/datasources.js', './js/reports.js', './js/api.js', './js/ai.js', './js/app.js', './js/rides.js', './js/sim.js',
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
  // La API (otro puerto/host) nunca se cachea: alertas, votos y admin deben ir siempre a la red
  const esEstatico = /(^|\.)(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|fonts\.googleapis\.com|fonts\.gstatic\.com|tile\.openstreetmap\.org|arcgis\.com|arcgisonline\.com|gis\.transmilenio\.gov\.co|datos\.gov\.co|ideca\.gov\.co)$/.test(url.hostname);
  // En producción la API vive en el mismo origen que la web: tampoco se cachea
  const esApi = !esExterno && /^\/(health|network|places|routes|chat|webhooks|incident-types|incidents|reporters|admin|auth|me|conductores|viajes|stats|cameras|integraciones|mapas|docs|redoc|openapi\.json)(\/|$)/.test(url.pathname);
  if (e.request.method !== 'GET' || esApi || (esExterno && !esEstatico)) return;
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
