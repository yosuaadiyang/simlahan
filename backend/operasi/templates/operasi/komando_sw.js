/* Service worker pusat komando: cangkang aplikasi, lapisan peta, dan ubin peta tersedia luring. */
"use strict";
var VERSION = {{ version|safe }};
var SHELL = {{ shell|safe }};
var LAYER_PREFIX = {{ layer_prefix|safe }};
var SHELL_CACHE = "komando-shell-" + VERSION;
var DATA_CACHE = "komando-data-" + VERSION;
var TILE_CACHE = "komando-ubin-" + VERSION;
var TILE_HOSTS = ["tile.openstreetmap.org", "server.arcgisonline.com", "tile.opentopomap.org"];
var MAX_TILES = 4000;

self.addEventListener("install", function (event) {
  // Halaman utama butuh sesi masuk, jadi disimpan saat pertama dibuka (bukan di sini).
  var assets = SHELL.filter(function (url) { return url !== SHELL[0]; });
  event.waitUntil(caches.open(SHELL_CACHE).then(function (cache) { return cache.addAll(assets); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  var keep = [SHELL_CACHE, DATA_CACHE, TILE_CACHE];
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.indexOf("komando-") === 0 && keep.indexOf(key) === -1;
    }).map(function (key) { return caches.delete(key); }));
  }).then(function () { return self.clients.claim(); }));
});

function networkFirst(request, cacheName) {
  return fetch(request).then(function (response) {
    if (response.ok && !response.redirected) {
      var copy = response.clone();
      caches.open(cacheName).then(function (cache) { cache.put(request, copy); });
    }
    return response;
  }).catch(function () {
    return caches.match(request, { ignoreSearch: request.mode === "navigate" }).then(function (cached) {
      return cached || new Response("Luring: data belum tersimpan di perangkat.", {
        status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" }
      });
    });
  });
}

function trimTiles() {
  caches.open(TILE_CACHE).then(function (cache) {
    cache.keys().then(function (keys) {
      if (keys.length > MAX_TILES) {
        keys.slice(0, keys.length - MAX_TILES).forEach(function (key) { cache.delete(key); });
      }
    });
  });
}

function cacheFirstTile(request) {
  return caches.open(TILE_CACHE).then(function (cache) {
    return cache.match(request).then(function (cached) {
      // Ekspor PNG meminta ubin dengan CORS; respons opaque tidak bisa dipakai untuk itu.
      if (cached && !(request.mode === "cors" && cached.type === "opaque")) { return cached; }
      return fetch(request).then(function (response) {
        if (response.ok || response.type === "opaque") {
          cache.put(request, response.clone());
          trimTiles();
        }
        return response;
      });
    });
  });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") { return; }
  var url = new URL(request.url);
  if (TILE_HOSTS.some(function (host) { return url.hostname.slice(-host.length) === host; })) {
    event.respondWith(cacheFirstTile(request));
    return;
  }
  if (url.origin !== self.location.origin) { return; }
  if (request.mode === "navigate" || url.pathname === SHELL[0]) {
    event.respondWith(networkFirst(request, SHELL_CACHE));
  } else if (url.pathname.indexOf(LAYER_PREFIX) === 0) {
    event.respondWith(networkFirst(request, DATA_CACHE));
  } else if (SHELL.indexOf(url.pathname) !== -1) {
    event.respondWith(caches.match(request).then(function (cached) { return cached || fetch(request); }));
  }
});
