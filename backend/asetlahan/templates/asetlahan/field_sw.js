/* Service worker aplikasi lapangan: cangkang aplikasi, batas bidang, dan ubin peta tersedia luring.
 * Halaman aplikasi (memuat nama petugas) dan batas bidang (data sesuai unit petugas) dihapus saat
 * sesi berakhir (dialihkan ke halaman masuk / 401 / 403) atau saat pengguna berganti (field.js). */
"use strict";
var VERSION = {{ version|safe }};
var SHELL = {{ shell|safe }};
var BOUNDARIES = {{ boundaries|safe }};
var SHELL_CACHE = "lapangan-shell-" + VERSION;
var DATA_CACHE = "lapangan-data-" + VERSION;
var TILE_CACHE = "lapangan-ubin-" + VERSION;
var TILE_HOSTS = ["tile.openstreetmap.org", "server.arcgisonline.com"];
var MAX_TILES = 3000;

self.addEventListener("install", function (event) {
  // Halaman aplikasi butuh sesi masuk, jadi disimpan saat pertama dibuka (bukan di sini).
  var assets = SHELL.filter(function (url) { return url !== SHELL[0]; });
  event.waitUntil(caches.open(SHELL_CACHE).then(function (cache) { return cache.addAll(assets); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  var keep = [SHELL_CACHE, DATA_CACHE, TILE_CACHE];
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.indexOf("lapangan-") === 0 && keep.indexOf(key) === -1;
    }).map(function (key) { return caches.delete(key); }));
  }).then(function () { return self.clients.claim(); }));
});

function purgePersonal() {
  return caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (key) {
      if (key.indexOf("lapangan-data-") === 0) { return caches.delete(key); }
      if (key.indexOf("lapangan-shell-") === 0) {
        return caches.open(key).then(function (cache) { return cache.delete(SHELL[0], { ignoreSearch: true }); });
      }
      return null;
    }));
  });
}

self.addEventListener("message", function (event) {
  if (event.data && event.data.type === "purge-personal") { event.waitUntil(purgePersonal()); }
});

function networkFirst(request, cacheName) {
  return fetch(request).then(function (response) {
    if (response.redirected || response.status === 401 || response.status === 403) {
      // Sesi berakhir / pengguna lain: jangan sisakan data pengguna sebelumnya.
      purgePersonal();
      return response;
    }
    if (response.ok) {
      var copy = response.clone();
      caches.open(cacheName).then(function (cache) { cache.put(request, copy); });
    }
    return response;
  }).catch(function () {
    return caches.match(request, { ignoreSearch: true }).then(function (cached) {
      return cached || Response.error();
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
      if (cached) { return cached; }
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
  } else if (url.pathname === BOUNDARIES) {
    event.respondWith(networkFirst(request, DATA_CACHE));
  } else if (SHELL.indexOf(url.pathname) !== -1) {
    event.respondWith(caches.match(request).then(function (cached) { return cached || fetch(request); }));
  }
});
