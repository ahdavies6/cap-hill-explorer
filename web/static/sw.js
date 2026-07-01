/* Cap Hill Explorer service worker — cache-first for map tiles + Leaflet CDN assets,
   so the map paints instantly on reload instead of re-fetching every tile. */
const TILE_CACHE = 'che-tiles-v1';
const ASSET_CACHE = 'che-assets-v1';

// Hosts whose responses we cache-first (tiles are opaque cross-origin — fine for a basemap).
const TILE_HOSTS = ['basemaps.cartocdn.com'];
const ASSET_HOSTS = ['unpkg.com', 'cdnjs.cloudflare.com', 'fonts.gstatic.com', 'fonts.googleapis.com'];

self.addEventListener('install', e => self.skipWaiting());

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keep = new Set([TILE_CACHE, ASSET_CACHE]);
    const names = await caches.keys();
    await Promise.all(names.filter(n => !keep.has(n)).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

function pickCache(host) {
  if (TILE_HOSTS.some(h => host.endsWith(h))) return TILE_CACHE;
  if (ASSET_HOSTS.some(h => host.endsWith(h))) return ASSET_CACHE;
  return null;
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch { return; }
  const cacheName = pickCache(url.host);
  if (!cacheName) return; // let the network handle everything else (API, HTML, etc.)

  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    const hit = await cache.match(req);
    if (hit) return hit;
    try {
      const res = await fetch(req);
      // cache successful or opaque (cross-origin no-cors) responses
      if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone());
      return res;
    } catch (err) {
      const fallback = await cache.match(req);
      if (fallback) return fallback;
      throw err;
    }
  })());
});
