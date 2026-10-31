/* Pusat komando operasi lapangan: peta, absen, kegiatan, uji tanah, warga, tugas,
 * kinerja, chat, SOS, AI Satelit, cetak peta, perintah suara, kompas & mode Live.
 * Laporan yang direkam tanpa sinyal disimpan di perangkat (IndexedDB) dan dikirim
 * saat daring; server menolak duplikat lewat client_id. */
(function () {
  "use strict";

  var config = JSON.parse(document.getElementById("komando-config").textContent);
  var urls = config.urls;
  var perms = config.perms;
  var DB_NAME = "simlahan-komando";
  var STORE = "antrean";
  var MAX_PHOTO_SIDE = 1600;
  var STORAGE_PREFIX = "komando:";
  // Kunci refresh token aplikasi utama (frontend/apps/leasing/src/auth/constants.ts).
  var MAIN_REFRESH_TOKEN_KEY = "simlahan.refreshToken";

  // ================================================================ Utilitas

  function $(id) { return document.getElementById(id); }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function store(key, value) {
    try {
      if (value === undefined) { return JSON.parse(localStorage.getItem(STORAGE_PREFIX + key)); }
      localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
    } catch (e) { return null; }
    return value;
  }

  var toastTimer = null;
  function toast(text, kind) {
    var el = $("toast");
    el.textContent = text;
    el.className = "toast " + (kind || "");
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, kind === "error" ? 7000 : 4000);
  }

  function uuid() {
    if (window.crypto && crypto.randomUUID) { return crypto.randomUUID(); }
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : (meta ? meta.content : "");
  }

  function errorText(data, fallback) {
    if (!data) { return fallback || "Terjadi kesalahan."; }
    if (data.error) { return data.error; }
    if (data.errors) {
      return Object.keys(data.errors).map(function (key) {
        var value = data.errors[key];
        return Array.isArray(value) ? value.join(" ") : String(value);
      }).join(" ");
    }
    return fallback || "Terjadi kesalahan.";
  }

  function ApiError(message, status, data) {
    this.message = message;
    this.status = status;
    this.data = data;
  }

  function request(url, options) {
    options = options || {};
    var init = { method: options.method || "GET", credentials: "same-origin", headers: { "Accept": "application/json" } };
    if (init.method !== "GET") { init.headers["X-CSRFToken"] = csrf(); }
    if (options.json !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.json);
    } else if (options.body) {
      init.body = options.body;
    }
    return fetch(url, init).catch(function () {
      // TypeError bawaan peramban ("Failed to fetch") berbahasa Inggris.
      throw new ApiError("Tidak dapat terhubung ke server. Periksa koneksi internet.", 0, null);
    }).then(function (response) {
      return response.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
        if (response.status === 401) {
          // Data peta pengguna ini tidak boleh tertinggal di perangkat setelah sesi berakhir.
          purgeOfflineData(true);
          sessionExpired();
          throw new ApiError("Sesi berakhir. Silakan masuk kembali.", 401, data);
        }
        if (!response.ok) {
          throw new ApiError(errorText(data, "Gagal (" + response.status + ")."), response.status, data);
        }
        return data;
      });
    });
  }

  function form(fields) {
    var data = new FormData();
    Object.keys(fields).forEach(function (key) {
      var value = fields[key];
      if (value !== undefined && value !== null && value !== "") { data.append(key, value); }
    });
    return data;
  }

  function fmtDate(iso, withTime) {
    if (!iso) { return "–"; }
    var d = new Date(iso);
    var pad = function (n) { return ("0" + n).slice(-2); };
    var text = pad(d.getDate()) + "-" + pad(d.getMonth() + 1) + "-" + d.getFullYear();
    return withTime ? text + " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) : text;
  }

  function fmtTime(iso) {
    if (!iso) { return "–"; }
    var d = new Date(iso);
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  function localInputValue(date) {
    var d = date || new Date();
    var offset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - offset).toISOString().slice(0, 16);
  }

  function pctText(value) { return value === null || value === undefined ? "–" : value + "%"; }

  function fillSelect(select, items, placeholder) {
    if (!select) { return; }
    var html = placeholder !== undefined ? '<option value="">' + escapeHtml(placeholder) + "</option>" : "";
    items.forEach(function (item) {
      html += '<option value="' + escapeHtml(item.value) + '">' + escapeHtml(item.label) + "</option>";
    });
    select.innerHTML = html;
  }

  function choiceLabel(kind, value) {
    var found = (config.choices[kind] || []).filter(function (c) { return c.value === value; })[0];
    return found ? found.label : value || "–";
  }

  var sessionWarned = false;
  function sessionExpired() {
    if (sessionWarned) { return; }
    sessionWarned = true;
    var el = $("toast");
    el.innerHTML = 'Sesi berakhir. <a href="' + escapeHtml(urls.login) + '">Masuk kembali</a> — laporan di antrean tetap tersimpan.';
    el.className = "toast error";
    el.hidden = false;
  }

  // ================================================================ Data di perangkat

  // Hapus lapisan peta tersimpan (dan halaman utama berisi konfigurasi pengguna).
  function purgeOfflineData(includePage) {
    if (!window.caches) { return Promise.resolve(); }
    return caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (key) {
        if (key.indexOf("komando-data-") === 0) { return caches.delete(key); }
        if (includePage && key.indexOf("komando-shell-") === 0) {
          return caches.open(key).then(function (cache) { return cache.delete(urls.scope, { ignoreSearch: true }); });
        }
        return null;
      }));
    }).catch(function () { /* Cache Storage tidak tersedia */ });
  }

  // Pengguna berganti di perangkat ini: buang data peta pengguna sebelumnya.
  (function checkUser() {
    var previous = store("pengguna");
    if (previous !== null && previous !== undefined && previous !== config.user.id) { purgeOfflineData(false); }
    store("pengguna", config.user.id);
  }());

  // ================================================================ Antrean luring (IndexedDB)

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE, { keyPath: "client_id" }); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function tx(mode, fn) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var transaction = db.transaction(STORE, mode);
        var result = fn(transaction.objectStore(STORE));
        transaction.oncomplete = function () { resolve(result && result.result !== undefined ? result.result : result); };
        transaction.onerror = function () { reject(transaction.error); };
        transaction.onabort = function () { reject(transaction.error); };
      });
    });
  }

  function queueAll() { return tx("readonly", function (s) { return s.getAll(); }); }
  function queuePut(item) { return tx("readwrite", function (s) { s.put(item); }); }
  function queueDelete(id) { return tx("readwrite", function (s) { s.delete(id); }); }
  function queueClear() { return tx("readwrite", function (s) { s.clear(); }).catch(function () { /* mode privat */ }); }

  // Antrean milik pengguna yang sedang masuk; laporan pengguna lain (atau tanpa
  // penanda pengguna) dibuang agar tidak terkirim atas nama orang lain.
  function myQueue() {
    return queueAll().then(function (items) {
      var mine = [];
      var others = [];
      items.forEach(function (item) { (item.user_id === config.user.id ? mine : others).push(item); });
      return Promise.all(others.map(function (item) { return queueDelete(item.client_id); })).then(function () { return mine; });
    });
  }

  function enqueue(url, label, fields, files) {
    var item = {
      client_id: fields.client_id || uuid(),
      url: url,
      label: label,
      fields: fields,
      files: files || [],
      created_at: new Date().toISOString(),
      user_id: config.user.id,
      error: ""
    };
    item.fields.client_id = item.client_id;
    return queuePut(item).then(function () { refreshQueue(); return item; });
  }

  var syncing = false;
  function sync(quiet) {
    if (syncing || !navigator.onLine) { return Promise.resolve(); }
    syncing = true;
    var sent = 0;
    return myQueue().then(function (items) {
      items.sort(function (a, b) { return a.created_at < b.created_at ? -1 : 1; });
      return items.reduce(function (chain, item) {
        return chain.then(function (stop) {
          if (stop) { return true; }
          var data = form(item.fields);
          (item.files || []).forEach(function (f) { data.append(f.field, f.blob, f.name); });
          return request(item.url, { method: "POST", body: data }).then(function () {
            sent += 1;
            return queueDelete(item.client_id).then(function () { return false; });
          }).catch(function (error) {
            if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 429) {
              item.error = error.message;
              return queuePut(item).then(function () { return false; });
            }
            return true;
          });
        });
      }, Promise.resolve(false));
    }).then(function () {
      syncing = false;
      refreshQueue();
      if (sent) {
        if (!quiet) { toast(sent + " laporan terkirim.", "ok"); }
        reloadData();
      }
    }).catch(function () { syncing = false; });
  }

  function refreshQueue() {
    return myQueue().then(function (items) {
      $("antrean-jumlah").textContent = items.length;
      $("antrean-pill").hidden = !items.length;
      $("riwayat-antrean-n").textContent = items.length ? "(" + items.length + ")" : "";
      $("daftar-antrean").innerHTML = items.length ? items.map(function (item) {
        return '<li><div class="title">' + escapeHtml(item.label) + '</div><div class="sub">' + fmtDate(item.created_at, true) +
          (item.error ? ' · <span class="danger-text">Ditolak: ' + escapeHtml(item.error) + "</span>" : " · menunggu sinyal") +
          '</div><div class="row"><button type="button" class="btn-small" data-hapus="' + escapeHtml(item.client_id) + '">Hapus</button></div></li>';
      }).join("") : '<li class="muted">Tidak ada antrean.</li>';
    }).catch(function () { /* IndexedDB tidak tersedia (mode privat) */ });
  }

  $("daftar-antrean").addEventListener("click", function (event) {
    var id = event.target.getAttribute("data-hapus");
    if (id && window.confirm("Hapus laporan ini dari antrean? Data belum terkirim akan hilang.")) {
      queueDelete(id).then(refreshQueue);
    }
  });
  $("kirim-sekarang").addEventListener("click", function () { sync(false); });

  // ================================================================ GPS

  var lastFix = null;
  var gpsWatch = null;

  function startGps() {
    if (!navigator.geolocation || gpsWatch !== null) { return; }
    gpsWatch = navigator.geolocation.watchPosition(function (pos) {
      lastFix = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: Math.round(pos.coords.accuracy),
                  heading: pos.coords.heading, speed: pos.coords.speed, at: Date.now() };
      $("kg-gps").textContent = "GPS: akurasi ±" + lastFix.accuracy + " m";
      onLiveFix();
    }, function () {
      $("kg-gps").textContent = "GPS tidak tersedia. Ketuk peta untuk menentukan titik.";
    }, { enableHighAccuracy: true, maximumAge: 15000, timeout: 30000 });
  }

  function currentPosition(timeout) {
    if (lastFix && Date.now() - lastFix.at < 60000) { return Promise.resolve(lastFix); }
    return new Promise(function (resolve) {
      if (!navigator.geolocation) { resolve(null); return; }
      navigator.geolocation.getCurrentPosition(function (pos) {
        lastFix = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: Math.round(pos.coords.accuracy),
                    heading: pos.coords.heading, speed: pos.coords.speed, at: Date.now() };
        resolve(lastFix);
      }, function () { resolve(null); }, { enableHighAccuracy: true, timeout: timeout || 10000, maximumAge: 30000 });
    });
  }

  function compress(file) {
    if (!file || !/^image\//.test(file.type)) { return Promise.resolve(file); }
    return new Promise(function (resolve) {
      var img = new Image();
      var url = URL.createObjectURL(file);
      img.onload = function () {
        var scale = Math.min(1, MAX_PHOTO_SIDE / Math.max(img.width, img.height));
        var canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob(function (blob) { resolve(blob || file); }, "image/jpeg", 0.82);
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function photoFiles(input, field, limit) {
    var files = Array.prototype.slice.call(input.files || [], 0, limit || 1);
    return Promise.all(files.map(function (file, index) {
      return compress(file).then(function (blob) {
        var image = blob !== file || /^image\//.test(file.type);
        return { field: field, blob: blob, name: image ? "foto-" + (index + 1) + ".jpg" : file.name };
      });
    }));
  }

  // ================================================================ Peta

  L.Icon.Default.imagePath = document.body.getAttribute("data-leaflet-images");
  var map = L.map("peta", { zoomControl: false, preferCanvas: true, attributionControl: true })
    .setView(config.center, config.zoom);
  L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

  var baseLayers = config.basemaps.map(function (spec) {
    return L.tileLayer(spec.url, { maxZoom: spec.maxZoom || 20, attribution: spec.attribution || "" });
  });
  var satelliteIndex = Math.max(0, config.basemaps.map(function (s) { return s.url; }).findIndex(function (u) { return /World_Imagery|satelit/i.test(u); }));
  var currentBase = 0;
  baseLayers[0].addTo(map);

  function setBase(index) {
    map.removeLayer(baseLayers[currentBase]);
    currentBase = index;
    baseLayers[index].addTo(map);
    baseLayers[index].bringToBack();
    document.querySelector('[data-tool="satellite"]').classList.toggle("active", index === satelliteIndex);
  }

  var modes = { warga: store("modeWarga") || "stance", korwil: store("modeKorwil") || "color" };
  var layerState = store("lapisan") || { korwil: true, warga: true, kegiatan: false, tanah: true, petugas: false, sos: true };
  var layers = {};
  var layerData = {};
  var selectedKorwil = null;

  var LAYER_SPECS = [
    { key: "korwil", name: "Batas Korwil", perm: true },
    { key: "warga", name: "Warga terdata", perm: perms.warga },
    { key: "kegiatan", name: "Kegiatan (90 hari)", perm: perms.kegiatan },
    { key: "tanah", name: "Uji tanah", perm: perms.tanah },
    { key: "petugas", name: "Petugas Live", perm: perms.lihatPetugas },
    { key: "sos", name: "SOS aktif", perm: perms.lihatSos },
    { key: "temuan", name: "Temuan ilegal", perm: perms.temuan },
    { key: "patroli", name: "Patroli SMART", perm: perms.patroli },
    { key: "bidang", name: "Penguasaan lahan", perm: perms.bidang },
    { key: "ancaman", name: "Zona ancaman", perm: perms.ancaman },
    { key: "foto360", name: "Foto situs 360°", perm: perms.foto360 }
  ].concat((config.commandLayers || []).map(function (l) {
    return { key: l.key, name: l.name + " (" + l.kind + ")", perm: true, ref: true, color: l.color, zoned: l.zoned, def: l.visible };
  })).filter(function (spec) { return spec.perm; });
  // Lapisan referensi baru mengikuti setelan "Tampil saat peta dibuka".
  LAYER_SPECS.forEach(function (spec) {
    if (spec.ref && !Object.prototype.hasOwnProperty.call(layerState, spec.key)) { layerState[spec.key] = !!spec.def; }
  });

  function rampColor(value) {
    if (value === null || value === undefined) { return "#6e7781"; }
    var stops = [[0, [207, 34, 46]], [50, [191, 135, 0]], [100, [26, 127, 55]]];
    var lower = value <= 50 ? stops[0] : stops[1];
    var upper = value <= 50 ? stops[1] : stops[2];
    var t = (value - lower[0]) / (upper[0] - lower[0]);
    var rgb = lower[1].map(function (c, i) { return Math.round(c + (upper[1][i] - c) * t); });
    return "rgb(" + rgb.join(",") + ")";
  }

  function korwilColor(props) {
    if (modes.korwil === "color") { return props.color || "#1d82f5"; }
    return rampColor((props.stats || {})[modes.korwil]);
  }

  function wargaColor(props) {
    var palette = config.colors[modes.warga] || {};
    return palette[props[modes.warga]] || "#8c959f";
  }

  function popupHtml(props) {
    var html = "<strong>" + escapeHtml(props.title) + "</strong>";
    (props.rows || []).forEach(function (row) { html += "<br>" + escapeHtml(row[0]) + ": " + escapeHtml(row[1]); });
    if (props.kind === "warga") {
      html += '<br><button type="button" class="btn-small" data-warga="' + props.id + '">Buka data warga</button>';
    }
    if (props.kind === "bidang") {
      html += '<br><button type="button" class="btn-small" data-bidang="' + props.id + '">Detail bidang</button>';
    }
    if (props.photo360) {
      html += '<br><button type="button" class="btn-small" data-foto360="' + escapeHtml(props.photo360) + '" data-judul="' + escapeHtml(props.title) + '">Lihat 360°</button>';
    }
    if (props.url) { html += '<br><a href="' + encodeURI(props.url) + '" target="_blank" rel="noopener">Buka data</a>'; }
    (props.photos || []).forEach(function (url) { html += ' <a href="' + encodeURI(url) + '" target="_blank" rel="noopener">📷</a>'; });
    return html;
  }

  function buildLayer(key, data) {
    if (key === "korwil") {
      return L.geoJSON(data, {
        style: function (f) {
          var color = korwilColor(f.properties);
          var selected = selectedKorwil === f.properties.id;
          return { color: selected ? "#fff" : color, weight: selected ? 4 : 2, fillColor: color, fillOpacity: modes.korwil === "color" ? 0.12 : 0.45 };
        },
        onEachFeature: function (f, layer) {
          layer.bindTooltip(f.properties.code, { permanent: true, direction: "center", className: "korwil-label" });
          layer.on("click", function (event) {
            if (toolMode) { return; }
            L.DomEvent.stopPropagation(event);
            showKorwil(f.properties, layer.getBounds());
          });
        }
      });
    }
    if (key === "petugas" || key === "sos") {
      return L.geoJSON(data, {
        pointToLayer: function (f, latlng) {
          var icon = key === "sos"
            ? L.divIcon({ className: "sos-icon", html: "🆘", iconSize: [30, 30] })
            : L.divIcon({ className: "officer-icon", html: f.properties.self ? "🟢" : "👮", iconSize: [26, 26] });
          return L.marker(latlng, { icon: icon, zIndexOffset: key === "sos" ? 1000 : 500 });
        },
        onEachFeature: function (f, layer) { layer.bindPopup(popupHtml(f.properties)); }
      });
    }
    if (key === "bidang" || key === "ancaman" || key.indexOf("ref-") === 0) {
      return L.geoJSON(data, {
        style: function (f) {
          var c = f.properties.color || "#0969da";
          if (key === "ancaman") { return { color: c, weight: 2, dashArray: "6 4", fillColor: c, fillOpacity: 0.25 }; }
          if (key === "bidang") { return { color: c, weight: 2, fillColor: c, fillOpacity: 0.35 }; }
          return { color: c, weight: 1.5, fillColor: c, fillOpacity: 0.18 };
        },
        pointToLayer: function (f, latlng) {
          return L.circleMarker(latlng, { radius: 5, color: "#fff", weight: 1, fillColor: f.properties.color || "#0969da", fillOpacity: 0.9 });
        },
        onEachFeature: function (f, layer) { layer.bindPopup(popupHtml(f.properties)); }
      });
    }
    if (key === "foto360") {
      return L.geoJSON(data, {
        pointToLayer: function (f, latlng) {
          return L.marker(latlng, { icon: L.divIcon({ className: "pano-icon", html: "◉", iconSize: [26, 26] }), title: f.properties.title });
        },
        onEachFeature: function (f, layer) { layer.bindPopup(popupHtml(f.properties)); }
      });
    }
    return L.geoJSON(data, {
      style: function (f) { return { color: f.properties.color || "#06b6d4", weight: 3, opacity: 0.85 }; },
      pointToLayer: function (f, latlng) {
        var color = key === "warga" ? wargaColor(f.properties) : f.properties.color;
        var radius = key === "warga" ? 5 : key === "tanah" ? 6 : 5;
        return L.circleMarker(latlng, {
          radius: radius, color: key === "tanah" ? "#000" : "#fff", weight: key === "tanah" ? 2 : 1,
          fillColor: color, fillOpacity: 0.9
        });
      },
      onEachFeature: function (f, layer) { layer.bindPopup(popupHtml(f.properties)); }
    });
  }

  function loadLayer(key) {
    var url = urls.layer.replace("__key__", key);
    return request(url).then(function (data) {
      layerData[key] = data;
      if (layers[key]) { map.removeLayer(layers[key]); }
      layers[key] = buildLayer(key, data);
      if (layerState[key]) { layers[key].addTo(map); }
      if (key === "korwil" && !store("sudahFit") && data.features.length) {
        map.fitBounds(layers.korwil.getBounds(), { padding: [20, 20] });
        store("sudahFit", true);
      }
      renderLegend();
      return data;
    }).catch(function (error) {
      if (error instanceof ApiError && error.status) { toast("Lapisan " + key + ": " + error.message, "error"); }
    });
  }

  function restyle(key) {
    if (layerData[key]) {
      if (layers[key]) { map.removeLayer(layers[key]); }
      layers[key] = buildLayer(key, layerData[key]);
      if (layerState[key]) { layers[key].addTo(map); }
    }
    renderLegend();
  }

  var extraLayers = {};
  function toggleExtra(spec, on) {
    if (!on) {
      if (extraLayers[spec.key]) { map.removeLayer(extraLayers[spec.key]); }
      return;
    }
    if (extraLayers[spec.key]) { extraLayers[spec.key].addTo(map); return; }
    request(spec.url).then(function (data) {
      extraLayers[spec.key] = L.geoJSON(data, {
        style: function (f) {
          var c = (f.properties || {}).color || "#0969da";
          return { color: c, weight: 2, fillColor: c, fillOpacity: (f.properties || {}).outline ? 0 : 0.3 };
        },
        pointToLayer: function (f, latlng) {
          return L.circleMarker(latlng, { radius: 6, color: "#fff", weight: 1, fillColor: (f.properties || {}).color || "#cf222e", fillOpacity: 0.9 });
        },
        onEachFeature: function (f, layer) { layer.bindPopup(popupHtml(f.properties || {})); }
      }).addTo(map);
    }).catch(function (error) { toast(error.message, "error"); });
  }

  function legendEntries() {
    var entries = [];
    var kinds = { stance: "stance", land: "land", rtrw: "rtrw" };
    var colors = config.colors[modes.warga];
    if (layerState.warga && colors) {
      Object.keys(colors).forEach(function (key) {
        entries.push({ color: colors[key], label: "Warga: " + choiceLabel(kinds[modes.warga], key), round: true });
      });
    }
    if (layerState.korwil) {
      if (modes.korwil === "color") {
        config.korwils.forEach(function (k) { entries.push({ color: k.color, label: "Korwil " + k.code + " – " + k.name }); });
      } else {
        [[0, "0%"], [50, "50%"], [100, "100%"]].forEach(function (s) { entries.push({ color: rampColor(s[0]), label: "Korwil " + s[1] }); });
      }
    }
    if (layerState.tanah) {
      Object.keys(config.colors.soil).forEach(function (key) {
        entries.push({ color: config.colors.soil[key], label: "Uji tanah: " + choiceLabel("suitability", key), round: true });
      });
    }
    if (layerState.temuan) {
      Object.keys(config.colors.illegal).forEach(function (key) {
        entries.push({ color: config.colors.illegal[key], label: "Temuan: " + choiceLabel("illegalKind", key), round: true });
      });
    }
    if (layerState.patroli) {
      entries.push({ color: "#06b6d4", label: "Jalur patroli SMART" });
      entries.push({ color: "#10b981", label: "Mulai patroli", round: true });
      entries.push({ color: "#f59e0b", label: "Observasi patroli", round: true });
      entries.push({ color: "#ef4444", label: "Selesai patroli", round: true });
    }
    if (layerState.kegiatan) {
      Object.keys(config.colors.activity).forEach(function (key) {
        entries.push({ color: config.colors.activity[key], label: "Kegiatan: " + choiceLabel("activityType", key), round: true });
      });
    }
    if (layerState.bidang && perms.bidang) {
      Object.keys(config.colors.control).forEach(function (key) {
        entries.push({ color: config.colors.control[key], label: "Bidang: " + choiceLabel("control", key) });
      });
    }
    if (layerState.ancaman && perms.ancaman) {
      Object.keys(config.colors.threat).forEach(function (key) {
        entries.push({ color: config.colors.threat[key], label: "Zona ancaman " + choiceLabel("threat", key).toLowerCase() });
      });
    }
    if (layerState.foto360 && perms.foto360) { entries.push({ color: "#0ea5e9", label: "Foto situs 360°", round: true }); }
    LAYER_SPECS.forEach(function (spec) {
      if (!spec.ref || !layerState[spec.key]) { return; }
      if (spec.zoned) {
        Object.keys(config.colors.zone).forEach(function (key) {
          entries.push({ color: config.colors.zone[key], label: spec.name.split(" (")[0] + ": " + choiceLabel("zone", key) });
        });
      }
      entries.push({ color: spec.color, label: spec.name + (spec.zoned ? " – lainnya" : "") });
    });
    return entries;
  }

  function renderLegend() {
    $("legenda-isi").innerHTML = legendEntries().map(function (e) {
      return '<li><span class="swatch' + (e.round ? " round" : "") + '" style="background:' + escapeHtml(e.color) + '"></span>' + escapeHtml(e.label) + "</li>";
    }).join("");
  }

  function renderLayerList() {
    var html = LAYER_SPECS.map(function (spec) {
      return '<li><label class="check"><input type="checkbox" data-lapisan="' + spec.key + '"' + (layerState[spec.key] ? " checked" : "") + "> " + escapeHtml(spec.name) + "</label></li>";
    }).join("");
    html += config.extraLayers.map(function (spec) {
      return '<li><label class="check"><input type="checkbox" data-ekstra="' + escapeHtml(spec.key) + '"> ' + escapeHtml(spec.name) + "</label></li>";
    }).join("");
    html += config.basemaps.map(function (spec, index) {
      return '<li><label class="check"><input type="radio" name="dasar" data-dasar="' + index + '"' + (index === currentBase ? " checked" : "") + "> Peta dasar: " + escapeHtml(spec.name) + "</label></li>";
    }).join("");
    $("daftar-lapisan").innerHTML = html;
  }

  $("daftar-lapisan").addEventListener("change", function (event) {
    var input = event.target;
    var key = input.getAttribute("data-lapisan");
    if (key) {
      layerState[key] = input.checked;
      store("lapisan", layerState);
      if (input.checked) {
        if (layers[key]) { layers[key].addTo(map); } else { loadLayer(key); }
      } else if (layers[key]) { map.removeLayer(layers[key]); }
      renderLegend();
    }
    var extra = input.getAttribute("data-ekstra");
    if (extra) {
      toggleExtra(config.extraLayers.filter(function (s) { return s.key === extra; })[0], input.checked);
    }
    var base = input.getAttribute("data-dasar");
    if (base !== null) { setBase(parseInt(base, 10)); }
  });

  $("mode-warga").value = modes.warga;
  $("mode-korwil").value = modes.korwil;
  $("mode-warga").addEventListener("change", function () { modes.warga = this.value; store("modeWarga", modes.warga); restyle("warga"); });
  $("mode-korwil").addEventListener("change", function () { modes.korwil = this.value; store("modeKorwil", modes.korwil); restyle("korwil"); });

  map.on("popupopen", function (event) {
    var element = event.popup.getElement();
    var button = element.querySelector("[data-warga]");
    if (button) { button.addEventListener("click", function () { openResident(parseInt(button.getAttribute("data-warga"), 10)); }); }
    var plot = element.querySelector("[data-bidang]");
    if (plot) { plot.addEventListener("click", function () { openPlot(plot.getAttribute("data-bidang")); }); }
    var pano = element.querySelector("[data-foto360]");
    if (pano) { pano.addEventListener("click", function () { openPano(pano.getAttribute("data-foto360"), pano.getAttribute("data-judul")); }); }
  });

  // ---------------------------------------------------------------- Info Korwil

  function showKorwil(props, bounds) {
    selectedKorwil = props.id;
    restyle("korwil");
    var stats = props.stats || {};
    $("info-judul").textContent = props.title;
    $("in-warga").textContent = stats.total || 0;
    $("in-pro").textContent = pctText(stats.pro_pct);
    $("in-rtrw").textContent = pctText(stats.rtrw_pct);
    $("in-belum").textContent = stats.pending || 0;
    $("in-sudah").textContent = stats.released || 0;
    $("in-kegiatan").textContent = stats.activities || 0;
    $("info-korwil").hidden = false;
    $("info-fokus").onclick = function () { map.fitBounds(bounds, { padding: [30, 30] }); };
    $("info-cetak").onclick = function () { openPrint(props.id); };
    $("info-warga").onclick = function () { $("warga-korwil").value = String(props.id); showTab("warga"); };
  }

  // ================================================================ Ringkasan

  function loadSummary() {
    if (!navigator.onLine) { return; }
    request(urls.summary).then(function (data) {
      $("st-kegiatan").textContent = data.activities;
      $("st-pro").textContent = pctText(data.pro_pct);
      $("st-rtrw").textContent = pctText(data.rtrw_pct);
      $("st-korwil").textContent = data.korwil;
      $("st-tanah").textContent = data.soil;
      $("diperbarui").textContent = "Diperbarui " + fmtDate(data.updated_at, true) + " · " + data.present_today +
        " petugas hadir · " + data.online + " Live" + (data.sos_open ? " · 🆘 " + data.sos_open + " SOS aktif" : "");
    }).catch(function () { /* ditampilkan saat lapisan gagal */ });
  }

  document.querySelectorAll(".stat").forEach(function (button) {
    button.addEventListener("click", function () {
      var mode = button.getAttribute("data-mode");
      var layer = button.getAttribute("data-layer");
      var target = button.getAttribute("data-goto");
      if (mode) {
        modes.warga = mode;
        $("mode-warga").value = mode;
        modes.korwil = mode === "stance" ? "pro_pct" : "rtrw_pct";
        $("mode-korwil").value = modes.korwil;
        restyle("warga");
        restyle("korwil");
        showTab("peta");
        $("legenda").hidden = false;
      } else if (layer) {
        layerState[layer] = true;
        store("lapisan", layerState);
        renderLayerList();
        if (layers[layer]) { layers[layer].addTo(map); } else { loadLayer(layer); }
        showTab("peta");
      } else if (target) {
        showTab(target);
      }
    });
  });

  // ================================================================ Alat peta

  var toolMode = null;
  var measurePoints = [];
  var measureLine = null;
  var measureGroup = L.layerGroup().addTo(map);
  var tapMarker = null;
  var tappedPoint = null;

  function setTool(mode) {
    if (toolMode === "measure" && mode !== "measure") { resetMeasure(); $("ukur").hidden = true; }
    if (toolMode === "ai" && mode !== "ai") { stopAi(); }
    toolMode = mode;
    document.querySelector('[data-tool="measure"]').classList.toggle("active", mode === "measure");
    document.querySelector('[data-tool="ai"]').classList.toggle("active", mode === "ai");
    map.getContainer().style.cursor = mode ? "crosshair" : "";
  }

  function resetMeasure() {
    measurePoints = [];
    measureLine = null;
    measureGroup.clearLayers();
    $("ukur-jarak").textContent = "0 m";
  }

  function formatDistance(meters) {
    return meters >= 1000 ? (meters / 1000).toFixed(2) + " km" : Math.round(meters) + " m";
  }

  map.on("click", function (event) {
    if (toolMode === "measure") {
      measurePoints.push(event.latlng);
      if (!measureLine) { measureLine = L.polyline(measurePoints, { color: "#f59e0b", weight: 3, dashArray: "6 6" }).addTo(measureGroup); }
      measureLine.setLatLngs(measurePoints);
      var total = 0;
      for (var i = 1; i < measurePoints.length; i += 1) { total += map.distance(measurePoints[i - 1], measurePoints[i]); }
      $("ukur-jarak").textContent = formatDistance(total);
      L.circleMarker(event.latlng, { radius: 3, color: "#f59e0b" }).addTo(measureGroup);
      return;
    }
    if (toolMode) { return; }
    tappedPoint = event.latlng;
    if (tapMarker) { tapMarker.setLatLng(tappedPoint); } else { tapMarker = L.marker(tappedPoint).addTo(map); }
    tapMarker.bindPopup("Titik dipilih untuk laporan").openPopup();
  });

  $("ukur-ulang").addEventListener("click", resetMeasure);
  $("ukur-tutup").addEventListener("click", function () {
    setTool(null);
    resetMeasure();
    $("ukur").hidden = true;
  });

  var locateMarker = null;
  function locate() {
    currentPosition(15000).then(function (fix) {
      if (!fix) { toast("Lokasi tidak tersedia. Izinkan akses lokasi di peramban.", "error"); return; }
      var latlng = [fix.lat, fix.lng];
      if (locateMarker) { map.removeLayer(locateMarker); }
      locateMarker = L.layerGroup([
        L.circle(latlng, { radius: fix.accuracy, color: "#38bdf8", weight: 1, fillOpacity: 0.1 }),
        L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2, fillColor: "#38bdf8", fillOpacity: 1 })
      ]).addTo(map);
      map.setView(latlng, Math.max(map.getZoom(), 17));
    });
  }

  function toggleFullscreen() {
    var doc = document;
    if (doc.fullscreenElement || doc.webkitFullscreenElement) {
      (doc.exitFullscreen || doc.webkitExitFullscreen).call(doc);
    } else {
      var el = doc.documentElement;
      var fn = el.requestFullscreen || el.webkitRequestFullscreen;
      if (fn) { fn.call(el); } else { toast("Layar penuh tidak didukung perangkat ini.", "error"); }
    }
  }

  document.querySelector(".map-tools").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-tool]");
    if (!button) { return; }
    var tool = button.getAttribute("data-tool");
    runTool(tool);
  });

  function runTool(tool) {
    if (tool === "zoom-in") { map.zoomIn(); }
    else if (tool === "zoom-out") { map.zoomOut(); }
    else if (tool === "fullscreen") { toggleFullscreen(); }
    else if (tool === "locate") { showTab("peta"); locate(); }
    else if (tool === "measure") {
      showTab("peta");
      if (toolMode === "measure") { $("ukur-tutup").click(); } else { setTool("measure"); $("ukur").hidden = false; }
    }
    else if (tool === "satellite") { setBase(currentBase === satelliteIndex ? 0 : satelliteIndex); renderLayerList(); }
    else if (tool === "tactical") { setTactical(!map.getContainer().classList.contains("tactical")); }
    else if (tool === "clear-analysis") { clearAnalysis(); }
    else if (tool === "ai") { showTab("peta"); startAi(); }
    else if (tool === "print") { openPrint(selectedKorwil); }
    else if (tool === "voice") { startVoice(); }
    else if (tool === "chat") { showTab("chat"); }
    else if (tool === "legend") { showTab("peta"); $("legenda").hidden = !$("legenda").hidden; }
    else if (tool === "search") { openSearch(); }
  }

  document.querySelectorAll("[data-close]").forEach(function (button) {
    button.addEventListener("click", function () {
      $(button.getAttribute("data-close")).hidden = true;
      if (button.getAttribute("data-close") === "info-korwil") { selectedKorwil = null; restyle("korwil"); }
    });
  });

  // ---------------------------------------------------------------- AI Satelit

  var aiStart = null;
  var aiRect = null;

  function aiPointer(event) { return map.mouseEventToLatLng(event); }

  function aiDown(event) {
    if (toolMode !== "ai") { return; }
    event.preventDefault();
    aiStart = aiPointer(event);
    if (aiRect) { map.removeLayer(aiRect); }
    aiRect = L.rectangle([aiStart, aiStart], { color: "#1d82f5", weight: 2, dashArray: "4 4", fillOpacity: 0.1 }).addTo(map);
    map.getContainer().setPointerCapture && map.getContainer().setPointerCapture(event.pointerId);
  }

  function aiMove(event) {
    if (toolMode !== "ai" || !aiStart) { return; }
    aiRect.setBounds(L.latLngBounds(aiStart, aiPointer(event)));
  }

  function aiUp(event) {
    if (toolMode !== "ai" || !aiStart) { return; }
    var bounds = L.latLngBounds(aiStart, aiPointer(event));
    aiStart = null;
    var size = map.latLngToContainerPoint(bounds.getNorthEast()).distanceTo(map.latLngToContainerPoint(bounds.getSouthWest()));
    if (size < 15) { return; }
    setTool(null);
    runAi(bounds);
  }

  function startAi() {
    if (!perms.aiSatelit) { toast("Anda tidak berhak memakai AI Satelit.", "error"); return; }
    setTool("ai");
    map.dragging.disable();
    $("ai-petunjuk").hidden = false;
    var el = map.getContainer();
    el.addEventListener("pointerdown", aiDown);
    el.addEventListener("pointermove", aiMove);
    el.addEventListener("pointerup", aiUp);
  }

  function stopAi() {
    map.dragging.enable();
    $("ai-petunjuk").hidden = true;
    var el = map.getContainer();
    el.removeEventListener("pointerdown", aiDown);
    el.removeEventListener("pointermove", aiMove);
    el.removeEventListener("pointerup", aiUp);
    aiStart = null;
  }

  $("ai-batal").addEventListener("click", function () {
    if (aiRect) { map.removeLayer(aiRect); aiRect = null; }
    setTool(null);
  });

  function aiBars(cover) {
    var labels = { vegetasi_pct: "Vegetasi", bangunan_pct: "Bangunan", lahan_terbuka_pct: "Lahan terbuka", air_pct: "Air", jalan_pct: "Jalan" };
    return Object.keys(labels).map(function (key) {
      var value = Math.max(0, Math.min(100, Number(cover[key]) || 0));
      return '<div class="bar"><span style="width:110px">' + labels[key] + '</span><div class="progress"><i style="width:' + value + '%"></i></div><b>' + Math.round(value) + "%</b></div>";
    }).join("");
  }

  function summaryRows(summary) {
    var rows = [["Luas", (summary.luas_ha || 0) + " ha"]];
    if (summary.warga) {
      rows.push(["Warga terdata", summary.warga.total], ["Warga pro", summary.warga.pro], ["Warga menolak", summary.warga.menolak],
                ["Lahan sudah dibebaskan", summary.warga.lahan_sudah], ["RTRW sesuai", summary.warga.rtrw_sesuai]);
    }
    if (summary.kegiatan !== undefined) { rows.push(["Kegiatan", summary.kegiatan]); }
    if (summary.uji_tanah) { Object.keys(summary.uji_tanah).forEach(function (k) { rows.push(["Uji tanah – " + k, summary.uji_tanah[k]]); }); }
    if (summary.bidang_pengadaan) { rows.push(["Bidang pengadaan", summary.bidang_pengadaan.total + " (" + summary.bidang_pengadaan.lepas + " sudah lepas)"]); }
    if (summary.aset_lahan !== undefined) { rows.push(["Aset lahan", summary.aset_lahan], ["Okupasi terbuka", summary.okupasi_terbuka]); }
    return '<table class="table">' + rows.map(function (r) { return "<tr><th>" + escapeHtml(r[0]) + "</th><td>" + escapeHtml(r[1]) + "</td></tr>"; }).join("") + "</table>";
  }

  function runAi(bounds) {
    var dialog = $("dlg-ai");
    $("ai-isi").innerHTML = '<p>Mengunduh citra dan menganalisis area… (bisa sampai 1 menit)</p>';
    dialog.showModal();
    request(urls.satellite, { method: "POST", json: { bbox: [bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()] } })
      .then(function (data) {
        var html = "";
        if (data.image) { html += '<img class="ai-image" alt="Citra satelit area" src="' + escapeHtml(data.image) + '">'; }
        if (data.ai && data.ai.tutupan_lahan) {
          html += "<h4>Tutupan lahan</h4>" + aiBars(data.ai.tutupan_lahan);
          html += "<p><b>Perkiraan bangunan:</b> " + escapeHtml(data.ai.perkiraan_jumlah_bangunan) + "</p>";
          html += "<p>" + escapeHtml(data.ai.ringkasan) + "</p>";
          if ((data.ai.temuan || []).length) { html += "<h4>Temuan</h4><ul>" + data.ai.temuan.map(function (t) { return "<li>" + escapeHtml(t) + "</li>"; }).join("") + "</ul>"; }
          if ((data.ai.rekomendasi || []).length) { html += "<h4>Rekomendasi</h4><ul>" + data.ai.rekomendasi.map(function (t) { return "<li>" + escapeHtml(t) + "</li>"; }).join("") + "</ul>"; }
        } else {
          html += '<p class="muted">Analisis AI tidak tersedia' + (data.error ? ": " + escapeHtml(data.error) : " (kunci AI belum diatur).") + " Ringkasan data tetap ditampilkan.</p>";
        }
        html += "<h4>Data SimLahan di area ini</h4>" + summaryRows(data.summary || {});
        html += '<p class="small"><a href="' + escapeHtml(data.admin) + '" target="_blank" rel="noopener">Buka riwayat analisis</a></p>';
        $("ai-isi").innerHTML = html;
      })
      .catch(function (error) { $("ai-isi").innerHTML = '<p class="danger-text">' + escapeHtml(error.message || "Gagal menganalisis.") + "</p>"; });
  }

  // ---------------------------------------------------------------- Cetak / export PNG

  var PAPER_MM = { A3: [420, 297], A2: [594, 420], A1: [841, 594], A0: [1189, 841] };
  var PAPER_DPI = { A3: 150, A2: 150, A1: 120, A0: 100 };
  var LEGEND_COLUMNS = 3;

  function openPrint(korwilId) {
    fillSelect($("cetak-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " – " + k.name }; }), "Semua Korwil (wilayah kerja)");
    $("cetak-korwil").value = korwilId ? String(korwilId) : "";
    $("cetak-status").textContent = "";
    $("dlg-cetak").showModal();
  }

  function loadImage(url) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = function () { resolve(img); };
      img.onerror = function () { resolve(null); };
      img.src = url;
    });
  }

  function tileUrl(template, z, x, y) {
    var sub = "abc"[Math.abs(x + y) % 3];
    return template.replace("{s}", sub).replace("{z}", z).replace("{x}", x).replace("{y}", y).replace("{r}", "");
  }

  function printBounds(korwilId) {
    var data = layerData.korwil;
    if (data && data.features.length) {
      var features = korwilId ? data.features.filter(function (f) { return String(f.properties.id) === String(korwilId); }) : data.features;
      if (features.length) { return L.geoJSON({ type: "FeatureCollection", features: features }).getBounds(); }
    }
    return map.getBounds();
  }

  function exportPng() {
    var korwilId = $("cetak-korwil").value;
    var paper = $("cetak-kertas").value;
    var landscape = $("cetak-orientasi").value === "landscape";
    var dpi = PAPER_DPI[paper];
    var mm = PAPER_MM[paper];
    var width = Math.round((landscape ? mm[0] : mm[1]) / 25.4 * dpi);
    var height = Math.round((landscape ? mm[1] : mm[0]) / 25.4 * dpi);
    var unit = width / 1000;
    var header = Math.round(70 * unit);
    // Kaki peta memuat seluruh legenda (kolom 200 satuan di antara skala dan panah utara).
    var entries = legendEntries();
    var legendRows = Math.ceil(entries.length / LEGEND_COLUMNS);
    var footer = Math.round(Math.max(90, 34 + legendRows * 22) * unit);
    var mapW = width;
    var mapH = height - header - footer;
    var bounds = printBounds(korwilId).pad(0.05);
    var spec = config.basemaps[currentBase];
    var crs = L.CRS.EPSG3857;
    var zoom = Math.min(spec.maxZoom || 19, 19);
    for (; zoom > 1; zoom -= 1) {
      var nw = crs.latLngToPoint(bounds.getNorthWest(), zoom);
      var se = crs.latLngToPoint(bounds.getSouthEast(), zoom);
      if (se.x - nw.x <= mapW && se.y - nw.y <= mapH) { break; }
    }
    var center = crs.latLngToPoint(bounds.getCenter(), zoom);
    var origin = L.point(center.x - mapW / 2, center.y - mapH / 2);
    var canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    var x0 = Math.floor(origin.x / 256);
    var y0 = Math.floor(origin.y / 256);
    var x1 = Math.floor((origin.x + mapW) / 256);
    var y1 = Math.floor((origin.y + mapH) / 256);
    var jobs = [];
    var limit = Math.pow(2, zoom);
    for (var tx = x0; tx <= x1; tx += 1) {
      for (var ty = y0; ty <= y1; ty += 1) {
        if (ty < 0 || ty >= limit) { continue; }
        jobs.push({ x: tx, y: ty, wrap: ((tx % limit) + limit) % limit });
      }
    }
    $("cetak-status").textContent = "Menyiapkan peta… 0/" + jobs.length + " ubin";
    $("cetak-mulai").disabled = true;
    var done = 0;
    var queue = jobs.slice();
    function worker() {
      var job = queue.shift();
      if (!job) { return Promise.resolve(); }
      return loadImage(tileUrl(spec.url, zoom, job.wrap, job.y)).then(function (img) {
        if (img) { ctx.drawImage(img, job.x * 256 - origin.x, header + job.y * 256 - origin.y, 256, 256); }
        done += 1;
        $("cetak-status").textContent = "Menyiapkan peta… " + done + "/" + jobs.length + " ubin";
        return worker();
      });
    }
    var workers = [];
    for (var w = 0; w < 6; w += 1) { workers.push(worker()); }
    Promise.all(workers).then(function () {
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, header, mapW, mapH);
      ctx.clip();
      drawVectors(ctx, crs, zoom, origin, header, unit, korwilId);
      ctx.restore();
      drawFrame(ctx, width, height, header, footer, unit, korwilId, paper, zoom, bounds, entries);
      canvas.toBlob(function (blob) {
        $("cetak-mulai").disabled = false;
        if (!blob) { $("cetak-status").textContent = "Peramban menolak membuat PNG (ukuran terlalu besar). Pilih kertas lebih kecil."; return; }
        var korwil = config.korwils.filter(function (k) { return String(k.id) === korwilId; })[0];
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "peta-" + (korwil ? "korwil-" + korwil.code : "semua-korwil") + "-" + paper + ".png";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(link.href); }, 10000);
        $("cetak-status").textContent = "Selesai. Berkas PNG diunduh.";
      }, "image/png");
    }).catch(function () {
      $("cetak-mulai").disabled = false;
      $("cetak-status").textContent = "Gagal menyiapkan peta.";
    });
  }

  function project(crs, zoom, origin, header, lng, lat) {
    var p = crs.latLngToPoint(L.latLng(lat, lng), zoom);
    return [p.x - origin.x, header + p.y - origin.y];
  }

  function drawPolygon(ctx, rings, crs, zoom, origin, header) {
    rings.forEach(function (ring) {
      ring.forEach(function (coord, i) {
        var p = project(crs, zoom, origin, header, coord[0], coord[1]);
        if (i === 0) { ctx.moveTo(p[0], p[1]); } else { ctx.lineTo(p[0], p[1]); }
      });
      ctx.closePath();
    });
  }

  function drawVectors(ctx, crs, zoom, origin, header, unit, korwilId) {
    var korwils = layerData.korwil && layerState.korwil ? layerData.korwil.features : [];
    korwils.forEach(function (f) {
      var focus = !korwilId || String(f.properties.id) === korwilId;
      var color = korwilColor(f.properties);
      var geom = f.geometry;
      var polys = geom.type === "MultiPolygon" ? geom.coordinates : [geom.coordinates];
      ctx.beginPath();
      polys.forEach(function (rings) { drawPolygon(ctx, rings, crs, zoom, origin, header); });
      ctx.globalAlpha = focus ? (modes.korwil === "color" ? 0.15 : 0.4) : 0.05;
      ctx.fillStyle = color;
      ctx.fill("evenodd");
      ctx.globalAlpha = 1;
      ctx.lineWidth = Math.max(2, 3 * unit);
      ctx.strokeStyle = focus ? color : "#888888";
      ctx.stroke();
      var c = L.geoJSON(f).getBounds().getCenter();
      var p = project(crs, zoom, origin, header, c.lng, c.lat);
      ctx.font = "bold " + Math.round(28 * unit) + "px sans-serif";
      ctx.textAlign = "center";
      ctx.lineWidth = Math.max(3, 5 * unit);
      ctx.strokeStyle = "#000";
      ctx.strokeText(f.properties.code, p[0], p[1]);
      ctx.fillStyle = "#fff";
      ctx.fillText(f.properties.code, p[0], p[1]);
    });
    ["warga", "kegiatan", "tanah"].forEach(function (key) {
      if (!layerState[key] || !layerData[key]) { return; }
      layerData[key].features.forEach(function (f) {
        if (!f.geometry || f.geometry.type !== "Point") { return; }
        var p = project(crs, zoom, origin, header, f.geometry.coordinates[0], f.geometry.coordinates[1]);
        ctx.beginPath();
        ctx.arc(p[0], p[1], Math.max(3, (key === "tanah" ? 7 : 5) * unit), 0, Math.PI * 2);
        ctx.fillStyle = key === "warga" ? wargaColor(f.properties) : f.properties.color;
        ctx.fill();
        ctx.lineWidth = Math.max(1, 1.5 * unit);
        ctx.strokeStyle = key === "tanah" ? "#000" : "#fff";
        ctx.stroke();
      });
    });
  }

  // Label panjang diperkecil hingga 10 px (skala kertas), lalu keterangan dalam
  // kurung dibuang, baru terakhir dipotong "…".
  function fitText(ctx, text, maxWidth, unit) {
    var short = text.replace(/\s*\([^)]*\)\s*$/, "");
    var candidates = short && short !== text ? [text, short] : [text];
    for (var i = 0; i < candidates.length; i++) {
      for (var size = 13; size >= 10; size--) {
        ctx.font = Math.round(size * unit) + "px sans-serif";
        if (ctx.measureText(candidates[i]).width <= maxWidth) return candidates[i];
      }
    }
    var cut = candidates[candidates.length - 1];
    while (cut.length > 1 && ctx.measureText(cut + "…").width > maxWidth) cut = cut.slice(0, -1);
    return cut.replace(/\s+$/, "") + "…";
  }

  function drawFrame(ctx, width, height, header, footer, unit, korwilId, paper, zoom, bounds, entries) {
    var korwil = config.korwils.filter(function (k) { return String(k.id) === korwilId; })[0];
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, header);
    ctx.fillRect(0, height - footer, width, footer);
    ctx.fillStyle = "#e8eef3";
    ctx.fillRect(0, header - 2 * unit, width, 2 * unit);
    ctx.fillRect(0, height - footer, width, 2 * unit);
    ctx.fillStyle = "#1d82f5";
    ctx.font = "bold " + Math.round(30 * unit) + "px sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(config.appName + " · Peta " + (korwil ? "Korwil " + korwil.code + " – " + korwil.name : "Seluruh Korwil"), 24 * unit, header / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#28313c";
    ctx.font = Math.round(16 * unit) + "px sans-serif";
    ctx.fillText("Dicetak " + fmtDate(new Date().toISOString(), true) + " · Kertas " + paper + " · oleh " + config.user.name, width - 24 * unit, header / 2);
    // Skala
    var lat = bounds.getCenter().lat;
    var metersPerPx = 40075016.686 * Math.cos(lat * Math.PI / 180) / (256 * Math.pow(2, zoom));
    var target = 200 * unit * metersPerPx;
    var nice = [1, 2, 5].reduce(function (best, base) {
      var exp = Math.pow(10, Math.floor(Math.log10(target)));
      var candidate = base * exp;
      return candidate <= target && candidate > best ? candidate : best;
    }, 0) || target;
    var barPx = nice / metersPerPx;
    var by = height - footer / 2;
    ctx.fillStyle = "#28313c";
    ctx.fillRect(24 * unit, by, barPx, 6 * unit);
    ctx.textAlign = "left";
    ctx.font = Math.round(14 * unit) + "px sans-serif";
    ctx.fillText(formatDistance(nice), 24 * unit, by - 14 * unit);
    // Panah utara
    var ax = width - 60 * unit;
    var ay = height - footer / 2;
    ctx.beginPath();
    ctx.moveTo(ax, ay - 28 * unit);
    ctx.lineTo(ax - 12 * unit, ay + 12 * unit);
    ctx.lineTo(ax, ay + 4 * unit);
    ctx.lineTo(ax + 12 * unit, ay + 12 * unit);
    ctx.closePath();
    ctx.fill();
    ctx.textAlign = "center";
    ctx.fillText("U", ax, ay + 28 * unit);
    // Legenda
    var x = 240 * unit;
    var y = height - footer + 20 * unit;
    ctx.textAlign = "left";
    ctx.font = Math.round(13 * unit) + "px sans-serif";
    var rows = Math.max(1, Math.ceil(entries.length / LEGEND_COLUMNS));
    // Lebar kolom mengikuti ruang antara skala dan panah utara.
    var legendEnd = width - 90 * unit;
    var columnWidth = Math.max(200 * unit, (legendEnd - x) / LEGEND_COLUMNS);
    var lastColumn = Math.ceil(entries.length / rows) - 1;
    entries.forEach(function (entry, index) {
      var column = Math.floor(index / rows);
      var ex = x + column * columnWidth;
      // Kolom terakhir boleh memakai ruang hingga panah utara.
      var textWidth = (column === lastColumn ? legendEnd - ex : columnWidth - 10 * unit) - 20 * unit;
      var ey = y + (index % rows) * 22 * unit;
      ctx.fillStyle = entry.color;
      ctx.fillRect(ex, ey - 7 * unit, 14 * unit, 14 * unit);
      ctx.fillStyle = "#28313c";
      ctx.fillText(fitText(ctx, entry.label, textWidth, unit), ex + 20 * unit, ey);
    });
    ctx.fillStyle = "#616e80";
    ctx.font = Math.round(11 * unit) + "px sans-serif";
    ctx.textAlign = "right";
    var attribution = (config.basemaps[currentBase].attribution || "").replace(/<[^>]+>/g, "").replace(/&copy;/g, "©");
    ctx.fillText(attribution, width - 100 * unit, height - 10 * unit);
  }

  $("cetak-mulai").addEventListener("click", exportPng);

  // ---------------------------------------------------------------- Perintah suara

  var recognition = null;
  function startVoice() {
    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { toast("Perintah suara tidak didukung peramban ini. Gunakan Chrome.", "error"); return; }
    if (recognition) { recognition.abort(); return; }
    recognition = new Recognition();
    recognition.lang = "id-ID";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    $("suara").hidden = false;
    $("suara-teks").textContent = "";
    document.querySelector('[data-tool="voice"]').classList.add("active");
    recognition.onresult = function (event) {
      var result = event.results[event.results.length - 1];
      $("suara-teks").textContent = result[0].transcript;
      if (result.isFinal) { runVoice(result[0].transcript); }
    };
    recognition.onerror = function (event) {
      if (event.error === "not-allowed") { toast("Izinkan mikrofon untuk perintah suara.", "error"); }
    };
    recognition.onend = function () {
      recognition = null;
      $("suara").hidden = true;
      document.querySelector('[data-tool="voice"]').classList.remove("active");
    };
    recognition.start();
  }

  function runVoice(text) {
    var t = text.toLowerCase().trim();
    var korwil = t.match(/korwil\s+([a-z0-9]+)/);
    if (korwil) {
      var found = config.korwils.filter(function (k) { return k.code.toLowerCase() === korwil[1]; })[0];
      if (found) { focusKorwil(found.id); return; }
    }
    var command = COMMANDS.filter(function (c) {
      return c.words.some(function (w) { return t.indexOf(w) !== -1; });
    })[0];
    if (command) { command.run(); toast("Perintah: " + command.label, "ok"); return; }
    var query = t.replace(/^(cari|tampilkan|temukan)\s+/, "");
    openSearch(query);
  }

  function focusKorwil(id) {
    showTab("peta");
    var data = layerData.korwil;
    var feature = data && data.features.filter(function (f) { return f.properties.id === id; })[0];
    if (feature) {
      var bounds = L.geoJSON(feature).getBounds();
      map.fitBounds(bounds, { padding: [30, 30] });
      showKorwil(feature.properties, bounds);
    }
  }

  // ---------------------------------------------------------------- Kompas & Live

  var heading = null;
  function onOrientation(event) {
    var value = null;
    if (typeof event.webkitCompassHeading === "number") { value = event.webkitCompassHeading; }
    else if (event.absolute && typeof event.alpha === "number") { value = (360 - event.alpha) % 360; }
    if (value === null) { return; }
    heading = Math.round(value);
    $("kompas-cincin").style.transform = "rotate(" + (-heading) + "deg)";
    var dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    $("kompas-derajat").textContent = heading + "° " + dirs[Math.round(heading / 45) % 8];
  }

  function startCompass() {
    var Orientation = window.DeviceOrientationEvent;
    if (!Orientation) { $("kompas-derajat").textContent = "tanpa sensor"; return Promise.resolve(); }
    var ask = typeof Orientation.requestPermission === "function" ? Orientation.requestPermission() : Promise.resolve("granted");
    return ask.then(function (state) {
      if (state !== "granted") { return; }
      if ("ondeviceorientationabsolute" in window) {
        window.addEventListener("deviceorientationabsolute", onOrientation);
      } else {
        window.addEventListener("deviceorientation", onOrientation);
      }
    }).catch(function () { /* izin ditolak */ });
  }

  var live = false;
  var liveMarker = null;
  var lastSent = 0;
  var lastSentFix = null;
  var follow = true;

  map.on("dragstart", function () { follow = false; });

  function battery() {
    if (!navigator.getBattery) { return Promise.resolve(null); }
    return navigator.getBattery().then(function (b) { return Math.round(b.level * 100); }).catch(function () { return null; });
  }

  function onLiveFix() {
    if (!live || !lastFix) { return; }
    var latlng = [lastFix.lat, lastFix.lng];
    if (!liveMarker) {
      liveMarker = L.circleMarker(latlng, { radius: 9, color: "#fff", weight: 3, fillColor: "#1d82f5", fillOpacity: 1 }).addTo(map);
    } else { liveMarker.setLatLng(latlng); }
    if (follow) { map.panTo(latlng); }
    var moved = lastSentFix ? map.distance(latlng, [lastSentFix.lat, lastSentFix.lng]) : Infinity;
    if (perms.live && navigator.onLine && (Date.now() - lastSent > 20000 || moved > 25)) {
      lastSent = Date.now();
      lastSentFix = lastFix;
      battery().then(function (level) {
        request(urls.position, { method: "POST", body: form({
          lat: lastFix.lat, lng: lastFix.lng, accuracy: lastFix.accuracy,
          heading: heading !== null ? heading : lastFix.heading, speed: lastFix.speed, battery: level
        }) }).catch(function () { lastSent = 0; });
      });
    }
  }

  $("live").addEventListener("click", function () {
    live = !live;
    this.setAttribute("aria-pressed", live ? "true" : "false");
    if (live) {
      follow = true;
      startCompass();
      startGps();
      if (perms.lihatPetugas) {
        layerState.petugas = true;
        renderLayerList();
        loadLayer("petugas");
      }
      onLiveFix();
      toast(perms.live ? "Mode Live aktif: posisi Anda dibagikan ke pusat komando." : "Mode Live aktif.", "ok");
    } else {
      if (liveMarker) { map.removeLayer(liveMarker); liveMarker = null; }
      if (perms.live) { request(urls.position, { method: "POST", body: form({ stop: "1" }) }).catch(function () {}); }
      lastSentFix = null;
      toast("Mode Live dimatikan.");
    }
  });
  $("kompas").addEventListener("click", function (event) {
    if (event.target.id !== "live") { startCompass(); follow = true; }
  });

  // ================================================================ Tab

  var currentTab = "peta";
  // Tab di balik tombol "Lainnya" agar bilah tab muat di layar ponsel.
  var MORE_TABS = ["beranda", "spasial", "persetujuan", "laporan", "peringkat", "struktur", "historis", "feed", "ai"];
  // Tab dan sub-tab yang tidak bisa dipakai peran pengguna tidak ditampilkan.
  var TAB_ALLOWED = {
    absen: perms.absen,
    korwil: perms.lapor || perms.tambahTanah || perms.kegiatan,
    warga: perms.warga,
    tasks: perms.tugas,
    laporan: perms.laporanHarian,
    historis: perms.historis,
    chat: perms.chat
  };
  var SUB_ALLOWED = { kegiatan: perms.lapor, tanah: perms.tambahTanah, riwayat: perms.kegiatan };
  function applyTabPermissions() {
    Object.keys(TAB_ALLOWED).forEach(function (name) {
      var button = document.querySelector('.tabbar button[data-tab="' + name + '"]');
      if (button) { button.hidden = !TAB_ALLOWED[name]; }
      var entry = document.querySelector('.more-menu button[data-buka="' + name + '"]');
      if (entry) { entry.hidden = !TAB_ALLOWED[name]; }
    });
    var firstSub = null;
    document.querySelectorAll(".segmented button[data-sub]").forEach(function (button) {
      var sub = button.getAttribute("data-sub");
      button.hidden = SUB_ALLOWED[sub] === false;
      if (!button.hidden && !firstSub) { firstSub = button; }
    });
    var active = document.querySelector(".segmented button[data-sub].active");
    if (firstSub && active && active.hidden) { firstSub.click(); }
  }
  function showTab(name) {
    if (TAB_ALLOWED[name] === false) { name = "peta"; }
    currentTab = name;
    var barTab = MORE_TABS.indexOf(name) !== -1 ? "lainnya" : name;
    document.querySelectorAll(".tab-view").forEach(function (view) {
      if (view.id === "tab-peta") { return; }
      view.hidden = view.id !== "tab-" + name;
    });
    document.querySelectorAll(".tabbar button").forEach(function (button) {
      button.classList.toggle("active", button.getAttribute("data-tab") === barTab);
    });
    if (name === "absen") { loadAttendance(); }
    if (name === "korwil") { loadMyReports(); loadTaskOptions(); }
    if (name === "warga") { loadResidents(); }
    if (name === "tasks") { loadTasks(); }
    if (name === "laporan") { loadReports(); }
    if (name === "persetujuan") { loadApprovals(); }
    if (name === "beranda") { loadHome(); }
    if (name === "spasial") { loadSpatial(); }
    if (name === "historis") { loadHistory(); }
    if (name === "perf") { loadPerformance(); }
    if (name === "peringkat") { loadLeaderboard(); }
    if (name === "struktur") { loadStructure(); }
    if (name === "feed") {
      if ($("feed-korwil").options.length <= 1) {
        fillSelect($("feed-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code }; }), "Semua Korwil");
      }
      loadFeed();
    }
    if (name === "chat") { loadChat(true); }
    syncSosSpace();
    setTimeout(function () { map.invalidateSize(); }, 50);
  }

  document.querySelector(".tabbar").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-tab]");
    if (button) { showTab(button.getAttribute("data-tab")); }
  });
  $("tab-lainnya").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-buka]");
    if (button) { showTab(button.getAttribute("data-buka")); }
  });

  // ================================================================ Absen

  function attendanceCard(a) {
    if (!a) { return "<b>Belum absen hari ini.</b> Jam masuk " + escapeHtml(config.settings.workStart) + ", pulang " + escapeHtml(config.settings.workEnd) + "."; }
    var area = function (value) { return value === false ? ' <span class="badge" style="background:#9a6700">di luar wilayah</span>' : ""; };
    return "<b>" + escapeHtml(a.status_label) + "</b>" + (a.korwil ? " · " + escapeHtml(a.korwil) : "") +
      "<br>Masuk: " + fmtTime(a.check_in_at) + area(a.check_in_in_area) +
      " · Pulang: " + fmtTime(a.check_out_at) + area(a.check_out_in_area) +
      (a.worked_minutes !== null ? "<br>Durasi kerja: " + Math.floor(a.worked_minutes / 60) + " j " + (a.worked_minutes % 60) + " m" : "") +
      (a.note ? "<br><span class='muted'>" + escapeHtml(a.note) + "</span>" : "");
  }

  function loadAttendance() {
    if (!perms.absen) { $("absen-hari-ini").textContent = "Akun Anda tidak memakai absen di aplikasi ini."; return; }
    request(urls.attendance).then(function (data) {
      var today = data.today;
      $("absen-hari-ini").innerHTML = attendanceCard(today);
      $("absen-masuk").disabled = !!(today && today.check_in_at);
      $("absen-pulang").disabled = !(today && today.check_in_at && !today.check_out_at);
      $("absen-riwayat").innerHTML = data.history.map(function (a) {
        return "<li><div class='title'>" + fmtDate(a.date) + " · " + escapeHtml(a.status_label) + "</div><div class='sub'>Masuk " + fmtTime(a.check_in_at) +
          " · Pulang " + fmtTime(a.check_out_at) + (a.missing_checkout ? " · lupa absen pulang" : "") + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada riwayat.</li>";
    }).catch(function (error) { $("absen-hari-ini").textContent = error.message || "Absen butuh koneksi internet."; });
    loadLeaveRequests();
  }

  function doAttendance(action) {
    if (!navigator.onLine) { toast("Absen butuh koneksi internet.", "error"); return; }
    var button = $(action === "masuk" ? "absen-masuk" : "absen-pulang");
    button.disabled = true;
    toast("Mengambil lokasi GPS…");
    currentPosition(20000).then(function (fix) {
      if (!fix) { throw new ApiError("Lokasi GPS wajib untuk absen. Izinkan akses lokasi.", 0); }
      return photoFiles($("absen-foto"), "foto", 1).then(function (files) {
        var data = form({ aksi: action, lat: fix.lat, lng: fix.lng, accuracy: fix.accuracy });
        files.forEach(function (f) { data.append(f.field, f.blob, f.name); });
        return request(urls.attendance, { method: "POST", body: data });
      });
    }).then(function (data) {
      $("absen-foto").value = "";
      var warnings = (data.warnings || []).join(" ");
      toast((action === "masuk" ? "Absen masuk tercatat. " : "Absen pulang tercatat. ") + warnings, warnings ? "" : "ok");
      loadAttendance();
      loadSummary();
    }).catch(function (error) {
      toast(error.message || "Absen gagal.", "error");
      button.disabled = false;
    });
  }

  $("absen-masuk").addEventListener("click", function () { doAttendance("masuk"); });
  $("absen-pulang").addEventListener("click", function () { doAttendance("pulang"); });
  $("form-izin").addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(this);
    data.append("aksi", "izin");
    request(urls.attendance, { method: "POST", body: data }).then(function () {
      toast("Pengajuan terkirim, menunggu persetujuan koordinator.", "ok");
      event.target.reset();
      loadAttendance();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  function loadLeaveRequests() {
    if (!perms.setujuiIzin) { return; }
    $("izin-tim").hidden = false;
    request(urls.leaveRequests).then(function (data) {
      $("izin-tim-daftar").innerHTML = data.results.map(function (a) {
        return "<li><div class='title'>" + escapeHtml(a.user) + " · " + fmtDate(a.date) + " · " + escapeHtml(a.status_label) + "</div>" +
          "<div class='sub'>" + escapeHtml(a.note || "") + (a.attachment ? " · <a href='" + escapeHtml(a.attachment) + "' target='_blank' rel='noopener'>lampiran</a>" : "") + "</div>" +
          "<div class='row'><button type='button' class='btn-small' data-izin='" + a.id + "' data-keputusan='setuju'>Setujui</button>" +
          "<button type='button' class='btn-small' data-izin='" + a.id + "' data-keputusan='tolak'>Tolak</button></div></li>";
      }).join("") || "<li class='muted'>Tidak ada pengajuan menunggu.</li>";
    }).catch(function (error) { $("izin-tim-daftar").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  $("izin-tim-daftar").addEventListener("click", function (event) {
    var id = event.target.getAttribute("data-izin");
    if (!id) { return; }
    var decision = event.target.getAttribute("data-keputusan");
    request(urls.leaveDecision.replace("/0/", "/" + id + "/"), { method: "POST", body: form({ keputusan: decision }) }).then(function () {
      toast(decision === "setuju" ? "Pengajuan disetujui." : "Pengajuan ditolak.", "ok");
      loadLeaveRequests();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  // ================================================================ Lapor kegiatan & uji tanah

  var chosenResidents = {};

  function renderChosen() {
    var stanceOptions = '<option value="">sikap tetap</option>' + config.choices.stance.map(function (c) {
      return '<option value="' + escapeHtml(c.value) + '">' + escapeHtml(c.label) + "</option>";
    }).join("");
    $("kg-warga").innerHTML = Object.keys(chosenResidents).map(function (id) {
      var r = chosenResidents[id];
      return '<li data-id="' + id + '">' + escapeHtml(r.name) +
        (perms.ubahWarga ? ' <select data-sikap="' + id + '" aria-label="Sikap baru">' + stanceOptions + "</select>" : "") +
        ' <button type="button" class="close" data-lepas="' + id + '">✕</button></li>';
    }).join("");
    Object.keys(chosenResidents).forEach(function (id) {
      var select = document.querySelector('[data-sikap="' + id + '"]');
      if (select) { select.value = chosenResidents[id].newStance || ""; }
    });
  }

  $("kg-warga").addEventListener("change", function (event) {
    var id = event.target.getAttribute("data-sikap");
    if (id) { chosenResidents[id].newStance = event.target.value; }
  });
  $("kg-warga").addEventListener("click", function (event) {
    var id = event.target.getAttribute("data-lepas");
    if (id) { delete chosenResidents[id]; renderChosen(); }
  });

  var suggestTimer = null;
  $("kg-cari-warga").addEventListener("input", function () {
    var q = this.value.trim();
    clearTimeout(suggestTimer);
    if (q.length < 2 || !perms.warga) { $("kg-saran").innerHTML = ""; return; }
    suggestTimer = setTimeout(function () {
      request(urls.residents + "?q=" + encodeURIComponent(q)).then(function (data) {
        $("kg-saran").innerHTML = data.results.slice(0, 10).map(function (r) {
          return '<li data-id="' + r.id + '" data-name="' + escapeHtml(r.name) + '">' + escapeHtml(r.name) + ' <span class="muted small">' + escapeHtml(r.number + " · " + (r.village || "") + " · " + choiceLabel("stance", r.stance)) + "</span></li>";
        }).join("");
      }).catch(function () { $("kg-saran").innerHTML = ""; });
    }, 250);
  });
  $("kg-saran").addEventListener("click", function (event) {
    var li = event.target.closest("li[data-id]");
    if (!li) { return; }
    chosenResidents[li.getAttribute("data-id")] = { name: li.getAttribute("data-name"), newStance: "" };
    $("kg-saran").innerHTML = "";
    $("kg-cari-warga").value = "";
    renderChosen();
  });

  // ================================================================ Bagian laporan per jenis

  var TYPE_ICONS = { komsos: "💬", topografi: "📐", temuan_ilegal: "⚠️", taman_buru: "🌲", lainnya: "📋" };
  var AUTO_TITLE = ["komsos", "topografi", "temuan_ilegal", "taman_buru"];
  var MAX_NEW_RESIDENTS = 10;
  var newResidents = [];
  var patrolFindings = [];
  var findingFiles = [];
  var seedlings = [];
  var smartFile = null;
  var smartPoint = null;
  var tiMode = "baru";
  var tiFound = {};

  function renderTypeCards() {
    var current = $("kg-jenis").value;
    $("kg-kartu").innerHTML = config.choices.fieldTypes.map(function (value) {
      return '<button type="button" role="radio" data-kartu="' + escapeHtml(value) + '" aria-checked="' + (current === value) + '"' +
        (current === value ? ' class="active"' : "") + '><span aria-hidden="true">' + (TYPE_ICONS[value] || "📋") + "</span>" +
        escapeHtml(choiceLabel("activityType", value)) + "</button>";
    }).join("");
  }

  function applyActivityType() {
    var type = $("kg-jenis").value;
    document.querySelectorAll("#form-kegiatan .jenis-part").forEach(function (part) {
      part.hidden = part.getAttribute("data-jenis") !== type;
    });
    var auto = AUTO_TITLE.indexOf(type) !== -1;
    $("kg-judul-label").textContent = type === "lainnya" ? "Nama kegiatan" : auto ? "Judul (opsional, dibuat otomatis)" : "Judul";
    $("kg-uraian-label").textContent = type === "komsos" ? "Narasi hasil komsos" : "Uraian / narasi";
    $("kg-lokasi").required = type === "taman_buru";
    renderTypeCards();
    updateImpact();
  }

  $("kg-kartu").addEventListener("click", function (event) {
    var button = event.target.closest("[data-kartu]");
    if (!button) { return; }
    $("kg-jenis").value = button.getAttribute("data-kartu");
    applyActivityType();
  });
  $("kg-jenis").addEventListener("change", applyActivityType);

  // --- Komsos: warga baru ---

  function newResidentInputs() { return document.querySelectorAll("#kg-warga-baru-form [data-wb]"); }

  function closeNewResident() {
    newResidentInputs().forEach(function (input) { input.value = ""; });
    document.querySelectorAll("#kg-warga-baru-form .pilih-sikap").forEach(function (sel) { sel.value = "belum"; });
    $("kg-warga-baru-form").hidden = true;
    $("kg-warga-baru-buka").hidden = !perms.tambahWarga;
  }

  function renderNewResidents() {
    $("kg-warga-baru").innerHTML = newResidents.map(function (person, index) {
      var info = [choiceLabel("residency", person.status_warga || ""), person.kampung].filter(Boolean).join(" · ");
      return "<li>🆕 " + escapeHtml(person.nama) + (info ? ' <span class="muted small">' + escapeHtml(info) + "</span>" : "") +
        ' <button type="button" class="close" data-hapus-wb="' + index + '" aria-label="Hapus">✕</button></li>';
    }).join("");
  }

  $("kg-warga-baru-buka").addEventListener("click", function () {
    if (newResidents.length >= MAX_NEW_RESIDENTS) { toast("Paling banyak " + MAX_NEW_RESIDENTS + " warga baru per laporan.", "error"); return; }
    $("kg-warga-baru-form").hidden = false;
    this.hidden = true;
  });
  $("kg-warga-baru-batal").addEventListener("click", closeNewResident);
  $("kg-warga-baru-simpan").addEventListener("click", function () {
    var person = {};
    newResidentInputs().forEach(function (input) {
      var value = (input.value || "").trim();
      if (value) { person[input.getAttribute("data-wb")] = value; }
    });
    if (!person.nama) { toast("Nama warga wajib diisi.", "error"); return; }
    newResidents.push(person);
    renderNewResidents();
    closeNewResident();
  });
  $("kg-warga-baru").addEventListener("click", function (event) {
    var index = event.target.getAttribute("data-hapus-wb");
    if (index !== null) { newResidents.splice(parseInt(index, 10), 1); renderNewResidents(); }
  });

  // --- Temuan ilegal: baru / berulang ---

  var TI_PROFILE = { ti_aktivitas: "kind", ti_lokasi: "location_name", ti_pemilik: "owner_name", ti_pemilik_hp: "owner_phone",
    ti_domisili: "owner_domicile", ti_pengurus: "manager_name", ti_pengurus_hp: "manager_phone", ti_luas: "area_ha",
    ti_status_hutan: "forest_status", ti_mulai: "business_started" };

  function tiInput(name) { return document.querySelector('#form-kegiatan [name="' + name + '"]'); }

  function clearTiProfile() {
    Object.keys(TI_PROFILE).forEach(function (name) { tiInput(name).value = ""; });
    $("ti-aktivitas").value = (config.choices.illegalKind[0] || {}).value || "";
  }

  function setTiMode(mode) {
    tiMode = mode;
    document.querySelectorAll("#ti-mode [data-ti-mode]").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-ti-mode") === mode); });
    $("ti-berulang").hidden = mode !== "berulang";
    $("ti-id").value = "";
    $("ti-terpilih").textContent = mode === "berulang" ? "Belum ada temuan dipilih." : "";
    $("ti-saran").innerHTML = "";
    $("ti-cari").value = "";
    clearTiProfile();
  }

  $("ti-mode").addEventListener("click", function (event) {
    var button = event.target.closest("[data-ti-mode]");
    if (button && !button.hidden) { setTiMode(button.getAttribute("data-ti-mode")); }
  });

  var tiTimer = null;
  $("ti-cari").addEventListener("input", function () {
    var q = this.value.trim();
    clearTimeout(tiTimer);
    if (q.length < 2) { $("ti-saran").innerHTML = ""; return; }
    tiTimer = setTimeout(function () {
      request(urls.illegalFindings + "?q=" + encodeURIComponent(q)).then(function (data) {
        tiFound = {};
        $("ti-saran").innerHTML = data.results.map(function (f) {
          tiFound[f.id] = f;
          return '<li data-id="' + f.id + '">' + escapeHtml(f.location_name) + ' <span class="muted small">' +
            escapeHtml(f.number + " · " + f.kind_label + (f.owner_name ? " · " + f.owner_name : "")) + "</span></li>";
        }).join("") || "<li class='muted'>Tidak ditemukan.</li>";
      }).catch(function () { $("ti-saran").innerHTML = ""; });
    }, 300);
  });
  $("ti-saran").addEventListener("click", function (event) {
    var li = event.target.closest("li[data-id]");
    var found = li && tiFound[li.getAttribute("data-id")];
    if (!found) { return; }
    $("ti-id").value = found.id;
    Object.keys(TI_PROFILE).forEach(function (name) { tiInput(name).value = found[TI_PROFILE[name]] || ""; });
    $("ti-terpilih").textContent = "Dipilih: " + found.number + " – " + found.location_name + ". Isian profil yang diubah ikut diperbarui.";
    $("ti-saran").innerHTML = "";
    if (found.lat !== null && !$("kg-titik").checked) { smartPoint = null; }
  });

  // --- Patroli Taman Buru ---

  function renderRoutes() {
    $("tb-rute").innerHTML = config.choices.patrolRoute.map(function (c) {
      return '<label class="check"><input type="checkbox" value="' + escapeHtml(c.value) + '"> ' + escapeHtml(c.label) + "</label>";
    }).join("");
  }

  function optionsHtml(kind, current, placeholder) {
    return (placeholder ? '<option value="">' + escapeHtml(placeholder) + "</option>" : "") + config.choices[kind].map(function (c) {
      return '<option value="' + escapeHtml(c.value) + '"' + (String(c.value) === String(current) ? " selected" : "") + ">" + escapeHtml(c.label) + "</option>";
    }).join("");
  }

  function renderPatrolFindings() {
    $("tb-temuan").innerHTML = patrolFindings.map(function (f, i) {
      var files = findingFiles[i] || [];
      return '<div class="card mini" data-tf-row="' + i + '"><div class="row"><b>Temuan ' + (i + 1) + "</b>" +
        '<button type="button" class="close" data-tf-hapus="' + i + '" aria-label="Hapus temuan">✕</button></div>' +
        '<div class="grid2"><label class="field">Kategori <select data-tf="' + i + ':kategori">' + optionsHtml("findingCategory", f.kategori, "—") + "</select></label>" +
        '<label class="field">Jumlah <input type="number" min="0" data-tf="' + i + ':jumlah" value="' + escapeHtml(f.jumlah == null ? "" : f.jumlah) + '"></label>' +
        '<label class="field">Status hutan <input maxlength="128" data-tf="' + i + ':status_hutan" value="' + escapeHtml(f.status_hutan || "") + '"></label>' +
        '<label class="field">Aktivitas baru? <select data-tf="' + i + ':aktivitas_baru"><option value="">—</option><option value="ada"' + (f.aktivitas_baru === "ada" ? " selected" : "") + '>Ada</option><option value="tidak"' + (f.aktivitas_baru === "tidak" ? " selected" : "") + ">Tidak ada</option></select></label></div>" +
        '<label class="field">Deskripsi <input maxlength="500" data-tf="' + i + ':deskripsi" value="' + escapeHtml(f.deskripsi || "") + '" placeholder="Mis. Hamparan pohon meranti"></label>' +
        '<label class="field">Keterangan <input maxlength="500" data-tf="' + i + ':keterangan" value="' + escapeHtml(f.keterangan || "") + '"></label>' +
        '<label class="field">Foto bukti (maks 3) <span class="muted small" data-tf-jumlah="' + i + '">' + (files.length ? files.length + " foto dipilih" : "") + "</span>" +
        ' <input type="file" accept="image/*" capture="environment" multiple data-tf-foto="' + i + '"></label>' +
        (f.foto_smart ? '<p class="small muted">' + f.foto_smart + " foto dari berkas SMART tersimpan di jejak patroli.</p>" : "") + "</div>";
    }).join("");
  }

  function renderSeedlings() {
    $("tb-bibit").innerHTML = seedlings.map(function (b, i) {
      return '<div class="row wrap"><span class="pill">' + escapeHtml(choiceLabel("seedling", b.jenis)) + "</span>" +
        '<input maxlength="128" placeholder="Jenis bibit" data-bb="' + i + ':nama" value="' + escapeHtml(b.nama || "") + '">' +
        '<input type="number" min="0" placeholder="Jumlah" data-bb="' + i + ':jumlah" value="' + escapeHtml(b.jumlah || "") + '" style="max-width:110px">' +
        '<button type="button" class="close" data-bb-hapus="' + i + '" aria-label="Hapus bibit">✕</button></div>';
    }).join("");
  }

  $("tb-temuan-tambah").addEventListener("click", function () {
    if (patrolFindings.length >= 50) { toast("Paling banyak 50 temuan.", "error"); return; }
    patrolFindings.push({ kategori: "", deskripsi: "", jumlah: "", status_hutan: "", aktivitas_baru: "", keterangan: "" });
    findingFiles.push([]);
    renderPatrolFindings();
  });
  $("tb-temuan").addEventListener("input", function (event) {
    var key = event.target.getAttribute("data-tf");
    if (!key) { return; }
    var parts = key.split(":");
    patrolFindings[parseInt(parts[0], 10)][parts[1]] = event.target.value;
  });
  $("tb-temuan").addEventListener("change", function (event) {
    var key = event.target.getAttribute("data-tf");
    if (key) { var parts = key.split(":"); patrolFindings[parseInt(parts[0], 10)][parts[1]] = event.target.value; return; }
    var index = event.target.getAttribute("data-tf-foto");
    if (index !== null) {
      findingFiles[parseInt(index, 10)] = Array.prototype.slice.call(event.target.files, 0, 3);
      var count = document.querySelector('[data-tf-jumlah="' + index + '"]');
      if (count) { count.textContent = findingFiles[parseInt(index, 10)].length + " foto dipilih"; }
      if (event.target.files.length > 3) { toast("Hanya 3 foto pertama yang dipakai.", "error"); }
    }
  });
  $("tb-temuan").addEventListener("click", function (event) {
    var index = event.target.getAttribute("data-tf-hapus");
    if (index === null) { return; }
    patrolFindings.splice(parseInt(index, 10), 1);
    findingFiles.splice(parseInt(index, 10), 1);
    renderPatrolFindings();
  });
  document.querySelectorAll("[data-bibit]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (seedlings.length >= 50) { toast("Paling banyak 50 baris bibit.", "error"); return; }
      seedlings.push({ jenis: button.getAttribute("data-bibit"), nama: "", jumlah: "" });
      renderSeedlings();
    });
  });
  $("tb-bibit").addEventListener("input", function (event) {
    var key = event.target.getAttribute("data-bb");
    if (!key) { return; }
    var parts = key.split(":");
    seedlings[parseInt(parts[0], 10)][parts[1]] = event.target.value;
  });
  $("tb-bibit").addEventListener("click", function (event) {
    var index = event.target.getAttribute("data-bb-hapus");
    if (index !== null) { seedlings.splice(parseInt(index, 10), 1); renderSeedlings(); }
  });

  $("tb-mode").addEventListener("change", function () {
    $("tb-smart").hidden = this.value === "manual";
    if (this.value === "manual") { smartFile = null; smartPoint = null; $("tb-smart-file").value = ""; }
  });

  function toLocalInput(iso) {
    var date = iso ? new Date(iso) : null;
    return date && !isNaN(date.getTime()) ? localInputValue(date) : "";
  }

  function applySmart(data) {
    var form = $("form-kegiatan");
    var set = function (name, value) { var el = form.querySelector('[name="' + name + '"]'); if (el && value) { el.value = value; } };
    set("lokasi", data.location_name);
    set("tb_grid", data.grid);
    set("tb_objektif", data.objective);
    set("tb_ketua", data.team_leader);
    set("tb_regu", data.team);
    set("tb_stasiun", data.station);
    set("tb_transport", data.transport);
    set("tb_mulai", toLocalInput(data.started));
    set("tb_selesai", toLocalInput(data.ended));
    if (data.distance_m) { $("tb-jarak").value = (data.distance_m / 1000).toFixed(2); }
    var narrative = form.querySelector('[name="uraian"]');
    if (!narrative.value.trim()) { narrative.value = data.narrative || ""; }
    smartPoint = data.lat !== null && data.lng !== null ? { lat: data.lat, lng: data.lng, accuracy: "" } : null;
    if ($("tb-mode").value === "smart") { patrolFindings = []; findingFiles = []; }
    (data.findings || []).forEach(function (f) {
      patrolFindings.push({ kategori: f.category, deskripsi: f.description, jumlah: f.quantity === null ? "" : f.quantity,
        status_hutan: f.forest_status, aktivitas_baru: "", keterangan: f.note, lat: f.lat, lng: f.lng, foto_smart: f.photos });
      findingFiles.push([]);
    });
    renderPatrolFindings();
    $("tb-smart-info").textContent = data.counts.observations + " observasi · " + data.counts.track + " titik jalur · " +
      data.counts.photos + " foto terbaca. Periksa & lengkapi, lalu simpan.";
  }

  $("tb-smart-file").addEventListener("change", function () {
    smartFile = this.files && this.files[0] ? this.files[0] : null;
    smartPoint = null;
    if (!smartFile) { return; }
    if (smartFile.size > 15 * 1024 * 1024) { toast("Berkas SMART maksimal 15 MB.", "error"); smartFile = null; this.value = ""; return; }
    if (!navigator.onLine) {
      $("tb-smart-info").textContent = "Tanpa sinyal: pratinjau belum bisa dibuat, berkas tetap dikirim bersama laporan.";
      return;
    }
    var data = new FormData();
    data.append("smart", smartFile, smartFile.name);
    $("tb-smart-info").textContent = "Memproses berkas SMART…";
    request(urls.patrolPreview, { method: "POST", body: data }).then(applySmart).catch(function (error) {
      $("tb-smart-info").textContent = error.message || "Berkas SMART tidak dikenali.";
      smartFile = null;
      $("tb-smart-file").value = "";
    });
  });

  // --- Kegiatan lainnya: tingkat dampak ---

  function impactTier(score) {
    if (score <= 1) { return "rutin"; }
    if (score <= 3) { return "operasional"; }
    if (score <= 5) { return "signifikan"; }
    return "kritis";
  }

  function updateImpact() {
    var form = $("form-kegiatan");
    var values = ["dampak_cakupan", "dampak_risiko", "dampak_hasil"].map(function (name) { return form.querySelector('[name="' + name + '"]').value; });
    var box = $("kg-dampak");
    if ($("kg-jenis").value !== "lainnya" || values.indexOf("") !== -1) { box.hidden = true; return; }
    var tier = impactTier(values.reduce(function (sum, v) { return sum + parseInt(v, 10); }, 0));
    var points = config.impactPoints[tier];
    var high = tier === "signifikan" || tier === "kritis";
    box.hidden = false;
    box.className = "impact-box" + (high ? " high" : "");
    box.textContent = "Tingkat: " + choiceLabel("impactTier", tier) + " – " + (high
      ? "dihitung " + config.impactPoints.operasional + " poin sementara; " + points + " poin setelah dikonfirmasi atasan."
      : points + " poin.");
  }
  document.querySelectorAll('#form-kegiatan [data-jenis="lainnya"] select').forEach(function (sel) { sel.addEventListener("change", updateImpact); });

  function typeFields(type) {
    var form = $("form-kegiatan");
    var fields = {};
    var files = [];
    var part = form.querySelector('.jenis-part[data-jenis="' + type + '"]');
    if (part) {
      part.querySelectorAll("[name]").forEach(function (input) {
        if (input.type === "file") { return; }
        fields[input.name] = input.value;
      });
    }
    if (type === "komsos" && newResidents.length) {
      fields.warga_baru = JSON.stringify(newResidents);
    }
    if (type === "temuan_ilegal" && tiMode === "baru") { delete fields.temuan_id; }
    if (type === "taman_buru") {
      fields.tb_rute = Array.prototype.map.call($("tb-rute").querySelectorAll("input:checked"), function (i) { return i.value; }).join(",");
      ["tb_mulai", "tb_selesai"].forEach(function (name) { fields[name] = fields[name] ? new Date(fields[name]).toISOString() : ""; });
      var km = parseFloat($("tb-jarak").value);
      if (!isNaN(km) && km >= 0) { fields.jarak_m = Math.round(km * 1000); }
      fields.temuan_patroli = JSON.stringify(patrolFindings.map(function (f) {
        return { kategori: f.kategori, deskripsi: f.deskripsi, jumlah: f.jumlah, status_hutan: f.status_hutan,
          aktivitas_baru: f.aktivitas_baru, keterangan: f.keterangan, lat: f.lat, lng: f.lng };
      }));
      fields.bibit = JSON.stringify(seedlings);
      if (smartFile && fields.tb_mode !== "manual") { files.push({ field: "smart", blob: smartFile, name: smartFile.name }); }
    }
    return { fields: fields, files: files };
  }

  function checkTypeFields(type, fields) {
    if (type === "lainnya" && (!fields.dampak_cakupan || !fields.dampak_risiko || !fields.dampak_hasil)) {
      return "Nilai dampak kegiatan (cakupan, risiko, hasil) wajib dipilih.";
    }
    if (type === "temuan_ilegal") {
      if (tiMode === "berulang" && !fields.temuan_id) { return "Pilih temuan yang dikunjungi ulang."; }
      if (!(fields.ti_lokasi || "").trim()) { return "Lokasi temuan wajib diisi."; }
    }
    if (type === "taman_buru") {
      if (patrolFindings.some(function (f) { return !(f.deskripsi || "").trim(); })) { return "Deskripsi tiap temuan wajib diisi."; }
      if (seedlings.some(function (b) { return !(b.nama || "").trim() || !/^\d+$/.test(String(b.jumlah)); })) { return "Isi jenis dan jumlah tiap bibit."; }
    }
    return "";
  }

  function findingPhotoFiles() {
    var jobs = findingFiles.map(function (list, index) {
      return Promise.all(list.map(function (file) {
        return compress(file).then(function (blob) { return { field: "foto_temuan_" + index, blob: blob, name: file.name.replace(/\.[^.]+$/, "") + ".jpg" }; });
      }));
    });
    return Promise.all(jobs).then(function (groups) { return [].concat.apply([], groups); });
  }

  function resetTypeParts() {
    newResidents = [];
    patrolFindings = [];
    findingFiles = [];
    seedlings = [];
    smartFile = null;
    smartPoint = null;
    renderNewResidents();
    renderPatrolFindings();
    renderSeedlings();
    closeNewResident();
    setTiMode(perms.tambahTemuan ? "baru" : "berulang");
    $("tb-smart").hidden = true;
    $("tb-smart-info").textContent = "Jalur, observasi, foto, dan data tim diisi otomatis; periksa lalu simpan.";
    applyActivityType();
  }

  function reportPoint(useTap, preferred) {
    if (useTap) {
      if (!tappedPoint) { return Promise.reject(new ApiError("Ketuk titik di peta terlebih dahulu.", 0)); }
      return Promise.resolve({ lat: tappedPoint.lat, lng: tappedPoint.lng, accuracy: "" });
    }
    if (preferred) { return Promise.resolve(preferred); }
    return currentPosition(10000);
  }

  $("form-kegiatan").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!perms.lapor) { toast("Anda tidak berhak melapor kegiatan.", "error"); return; }
    var formEl = this;
    var data = new FormData(formEl);
    var type = data.get("jenis");
    var fields = {
      jenis: type, judul: (data.get("judul") || "").trim(), uraian: data.get("uraian"),
      waktu: data.get("waktu") ? new Date(data.get("waktu")).toISOString() : new Date().toISOString(),
      durasi: data.get("durasi"), peserta: data.get("peserta"), hasil: data.get("hasil"),
      korwil: data.get("korwil"), tugas: data.get("tugas"),
      pendamping: (data.get("pendamping") || "").trim(), lokasi: (data.get("lokasi") || "").trim(),
      warga: Object.keys(chosenResidents).join(",")
    };
    var stances = {};
    Object.keys(chosenResidents).forEach(function (id) { if (chosenResidents[id].newStance) { stances[id] = chosenResidents[id].newStance; } });
    if (Object.keys(stances).length) { fields.sikap = JSON.stringify(stances); }
    if (!fields.judul && AUTO_TITLE.indexOf(type) === -1) { toast(type === "lainnya" ? "Nama kegiatan wajib diisi." : "Judul wajib diisi.", "error"); return; }
    if (type === "taman_buru" && !fields.lokasi) { toast("Nama lokasi patroli wajib diisi.", "error"); return; }
    var extra = typeFields(type);
    Object.keys(extra.fields).forEach(function (key) { fields[key] = extra.fields[key]; });
    var problem = checkTypeFields(type, fields);
    if (problem) { toast(problem, "error"); return; }
    var label = fields.judul || choiceLabel("activityType", type) + (fields.lokasi ? " – " + fields.lokasi : "");
    var voiceInput = formEl.querySelector('[name="suara"]');
    var voice = voiceInput && voiceInput.files && voiceInput.files[0];
    if (voice && voice.size > 10 * 1024 * 1024) { toast("Rekaman suara maksimal 10 MB.", "error"); return; }
    if (voice && !/\.(m4a|mp3|wav|ogg|webm)$/i.test(voice.name)) { toast("Rekaman suara harus M4A, MP3, WAV, OGG, atau WEBM.", "error"); return; }
    var preferred = type === "taman_buru" && fields.tb_mode !== "manual" ? smartPoint : null;
    reportPoint($("kg-titik").checked, preferred).then(function (point) {
      if (point) { fields.lat = point.lat; fields.lng = point.lng; fields.accuracy = point.accuracy; }
      if ((type === "temuan_ilegal" && tiMode === "baru") || (type === "taman_buru" && !smartFile)) {
        if (!point) { throw new ApiError("Lokasi GPS wajib untuk jenis ini. Ketuk peta bila GPS tidak tersedia.", 0); }
      }
      return Promise.all([photoFiles(formEl.querySelector('[name="foto"]'), "foto", 5), findingPhotoFiles()]);
    }).then(function (groups) {
      var files = groups[0].concat(groups[1], extra.files);
      if (voice) { files.push({ field: "suara", blob: voice, name: voice.name }); }
      return enqueue(urls.activities, "Kegiatan: " + label, fields, files);
    }).then(function () {
      formEl.reset();
      chosenResidents = {};
      renderChosen();
      $("kg-jenis").value = type;
      resetTypeParts();
      $("kg-waktu").value = localInputValue();
      toast(navigator.onLine ? "Laporan disimpan, mengirim…" : "Tanpa sinyal: laporan disimpan di perangkat dan dikirim otomatis nanti.", "ok");
      sync(false);
    }).catch(function (error) { toast(error.message || "Gagal menyimpan laporan.", "error"); });
  });

  $("form-tanah").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!perms.tambahTanah) { toast("Anda tidak berhak mencatat uji tanah.", "error"); return; }
    var formEl = this;
    var data = new FormData(formEl);
    var fields = { waktu: new Date().toISOString() };
    ["kedalaman", "tekstur", "warna", "ph", "kadar_air", "c_organik", "daya_dukung", "cbr", "kelayakan", "lab", "catatan"].forEach(function (key) {
      fields[key] = data.get(key);
    });
    reportPoint($("tn-titik").checked).then(function (point) {
      if (!point) { throw new ApiError("Lokasi GPS wajib untuk uji tanah. Ketuk peta bila GPS tidak tersedia.", 0); }
      fields.lat = point.lat;
      fields.lng = point.lng;
      fields.accuracy = point.accuracy;
      return Promise.all([photoFiles(formEl.querySelector('[name="foto"]'), "foto", 1),
                          Promise.resolve(Array.prototype.slice.call(formEl.querySelector('[name="laporan"]').files, 0, 1).map(function (f) { return { field: "laporan", blob: f, name: f.name }; }))]);
    }).then(function (groups) {
      return enqueue(urls.soil, "Uji tanah " + fmtDate(fields.waktu, true), fields, groups[0].concat(groups[1]));
    }).then(function () {
      formEl.reset();
      $("tn-kelayakan").value = "belum";
      toast(navigator.onLine ? "Uji tanah disimpan, mengirim…" : "Tanpa sinyal: data disimpan di perangkat.", "ok");
      sync(false);
    }).catch(function (error) { toast(error.message || "Gagal menyimpan uji tanah.", "error"); });
  });

  document.querySelectorAll(".segmented button[data-sub]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (button.hidden) { return; }
      var sub = button.getAttribute("data-sub");
      document.querySelectorAll(".segmented button[data-sub]").forEach(function (b) { b.classList.toggle("active", b === button); });
      document.querySelectorAll("[data-sub-view]").forEach(function (view) { view.hidden = view.getAttribute("data-sub-view") !== sub; });
      if (sub === "riwayat") { loadMyReports(); }
    });
  });

  function loadMyReports() {
    refreshQueue();
    if (!perms.kegiatan || !navigator.onLine) { return; }
    var scope = $("riwayat-lingkup").value;
    request(urls.activities + (scope ? "?lingkup=" + scope : "")).then(function (data) {
      $("daftar-kegiatan").innerHTML = data.results.map(function (a) {
        var extras = [];
        if (a.location_name) { extras.push("📍 " + a.location_name); }
        extras.push(a.points + " poin");
        if (a.impact_label) { extras.push("Dampak " + a.impact_label + (a.impact_pending ? " (menunggu konfirmasi)" : "")); }
        if (a.ai_stance) { extras.push("AI: " + choiceLabel("stance", a.ai_stance)); }
        if (a.temuan) { extras.push("⚠️ " + a.temuan.number + " " + a.temuan.kind + (a.temuan.is_new ? " (baru)" : " (kunjungan ke-" + a.temuan.visits + ")")); }
        if (a.patroli) {
          extras.push("🌲 " + a.patroli.findings + " temuan · bibit dirawat " + a.patroli.tended + " · diproduksi " + a.patroli.produced +
            (a.patroli.smart ? " · jejak SMART" : ""));
        }
        return "<li><div class='title'>" + escapeHtml(a.title) + (a.verified ? " ✅" : "") + "</div><div class='sub'>" + escapeHtml(a.number + " · " + a.type_label + " · " + fmtDate(a.started_at, true) +
          (a.korwil ? " · Korwil " + a.korwil : "") + " · " + a.reporter) + "</div>" +
          "<div class='sub'>" + escapeHtml(extras.join(" · ")) + "</div>" +
          (a.can_confirm ? "<div class='row'><button type='button' class='btn-small' data-konfirmasi='" + a.id + "'>Konfirmasi dampak " + escapeHtml(a.impact_label) + "</button></div>" : "") +
          (a.photos.length ? "<div class='row wrap'>" + a.photos.map(function (url) { return "<a href='" + escapeHtml(url) + "' target='_blank' rel='noopener'>📷</a>"; }).join(" ") + "</div>" : "") +
          (a.voice ? "<div class='row wrap'><audio controls preload='none' src='" + escapeHtml(a.voice) + "'></audio><a class='small' href='" + escapeHtml(a.voice) + "'>🎙️ Unduh rekaman</a></div>" : "") +
          (perms.verifikasi && !a.verified ? "<div class='row'><button type='button' class='btn-small' data-verifikasi='" + a.id + "'>Verifikasi</button></div>" : "") +
          (a.lat !== null ? "<div class='row'><button type='button' class='btn-small' data-lihat='" + a.lat + "," + a.lng + "'>Lihat di peta</button></div>" : "") + "</li>";
      }).join("") || "<li class='muted'>Belum ada laporan.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }
  $("riwayat-lingkup").addEventListener("change", loadMyReports);
  $("daftar-kegiatan").addEventListener("click", function (event) {
    var confirmId = event.target.getAttribute("data-konfirmasi");
    if (confirmId) {
      request(urls.impactConfirm.replace("/0/", "/" + confirmId + "/"), { method: "POST", body: form({}) })
        .then(function () { toast("Dampak dikonfirmasi; poin penuh berlaku.", "ok"); loadMyReports(); })
        .catch(function (error) { toast(error.message, "error"); });
      return;
    }
    var id = event.target.getAttribute("data-verifikasi");
    if (id) {
      request(urls.verify.replace("/0/", "/" + id + "/"), { method: "POST", body: form({ verified: "1" }) })
        .then(function () { toast("Kegiatan diverifikasi.", "ok"); loadMyReports(); })
        .catch(function (error) { toast(error.message, "error"); });
    }
    flyFromButton(event);
  });

  function flyFromButton(event) {
    var target = event.target.getAttribute("data-lihat");
    if (!target) { return; }
    var parts = target.split(",").map(Number);
    showTab("peta");
    map.setView(parts, 18);
    L.popup().setLatLng(parts).setContent("Lokasi laporan").openOn(map);
  }

  function loadTaskOptions() {
    if (!perms.tugas || !navigator.onLine) { return; }
    request(urls.tasks).then(function (data) {
      var current = $("kg-tugas").value;
      fillSelect($("kg-tugas"), data.results.map(function (t) { return { value: t.id, label: t.number + " " + t.title }; }), "—");
      $("kg-tugas").value = current;
    }).catch(function () {});
  }

  // ================================================================ Warga

  function loadResidents() {
    if (!perms.warga) { $("warga-daftar").innerHTML = "<li class='muted'>Anda tidak berhak melihat data warga.</li>"; return; }
    var params = [];
    if ($("warga-cari").value.trim()) { params.push("q=" + encodeURIComponent($("warga-cari").value.trim())); }
    if ($("warga-korwil").value) { params.push("korwil=" + $("warga-korwil").value); }
    if ($("warga-sikap").value) { params.push("sikap=" + $("warga-sikap").value); }
    request(urls.residents + (params.length ? "?" + params.join("&") : "")).then(function (data) {
      $("warga-daftar").innerHTML = data.results.map(function (r) {
        var color = config.colors.stance[r.stance] || "#57606a";
        return "<li class='clickable' data-warga='" + r.id + "'><div class='title'>" + escapeHtml(r.name) +
          " <span class='badge' style='background:" + color + "'>" + escapeHtml(choiceLabel("stance", r.stance)) + "</span></div><div class='sub'>" +
          escapeHtml([r.number, r.korwil ? "Korwil " + r.korwil : "", r.village, choiceLabel("land", r.land), choiceLabel("rtrw", r.rtrw)].filter(Boolean).join(" · ")) +
          "</div></li>";
      }).join("") || "<li class='muted'>Tidak ada warga yang cocok.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }

  var residentTimer = null;
  $("warga-cari").addEventListener("input", function () { clearTimeout(residentTimer); residentTimer = setTimeout(loadResidents, 300); });
  $("warga-korwil").addEventListener("change", loadResidents);
  $("warga-sikap").addEventListener("change", loadResidents);
  $("warga-daftar").addEventListener("click", function (event) {
    var li = event.target.closest("[data-warga]");
    if (li) { openResident(parseInt(li.getAttribute("data-warga"), 10)); }
  });

  $("warga-tambah-buka").addEventListener("click", function () {
    if (!perms.tambahWarga) { toast("Anda tidak berhak menambah warga.", "error"); return; }
    $("form-warga").hidden = false;
    startGps();
  });
  $("warga-tambah-batal").addEventListener("click", function () { $("form-warga").hidden = true; });
  $("form-warga").addEventListener("submit", function (event) {
    event.preventDefault();
    var formEl = this;
    var data = new FormData(formEl);
    var usePosition = data.get("pakai_gps");
    data.delete("pakai_gps");
    var ready = usePosition ? currentPosition(10000) : Promise.resolve(null);
    ready.then(function (fix) {
      if (usePosition && !fix && tappedPoint) { fix = { lat: tappedPoint.lat, lng: tappedPoint.lng, accuracy: "" }; }
      if (fix) { data.append("lat", fix.lat); data.append("lng", fix.lng); }
      return request(urls.residents, { method: "POST", body: data });
    }).then(function (resident) {
      toast("Warga " + resident.name + " tersimpan (" + resident.number + ").", "ok");
      formEl.reset();
      formEl.hidden = true;
      loadResidents();
      loadLayer("warga");
      loadSummary();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  function openResident(id) {
    var dialog = $("dlg-warga");
    $("wd-judul").textContent = "Memuat…";
    $("wd-isi").innerHTML = "";
    if (!dialog.open) { dialog.showModal(); }
    request(urls.resident.replace("/0/", "/" + id + "/")).then(renderResident).catch(function (error) {
      $("wd-isi").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>";
    });
  }

  function selectHtml(name, kind, value) {
    return '<select name="' + name + '">' + config.choices[kind].map(function (c) {
      return '<option value="' + escapeHtml(c.value) + '"' + (c.value === value ? " selected" : "") + ">" + escapeHtml(c.label) + "</option>";
    }).join("") + "</select>";
  }

  function dossierHtml(r) {
    var rows = [
      ["Status responden", r.residency ? choiceLabel("residency", r.residency) : ""],
      ["Jenis kelamin", r.gender ? choiceLabel("gender", r.gender) : ""],
      ["Umur", r.age !== null ? r.age + " tahun" : ""],
      ["Pekerjaan", r.occupation],
      ["Asal daerah", r.origin],
      ["Lama menetap", r.years_living !== null ? r.years_living + " tahun" : ""],
      ["Nama pasangan", r.spouse_name],
      ["Pekerjaan pasangan", r.spouse_occupation],
      ["Jumlah anak", r.child_count !== null ? String(r.child_count) : ""],
      ["Data anak", r.children_detail],
      ["Luas lahan", r.land_area_m2 !== null ? r.land_area_m2 + " m²" : ""],
      ["Penggarapan", r.cultivation ? choiceLabel("cultivation", r.cultivation) : ""],
      ["Zona RTRW", choiceLabel("zone", r.zone)],
      ["Kondisi lahan", r.land_condition]
    ].filter(function (row) { return row[1]; });
    if (!rows.length) { return ""; }
    return "<h4>Dossier warga</h4><dl class='small dossier'>" + rows.map(function (row) {
      return "<dt>" + escapeHtml(row[0]) + "</dt><dd>" + escapeHtml(row[1]) + "</dd>";
    }).join("") + "</dl>";
  }

  function numberValue(value) { return value === null || value === undefined ? "" : escapeHtml(String(value)); }

  function renderResident(r) {
    $("wd-judul").textContent = r.name + " · " + r.number;
    var edit = perms.ubahWarga;
    var html = "<p class='small muted'>" + escapeHtml([r.korwil ? "Korwil " + r.korwil : "", r.village, r.address, r.phone, r.members ? r.members + " jiwa" : "",
      r.last_visited ? "dikunjungi " + fmtDate(r.last_visited) : "belum pernah dikunjungi"].filter(Boolean).join(" · ")) + "</p>";
    if (edit) {
      html += "<div class='row wrap'>" + config.choices.stance.map(function (c) {
        return "<button type='button' class='btn-small' data-set-sikap='" + escapeHtml(c.value) + "' style='border-color:" + (config.colors.stance[c.value] || "#555") + (c.value === r.stance ? ";background:" + config.colors.stance[c.value] : "") + "'>" + escapeHtml(c.label) + "</button>";
      }).join("") + "</div>";
      html += "<div class='grid2' id='wd-form'><label class='field'>Status lahan " + selectHtml("lahan", "land", r.land) + "</label>" +
        "<label class='field'>RTRW " + selectHtml("rtrw", "rtrw", r.rtrw) + "</label>" +
        "<label class='field'>Zona RTRW " + selectHtml("zona", "zone", r.zone) + "</label>" +
        "<label class='field'>Pilihan " + selectHtml("pilihan", "relocation", r.relocation) + "</label>" +
        "<label class='field'>Penggarapan lahan " + selectHtml("penggarapan", "cultivation", r.cultivation) + "</label>" +
        "<label class='field'>Status responden " + selectHtml("status_warga", "residency", r.residency) + "</label>" +
        "<label class='field'>Jenis kelamin " + selectHtml("gender", "gender", r.gender) + "</label>" +
        "<label class='field'>Umur <input type='number' name='umur' min='0' max='130' inputmode='numeric' value='" + numberValue(r.age) + "'></label>" +
        "<label class='field'>Pekerjaan <input name='pekerjaan' maxlength='128' value='" + escapeHtml(r.occupation) + "'></label>" +
        "<label class='field'>Asal daerah <input name='asal' maxlength='128' value='" + escapeHtml(r.origin) + "'></label>" +
        "<label class='field'>Lama menetap (tahun) <input type='number' name='menetap' min='0' max='130' inputmode='numeric' value='" + numberValue(r.years_living) + "'></label>" +
        "<label class='field'>Nama pasangan <input name='pasangan' maxlength='255' value='" + escapeHtml(r.spouse_name) + "'></label>" +
        "<label class='field'>Pekerjaan pasangan <input name='pekerjaan_pasangan' maxlength='128' value='" + escapeHtml(r.spouse_occupation) + "'></label>" +
        "<label class='field'>Jumlah anak <input type='number' name='anak' min='0' max='50' inputmode='numeric' value='" + numberValue(r.child_count) + "'></label>" +
        "<label class='field'>Data anak <textarea name='data_anak' rows='2' maxlength='2000' placeholder='Nama, umur, sekolah/pekerjaan'>" + escapeHtml(r.children_detail) + "</textarea></label>" +
        "<label class='field'>Luas lahan (m²) <input type='number' step='0.01' min='0' name='luas_lahan' inputmode='decimal' value='" + numberValue(r.land_area_m2) + "'></label>" +
        "<label class='field'>Kondisi lahan <textarea name='kondisi_lahan' rows='2' maxlength='2000'>" + escapeHtml(r.land_condition) + "</textarea></label>" +
        "<label class='field'>Catatan baru <input name='catatan' maxlength='2000'></label></div>" +
        "<div class='row wrap'><button type='button' class='btn primary' id='wd-simpan'>Simpan</button>" +
        "<button type='button' class='btn' id='wd-gps'>📍 Set lokasi dari GPS</button></div>";
    } else {
      html += "<p>Sikap: <b>" + escapeHtml(choiceLabel("stance", r.stance)) + "</b> · " + escapeHtml(choiceLabel("land", r.land)) + " · " + escapeHtml(choiceLabel("rtrw", r.rtrw)) + "</p>";
      html += dossierHtml(r);
    }
    html += "<div class='row wrap'>" + (r.lat !== null ? "<button type='button' class='btn-small' id='wd-peta'>🗺️ Tampilkan di peta</button>" : "") +
      (perms.lapor ? "<button type='button' class='btn-small' id='wd-lapor'>📝 Lapor kunjungan</button>" : "") + "</div>";
    if (r.note) { html += "<h4>Catatan</h4><pre class='small' style='white-space:pre-wrap'>" + escapeHtml(r.note) + "</pre>"; }
    if (r.history.length) {
      html += "<h4>Riwayat sikap</h4><ul class='small'>" + r.history.map(function (h) {
        return "<li>" + fmtDate(h.at, true) + ": " + escapeHtml(h.from) + " → " + escapeHtml(h.to) + " (" + escapeHtml(h.by) + ")</li>";
      }).join("") + "</ul>";
    }
    if (r.activities.length) {
      html += "<h4>Kegiatan</h4><ul class='small'>" + r.activities.map(function (a) {
        return "<li>" + fmtDate(a.at) + " · " + escapeHtml(a.number + " " + a.title) + "</li>";
      }).join("") + "</ul>";
    }
    $("wd-isi").innerHTML = html;
    var save = function (extra) {
      var data = new FormData();
      var formEl = $("wd-form");
      if (formEl) { formEl.querySelectorAll("select, input, textarea").forEach(function (input) { data.append(input.name, input.value); }); }
      Object.keys(extra || {}).forEach(function (k) { data.set(k, extra[k]); });
      return request(urls.resident.replace("/0/", "/" + r.id + "/"), { method: "POST", body: data }).then(function (updated) {
        toast("Data warga diperbarui.", "ok");
        renderResident(updated);
        loadLayer("warga");
        loadSummary();
      }).catch(function (error) { toast(error.message, "error"); });
    };
    $("wd-isi").querySelectorAll("[data-set-sikap]").forEach(function (button) {
      button.addEventListener("click", function () { save({ sikap: button.getAttribute("data-set-sikap") }); });
    });
    if ($("wd-simpan")) { $("wd-simpan").addEventListener("click", function () { save(); }); }
    if ($("wd-gps")) {
      $("wd-gps").addEventListener("click", function () {
        currentPosition(15000).then(function (fix) {
          if (!fix) { toast("GPS tidak tersedia.", "error"); return; }
          save({ lat: fix.lat, lng: fix.lng });
        });
      });
    }
    if ($("wd-peta")) {
      $("wd-peta").addEventListener("click", function () {
        $("dlg-warga").close();
        showTab("peta");
        map.setView([r.lat, r.lng], 18);
        L.popup().setLatLng([r.lat, r.lng]).setContent(escapeHtml(r.name)).openOn(map);
      });
    }
    if ($("wd-lapor")) {
      $("wd-lapor").addEventListener("click", function () {
        $("dlg-warga").close();
        chosenResidents = {};
        chosenResidents[r.id] = { name: r.name, newStance: "" };
        renderChosen();
        $("kg-jenis").value = "komsos";
        applyActivityType();
        document.querySelector('#form-kegiatan [name="judul"]').value = "";
        showTab("korwil");
      });
    }
  }

  // ================================================================ Tugas

  var OPEN_TASK = ["baru", "dikerjakan", "menunggu", "dilaporkan"];
  var TASK_ACTIONS = {
    mulai: { label: "▶ Mulai kerjakan", cls: "primary" },
    lapor: { label: "📤 Laporkan selesai", cls: "primary" },
    kendala: { label: "⚠ Ada kendala", cls: "", note: true },
    lanjut: { label: "▶ Lanjutkan", cls: "primary" },
    verifikasi: { label: "✔ Verifikasi selesai", cls: "primary" },
    kembalikan: { label: "↩ Kembalikan untuk revisi", cls: "", note: true },
    batal: { label: "✕ Batalkan tugas", cls: "danger" }
  };
  var taskFilter = "saya";
  var openTaskId = null;

  function stageBadge(t) {
    return "<span class='badge' style='background:" + escapeHtml(t.stage_color) + "'>" + escapeHtml(t.stage_label) + "</span>";
  }

  function taskMeta(t) {
    return [t.number, t.priority_label, t.activity_label, t.due_date ? "tenggat " + fmtDate(t.due_date) : "",
      t.korwil ? "Korwil " + t.korwil : "", t.mine ? (t.giver && !t.given ? "dari " + t.giver : "") : (t.assignee ? "untuk " + t.assignee : ""),
      t.points ? t.points + " poin" : ""].filter(Boolean).join(" · ");
  }

  function loadTasks() {
    if (!perms.tugas) { $("tugas-daftar").innerHTML = "<li class='muted'>Anda tidak berhak melihat tugas.</li>"; return; }
    request(urls.tasks + "?filter=" + taskFilter).then(function (data) {
      $("tugas-baru-buka").hidden = !data.can_create;
      $("tugas-daftar").innerHTML = data.results.map(function (t) {
        return "<li class='clickable' data-tugas='" + t.id + "'><div class='title'>" + escapeHtml(t.title) + " " + stageBadge(t) +
          (t.overdue ? " <span class='badge' style='background:#cf222e'>terlambat</span>" : "") + "</div>" +
          "<div class='sub'>" + escapeHtml(taskMeta(t)) + "</div>" +
          "<div class='progress'><i style='width:" + t.progress + "%'></i></div>" +
          (perms.lapor && t.mine && OPEN_TASK.indexOf(t.status) !== -1 && t.status !== "dilaporkan"
            ? "<div class='row'><button type='button' class='btn-small' data-lapor-tugas='" + t.id + "' data-judul='" + escapeHtml(t.title) + "'>📝 Lapor kegiatan</button></div>" : "") +
          "</li>";
      }).join("") || "<li class='muted'>Tidak ada tugas di daftar ini.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }

  $("tugas-filter").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-filter]");
    if (!button) { return; }
    taskFilter = button.getAttribute("data-filter");
    $("tugas-filter").querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b === button); });
    loadTasks();
  });

  $("tugas-daftar").addEventListener("click", function (event) {
    var lapor = event.target.getAttribute("data-lapor-tugas");
    if (lapor) {
      loadTaskOptions();
      showTab("korwil");
      setTimeout(function () { $("kg-tugas").value = lapor; }, 400);
      document.querySelector('#form-kegiatan [name="judul"]').value = event.target.getAttribute("data-judul");
      return;
    }
    var li = event.target.closest("[data-tugas]");
    if (li) { openTask(parseInt(li.getAttribute("data-tugas"), 10)); }
  });

  function openTask(id) {
    openTaskId = id;
    $("td-judul").textContent = "Memuat…";
    $("td-isi").innerHTML = "";
    if (!$("dlg-tugas").open) { $("dlg-tugas").showModal(); }
    request(urls.task.replace("/0/", "/" + id + "/")).then(renderTask).catch(function (error) {
      $("td-isi").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>";
    });
  }

  function renderTask(t) {
    $("td-judul").innerHTML = escapeHtml(t.number + " " + t.title) + " " + stageBadge(t);
    var rows = [
      ["Penerima utama", t.assignee], ["Pemberi tugas", t.giver], ["Kontributor", t.contributors.join(", ")],
      ["Jenis kegiatan", t.activity_label], ["Prioritas", t.priority_label], ["Tenggat", t.due_date ? fmtDate(t.due_date) + (t.overdue ? " (terlambat)" : "") : ""],
      ["Korwil", t.korwil], ["Nilai poin", t.points ? t.points + " poin per orang" : ""], ["Status", t.status_label]
    ].filter(function (r) { return r[1]; });
    var html = (t.description ? "<p class='pre'>" + escapeHtml(t.description) + "</p>" : "") +
      "<table class='table kv'><tbody>" + rows.map(function (r) { return "<tr><th>" + escapeHtml(r[0]) + "</th><td>" + escapeHtml(r[1]) + "</td></tr>"; }).join("") + "</tbody></table>";
    var canProgress = t.mine && t.status === "dikerjakan";
    html += "<div class='stack'><div class='row'><span class='small'>Progres</span>" +
      (canProgress ? "<input type='range' min='0' max='100' step='10' value='" + t.progress + "' id='td-progres' aria-label='Progres'><span class='small' id='td-progres-n'>" + t.progress + "%</span>" +
        "<button type='button' class='btn-small' id='td-progres-simpan'>Simpan</button>"
        : "<div class='progress grow'><i style='width:" + t.progress + "%'></i></div><span class='small'>" + t.progress + "%</span>") + "</div></div>";
    if (t.actions.length) {
      var reporting = t.actions.indexOf("lapor") !== -1;
      html += "<div class='stack card-box'><label class='field'>Catatan" + (reporting ? " / ringkasan hasil" : "") +
        " <textarea id='td-catatan' rows='3' maxlength='2000' placeholder='Wajib untuk kendala dan pengembalian'></textarea></label>" +
        (reporting ? "<label class='field'>Foto bukti (opsional) <input type='file' id='td-foto' accept='image/*' capture='environment'></label>" +
          "<label class='check'><input type='checkbox' id='td-gps' checked> Sertakan lokasi GPS saat ini</label>" : "") +
        "<div class='row wrap'>" + t.actions.map(function (a) {
          var spec = TASK_ACTIONS[a] || { label: a, cls: "" };
          return "<button type='button' class='btn " + spec.cls + "' data-aksi='" + a + "'>" + escapeHtml(spec.label) + "</button>";
        }).join("") + "</div></div>";
    }
    if (t.points_awarded.length) {
      html += "<h3>Poin diberikan</h3><ul class='list compact'>" + t.points_awarded.map(function (p) {
        return "<li>" + escapeHtml(p.name) + " · " + escapeHtml(p.role) + " · <b>" + p.points + " poin</b></li>";
      }).join("") + "</ul>";
    }
    html += "<h3>Riwayat</h3><ul class='timeline'>" + (t.events.map(function (e) {
      return "<li><div><b>" + escapeHtml(e.label) + "</b> · " + escapeHtml(e.by) + " · <span class='muted small'>" + fmtDate(e.at, true) + "</span></div>" +
        (e.note ? "<div class='small pre'>" + escapeHtml(e.note) + "</div>" : "") +
        (e.photo ? "<a href='" + escapeHtml(e.photo) + "' target='_blank' rel='noopener'><img class='thumb' src='" + escapeHtml(e.photo) + "' alt='Foto bukti' loading='lazy'></a>" : "") +
        (e.lat !== null ? " <button type='button' class='btn-small' data-lihat='" + e.lat + "," + e.lng + "'>📍 Lokasi</button>" : "") + "</li>";
    }).join("") || "<li class='muted'>Belum ada riwayat.</li>") + "</ul>";
    $("td-isi").innerHTML = html;
  }

  $("td-isi").addEventListener("input", function (event) {
    if (event.target.id === "td-progres") { $("td-progres-n").textContent = event.target.value + "%"; }
  });

  $("td-isi").addEventListener("click", function (event) {
    if (event.target.getAttribute("data-lihat")) { $("dlg-tugas").close(); flyFromButton(event); return; }
    if (event.target.id === "td-progres-simpan") {
      request(urls.task.replace("/0/", "/" + openTaskId + "/"), { method: "POST", body: form({ progress: $("td-progres").value }) })
        .then(function (t) { toast("Progres disimpan.", "ok"); renderTask(t); loadTasks(); })
        .catch(function (error) { toast(error.message, "error"); });
      return;
    }
    var action = event.target.getAttribute("data-aksi");
    if (!action) { return; }
    event.preventDefault();
    var note = ($("td-catatan") || {}).value || "";
    if (TASK_ACTIONS[action] && TASK_ACTIONS[action].note && !note.trim()) { toast("Isi catatan terlebih dahulu.", "error"); $("td-catatan").focus(); return; }
    if (action === "batal" && !window.confirm("Batalkan tugas ini?")) { return; }
    var button = event.target;
    button.disabled = true;
    var useGps = action === "lapor" && $("td-gps") && $("td-gps").checked;
    var photoInput = action === "lapor" ? $("td-foto") : null;
    Promise.all([useGps ? currentPosition(10000) : Promise.resolve(null), photoInput ? photoFiles(photoInput, "foto", 1) : Promise.resolve([])])
      .then(function (results) {
        var fix = results[0];
        var data = form({ aksi: action, catatan: note.trim(), lat: fix ? fix.lat : "", lng: fix ? fix.lng : "" });
        results[1].forEach(function (f) { data.append(f.field, f.blob, f.name); });
        return request(urls.task.replace("/0/", "/" + openTaskId + "/"), { method: "POST", body: data });
      }).then(function (t) {
        toast("Tugas: " + t.stage_label + ".", "ok");
        renderTask(t);
        loadTasks();
        loadBadges();
      }).catch(function (error) {
        button.disabled = false;
        toast(error.message, "error");
      });
  });

  var assigneesLoaded = false;
  $("tugas-baru-buka").addEventListener("click", function () {
    var dialog = $("dlg-tugas-baru");
    $("form-tugas-baru").reset();
    if (!assigneesLoaded) {
      fillSelect($("tb-jenis"), config.choices.activityType, "— tanpa jenis —");
      fillSelect($("tb-prioritas"), config.choices.priority);
      $("tb-prioritas").value = "normal";
      fillSelect($("tb-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " · " + k.name }; }), "Ikuti Korwil penerima");
    }
    request(urls.taskAssignees).then(function (data) {
      assigneesLoaded = true;
      var people = data.results.map(function (p) { return { value: p.id, label: p.name + (p.position ? " · " + p.position : "") }; });
      fillSelect($("tb-penerima"), people, "— pilih —");
      $("tb-kontributor").innerHTML = people.map(function (p) {
        return "<label class='check'><input type='checkbox' value='" + escapeHtml(p.value) + "'> " + escapeHtml(p.label) + "</label>";
      }).join("") || "<span class='muted small'>Tidak ada bawahan.</span>";
      dialog.showModal();
    }).catch(function (error) { toast(error.message, "error"); });
  });
  $("dlg-tugas-baru").addEventListener("click", function (event) {
    if (event.target.hasAttribute("data-tutup")) { $("dlg-tugas-baru").close(); }
  });
  $("form-tugas-baru").addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(this);
    var contributors = Array.prototype.map.call($("tb-kontributor").querySelectorAll("input:checked"), function (i) { return i.value; });
    data.append("kontributor", contributors.join(","));
    request(urls.tasks, { method: "POST", body: data }).then(function (t) {
      toast("Tugas " + t.number + " dikirim ke " + t.assignee + ".", "ok");
      $("dlg-tugas-baru").close();
      loadTasks();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  // ================================================================ Laporan harian berjenjang

  var reportHome = null;
  var openReportId = null;
  var reportAi = false;

  function reportItem(r, checkbox) {
    return "<li" + (checkbox ? "" : " class='clickable' data-laporan='" + r.id + "'") + ">" +
      (checkbox ? "<label class='check'><input type='checkbox' value='" + r.id + "' " + (checkbox === "checked" ? "checked" : "") + "> " : "") +
      "<span><span class='title'>" + escapeHtml(r.number + " · " + r.author) + "</span>" +
      " <span class='badge'>" + escapeHtml(r.status_label) + "</span>" +
      "<div class='sub'>" + escapeHtml([fmtDate(r.date), r.author_position, r.korwil ? "Korwil " + r.korwil : ""].filter(Boolean).join(" · ")) + "</div>" +
      (r.return_note ? "<div class='sub danger-text'>Catatan " + escapeHtml(r.returned_by) + ": " + escapeHtml(r.return_note) + "</div>" : "") +
      (r.excerpt && !r.return_note ? "<div class='sub clamp'>" + escapeHtml(r.excerpt) + "</div>" : "") +
      "</span>" + (checkbox ? "</label> <button type='button' class='btn-small' data-laporan='" + r.id + "'>Buka</button>" : "") + "</li>";
  }

  function showReportView(name) {
    $("lh-seg").querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-lh") === name); });
    document.querySelectorAll("[data-lh-view]").forEach(function (view) { view.hidden = view.getAttribute("data-lh-view") !== name; });
    if (name === "lacak") { loadTrace(); }
    if (name === "rekap") { prepareRecap(); }
  }

  $("lh-seg").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-lh]");
    if (button) { showReportView(button.getAttribute("data-lh")); }
  });

  function loadReports() {
    if (!perms.laporanHarian) { $("lh-atasan").textContent = "Anda tidak berhak memakai laporan harian."; return; }
    request(urls.dailyReports + "?hari=" + $("lh-hari").value).then(function (data) {
      reportHome = data;
      $("lh-atasan").innerHTML = (data.position ? "Posisi Anda: <b>" + escapeHtml(data.position) + "</b>. " : "") +
        (data.supervisor ? "Laporan dikirim ke <b>" + escapeHtml(data.supervisor.name) + "</b>" + (data.supervisor.position ? " (" + escapeHtml(data.supervisor.position) + ")" : "") + "."
          : "Anda di puncak rantai laporan: tinjau dan tandai laporan masuk selesai.");
      $("lh-kegiatan").innerHTML = data.activities.map(function (a) {
        return "<label class='check'><input type='checkbox' value='" + a.id + "' checked> " +
          escapeHtml(fmtDate(a.at, true) + " · " + a.type_label + " · " + a.title + (a.korwil ? " · Korwil " + a.korwil : "") + " · " + a.points + " poin") + "</label>";
      }).join("") || "<span class='muted small'>Tidak ada kegiatan yang belum dilaporkan.</span>";
      $("lh-sumber-wrap").hidden = !data.inbox.length || !data.can_send;
      $("lh-sumber").innerHTML = data.inbox.map(function (r) { return reportItem(r, "checked"); }).join("");
      $("lh-revisi-wrap").hidden = !data.revisions.length;
      $("lh-revisi").innerHTML = data.revisions.map(function (r) { return reportItem(r); }).join("");
      $("form-lh").hidden = !data.can_send;
      var inboxCount = data.inbox.length;
      $("lh-masuk-n").textContent = inboxCount || "";
      $("lh-masuk-info").textContent = data.can_finish
        ? "Anda di puncak rantai: centang laporan lalu tandai selesai ditinjau, atau kembalikan untuk revisi."
        : "Laporan masuk ikut dirangkum saat Anda mengirim laporan ke atasan (tab Buat), atau kembalikan untuk revisi.";
      $("lh-masuk").innerHTML = data.inbox.map(function (r) { return data.can_finish ? reportItem(r, "plain") : reportItem(r); }).join("") ||
        "<li class='muted'>Tidak ada laporan masuk.</li>";
      $("lh-selesai").hidden = !(data.can_finish && inboxCount);
    }).catch(function (error) { $("lh-atasan").textContent = error.message; });
  }

  function checkedIds(container) {
    return Array.prototype.map.call(container.querySelectorAll("input[type=checkbox]:checked"), function (i) { return i.value; }).join(",");
  }

  $("lh-hari").addEventListener("change", loadReports);
  $("lh-isi").addEventListener("input", function () { reportAi = false; $("lh-susun-info").textContent = ""; });
  $("lh-susun").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    $("lh-susun-info").textContent = "Menyusun…";
    request(urls.dailyReportCompose, { method: "POST", body: form({ kegiatan: checkedIds($("lh-kegiatan")), laporan: checkedIds($("lh-sumber")) }) })
      .then(function (data) {
        $("lh-isi").value = data.content;
        reportAi = data.ai;
        $("lh-susun-info").textContent = data.ai ? "Disusun AI dari kegiatan terpilih; periksa sebelum dikirim." : "Disusun dari templat; lengkapi sebelum dikirim.";
      }).catch(function (error) { $("lh-susun-info").textContent = ""; toast(error.message, "error"); })
      .then(function () { button.disabled = false; });
  });
  $("form-lh").addEventListener("submit", function (event) {
    event.preventDefault();
    var formEl = this;
    var data = new FormData(formEl);
    data.append("kegiatan", checkedIds($("lh-kegiatan")));
    data.append("laporan", checkedIds($("lh-sumber")));
    if (reportAi) { data.append("ai", "1"); }
    $("lh-kirim").disabled = true;
    request(urls.dailyReports, { method: "POST", body: data }).then(function (r) {
      toast("Laporan " + r.number + " terkirim ke " + r.recipient + ".", "ok");
      formEl.reset();
      reportAi = false;
      $("lh-susun-info").textContent = "";
      loadReports();
      loadBadges();
    }).catch(function (error) { toast(error.message, "error"); })
      .then(function () { $("lh-kirim").disabled = false; });
  });
  $("lh-selesai").addEventListener("click", function () {
    var ids = checkedIds($("lh-masuk"));
    if (!ids) { toast("Centang laporan yang sudah ditinjau.", "error"); return; }
    request(urls.dailyReportFinish, { method: "POST", body: form({ laporan: ids }) }).then(function (data) {
      toast(data.reviewed + " laporan ditandai selesai ditinjau.", "ok");
      loadReports();
      loadBadges();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  function openReportFrom(event) {
    var target = event.target.closest("[data-laporan]");
    if (!target || event.target.matches("input")) { return; }
    event.preventDefault();
    openReport(parseInt(target.getAttribute("data-laporan"), 10));
  }
  ["lh-revisi", "lh-sumber", "lh-masuk", "lh-lacak"].forEach(function (id) { $(id).addEventListener("click", openReportFrom); });

  function openReport(id) {
    openReportId = id;
    $("ld-judul").textContent = "Memuat…";
    $("ld-isi").innerHTML = "";
    if (!$("dlg-laporan").open) { $("dlg-laporan").showModal(); }
    request(urls.dailyReport.replace("/0/", "/" + id + "/")).then(renderReport).catch(function (error) {
      $("ld-isi").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>";
    });
  }

  function renderReport(r) {
    $("ld-judul").innerHTML = escapeHtml(r.number + " · " + r.author) + " <span class='badge'>" + escapeHtml(r.status_label) + "</span>";
    var html = "<p class='small muted'>" + escapeHtml([fmtDate(r.date), r.author_position, r.korwil ? "Korwil " + r.korwil : "",
      r.recipient ? "kepada " + r.recipient : "", r.ai_generated ? "disusun dengan bantuan AI" : ""].filter(Boolean).join(" · ")) + "</p>" +
      "<p class='small'>📍 " + escapeHtml(r.position) + "</p>";
    if (r.return_note) { html += "<p class='small danger-text'>Catatan pengembalian dari " + escapeHtml(r.returned_by) + ": " + escapeHtml(r.return_note) + "</p>"; }
    if (r.revision_owner) {
      html += "<div class='stack card-box'><label class='field'>Perbaiki isi laporan <textarea id='ld-isi-baru' rows='10' maxlength='20000'>" + escapeHtml(r.content) + "</textarea></label>" +
        "<label class='field'>Tambah lampiran <input type='file' id='ld-lampiran' multiple></label>" +
        "<div class='row wrap'><button type='button' class='btn primary' data-aksi-laporan='perbaiki'>💾 Simpan perbaikan &amp; kirim balik</button>" +
        (r.can_close ? "<button type='button' class='btn danger' data-aksi-laporan='tutup'>Tutup laporan</button>" : "") + "</div>" +
        (reportHome && reportHome.subordinates.length
          ? "<div class='row wrap'><select id='ld-bawahan' aria-label='Bawahan'>" + reportHome.subordinates.map(function (p) {
            return "<option value='" + p.id + "'>" + escapeHtml(p.name + (p.position ? " · " + p.position : "")) + "</option>";
          }).join("") + "</select><input id='ld-catatan-teruskan' maxlength='2000' placeholder='Catatan untuk bawahan'>" +
            "<button type='button' class='btn' data-aksi-laporan='teruskan'>⤵ Teruskan revisi ke bawahan</button></div>" : "") + "</div>";
    } else {
      html += "<div class='report-body'>" + escapeHtml(r.content) + "</div>";
    }
    if (r.in_inbox) {
      html += "<div class='stack card-box'><label class='field'>Catatan pengembalian <textarea id='ld-catatan' rows='2' maxlength='2000' placeholder='Apa yang perlu diperbaiki'></textarea></label>" +
        "<div class='row wrap'><button type='button' class='btn' data-aksi-laporan='kembalikan'>↩ Kembalikan untuk revisi</button>" +
        (reportHome && reportHome.can_finish ? "<button type='button' class='btn primary' data-aksi-laporan='selesai'>✔ Selesai ditinjau</button>" : "") + "</div></div>";
    }
    if (r.attachments.length) {
      html += "<h3>Lampiran</h3><div class='row wrap'>" + r.attachments.map(function (a) {
        return "<a class='btn-small' href='" + escapeHtml(a.url) + "' target='_blank' rel='noopener'>📎 " + escapeHtml(a.name) + "</a>";
      }).join("") + "</div>";
    }
    if (r.sources.length) {
      html += "<h3>Laporan bawahan yang dirangkum</h3><ul class='list compact'>" + r.sources.map(function (s) { return reportItem(s); }).join("") + "</ul>";
    }
    if (r.activities.length) {
      html += "<h3>Kegiatan</h3><ul class='list compact'>" + r.activities.map(function (a) {
        return "<li>" + escapeHtml(a.number + " · " + a.type_label + " · " + a.title + " · " + fmtDate(a.at, true)) + "</li>";
      }).join("") + "</ul>";
    }
    html += "<h3>Riwayat</h3><ul class='timeline'>" + r.events.map(function (e) {
      return "<li><div><b>" + escapeHtml(e.label) + "</b> · " + escapeHtml(e.by) + (e.to ? " → " + escapeHtml(e.to) : "") +
        " · <span class='muted small'>" + fmtDate(e.at, true) + "</span></div>" + (e.note ? "<div class='small pre'>" + escapeHtml(e.note) + "</div>" : "") + "</li>";
    }).join("") + "</ul>";
    $("ld-isi").innerHTML = html;
  }

  $("ld-isi").addEventListener("click", function (event) {
    var nested = event.target.closest("[data-laporan]");
    if (nested) { event.preventDefault(); openReport(parseInt(nested.getAttribute("data-laporan"), 10)); return; }
    var action = event.target.getAttribute("data-aksi-laporan");
    if (!action) { return; }
    event.preventDefault();
    var url = urls.dailyReportAction.replace("/0/", "/" + openReportId + "/");
    var body;
    if (action === "selesai") {
      request(urls.dailyReportFinish, { method: "POST", body: form({ laporan: openReportId }) }).then(function () {
        toast("Laporan ditandai selesai ditinjau.", "ok");
        afterReportChange(openReportId);
      }).catch(function (error) { toast(error.message, "error"); });
      return;
    }
    if (action === "kembalikan") {
      if (!$("ld-catatan").value.trim()) { toast("Isi catatan pengembalian.", "error"); $("ld-catatan").focus(); return; }
      body = form({ catatan: $("ld-catatan").value.trim() });
    } else if (action === "teruskan") {
      if (!$("ld-catatan-teruskan").value.trim()) { toast("Isi catatan untuk bawahan.", "error"); $("ld-catatan-teruskan").focus(); return; }
      body = form({ bawahan: $("ld-bawahan").value, catatan: $("ld-catatan-teruskan").value.trim() });
    } else if (action === "perbaiki") {
      body = form({ isi: $("ld-isi-baru").value });
      Array.prototype.forEach.call($("ld-lampiran").files || [], function (file) { body.append("lampiran", file, file.name); });
    } else if (action === "tutup") {
      if (!window.confirm("Tutup laporan ini? Kegiatan dan laporan bawahan di dalamnya dilepas agar bisa dilaporkan ulang.")) { return; }
      body = form({});
    }
    request(url.replace("__aksi__", action), { method: "POST", body: body }).then(function (r) {
      toast({ kembalikan: "Laporan dikembalikan ke " + r.author + ".", teruskan: "Revisi diteruskan ke bawahan.", perbaiki: "Perbaikan terkirim.", tutup: "Laporan ditutup." }[action], "ok");
      renderReport(r);
      afterReportChange();
    }).catch(function (error) { toast(error.message, "error"); });
  });

  function afterReportChange(reopen) {
    loadReports();
    loadBadges();
    if (currentTab === "persetujuan") { loadApprovals(); }
    if (reopen) { openReport(reopen); }
  }

  function loadTrace() {
    request(urls.dailyReportTrace).then(function (data) {
      $("lh-lacak").innerHTML = data.results.map(function (r) {
        return "<li class='clickable' data-laporan='" + r.id + "'><div class='title'>" + escapeHtml(r.number + " · " + r.author) +
          (r.done ? " ✅" : "") + "</div><div class='sub'>" + escapeHtml(fmtDate(r.date) + (r.korwil ? " · Korwil " + r.korwil : "")) + "</div>" +
          "<div class='steps'>" + r.steps.map(function (s) { return "<span>" + escapeHtml(s) + "</span>"; }).join("") + "</div>" +
          "<div class='sub'>" + escapeHtml(r.position) + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada laporan terkirim 14 hari terakhir.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }

  function prepareRecap() {
    if ($("rekap-korwil").options.length) { return; }
    fillSelect($("rekap-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " · " + k.name }; }), "Semua Korwil");
    fillSelect($("rekap-jenis"), config.choices.activityType, "Semua jenis");
  }
  $("rekap-periode").addEventListener("change", function () { $("rekap-rentang").hidden = this.value !== "rentang"; });
  $("form-rekap").addEventListener("submit", function (event) {
    event.preventDefault();
    var params = new URLSearchParams();
    new FormData(this).forEach(function (value, key) {
      if (value && (key !== "dari" && key !== "sampai" || $("rekap-periode").value === "rentang")) { params.append(key, value); }
    });
    var button = this.querySelector("[type=submit]");
    button.disabled = true;
    download(urls.recap + "?" + params.toString(), "rekap-komando.xlsx", "Rekap Excel diunduh.")
      .then(function () { button.disabled = false; });
  });

  // ================================================================ Persetujuan

  var APPROVAL_COLORS = { izin: "#9a6700", dampak: "#cf222e", tugas: "#0b5fcc", laporan: "#1f7a00", revisi: "#8250df" };

  function loadApprovals() {
    request(urls.approvals).then(function (data) {
      $("setuju-daftar").innerHTML = data.pending.map(function (item) {
        var actions = "";
        if (item.kind === "izin") {
          actions = "<button type='button' class='btn-small' data-izin-ok='" + item.id + "' data-keputusan='setuju'>Setujui</button>" +
            "<button type='button' class='btn-small' data-izin-ok='" + item.id + "' data-keputusan='tolak'>Tolak</button>";
        } else if (item.kind === "dampak") {
          actions = "<button type='button' class='btn-small' data-dampak='" + item.id + "'>Konfirmasi dampak</button>";
        } else if (item.kind === "tugas") {
          actions = "<button type='button' class='btn-small' data-buka-tugas='" + item.id + "'>Periksa &amp; verifikasi</button>";
        } else {
          actions = "<button type='button' class='btn-small' data-laporan='" + item.id + "'>" + (item.kind === "revisi" ? "Perbaiki" : "Tinjau") + "</button>";
        }
        return "<li><div class='title'><span class='badge' style='background:" + (APPROVAL_COLORS[item.kind] || "#57606a") + "'>" + escapeHtml(item.kind_label) + "</span> " + escapeHtml(item.title) + "</div>" +
          "<div class='sub'>" + escapeHtml([item.sub, item.at ? fmtDate(item.at, true) : ""].filter(Boolean).join(" · ")) + "</div>" +
          "<div class='row wrap'>" + actions + "</div></li>";
      }).join("") || "<li class='muted'>Tidak ada yang menunggu keputusan Anda. 🎉</li>";
      $("setuju-riwayat").innerHTML = data.history.map(function (row) {
        return "<li><div class='title'>" + (row.approved ? "✅ " : "↩ ") + escapeHtml(row.decision + " · " + row.title) + "</div>" +
          "<div class='sub'>" + escapeHtml([fmtDate(row.at, true), row.note].filter(Boolean).join(" · ")) + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada keputusan 30 hari terakhir.</li>";
    }).catch(function (error) { $("setuju-daftar").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  $("setuju-daftar").addEventListener("click", function (event) {
    var target = event.target;
    var done = function (text) { toast(text, "ok"); loadApprovals(); loadBadges(); };
    var fail = function (error) { toast(error.message, "error"); };
    if (target.getAttribute("data-izin-ok")) {
      var decision = target.getAttribute("data-keputusan");
      request(urls.leaveDecision.replace("/0/", "/" + target.getAttribute("data-izin-ok") + "/"), { method: "POST", body: form({ keputusan: decision }) })
        .then(function () { done(decision === "setuju" ? "Pengajuan disetujui." : "Pengajuan ditolak."); }).catch(fail);
    } else if (target.getAttribute("data-dampak")) {
      request(urls.impactConfirm.replace("/0/", "/" + target.getAttribute("data-dampak") + "/"), { method: "POST", body: form({}) })
        .then(function () { done("Dampak dikonfirmasi; poin penuh berlaku."); }).catch(fail);
    } else if (target.getAttribute("data-buka-tugas")) {
      openTask(parseInt(target.getAttribute("data-buka-tugas"), 10));
    } else if (target.getAttribute("data-laporan")) {
      if (!reportHome && perms.laporanHarian) { loadReports(); }
      openReport(parseInt(target.getAttribute("data-laporan"), 10));
    }
  });

  $("dlg-tugas").addEventListener("close", function () { if (currentTab === "persetujuan") { loadApprovals(); } });

  function loadBadges() {
    if (!navigator.onLine) { return; }
    request(urls.badges).then(function (data) {
      var approvals = data.persetujuan || 0;
      var reports = data.laporan || 0;
      $("menu-persetujuan-n").textContent = approvals || "";
      $("menu-laporan-n").textContent = reports || "";
      $("tugas-verifikasi-n").textContent = data.tugas || "";
      $("tab-menu-dot").hidden = !(approvals || reports);
    }).catch(function () {});
  }

  // ================================================================ Grafik ringan (SVG)

  var STANCE_KEYS = ["mendukung", "netral", "menolak", "belum"];
  function stanceColor(key) { return config.colors.stance[key] || "#57606a"; }
  function fmtNum(value, digits) {
    if (value === null || value === undefined) { return "–"; }
    return Number(value).toLocaleString("id-ID", { maximumFractionDigits: digits === undefined ? 0 : digits });
  }
  function shortDate(iso) { return iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) : ""; }
  function emptyChart() { return "<p class='muted small'>Belum ada data.</p>"; }

  // Garis persentase (0–100). Nilai kosong (null) memutus garis.
  function lineChart(points, series) {
    if (!points.length) { return emptyChart(); }
    var w = 400, h = 170, left = 30, right = 10, top = 8, bottom = 22;
    var step = points.length > 1 ? (w - left - right) / (points.length - 1) : 0;
    var x = function (i) { return left + i * step; };
    var y = function (v) { return top + (100 - v) / 100 * (h - top - bottom); };
    var svg = "<svg viewBox='0 0 " + w + " " + h + "' class='svg-chart' role='img' aria-label='Grafik tren'>";
    [0, 50, 100].forEach(function (v) {
      svg += "<line x1='" + left + "' x2='" + (w - right) + "' y1='" + y(v) + "' y2='" + y(v) + "' class='grid'/>" +
        "<text x='" + (left - 4) + "' y='" + (y(v) + 3) + "' text-anchor='end'>" + v + "%</text>";
    });
    var every = Math.max(1, Math.ceil(points.length / 6));
    points.forEach(function (p, i) {
      if (i % every === 0 || i === points.length - 1) {
        svg += "<text x='" + x(i) + "' y='" + (h - 6) + "' text-anchor='middle'>" + escapeHtml(shortDate(p.date)) + "</text>";
      }
    });
    series.forEach(function (s) {
      var d = "", pen = "M";
      points.forEach(function (p, i) {
        var v = p[s.key];
        if (v === null || v === undefined) { pen = "M"; return; }
        d += pen + x(i).toFixed(1) + " " + y(v).toFixed(1) + " ";
        pen = "L";
      });
      if (d) { svg += "<path d='" + d + "' fill='none' stroke='" + escapeHtml(s.color) + "' stroke-width='2'/>"; }
      points.forEach(function (p, i) {
        var v = p[s.key];
        if (v === null || v === undefined) { return; }
        svg += "<circle cx='" + x(i).toFixed(1) + "' cy='" + y(v).toFixed(1) + "' r='2.5' fill='" + escapeHtml(s.color) + "'><title>" +
          escapeHtml(s.label + " " + fmtDate(p.date) + ": " + v + "%") + "</title></circle>";
      });
    });
    svg += "</svg>";
    return svg + "<div class='legend-row'>" + series.map(function (s) {
      return "<span><i style='background:" + escapeHtml(s.color) + "'></i>" + escapeHtml(s.label) + "</span>";
    }).join("") + "</div>";
  }

  function barChart(rows, key, labelOf, color, titleOf) {
    if (!rows.some(function (r) { return r[key]; })) { return emptyChart(); }
    var w = 400, h = 130, left = 26, bottom = 18, top = 6;
    var max = Math.max.apply(null, rows.map(function (r) { return r[key] || 0; }).concat([1]));
    var slot = (w - left) / rows.length;
    var bar = Math.max(1, slot * 0.7);
    var svg = "<svg viewBox='0 0 " + w + " " + h + "' class='svg-chart' role='img' aria-label='Grafik batang'>" +
      "<line x1='" + left + "' x2='" + w + "' y1='" + (h - bottom) + "' y2='" + (h - bottom) + "' class='grid'/>" +
      "<text x='" + (left - 4) + "' y='" + (top + 8) + "' text-anchor='end'>" + fmtNum(max, 1) + "</text>";
    var every = Math.max(1, Math.ceil(rows.length / 7));
    rows.forEach(function (r, i) {
      var v = r[key] || 0;
      var bh = v / max * (h - top - bottom);
      var bx = left + i * slot + (slot - bar) / 2;
      svg += "<rect x='" + bx.toFixed(1) + "' y='" + (h - bottom - bh).toFixed(1) + "' width='" + bar.toFixed(1) + "' height='" + Math.max(bh, v ? 1 : 0).toFixed(1) +
        "' rx='1.5' fill='" + escapeHtml(color) + "'><title>" + escapeHtml(titleOf(r)) + "</title></rect>";
      if (i % every === 0) {
        svg += "<text x='" + (bx + bar / 2).toFixed(1) + "' y='" + (h - 5) + "' text-anchor='middle'>" + escapeHtml(labelOf(r)) + "</text>";
      }
    });
    return svg + "</svg>";
  }

  function radarChart(items) {
    var w = 300, h = 230, cx = w / 2, cy = h / 2, r = 70, n = items.length;
    var point = function (i, v) {
      var angle = -Math.PI / 2 + i * 2 * Math.PI / n;
      return [cx + Math.cos(angle) * r * v / 100, cy + Math.sin(angle) * r * v / 100];
    };
    var coords = function (pair) { return pair[0].toFixed(1) + "," + pair[1].toFixed(1); };
    var svg = "<svg viewBox='0 0 " + w + " " + h + "' class='svg-chart radar' role='img' aria-label='Radar kinerja'>";
    [25, 50, 75, 100].forEach(function (v) {
      svg += "<polygon class='grid' fill='none' points='" + items.map(function (_x, i) { return coords(point(i, v)); }).join(" ") + "'/>";
    });
    items.forEach(function (item, i) {
      var end = point(i, 100), at = point(i, 116);
      var dx = at[0] - cx;
      var anchor = Math.abs(dx) < 8 ? "middle" : dx > 0 ? "start" : "end";
      var y = at[1] + (at[1] < cy - 8 ? -6 : at[1] > cy + 8 ? 8 : 0);
      svg += "<line class='grid' x1='" + cx + "' y1='" + cy + "' x2='" + end[0].toFixed(1) + "' y2='" + end[1].toFixed(1) + "'/>" +
        "<text x='" + at[0].toFixed(1) + "' y='" + y.toFixed(1) + "' text-anchor='" + anchor + "'>" + escapeHtml(item.label) +
        "<tspan x='" + at[0].toFixed(1) + "' dy='11' class='val'>" + item.value + "%</tspan></text>";
    });
    svg += "<polygon points='" + items.map(function (item, i) { return coords(point(i, Math.min(Math.max(item.value || 0, 0), 100))); }).join(" ") +
      "' fill='rgba(29,130,245,.25)' stroke='#1d82f5' stroke-width='2'/>";
    return svg + "</svg>";
  }

  function heatGrid(days) {
    if (!days.length) { return emptyChart(); }
    var first = new Date(days[0].date + "T00:00:00");
    var html = "";
    for (var i = 0; i < (first.getDay() + 6) % 7; i += 1) { html += "<i class='kosong'></i>"; }
    days.forEach(function (d) {
      var level = d.activities >= 6 ? 4 : d.activities >= 3 ? 3 : d.activities >= 1 ? 2 : (DAY_CLASS[d.status] ? 1 : 0);
      html += "<i class='h" + level + "' title='" + escapeHtml(fmtDate(d.date) + " · " + d.activities + " kegiatan" + (d.status ? " · " + d.status : "")) + "'></i>";
    });
    return "<div class='heat'>" + html + "</div><div class='legend-row small muted'>Sedikit <i class='heat-key h1'></i><i class='heat-key h2'></i><i class='heat-key h3'></i><i class='heat-key h4'></i> Banyak · hari hadir tanpa kegiatan berwarna paling muda</div>";
  }

  function stanceBar(row) {
    var total = STANCE_KEYS.reduce(function (sum, key) { return sum + (row[key] || 0); }, 0);
    if (!total) { return "<div class='stack-bar empty'></div>"; }
    return "<div class='stack-bar'>" + STANCE_KEYS.map(function (key) {
      var n = row[key] || 0;
      return n ? "<span style='width:" + (n * 100 / total).toFixed(2) + "%;background:" + escapeHtml(stanceColor(key)) + "' title='" + escapeHtml(choiceLabel("stance", key) + ": " + n) + "'></span>" : "";
    }).join("") + "</div>";
  }

  function insightHtml(data) {
    return "<div>" + escapeHtml(data.text).replace(/\n/g, "<br>") + "</div><div class='small muted'>" +
      (data.ai ? "Disusun AI dari angka di atas; periksa kembali sebelum dipakai." : "Ringkasan otomatis dari angka di atas.") + "</div>";
  }

  function askInsight(button, box, url, fields) {
    button.disabled = true;
    box.className = "small muted";
    box.textContent = "Menyusun wawasan…";
    request(url, { method: "POST", body: form(fields) }).then(function (data) {
      box.className = "small";
      box.innerHTML = insightHtml(data);
    }).catch(function (error) { box.textContent = error.message; })
      .then(function () { button.disabled = false; });
  }

  function download(url, fallbackName, message) {
    // Unduh lewat fetch agar galat tampil sebagai pesan, bukan halaman JSON.
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) {
        return response.json().catch(function () { return null; }).then(function (data) {
          throw new ApiError(errorText(data, "Gagal mengunduh (" + response.status + ")."), response.status, data);
        });
      }
      var match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
      return response.blob().then(function (blob) {
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = match ? match[1] : fallbackName;
        document.body.appendChild(link);
        link.click();
        setTimeout(function () { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
        toast(message, "ok");
      });
    }).catch(function (error) { toast(error.message || "Unduhan butuh koneksi internet.", "error"); });
  }

  // ================================================================ Kinerja

  var DAY_CLASS = { hadir: "hadir", terlambat: "terlambat", izin: "izin", sakit: "sakit", cuti: "cuti", dinas: "dinas" };
  var perfTarget = "";
  var perfPoints = [];
  var perfLayer = L.layerGroup();

  function renderPerformance(me) {
    var calendar = "";
    if (me.days.length && me.days.length <= 62) {
      var first = new Date(me.days[0].date + "T00:00:00");
      var offset = (first.getDay() + 6) % 7;
      for (var i = 0; i < offset; i += 1) { calendar += "<div style='visibility:hidden'></div>"; }
      var today = new Date().toISOString().slice(0, 10);
      me.days.forEach(function (d) {
        var cls = DAY_CLASS[d.status] || (d.workday && d.date < today ? "alpa" : "");
        if (d.approval === "menunggu" || d.approval === "ditolak") { cls += " " + d.approval; }
        if (!d.workday) { cls += " libur"; }
        calendar += "<div class='" + cls + "' title='" + escapeHtml(d.date + (d.status ? " · " + d.status : "") + (d.approval === "menunggu" ? " (menunggu persetujuan)" : d.approval === "ditolak" ? " (ditolak)" : "") + " · " + d.activities + " kegiatan") + "'>" +
          parseInt(d.date.slice(8), 10) + (d.activities ? "•" : "") + "</div>";
      });
    }
    return "<div class='score'><div class='score-ring' style='--p:" + Math.round(me.score) + "'><div><b>" + escapeHtml(me.grade) + "</b><span class='small'>" + me.score + "</span></div></div>" +
      "<div><b>" + escapeHtml(me.user) + "</b><br><span class='muted small'>" + fmtDate(me.start) + " – " + fmtDate(me.end) + " · " + me.workdays + " hari kerja</span></div></div>" +
      "<div class='metrics'>" +
      "<div class='metric'><b>" + me.attendance_pct + "%</b><span>Kehadiran (" + me.present_days + " hari, " + me.late_days + " terlambat)</span></div>" +
      "<div class='metric'><b>" + pctText(me.on_time_pct) + "</b><span>Tepat waktu</span></div>" +
      "<div class='metric'><b>" + me.activities + "/" + me.activity_target + "</b><span>Kegiatan vs target</span></div>" +
      "<div class='metric'><b>" + me.residents_visited + "</b><span>Warga dikunjungi</span></div>" +
      "<div class='metric'><b>" + me.tasks_on_time + "/" + me.tasks_due + "</b><span>Tugas tepat waktu</span></div>" +
      "<div class='metric'><b>" + me.tasks_overdue + "</b><span>Tugas terlambat (terbuka)</span></div>" +
      "</div>" + (calendar ? "<h3>Kalender</h3><div class='calendar'>" + ["Sn", "Sl", "Rb", "Km", "Jm", "Sb", "Mg"].map(function (d) { return "<div class='muted' style='background:none'>" + d + "</div>"; }).join("") + calendar + "</div>" : "");
  }

  function renderPerformanceDetail(detail) {
    perfPoints = detail.points;
    var daily = detail.daily.length <= 62;
    var rows = daily ? detail.daily : detail.weekly;
    var label = daily ? function (r) { return r.date.slice(8, 10); } : function (r) { return r.week.slice(-3); };
    var title = function (unit) {
      return function (r) { return (daily ? fmtDate(r.date) : r.week + " (mulai " + fmtDate(r.start) + ")") + ": " + fmtNum(r[unit], 1) + (unit === "points" ? " poin" : " kegiatan"); };
    };
    var html = "<div class='grid2 split'>" +
      "<div><h3>Kegiatan " + (daily ? "harian" : "mingguan") + "</h3><div class='chart'>" + barChart(rows, "activities", label, "#1d82f5", title("activities")) + "</div></div>" +
      "<div><h3>Poin usaha " + (daily ? "harian" : "mingguan") + "</h3><div class='chart'>" + barChart(rows, "points", label, "#1a7f37", title("points")) + "</div></div>" +
      "</div><div class='grid2 split'>" +
      "<div><h3>Profil kinerja</h3><div class='chart'>" + radarChart(detail.radar) + "</div></div>" +
      "<div><h3>Aktivitas 90 hari</h3>" + heatGrid(detail.heat) + "</div></div>" +
      "<div class='row wrap'><button type='button' class='btn-small' id='kinerja-peta'" + (detail.points.length ? "" : " disabled") + ">🗺️ Lihat sebaran di peta (" + detail.points.length + " titik)</button></div>";
    html += "<h3>Tugas terbuka</h3><ul class='list compact'>" + (detail.tasks.map(function (t) {
      return "<li class='clickable' data-buka-tugas='" + t.id + "'><b>" + escapeHtml(t.number) + "</b> " + escapeHtml(t.title) +
        "<div class='sub'>" + escapeHtml(t.status_label) + (t.due_date ? " · tenggat " + fmtDate(t.due_date) : "") + (t.overdue ? " · <span class='danger-text'>terlambat</span>" : "") + (t.points ? " · " + t.points + " poin" : "") + "</div></li>";
    }).join("") || "<li class='muted'>Tidak ada tugas terbuka.</li>") + "</ul>";
    html += "<h3>Kegiatan terakhir</h3><ul class='list compact'>" + (detail.recent.map(function (a) {
      return "<li><b>" + escapeHtml(a.title || a.type_label) + "</b> " + (a.verified ? "<span class='badge' style='background:#1a7f37'>terverifikasi</span>" : "") +
        "<div class='sub'>" + escapeHtml([a.number, a.type_label, a.korwil ? "Korwil " + a.korwil : ""].filter(Boolean).join(" · ")) + " · " + fmtDate(a.at, true) + " · " + fmtNum(a.points, 1) + " poin</div></li>";
    }).join("") || "<li class='muted'>Belum ada kegiatan.</li>") + "</ul>";
    return html;
  }

  function loadPerformance() {
    if (map.hasLayer(perfLayer)) { map.removeLayer(perfLayer); }
    var params = "?rinci=1&periode=" + $("kinerja-periode").value + (perfTarget ? "&petugas=" + perfTarget : "");
    request(urls.performance + params).then(function (data) {
      $("kinerja-isi").innerHTML = renderPerformance(data.me);
      $("kinerja-rinci").innerHTML = data.detail ? renderPerformanceDetail(data.detail) : "";
      if (data.team) {
        $("kinerja-tim").hidden = false;
        var select = $("kinerja-petugas");
        select.hidden = false;
        fillSelect(select, data.team.map(function (row) { return { value: row.user_id, label: row.user }; }), "Kinerja saya");
        select.value = perfTarget;
        $("kinerja-tim-isi").innerHTML = data.team.map(function (row, index) {
          return "<tr class='clickable' data-petugas='" + row.user_id + "'><td>" + (index + 1) + "</td><td>" + escapeHtml(row.user) + "</td><td><b>" + row.score + "</b> " + row.grade +
            "</td><td>" + row.attendance_pct + "%</td><td>" + row.activities + "/" + row.activity_target + "</td><td>" + row.task_pct + "%</td></tr>";
        }).join("");
      }
    }).catch(function (error) { $("kinerja-isi").textContent = error.message; $("kinerja-rinci").innerHTML = ""; });
  }

  function openPerformance(userId) {
    perfTarget = userId ? String(userId) : "";
    $("kinerja-wawasan-isi").className = "small muted";
    $("kinerja-wawasan-isi").textContent = "Ringkasan kekuatan, kelemahan, dan saran untuk periode terpilih.";
    showTab("perf");
  }

  $("kinerja-periode").addEventListener("change", loadPerformance);
  $("kinerja-petugas").addEventListener("change", function () { openPerformance(this.value); });
  $("kinerja-rinci").addEventListener("click", function (event) {
    var task = event.target.closest("[data-buka-tugas]");
    if (task) { openTask(parseInt(task.getAttribute("data-buka-tugas"), 10)); return; }
    if (event.target.closest("#kinerja-peta")) {
      perfLayer.clearLayers();
      perfPoints.forEach(function (p) {
        L.circleMarker([p.lat, p.lng], { radius: 5, color: "#fff", weight: 1, fillOpacity: 0.9, fillColor: p.kind === "absen" ? "#8250df" : "#1d82f5" })
          .bindTooltip(escapeHtml(p.label)).addTo(perfLayer);
      });
      perfLayer.addTo(map);
      showTab("peta");
      var bounds = L.latLngBounds(perfPoints.map(function (p) { return [p.lat, p.lng]; }));
      if (bounds.isValid()) { map.fitBounds(bounds.pad(0.2), { maxZoom: 16 }); }
      toast(perfPoints.length + " titik kerja ditampilkan (biru: kegiatan, ungu: absen). Buka Kinerja lagi untuk menyembunyikan.", "ok");
    }
  });
  $("kinerja-wawasan").addEventListener("click", function () {
    askInsight(this, $("kinerja-wawasan-isi"), urls.performanceInsight, { periode: $("kinerja-periode").value, petugas: perfTarget });
  });

  // ================================================================ Peringkat, struktur, feed, AI

  var TREND_BADGE = {
    naik: '<span class="badge" style="background:#1a7f37">↗ naik</span>',
    turun: '<span class="badge" style="background:#cf222e">↘ turun</span>',
    baru: '<span class="badge" style="background:#0969da">★ baru</span>',
    stabil: '<span class="badge" style="background:#8c959f">→ stabil</span>'
  };
  var GRADE_COLORS = { A: "#1a7f37", B: "#0b5fcc", C: "#bf8700", D: "#cf222e" };
  var boardView = "semua";

  function boardParams() {
    var params = new URLSearchParams({ periode: $("peringkat-periode").value, tampilan: boardView });
    if ($("peringkat-korwil").value) { params.append("korwil", $("peringkat-korwil").value); }
    if ($("peringkat-tier").value) { params.append("tier", $("peringkat-tier").value); }
    return params;
  }

  function loadLeaderboard() {
    request(urls.leaderboard + "?" + boardParams().toString()).then(function (data) {
      if ($("peringkat-tier").options.length <= 1) {
        fillSelect($("peringkat-tier"), data.tiers, "Semua tingkat");
        fillSelect($("peringkat-korwil"), data.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " · " + k.name }; }), "Semua Korwil");
      }
      $("peringkat-korwil").hidden = !perms.tim || data.korwils.length < 2;
      $("peringkat-tier").hidden = !perms.tim;
      $("peringkat-tampilan").hidden = !perms.tim;
      $("peringkat-wawasan-kotak").hidden = !perms.tim;
      $("peringkat-ringkas").innerHTML = "<div class='metric'><b>" + data.count + "</b><span>Petugas dinilai</span></div>" +
        "<div class='metric'><b>" + (data.average === null ? "–" : fmtNum(data.average, 1)) + "</b><span>Rata-rata skor</span></div>" +
        "<div class='metric grades'>" + ["A", "B", "C", "D"].map(function (g) {
          return "<span class='badge' style='background:" + GRADE_COLORS[g] + "'>" + g + " " + data.grades[g] + "</span>";
        }).join(" ") + "<span>Sebaran nilai</span></div>";
      $("peringkat-lencana").textContent = "Lencana: " + Object.keys(data.badges).map(function (key) { return data.badges[key].icon + " " + data.badges[key].label; }).join(" · ");
      $("peringkat-isi").innerHTML = data.results.map(function (row) {
        var badges = row.badges.map(function (key) {
          var b = data.badges[key];
          return b ? "<span class='lencana' title='" + escapeHtml(b.label) + "'>" + b.icon + "</span>" : "";
        }).join("");
        return "<div class='rank-row" + (perms.tim ? " clickable" : "") + "' data-petugas='" + row.user_id + "'>" +
          "<span class='rank-no'>#" + row.rank + "</span>" +
          "<span class='rank-name'><b>" + escapeHtml(row.user) + "</b> " + badges +
          "<br><span class='muted small'>" + escapeHtml([row.tier_label, row.korwils.length ? "Korwil " + row.korwils.join(", ") : ""].filter(Boolean).join(" · ")) +
          " · hadir " + row.attendance_pct + "% · kegiatan " + row.activities + "/" + row.activity_target + " · komsos " + row.komsos + "</span></span>" +
          "<span class='rank-score'><b>" + row.score + "</b> <span class='badge' style='background:" + (GRADE_COLORS[row.grade] || "#57606a") + "'>" + escapeHtml(row.grade) + "</span><br>" + (TREND_BADGE[row.trend] || "") + "</span></div>";
      }).join("") || "<p class='muted'>Belum ada anggota tim.</p>";
    }).catch(function (error) { $("peringkat-isi").textContent = error.message; });
  }

  function resetBoardInsight() {
    $("peringkat-wawasan-isi").className = "small muted";
    $("peringkat-wawasan-isi").textContent = "Siapa yang menonjol, siapa yang perlu didampingi, dan sarannya.";
  }
  ["peringkat-periode", "peringkat-korwil", "peringkat-tier"].forEach(function (id) {
    $(id).addEventListener("change", function () { resetBoardInsight(); loadLeaderboard(); });
  });
  $("peringkat-tampilan").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-tampilan]");
    if (!button) { return; }
    boardView = button.getAttribute("data-tampilan");
    this.querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b === button); });
    loadLeaderboard();
  });
  $("peringkat-isi").addEventListener("click", function (event) {
    var row = event.target.closest("[data-petugas]");
    if (row && perms.tim) { openPerformance(row.getAttribute("data-petugas")); }
  });
  $("peringkat-excel").addEventListener("click", function () {
    var button = this;
    var params = boardParams();
    params.set("tampilan", "semua");
    button.disabled = true;
    download(urls.leaderboardExcel + "?" + params.toString(), "peringkat.xlsx", "Peringkat Excel diunduh.")
      .then(function () { button.disabled = false; });
  });
  $("peringkat-wawasan").addEventListener("click", function () {
    var params = boardParams();
    var fields = {};
    params.forEach(function (value, key) { fields[key] = value; });
    fields.tampilan = "semua";
    askInsight(this, $("peringkat-wawasan-isi"), urls.leaderboardInsight, fields);
  });

  function loadStructure() {
    request(urls.structure).then(function (data) {
      $("struktur-isi").innerHTML = data.results.map(function (k) {
        var members = k.members.map(function (m) { return escapeHtml(m.name); }).join(", ") || "—";
        return "<div class='stack card clickable' data-korwil-detail='" + k.id + "'><b style='color:" + escapeHtml(k.color) + "'>Korwil " + escapeHtml(k.code) + " – " + escapeHtml(k.name) + "</b>" +
          "<div class='small'>Koordinator: <b>" + escapeHtml(k.coordinator || "—") + "</b></div>" +
          "<div class='small muted'>Anggota: " + members + "</div></div>";
      }).join("") || "<p class='muted'>Belum ada Korwil.</p>";
    }).catch(function (error) { $("struktur-isi").textContent = error.message; });
  }
  $("struktur-isi").addEventListener("click", function (event) {
    var card = event.target.closest("[data-korwil-detail]");
    if (card) { openKorwil(card.getAttribute("data-korwil-detail")); }
  });

  // ================================================================ Beranda

  function goResidents(stance, korwil) {
    if (!perms.warga) { return; }
    $("warga-sikap").value = stance || "";
    $("warga-korwil").value = korwil ? String(korwil) : "";
    $("warga-cari").value = "";
    showTab("warga");
  }

  var TREND_SERIES = function () {
    return [
      { key: "pro_pct", color: stanceColor("mendukung"), label: "Mendukung" },
      { key: "neutral_pct", color: stanceColor("netral"), label: "Netral" },
      { key: "contra_pct", color: stanceColor("menolak"), label: "Menolak" }
    ];
  };

  function stanceCards(stances, korwil) {
    return STANCE_KEYS.map(function (key) {
      var pct = stances[key + "_pct"];
      return "<button type='button' class='stance-card' data-sikap='" + key + "'" + (korwil ? " data-korwil='" + korwil + "'" : "") + (perms.warga ? "" : " disabled") +
        " style='--c:" + escapeHtml(stanceColor(key)) + "'><b>" + fmtNum(stances[key]) + "</b><span>" + escapeHtml(choiceLabel("stance", key)) +
        (pct !== undefined && pct !== null ? " · " + pct + "%" : "") + "</span></button>";
    }).join("");
  }

  function loadHome() {
    loadAnomalies();
    $("beranda-angka").innerHTML = "<p class='muted'>Memuat…</p>";
    request(urls.home).then(function (data) {
      var c = data.counts;
      $("beranda-waktu").textContent = "Diperbarui " + fmtDate(data.updated_at, true) + ". Angka hanya dari wilayah yang boleh Anda lihat.";
      $("beranda-angka").innerHTML =
        "<div class='metric'><b>" + fmtNum(c.total) + "</b><span>Warga terdata</span></div>" +
        "<div class='metric'><b>" + pctText(c.pro_pct) + "</b><span>Mendukung (dari yang diketahui)</span></div>" +
        "<div class='metric'><b>" + pctText(c.released_pct) + "</b><span>Lahan dilepas (" + fmtNum(c.released) + ")</span></div>" +
        "<div class='metric'><b>" + pctText(c.rtrw_pct) + "</b><span>Sesuai RTRW</span></div>";
      $("beranda-sikap").innerHTML = stanceCards(data.stances);
      $("beranda-tren").innerHTML = lineChart(data.trend, TREND_SERIES());
      $("beranda-korwil").innerHTML = data.korwils.map(function (k) {
        return "<tr class='clickable' data-korwil-detail='" + k.id + "'><td><b style='color:" + escapeHtml(k.color) + "'>" + escapeHtml(k.code) + "</b> " + escapeHtml(k.name) +
          "<div class='small muted'>" + escapeHtml(k.coordinator || "—") + " · " + k.members + " anggota</div></td>" +
          "<td>" + fmtNum(k.residents) + (k.target ? " / " + fmtNum(k.target) + " <span class='muted small'>(" + pctText(k.target_pct) + ")</span>" : "") + "</td>" +
          "<td style='min-width:90px'>" + stanceBar({ mendukung: k.pro, netral: k.neutral, menolak: k.contra, belum: k.unknown }) + "</td>" +
          "<td>" + pctText(k.pro_pct) + "</td><td>" + pctText(k.released_pct) + "</td><td>" + k.activities_week + "</td></tr>";
      }).join("") || "<tr><td colspan='6' class='muted'>Belum ada Korwil.</td></tr>";
      var maxType = Math.max.apply(null, data.activities_week.map(function (a) { return a.count; }).concat([1]));
      $("beranda-kegiatan").innerHTML = data.activities_week.map(function (a) {
        return "<div class='hbar'><span>" + escapeHtml(a.label) + "</span><i style='width:" + (a.count * 100 / maxType).toFixed(1) + "%;background:" + escapeHtml(a.color) + "'></i><b>" + a.count + "</b></div>";
      }).join("") || "<p class='muted small'>Belum ada kegiatan 7 hari terakhir.</p>";
      var maxSoil = Math.max.apply(null, data.soil.map(function (a) { return a.count; }).concat([1]));
      $("beranda-tanah").innerHTML = data.soil.map(function (a) {
        return "<div class='hbar'><span>" + escapeHtml(a.label) + "</span><i style='width:" + (a.count * 100 / maxSoil).toFixed(1) + "%;background:" + escapeHtml(config.colors.soil[a.value] || "#57606a") + "'></i><b>" + a.count + "</b></div>";
      }).join("");
    }).catch(function (error) { $("beranda-angka").textContent = error.message; });
  }

  $("beranda-muat").addEventListener("click", loadHome);
  $("beranda-sikap").addEventListener("click", function (event) {
    var card = event.target.closest("[data-sikap]");
    if (card) { goResidents(card.getAttribute("data-sikap")); }
  });
  $("beranda-korwil").addEventListener("click", function (event) {
    var row = event.target.closest("[data-korwil-detail]");
    if (row) { openKorwil(row.getAttribute("data-korwil-detail")); }
  });

  // ================================================================ Detail Korwil

  function openKorwil(id) {
    var dialog = $("dlg-korwil");
    $("kd-judul").textContent = "Korwil";
    $("kd-isi").innerHTML = "<p class='muted'>Memuat…</p>";
    if (!dialog.open) { dialog.showModal(); }
    request(urls.korwilDetail.replace("/0/", "/" + id + "/")).then(function (k) {
      $("kd-judul").innerHTML = "<span style='color:" + escapeHtml(k.color) + "'>Korwil " + escapeHtml(k.code) + "</span> – " + escapeHtml(k.name);
      var html = "<p class='small muted'>Koordinator: <b>" + escapeHtml(k.coordinator || "—") + "</b>" + (k.villages ? " · " + escapeHtml(k.villages) : "") + "</p>" +
        "<div class='metrics four'>" +
        "<div class='metric'><b>" + fmtNum(k.counts.total) + (k.target ? " / " + fmtNum(k.target) : "") + "</b><span>Warga" + (k.target ? " / target KK" : "") + "</span></div>" +
        "<div class='metric'><b>" + pctText(k.counts.pro_pct) + "</b><span>Mendukung</span></div>" +
        "<div class='metric'><b>" + pctText(k.counts.released_pct) + "</b><span>Lahan dilepas</span></div>" +
        "<div class='metric'><b>" + k.activities_week + " / " + k.activities_month + "</b><span>Kegiatan 7 / 30 hari</span></div></div>" +
        "<div class='stance-cards'>" + stanceCards(k.stances, k.id) + "</div>" +
        "<h3>Tren dukungan (8 pekan)</h3><div class='chart'>" + lineChart(k.trend, TREND_SERIES()) + "</div>" +
        "<h3>Anggota (" + k.members.length + ")</h3><div class='table-wrap'><table class='table'><thead><tr><th>Petugas</th><th>Skor bulan ini</th><th>Hadir</th><th>Kegiatan</th><th>Warga</th></tr></thead><tbody>" +
        (k.members.map(function (m) {
          var scored = m.score !== null;
          return "<tr" + (scored ? " class='clickable' data-petugas='" + m.id + "'" : "") + "><td><b>" + escapeHtml(m.name) + "</b><div class='small muted'>" + escapeHtml([m.role, m.position].filter(Boolean).join(" · ")) + "</div></td>" +
            "<td>" + (scored ? "<b>" + m.score + "</b> <span class='badge' style='background:" + (GRADE_COLORS[m.grade] || "#57606a") + "'>" + escapeHtml(m.grade) + "</span>" : "–") + "</td>" +
            "<td>" + pctText(m.attendance_pct) + "</td><td>" + (scored ? fmtNum(m.activities, 1) : "–") + "</td><td>" + (scored ? m.residents_visited : "–") + "</td></tr>";
        }).join("") || "<tr><td colspan='5' class='muted'>Belum ada anggota.</td></tr>") + "</tbody></table></div>";
      if (k.show_residents) {
        html += "<h3>Warga per sikap</h3>" + (k.residents_truncated ? "<p class='small muted'>Menampilkan 500 warga pertama (urut nama). Gunakan tab Warga untuk mencari.</p>" : "");
        html += STANCE_KEYS.map(function (key) {
          var rows = k.residents[key] || [];
          return "<details class='group'><summary><span class='badge' style='background:" + escapeHtml(stanceColor(key)) + "'>" + escapeHtml(choiceLabel("stance", key)) + "</span> " + rows.length + " warga</summary>" +
            "<ul class='list compact'>" + (rows.map(function (r) {
              return "<li class='clickable' data-warga='" + r.id + "'><b>" + escapeHtml(r.name) + "</b><div class='sub'>" + escapeHtml([r.number, r.village].filter(Boolean).join(" · ")) +
                " · komsos " + r.komsos + (r.last_komsos ? " (terakhir " + fmtDate(r.last_komsos) + ")" : "") + "</div></li>";
            }).join("") || "<li class='muted'>Tidak ada.</li>") + "</ul></details>";
        }).join("");
      }
      if (k.recent.length) {
        html += "<h3>Kegiatan terakhir</h3><ul class='list compact'>" + k.recent.map(function (a) {
          return "<li><b>" + escapeHtml(a.title || a.type_label) + "</b><div class='sub'>" + escapeHtml([a.number, a.type_label, a.by].filter(Boolean).join(" · ")) + " · " + fmtDate(a.at, true) + " · " + fmtNum(a.points, 1) + " poin</div></li>";
        }).join("") + "</ul>";
      }
      $("kd-isi").innerHTML = html;
    }).catch(function (error) { $("kd-isi").textContent = error.message; });
  }

  $("kd-isi").addEventListener("click", function (event) {
    var stance = event.target.closest("[data-sikap]");
    var resident = event.target.closest("[data-warga]");
    var officer = event.target.closest("[data-petugas]");
    if (stance) {
      $("dlg-korwil").close();
      goResidents(stance.getAttribute("data-sikap"), stance.getAttribute("data-korwil"));
    } else if (resident) {
      openResident(parseInt(resident.getAttribute("data-warga"), 10));
    } else if (officer) {
      $("dlg-korwil").close();
      openPerformance(officer.getAttribute("data-petugas"));
    }
  });

  // ================================================================ Anomali & risiko

  var LEVEL_COLORS = { kritis: "#7f1d1d", tinggi: "#ef4444", sedang: "#f59e0b", rendah: "#10b981", "": "#8c959f" };
  var LEVEL_LABELS = { kritis: "Kritis", tinggi: "Tinggi", sedang: "Sedang", rendah: "Rendah", "": "Data kurang" };

  function levelBadge(level) {
    return "<span class='badge' style='background:" + (LEVEL_COLORS[level] || "#8c959f") + "'>" + escapeHtml(LEVEL_LABELS[level] || level) + "</span>";
  }

  function loadAnomalies() {
    request(urls.anomalies).then(function (data) {
      $("beranda-anomali").innerHTML = data.anomalies.map(function (a) {
        return "<details class='anomaly' style='--c:" + (LEVEL_COLORS[a.level] || "#8c959f") + "'" + (a.level === "kritis" ? " open" : "") + "><summary>" + levelBadge(a.level) + " " + escapeHtml(a.title) +
          " <span class='muted small'>(" + a.items.length + ")</span></summary><ul class='list compact'>" + a.items.map(function (i) {
            var go = i.center ? " class='clickable' data-lat='" + i.center[0] + "' data-lng='" + i.center[1] + "'" : "";
            return "<li" + go + "><b>" + escapeHtml(i.label) + "</b>" + (i.center ? " 📍" : "") + "<div class='sub'>" + escapeHtml(i.detail) + "</div></li>";
          }).join("") + "</ul></details>";
      }).join("") || "<p class='small ok-text'>✓ Tidak ada anomali saat ini.</p>";
      $("beranda-risiko").innerHTML = data.risks.map(function (r) {
        return "<button type='button' class='risk' data-korwil-detail='" + r.id + "' style='--c:" + (LEVEL_COLORS[r.level] || "#8c959f") + "'><b>" + escapeHtml(r.code) + " · " + pctText(r.contra_pct) + "</b>" +
          "<span>" + escapeHtml(LEVEL_LABELS[r.level] || "") + " · " + r.contra + " kontra / " + r.known + "</span></button>";
      }).join("") || "<p class='muted small'>Belum ada Korwil.</p>";
    }).catch(function (error) { $("beranda-anomali").textContent = error.message; });
  }

  $("beranda-anomali").addEventListener("click", function (event) {
    var item = event.target.closest("[data-lat]");
    if (!item) { return; }
    showTab("peta");
    map.setView([parseFloat(item.getAttribute("data-lat")), parseFloat(item.getAttribute("data-lng"))], 16);
  });
  $("beranda-risiko").addEventListener("click", function (event) {
    var button = event.target.closest("[data-korwil-detail]");
    if (button) { openKorwil(button.getAttribute("data-korwil-detail")); }
  });

  // ================================================================ Peta & spasial

  var analysisLayer = L.layerGroup().addTo(map);

  function narrow() { return window.matchMedia("(max-width: 640px)").matches; }

  function showAnalysis(layer, bounds) {
    analysisLayer.clearLayers();
    analysisLayer.addLayer(layer);
    document.querySelector('[data-tool="clear-analysis"]').hidden = false;
    if (narrow()) { showTab("peta"); }
    if (bounds && bounds.isValid && bounds.isValid()) {
      // Panel samping menutupi ±440 px kanan peta di layar lebar.
      var side = !narrow() && document.querySelector(".tab-view.sheet:not([hidden])") ? 470 : 30;
      setTimeout(function () { map.fitBounds(bounds, { paddingTopLeft: [30, 30], paddingBottomRight: [side, 30], maxZoom: 17 }); }, narrow() ? 80 : 0);
    }
  }

  function clearAnalysis() {
    analysisLayer.clearLayers();
    document.querySelector('[data-tool="clear-analysis"]').hidden = true;
  }

  function setTactical(on) {
    map.getContainer().classList.toggle("tactical", on);
    document.querySelector('[data-tool="tactical"]').classList.toggle("active", on);
    store("taktis", on);
  }

  function ensureLayer(key) {
    if (!LAYER_SPECS.some(function (s) { return s.key === key; })) { return; }
    layerState[key] = true;
    store("lapisan", layerState);
    loadLayer(key);
    renderLayerList();
  }

  var spatialPart = "bidang";
  var spatialReady = false;
  var HEAT_SOURCES = [
    { value: "kegiatan", label: "Sebaran kegiatan", perm: perms.kegiatan },
    { value: "posisi", label: "Jejak GPS petugas", perm: perms.jejak },
    { value: "warga", label: "Sebaran warga terdata", perm: perms.warga }
  ].filter(function (s) { return s.perm; });
  var SPATIAL_ALLOWED = {
    bidang: perms.bidang, tumpang: true, audit: perms.warga, panas: HEAT_SOURCES.length > 0,
    jejak: perms.jejak, ancaman: perms.ancaman, foto: perms.foto360
  };

  function korwilOptions() {
    return config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " – " + k.name }; });
  }

  function prepareSpatial() {
    if (spatialReady) { return; }
    spatialReady = true;
    document.querySelectorAll("#spasial-bagian button").forEach(function (button) {
      button.hidden = !SPATIAL_ALLOWED[button.getAttribute("data-bagian")];
    });
    if (!SPATIAL_ALLOWED[spatialPart]) {
      spatialPart = Object.keys(SPATIAL_ALLOWED).filter(function (k) { return SPATIAL_ALLOWED[k]; })[0];
    }
    ["bd-korwil", "au-korwil"].forEach(function (id) { fillSelect($(id), korwilOptions(), "Semua Korwil"); });
    ["ib-korwil", "za-korwil"].forEach(function (id) { fillSelect($(id), korwilOptions(), "Otomatis dari lokasi"); });
    fillSelect($("bd-status"), config.choices.control, "Semua status");
    fillSelect($("ib-urgensi"), config.choices.urgency);
    fillSelect($("za-level"), config.choices.threat);
    $("za-level").value = "sedang";
    fillSelect($("ph-sumber"), HEAT_SOURCES);
    $("jj-tanggal").value = localInputValue().slice(0, 10);
    $("bd-impor").hidden = !perms.tambahBidang;
    document.querySelector('#ib-mode [data-mode="penguasaan"]').hidden = !perms.ubahBidang;
    $("form-ancaman").hidden = !perms.tambahAncaman;
    $("form-foto360").hidden = !perms.tambahFoto360;
  }

  function loadSpatial() {
    prepareSpatial();
    showSpatialPart(spatialPart);
  }

  function showSpatialPart(name) {
    spatialPart = name;
    document.querySelectorAll("#spasial-bagian button").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-bagian") === name); });
    document.querySelectorAll("#tab-spasial [data-panel]").forEach(function (panel) { panel.hidden = panel.getAttribute("data-panel") !== name; });
    if (name === "bidang") { loadPlots(); }
    if (name === "tumpang") { loadOverlapSources(); }
    if (name === "jejak") { loadTrackOfficers(); }
    if (name === "ancaman") { loadThreatZones(); }
    if (name === "foto") { loadSitePhotos(); }
  }

  $("spasial-bagian").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-bagian]");
    if (button) { showSpatialPart(button.getAttribute("data-bagian")); }
  });

  // ---------------------------------------------------------------- Penguasaan lahan

  var plotTimer = null;

  function haText(value) { return fmtNum(value, 2) + " ha"; }
  function pct1(value) { return value === null || value === undefined ? "–" : fmtNum(value, 1) + "%"; }

  function loadPlots() {
    var params = ["urut=" + $("bd-urut").value];
    if ($("bd-korwil").value) { params.push("korwil=" + $("bd-korwil").value); }
    if ($("bd-status").value) { params.push("status=" + $("bd-status").value); }
    if ($("bd-cari").value.trim()) { params.push("q=" + encodeURIComponent($("bd-cari").value.trim())); }
    $("bd-daftar").innerHTML = "<li class='muted'>Memuat…</li>";
    request(urls.plots + "?" + params.join("&")).then(function (data) {
      var s = data.summary;
      $("bd-ringkas").innerHTML =
        "<div class='metric'><b>" + fmtNum(s.total) + "</b><span>Bidang · " + haText(s.area_ha) + "</span></div>" +
        "<div class='metric'><b style='color:" + config.colors.control.sudah + "'>" + fmtNum(s.controlled) + "</b><span>Sudah dikuasai · " + haText(s.controlled_ha) + "</span></div>" +
        "<div class='metric'><b style='color:" + config.colors.control.belum + "'>" + fmtNum(s.pending) + "</b><span>Belum dikuasai · " + haText(s.pending_ha) + "</span></div>" +
        "<div class='metric'><b>" + pctText(s.controlled_pct) + "</b><span>Dikuasai · skor sisa " + fmtNum(s.score_pending, 1) + "</span></div>";
      $("bd-daftar").innerHTML = data.rows.map(function (r) {
        return "<li class='clickable' data-bidang='" + r.id + "'><div class='row' style='justify-content:space-between;gap:8px'><b>" + escapeHtml(r.number + (r.name ? " – " + r.name : "")) + "</b>" +
          "<b title='Skor prioritas'>" + fmtNum(r.score, 1) + "</b></div>" +
          "<div class='sub'><span class='badge' style='background:" + escapeHtml(r.color) + "'>" + escapeHtml(r.status_label) + "</span> " +
          escapeHtml([r.owner, r.korwil ? "Korwil " + r.korwil : "", haText(r.area_ha), r.zone_label.split(" (")[0], "urgensi " + r.urgency_label.toLowerCase()].filter(Boolean).join(" · ")) + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada bidang." + (perms.tambahBidang ? " Impor berkas KML/KMZ hasil pemetaan untuk mulai." : "") + "</li>";
      if (data.truncated) { $("bd-daftar").insertAdjacentHTML("beforeend", "<li class='muted small'>Menampilkan 2.000 dari " + fmtNum(data.total) + " bidang. Persempit dengan filter.</li>"); }
    }).catch(function (error) { $("bd-daftar").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  ["bd-korwil", "bd-status", "bd-urut"].forEach(function (id) { $(id).addEventListener("change", loadPlots); });
  $("bd-cari").addEventListener("input", function () { clearTimeout(plotTimer); plotTimer = setTimeout(loadPlots, 300); });
  $("bd-daftar").addEventListener("click", function (event) {
    var row = event.target.closest("[data-bidang]");
    if (row) { openPlot(row.getAttribute("data-bidang")); }
  });

  function plotUrl(id) { return urls.plot.replace("/0/", "/" + id + "/"); }

  function openPlot(id) {
    var dialog = $("dlg-bidang");
    $("bdd-judul").textContent = "Bidang";
    $("bdd-isi").innerHTML = "<p class='muted'>Memuat…</p>";
    if (!dialog.open) { dialog.showModal(); }
    request(plotUrl(id)).then(renderPlot).catch(function (error) { $("bdd-isi").textContent = error.message; });
  }

  var currentPlot = null;

  function renderPlot(p) {
    currentPlot = p;
    $("bdd-judul").innerHTML = escapeHtml(p.number + (p.name ? " – " + p.name : "")) + " <span class='badge' style='background:" + escapeHtml(p.color) + "'>" + escapeHtml(p.status_label) + "</span>";
    var info = [
      ["Pemilik", p.owner], ["Penjaga lahan", p.guard], ["Korwil", p.korwil], ["Tanggal dikuasai", p.controlled_on ? fmtDate(p.controlled_on) : ""],
      ["Tim penguasaan", p.team], ["Lapisan", p.layers.join(", ")], ["Sumber data", p.source], ["Catatan", p.note]
    ].filter(function (r) { return r[1]; });
    var html = "<div class='metrics four'>" +
      "<div class='metric'><b>" + haText(p.area_ha) + "</b><span>" + (p.official_ha !== null ? "Luas resmi · terukur " + haText(p.measured_ha || 0) : "Luas terukur") + "</span></div>" +
      "<div class='metric'><b>" + escapeHtml(p.zone_label.split(" (")[0]) + "</b><span>Zona</span></div>" +
      "<div class='metric'><b>" + escapeHtml(p.urgency_label) + "</b><span>Urgensi</span></div>" +
      "<div class='metric'><b>" + fmtNum(p.score, 1) + "</b><span>Skor prioritas</span></div></div>" +
      "<table class='table'><tbody>" + info.map(function (r) { return "<tr><td class='muted'>" + escapeHtml(r[0]) + "</td><td>" + escapeHtml(r[1]) + "</td></tr>"; }).join("") +
      (p.resident_id ? "<tr><td class='muted'>Warga</td><td><a href='#' data-warga='" + p.resident_id + "'>" + escapeHtml(p.resident) + "</a></td></tr>" : "") + "</tbody></table>";
    if (p.overlaps.length) {
      html += "<h3>Masuk lapisan referensi</h3><div class='stack'>" + p.overlaps.map(function (o) {
        return "<div class='hbar'><span title='" + escapeHtml(o.layer) + "'>" + escapeHtml(o.layer) + "</span><i style='width:" + Math.max(o.pct, 1) + "%;background:#c026d3'></i><b>" + fmtNum(o.pct, 1) + "%</b></div>";
      }).join("") + "</div>";
    }
    if (p.can_change) {
      html += "<h3>Perbarui penguasaan</h3><div class='stack card-form' id='bdd-form'><div class='grid2'>" +
        "<label class='field'>Status <select data-f='status'>" + config.choices.control.map(function (c) { return "<option value='" + c.value + "'" + (c.value === p.status ? " selected" : "") + ">" + escapeHtml(c.label) + "</option>"; }).join("") + "</select></label>" +
        "<label class='field'>Urgensi <select data-f='urgensi'>" + config.choices.urgency.map(function (c) { return "<option value='" + c.value + "'" + (c.value === p.urgency ? " selected" : "") + ">" + escapeHtml(c.label) + "</option>"; }).join("") + "</select></label>" +
        "<label class='field'>Tanggal dikuasai <input type='date' data-f='tanggal' value='" + escapeHtml(p.controlled_on) + "'></label>" +
        "<label class='field'>Tim penguasaan <input data-f='tim' maxlength='255' value='" + escapeHtml(p.team) + "'></label></div>" +
        "<label class='field'>Catatan perubahan <input data-f='catatan' maxlength='255'></label>" +
        "<div class='row'><button type='button' class='btn primary' id='bdd-simpan'>Simpan</button></div></div>";
    }
    html += "<h3>Riwayat status</h3><ul class='list compact'>" + (p.history.map(function (h) {
      return "<li><b>" + escapeHtml((h.old ? h.old + " → " : "") + h.new) + "</b><div class='sub'>" + escapeHtml(h.by) + " · " + fmtDate(h.time, true) + (h.note ? " · " + escapeHtml(h.note) : "") + "</div></li>";
    }).join("") || "<li class='muted'>Belum ada riwayat.</li>") + "</ul>" +
      "<div class='row'><button type='button' class='btn' id='bdd-peta'>🗺️ Lihat di peta</button>" + (p.admin ? "<a class='btn' href='" + encodeURI(p.admin) + "'>Ubah batas di panel admin</a>" : "") + "</div>";
    $("bdd-isi").innerHTML = html;
  }

  $("bdd-isi").addEventListener("click", function (event) {
    var resident = event.target.closest("[data-warga]");
    if (resident) { event.preventDefault(); openResident(parseInt(resident.getAttribute("data-warga"), 10)); return; }
    if (event.target.id === "bdd-peta" && currentPlot) {
      var shape = L.geoJSON(currentPlot.geometry, { style: { color: "#f59e0b", weight: 4, fillOpacity: 0.1 } });
      $("dlg-bidang").close();
      showAnalysis(shape, shape.getBounds());
      return;
    }
    if (event.target.id === "bdd-simpan" && currentPlot) {
      var fields = {};
      document.querySelectorAll("#bdd-form [data-f]").forEach(function (input) { fields[input.getAttribute("data-f")] = input.value; });
      var controlChanged = fields.status !== currentPlot.status || fields.tanggal !== (currentPlot.controlled_on || "") || fields.tim !== (currentPlot.team || "");
      if (!controlChanged) { delete fields.status; delete fields.tanggal; delete fields.tim; }
      if (fields.urgensi === currentPlot.urgency) { delete fields.urgensi; }
      if (!fields.status && !fields.urgensi) { toast("Tidak ada perubahan.", "error"); return; }
      var data = form(fields);
      if (fields.status && fields.tim === "") { data.append("tim", ""); }
      event.target.disabled = true;
      request(plotUrl(currentPlot.id), { method: "POST", body: data }).then(function (plot) {
        toast("Bidang diperbarui.", "ok");
        renderPlot(plot);
        loadPlots();
        if (layers.bidang) { loadLayer("bidang"); }
      }).catch(function (error) { toast(error.message, "error"); event.target.disabled = false; });
    }
  });

  var importMode = "baru";
  var IMPORT_HELP = {
    baru: "Setiap poligon menjadi bidang baru berstatus Belum dikuasai. Objek yang mirip bidang tercatat (titik tengah ≤200 m dan luas mirip) tidak dicentang.",
    penguasaan: "Poligon dicocokkan ke bidang terdekat (titik tengah ≤200 m; selisih luas ≤35% atau nama pemilik sama). Bidang yang cocok ditandai Sudah dikuasai; poligon tanpa pasangan dibuat sebagai bidang baru yang sudah dikuasai."
  };
  var MATCH_COLORS = { match: "#1a7f37", weak: "#bf8700", already: "#57606a", nomatch: "#0b5fcc", "new": "#0b5fcc", duplicate: "#9a6700" };

  function setImportMode(mode) {
    importMode = mode;
    document.querySelectorAll("#ib-mode button").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-mode") === mode); });
    document.querySelectorAll("#form-impor-bidang [data-penguasaan]").forEach(function (el) { el.hidden = mode !== "penguasaan"; });
    $("ib-bantuan").textContent = IMPORT_HELP[mode];
    resetImport();
  }

  function resetImport() {
    $("ib-hasil").innerHTML = "";
    $("ib-terapkan").disabled = true;
  }

  function importData(stage) {
    var formEl = $("form-impor-bidang");
    var data = new FormData(formEl);
    data.set("mode", importMode);
    data.set("tahap", stage);
    if (!data.get("korwil")) { data.delete("korwil"); }
    return data;
  }

  $("bd-impor").addEventListener("click", function () {
    $("form-impor-bidang").reset();
    setImportMode("baru");
    $("dlg-impor-bidang").showModal();
  });
  $("ib-mode").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-mode]");
    if (button) { setImportMode(button.getAttribute("data-mode")); }
  });
  $("ib-berkas").addEventListener("change", resetImport);
  $("form-impor-bidang").addEventListener("click", function (event) {
    if (event.target.hasAttribute("data-tutup")) { $("dlg-impor-bidang").close(); }
  });
  $("ib-pratinjau").addEventListener("click", function () {
    var file = $("ib-berkas").files[0];
    if (!file) { toast("Pilih berkas terlebih dahulu.", "error"); return; }
    if (file.size > 20 * 1024 * 1024) { toast("Berkas maksimal 20 MB.", "error"); return; }
    var button = this;
    button.disabled = true;
    $("ib-hasil").innerHTML = "<p class='muted'>Membaca berkas…</p>";
    request(urls.plotImport, { method: "POST", body: importData("pratinjau") }).then(function (data) {
      var counts = Object.keys(data.counts).map(function (k) {
        var label = (data.rows.filter(function (r) { return r.match === k; })[0] || {}).match_label || k;
        return "<span class='badge' style='background:" + (MATCH_COLORS[k] || "#57606a") + "'>" + escapeHtml(label) + ": " + data.counts[k] + "</span>";
      }).join(" ");
      $("ib-hasil").innerHTML = "<p class='small'>" + data.rows.length + " poligon di " + escapeHtml(data.file) + ". " + counts + "</p>" +
        "<label class='check'><input type='checkbox' id='ib-semua'> Pilih / lepas semua</label>" +
        "<div class='table-wrap'><table class='table'><thead><tr><th></th><th>Objek</th><th>Luas</th><th>Hasil</th></tr></thead><tbody>" +
        data.rows.map(function (r) {
          var checked = ["already", "duplicate"].indexOf(r.match) === -1;
          return "<tr><td><input type='checkbox' data-index='" + r.index + "'" + (checked ? " checked" : "") + (r.match === "already" ? " disabled" : "") + " aria-label='Pilih'></td>" +
            "<td><b>" + escapeHtml(r.name || "Objek " + (r.index + 1)) + "</b>" + (r.owner ? "<div class='small muted'>" + escapeHtml(r.owner) + "</div>" : "") + "</td>" +
            "<td>" + haText(r.area_ha) + "</td><td><span class='badge' style='background:" + (MATCH_COLORS[r.match] || "#57606a") + "'>" + escapeHtml(r.match_label) + "</span>" +
            (r.plot ? "<div class='small muted'>" + escapeHtml(r.plot.number + (r.plot.name ? " – " + r.plot.name : "")) + " · " + r.plot.distance_m + " m · selisih luas " + r.plot.area_diff_pct + "%</div>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
      $("ib-terapkan").disabled = false;
    }).catch(function (error) { $("ib-hasil").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>"; })
      .then(function () { button.disabled = false; });
  });
  $("ib-hasil").addEventListener("change", function (event) {
    if (event.target.id === "ib-semua") {
      var on = event.target.checked;
      this.querySelectorAll("input[data-index]:not(:disabled)").forEach(function (box) { box.checked = on; });
    }
  });
  $("form-impor-bidang").addEventListener("submit", function (event) {
    event.preventDefault();
    var chosen = [];
    $("ib-hasil").querySelectorAll("input[data-index]:checked").forEach(function (box) { chosen.push(box.getAttribute("data-index")); });
    if (!chosen.length) { toast("Pilih minimal satu objek.", "error"); return; }
    var data = importData("terapkan");
    data.set("pilih", chosen.join(","));
    var button = $("ib-terapkan");
    button.disabled = true;
    request(urls.plotImport, { method: "POST", body: data }).then(function (result) {
      toast(result.created + " bidang dibuat, " + result.updated + " diperbarui" + (result.skipped ? ", " + result.skipped + " dilewati" : "") + ".", "ok");
      $("dlg-impor-bidang").close();
      loadPlots();
      ensureLayer("bidang");
    }).catch(function (error) { toast(error.message, "error"); button.disabled = false; });
  });

  // ---------------------------------------------------------------- Tumpang tindih

  var overlapSources = null;
  var overlapResult = null;

  function loadOverlapSources() {
    if (overlapSources) { return; }
    request(urls.overlap).then(function (data) {
      overlapSources = data.sources;
      if (!overlapSources.length) {
        $("tt-hasil").innerHTML = "<p class='muted small'>Belum ada lapisan untuk dianalisis. Administrator dapat mencentang \"Tampil di pusat komando\" pada Lapisan peta referensi.</p>";
        $("tt-jalankan").disabled = true;
        return;
      }
      var items = overlapSources.map(function (s) { return { value: s.key, label: s.name }; });
      fillSelect($("tt-a"), items);
      fillSelect($("tt-b"), items);
      var refs = overlapSources.filter(function (s) { return s.key.indexOf("ref-") === 0; });
      $("tt-a").value = (refs[0] || overlapSources[0]).key;
      $("tt-b").value = (refs[1] || overlapSources.filter(function (s) { return s.key !== $("tt-a").value; })[0] || overlapSources[0]).key;
    }).catch(function (error) { $("tt-hasil").textContent = error.message; });
  }

  function overlapQuery() { return "?a=" + encodeURIComponent($("tt-a").value) + "&b=" + encodeURIComponent($("tt-b").value); }

  $("tt-jalankan").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    $("tt-csv").hidden = true;
    $("tt-hasil").innerHTML = "<p class='muted'>Menghitung…</p>";
    request(urls.overlap + overlapQuery()).then(function (d) {
      overlapResult = d;
      var html = "<div class='metrics four'>" +
        "<div class='metric'><b>" + haText(d.overlap_ha) + "</b><span>Tumpang tindih</span></div>" +
        "<div class='metric'><b>" + pct1(d.pct_a) + "</b><span>dari " + escapeHtml(d.a.name) + " (" + haText(d.a.area_ha) + ")</span></div>" +
        "<div class='metric'><b>" + pct1(d.pct_b) + "</b><span>dari " + escapeHtml(d.b.name) + " (" + haText(d.b.area_ha) + ")</span></div>" +
        "<div class='metric'><b>" + fmtNum(d.pairs.length) + "</b><span>Pasangan objek beririsan</span></div></div>";
      if (d.pairs.length) {
        html += "<div class='row'><button type='button' class='btn' id='tt-peta'>🗺️ Tampilkan irisan di peta</button></div>" +
          "<div class='table-wrap'><table class='table'><thead><tr><th>" + escapeHtml(d.a.name) + "</th><th>" + escapeHtml(d.b.name) + "</th><th>Irisan</th></tr></thead><tbody>" +
          d.pairs.slice(0, 50).map(function (p) { return "<tr><td>" + escapeHtml(p.a) + "</td><td>" + escapeHtml(p.b) + "</td><td>" + haText(p.area_ha) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
          (d.pairs.length > 50 ? "<p class='small muted'>50 irisan terbesar ditampilkan; unduh CSV untuk semuanya.</p>" : "");
      } else {
        html += "<p class='muted small'>Tidak ada irisan antara kedua lapisan.</p>";
      }
      if (d.truncated) { html += "<p class='small muted'>Dibatasi 5.000 irisan terbesar.</p>"; }
      $("tt-hasil").innerHTML = html;
      $("tt-csv").hidden = !d.pairs.length;
    }).catch(function (error) { $("tt-hasil").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>"; })
      .then(function () { button.disabled = false; });
  });
  $("tt-hasil").addEventListener("click", function (event) {
    if (event.target.id !== "tt-peta" || !overlapResult) { return; }
    var shapes = L.geoJSON({ type: "FeatureCollection", features: overlapResult.pairs.map(function (p) {
      return { type: "Feature", geometry: p.geometry, properties: p };
    }) }, {
      style: { color: "#dc2626", weight: 2, fillColor: "#dc2626", fillOpacity: 0.45 },
      onEachFeature: function (f, layer) { layer.bindPopup("<strong>" + escapeHtml(f.properties.a) + "</strong><br>∩ " + escapeHtml(f.properties.b) + "<br>" + haText(f.properties.area_ha)); }
    });
    showAnalysis(shapes, shapes.getBounds());
  });
  $("tt-csv").addEventListener("click", function () { download(urls.overlap + overlapQuery() + "&format=csv", "tumpang-tindih.csv", "CSV tumpang tindih diunduh."); });

  // ---------------------------------------------------------------- Audit RTRW

  var AUDIT_COLORS = { sesuai: "#1a7f37", beda: "#cf222e", belum_dinilai: "#bf8700", tak_dikenali: "#8250df", di_luar: "#57606a", tanpa_lokasi: "#8c959f" };
  var auditResult = null;

  function auditQuery() { return $("au-korwil").value ? "?korwil=" + $("au-korwil").value : ""; }

  $("au-jalankan").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    $("au-csv").hidden = true;
    $("au-hasil").innerHTML = "<p class='muted'>Mengaudit…</p>";
    request(urls.rtrwAudit + auditQuery()).then(function (d) {
      auditResult = d;
      var keys = Object.keys(d.labels);
      var html = d.layers.length
        ? "<p class='small muted'>Lapisan: " + escapeHtml(d.layers.join(", ")) + ". Kesesuaian (dari yang dinilai): <b>" + pctText(d.conform_pct) + "</b></p>"
        : "<p class='small muted'>Belum ada lapisan tata ruang, hutan, atau kawasan proyek yang ditandai tampil di pusat komando; semua warga terhitung di luar lapisan.</p>";
      html += "<div class='stance-cards'>" + keys.map(function (k) {
        return "<div class='stance-card' style='--c:" + AUDIT_COLORS[k] + "'><b>" + fmtNum(d.counts[k]) + "</b><span>" + escapeHtml(d.labels[k]) + "</span></div>";
      }).join("") + "</div>";
      if (d.korwils.length) {
        html += "<h3>Per Korwil</h3><div class='table-wrap'><table class='table'><thead><tr><th>Korwil</th><th>Sesuai</th><th>Tidak sesuai</th><th>Belum dinilai</th><th>Di luar</th></tr></thead><tbody>" +
          d.korwils.map(function (r) { return "<tr><td>" + escapeHtml(r.code) + "</td><td>" + r.sesuai + "</td><td><b style='color:" + AUDIT_COLORS.beda + "'>" + r.beda + "</b></td><td>" + r.belum_dinilai + "</td><td>" + r.di_luar + "</td></tr>"; }).join("") + "</tbody></table></div>";
      }
      var flagged = d.rows.filter(function (r) { return ["beda", "belum_dinilai", "tak_dikenali"].indexOf(r.category) !== -1; });
      html += "<div class='row'><button type='button' class='btn' id='au-peta'>🗺️ Tampilkan hasil di peta</button></div>";
      html += "<h3>Perlu ditindaklanjuti (" + flagged.length + ")</h3><ul class='list compact'>" + (flagged.slice(0, 100).map(function (r) {
        return "<li class='clickable' data-warga='" + r.id + "'><b>" + escapeHtml(r.name) + "</b> <span class='badge' style='background:" + AUDIT_COLORS[r.category] + "'>" + escapeHtml(r.category_label) + "</span>" +
          "<div class='sub'>" + escapeHtml([r.number, "Korwil " + r.korwil, "tercatat: " + r.recorded, r.detected ? "peta: " + r.detected : ""].filter(Boolean).join(" · ")) + "</div></li>";
      }).join("") || "<li class='muted'>Tidak ada.</li>") + "</ul>";
      if (d.truncated) { html += "<p class='small muted'>Audit dibatasi 5.000 warga pertama; pilih Korwil untuk mempersempit.</p>"; }
      $("au-hasil").innerHTML = html;
      $("au-csv").hidden = false;
    }).catch(function (error) { $("au-hasil").innerHTML = "<p class='danger-text'>" + escapeHtml(error.message) + "</p>"; })
      .then(function () { button.disabled = false; });
  });
  $("au-hasil").addEventListener("click", function (event) {
    var resident = event.target.closest("[data-warga]");
    if (resident) { openResident(parseInt(resident.getAttribute("data-warga"), 10)); return; }
    if (event.target.id !== "au-peta" || !auditResult) { return; }
    var group = L.featureGroup(auditResult.rows.filter(function (r) { return r.center; }).map(function (r) {
      return L.circleMarker(r.center, { radius: 6, color: "#fff", weight: 1, fillColor: AUDIT_COLORS[r.category], fillOpacity: 0.95 })
        .bindPopup("<strong>" + escapeHtml(r.name) + "</strong><br>" + escapeHtml(r.category_label) + "<br>Tercatat: " + escapeHtml(r.recorded) + (r.detected ? "<br>Peta: " + escapeHtml(r.detected) : ""));
    }));
    showAnalysis(group, group.getBounds());
  });
  $("au-csv").addEventListener("click", function () { download(urls.rtrwAudit + (auditQuery() ? auditQuery() + "&" : "?") + "format=csv", "audit-rtrw.csv", "CSV audit RTRW diunduh."); });

  // ---------------------------------------------------------------- Peta panas

  function heatColor(t) {
    var stops = [[255, 237, 160], [254, 178, 76], [240, 59, 32], [128, 0, 38]];
    var x = Math.min(Math.max(t, 0), 1) * (stops.length - 1);
    var i = Math.min(Math.floor(x), stops.length - 2);
    var f = x - i;
    return "rgb(" + stops[i].map(function (c, j) { return Math.round(c + (stops[i + 1][j] - c) * f); }).join(",") + ")";
  }

  $("ph-tampil").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    request(urls.heatmap + "?sumber=" + $("ph-sumber").value + "&periode=" + $("ph-periode").value).then(function (d) {
      var half = d.size / 2;
      var group = L.featureGroup(d.cells.map(function (c) {
        var t = d.max > 1 ? 0.3 + 0.7 * Math.log(c[2]) / Math.log(d.max) : 1;
        return L.rectangle([[c[0] - half, c[1] - half], [c[0] + half, c[1] + half]], { color: heatColor(t), weight: 1, opacity: 0.9, fillColor: heatColor(t), fillOpacity: 0.45 + 0.4 * t })
          .bindTooltip(c[2] + " data");
      }));
      $("ph-hasil").textContent = d.cells.length
        ? fmtNum(d.total) + " data di " + fmtNum(d.cells.length) + " sel (terpadat " + d.max + "), " + fmtDate(d.start) + " – " + fmtDate(d.end) + "."
        : "Tidak ada data pada periode ini.";
      if (d.cells.length) { showAnalysis(group, group.getBounds()); }
    }).catch(function (error) { $("ph-hasil").textContent = error.message; })
      .then(function () { button.disabled = false; });
  });

  // ---------------------------------------------------------------- Jejak GPS

  function loadTrackOfficers() {
    if (!perms.jejak) { return; }
    var current = $("jj-petugas").value;
    request(urls.track + "?tanggal=" + $("jj-tanggal").value).then(function (d) {
      fillSelect($("jj-petugas"), d.officers.map(function (o) { return { value: o.id, label: o.name }; }), d.officers.length ? "Pilih petugas…" : "Tidak ada jejak pada tanggal ini");
      if (d.officers.some(function (o) { return String(o.id) === current; })) { $("jj-petugas").value = current; }
    }).catch(function (error) { $("jj-hasil").textContent = error.message; });
  }

  $("jj-tanggal").addEventListener("change", loadTrackOfficers);
  $("jj-tampil").addEventListener("click", function () {
    if (!$("jj-petugas").value) { toast("Pilih petugas terlebih dahulu.", "error"); return; }
    var button = this;
    button.disabled = true;
    request(urls.track + "?tanggal=" + $("jj-tanggal").value + "&petugas=" + $("jj-petugas").value).then(function (d) {
      if (!d.points.length) { $("jj-hasil").textContent = "Tidak ada titik jejak."; return; }
      var latlngs = d.points.map(function (p) { return [p.lat, p.lng]; });
      var group = L.featureGroup([L.polyline(latlngs, { color: "#7c3aed", weight: 4, opacity: 0.85 })]);
      d.points.forEach(function (p, i) {
        if (i === 0 || i === d.points.length - 1) { return; }
        group.addLayer(L.circleMarker([p.lat, p.lng], { radius: 3, color: "#7c3aed", weight: 1, fillOpacity: 0.8 }).bindTooltip(p.time));
      });
      group.addLayer(L.circleMarker(latlngs[0], { radius: 7, color: "#fff", weight: 2, fillColor: "#10b981", fillOpacity: 1 }).bindTooltip("Mulai " + d.points[0].time));
      group.addLayer(L.circleMarker(latlngs[latlngs.length - 1], { radius: 7, color: "#fff", weight: 2, fillColor: "#ef4444", fillOpacity: 1 }).bindTooltip("Akhir " + d.points[d.points.length - 1].time));
      $("jj-hasil").innerHTML = "<b>" + escapeHtml(d.officer.name) + "</b>: " + fmtNum(d.distance_km, 2) + " km, " + d.points.length + " titik, " + escapeHtml(d.start) + "–" + escapeHtml(d.end) + ".";
      showAnalysis(group, group.getBounds());
    }).catch(function (error) { $("jj-hasil").textContent = error.message; })
      .then(function () { button.disabled = false; });
  });

  // ---------------------------------------------------------------- Zona ancaman

  function loadThreatZones() {
    $("za-daftar").innerHTML = "<li class='muted'>Memuat…</li>";
    request(urls.threatZones + ($("za-semua").checked ? "?semua=1" : "")).then(function (d) {
      $("za-daftar").innerHTML = d.zones.map(function (z) {
        return "<li" + (z.active ? "" : " class='inactive'") + "><div class='row' style='justify-content:space-between;gap:8px'><b>" + escapeHtml(z.name) + "</b>" +
          "<span class='badge' style='background:" + escapeHtml(z.color) + "'>" + escapeHtml(z.level_label) + "</span></div>" +
          "<div class='sub'>" + escapeHtml([z.korwil ? "Korwil " + z.korwil : "", haText(z.area_ha), z.by, fmtDate(z.created_at), z.active ? "" : "nonaktif"].filter(Boolean).join(" · ")) + "</div>" +
          (z.note ? "<div class='small'>" + escapeHtml(z.note) + "</div>" : "") +
          "<div class='row'><button type='button' class='btn-small' data-za-fokus='" + z.center.join(",") + "'>📍 Fokus</button>" +
          (z.can_change ? "<button type='button' class='btn-small' data-za-aksi='" + (z.active ? "nonaktif" : "aktif") + "' data-id='" + z.id + "'>" + (z.active ? "Nonaktifkan" : "Aktifkan") + "</button>" : "") +
          (z.can_delete ? "<button type='button' class='btn-small danger' data-za-aksi='hapus' data-id='" + z.id + "'>Hapus</button>" : "") + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada zona ancaman.</li>";
    }).catch(function (error) { $("za-daftar").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  $("za-semua").addEventListener("change", loadThreatZones);
  $("za-daftar").addEventListener("click", function (event) {
    var focus = event.target.closest("[data-za-fokus]");
    if (focus) {
      ensureLayer("ancaman");
      showTab("peta");
      map.setView(focus.getAttribute("data-za-fokus").split(",").map(parseFloat), 15);
      return;
    }
    var button = event.target.closest("[data-za-aksi]");
    if (!button) { return; }
    var action = button.getAttribute("data-za-aksi");
    if (action === "hapus" && !window.confirm("Hapus zona ancaman ini?")) { return; }
    button.disabled = true;
    request(urls.threatZoneAction.replace("/0/", "/" + button.getAttribute("data-id") + "/").replace("__aksi__", action), { method: "POST", body: form({}) }).then(function () {
      toast(action === "hapus" ? "Zona dihapus." : "Zona diperbarui.", "ok");
      loadThreatZones();
      if (layers.ancaman) { loadLayer("ancaman"); }
    }).catch(function (error) { toast(error.message, "error"); button.disabled = false; });
  });
  $("form-ancaman").addEventListener("submit", function (event) {
    event.preventDefault();
    var formEl = this;
    var data = new FormData(formEl);
    var submit = formEl.querySelector("[type=submit]");
    submit.disabled = true;
    reportPoint($("za-titik").checked).then(function (point) {
      if (!point) { throw new ApiError("Lokasi tidak tersedia. Ketuk titik di peta lalu centang \"Pakai titik\".", 0); }
      var fields = { name: data.get("name"), level: data.get("level"), radius: data.get("radius"), korwil: data.get("korwil"), note: data.get("note"), lat: point.lat, lng: point.lng };
      return request(urls.threatZones, { method: "POST", body: form(fields) });
    }).then(function () {
      toast("Zona ancaman disimpan.", "ok");
      formEl.reset();
      $("za-level").value = "sedang";
      loadThreatZones();
      ensureLayer("ancaman");
    }).catch(function (error) { toast(error.message, "error"); })
      .then(function () { submit.disabled = false; });
  });

  // ---------------------------------------------------------------- Foto 360°

  function loadSitePhotos() {
    $("f3-daftar").innerHTML = "<li class='muted'>Memuat…</li>";
    request(urls.sitePhotos).then(function (d) {
      $("f3-daftar").innerHTML = d.photos.map(function (p) {
        return "<li><b>" + escapeHtml(p.title) + "</b><div class='sub'>" + escapeHtml([p.korwil ? "Korwil " + p.korwil : "", p.captured_on ? fmtDate(p.captured_on) : "", p.uploaded_by].filter(Boolean).join(" · ")) + "</div>" +
          (p.note ? "<div class='small'>" + escapeHtml(p.note) + "</div>" : "") +
          "<div class='row'><button type='button' class='btn-small' data-f3-lihat='" + escapeHtml(p.url) + "' data-judul='" + escapeHtml(p.title) + "'>◉ Lihat 360°</button>" +
          "<button type='button' class='btn-small' data-f3-fokus='" + p.lat + "," + p.lng + "'>📍 Fokus</button>" +
          (p.can_delete ? "<button type='button' class='btn-small danger' data-f3-hapus='" + p.id + "'>Hapus</button>" : "") + "</div></li>";
      }).join("") || "<li class='muted'>Belum ada foto 360°.</li>";
    }).catch(function (error) { $("f3-daftar").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  $("f3-daftar").addEventListener("click", function (event) {
    var view = event.target.closest("[data-f3-lihat]");
    if (view) { openPano(view.getAttribute("data-f3-lihat"), view.getAttribute("data-judul")); return; }
    var focus = event.target.closest("[data-f3-fokus]");
    if (focus) {
      ensureLayer("foto360");
      showTab("peta");
      map.setView(focus.getAttribute("data-f3-fokus").split(",").map(parseFloat), 17);
      return;
    }
    var remove = event.target.closest("[data-f3-hapus]");
    if (remove && window.confirm("Hapus foto 360° ini?")) {
      remove.disabled = true;
      request(urls.sitePhotoDelete.replace("/0/", "/" + remove.getAttribute("data-f3-hapus") + "/"), { method: "POST", body: form({}) }).then(function () {
        toast("Foto dihapus.", "ok");
        loadSitePhotos();
        if (layers.foto360) { loadLayer("foto360"); }
      }).catch(function (error) { toast(error.message, "error"); remove.disabled = false; });
    }
  });
  $("form-foto360").addEventListener("submit", function (event) {
    event.preventDefault();
    var formEl = this;
    var data = new FormData(formEl);
    var file = data.get("foto");
    if (!file || !file.size) { toast("Pilih foto 360°.", "error"); return; }
    if (file.size > 20 * 1024 * 1024) { toast("Foto maksimal 20 MB.", "error"); return; }
    var submit = formEl.querySelector("[type=submit]");
    submit.disabled = true;
    reportPoint($("f3-titik").checked).then(function (point) {
      if (!point) { throw new ApiError("Lokasi tidak tersedia. Ketuk titik di peta lalu centang \"Pakai titik\".", 0); }
      data.set("lat", point.lat);
      data.set("lng", point.lng);
      if (!data.get("tanggal")) { data.delete("tanggal"); }
      return request(urls.sitePhotos, { method: "POST", body: data });
    }).then(function () {
      toast("Foto 360° diunggah.", "ok");
      formEl.reset();
      loadSitePhotos();
      ensureLayer("foto360");
    }).catch(function (error) { toast(error.message, "error"); })
      .then(function () { submit.disabled = false; });
  });

  // ---------------------------------------------------------------- Penampil 360°
  // Proyeksi equirectangular → perspektif di kanvas, tanpa pustaka tambahan.

  var pano = { pixels: null, width: 0, height: 0, yaw: 0, pitch: 0, fov: 90, frame: null, drag: null, pinch: null };

  function openPano(url, title) {
    $("v360-judul").textContent = title || "Foto 360°";
    $("v360-asli").href = url;
    var dialog = $("dlg-360");
    if (!dialog.open) { dialog.showModal(); }
    pano.pixels = null;
    pano.yaw = 0; pano.pitch = 0; pano.fov = 90;
    var canvas = $("v360-kanvas");
    var ctx = canvas.getContext("2d");
    sizePano();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#fff";
    ctx.font = "14px sans-serif";
    ctx.fillText("Memuat foto…", 16, 28);
    var image = new Image();
    image.onload = function () {
      // Dibatasi 4096 px agar memori ponsel aman.
      var scale = Math.min(1, 4096 / image.naturalWidth);
      var w = Math.max(1, Math.round(image.naturalWidth * scale));
      var h = Math.max(1, Math.round(image.naturalHeight * scale));
      var source = document.createElement("canvas");
      source.width = w; source.height = h;
      var sctx = source.getContext("2d");
      sctx.drawImage(image, 0, 0, w, h);
      pano.pixels = sctx.getImageData(0, 0, w, h).data;
      pano.width = w; pano.height = h;
      drawPano(false);
    };
    image.onerror = function () { ctx.fillText("Foto tidak dapat dimuat.", 16, 52); };
    image.src = url;
  }

  function sizePano() {
    var canvas = $("v360-kanvas");
    var box = $("v360").getBoundingClientRect();
    canvas.width = Math.max(200, Math.round(box.width));
    canvas.height = Math.max(120, Math.round(box.height));
  }

  function drawPano(fast) {
    if (!pano.pixels) { return; }
    var canvas = $("v360-kanvas");
    var step = fast ? 2 : 1;
    var W = Math.ceil(canvas.width / step), H = Math.ceil(canvas.height / step);
    var ctx = canvas.getContext("2d");
    var out = ctx.createImageData(W, H);
    var data = out.data, src = pano.pixels, sw = pano.width, sh = pano.height;
    var t = Math.tan(pano.fov * Math.PI / 360);
    var cy = Math.cos(pano.yaw), sy = Math.sin(pano.yaw), cp = Math.cos(pano.pitch), sp = Math.sin(pano.pitch);
    var aspect = H / W;
    for (var j = 0; j < H; j += 1) {
      var y = (1 - 2 * (j + 0.5) / H) * t * aspect;
      for (var i = 0; i < W; i += 1) {
        var x = (2 * (i + 0.5) / W - 1) * t;
        var y1 = y * cp + sp, z1 = -y * sp + cp;
        var x2 = x * cy + z1 * sy, z2 = -x * sy + z1 * cy;
        var lon = Math.atan2(x2, z2), lat = Math.atan2(y1, Math.sqrt(x2 * x2 + z2 * z2));
        var u = Math.floor((lon / (2 * Math.PI) + 0.5) * sw) % sw;
        var v = Math.min(sh - 1, Math.max(0, Math.floor((0.5 - lat / Math.PI) * sh)));
        var s = (v * sw + (u < 0 ? u + sw : u)) * 4, d = (j * W + i) * 4;
        data[d] = src[s]; data[d + 1] = src[s + 1]; data[d + 2] = src[s + 2]; data[d + 3] = 255;
      }
    }
    if (step === 1) {
      ctx.putImageData(out, 0, 0);
    } else {
      var tmp = document.createElement("canvas");
      tmp.width = W; tmp.height = H;
      tmp.getContext("2d").putImageData(out, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(tmp, 0, 0, canvas.width, canvas.height);
    }
  }

  function schedulePano(fast) {
    if (pano.frame) { cancelAnimationFrame(pano.frame); }
    pano.frame = requestAnimationFrame(function () { pano.frame = null; drawPano(fast); });
  }

  function turnPano(dx, dy) {
    var canvas = $("v360-kanvas");
    var perPixel = (pano.fov * Math.PI / 180) / Math.max(canvas.width, 1);
    pano.yaw -= dx * perPixel;
    pano.pitch = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, pano.pitch + dy * perPixel));
  }

  function zoomPano(factor) { pano.fov = Math.max(30, Math.min(110, pano.fov * factor)); }

  (function () {
    var box = $("v360");
    var pointers = {};
    box.addEventListener("pointerdown", function (event) {
      box.setPointerCapture(event.pointerId);
      pointers[event.pointerId] = { x: event.clientX, y: event.clientY };
      pano.drag = Object.keys(pointers).length === 1 ? { x: event.clientX, y: event.clientY } : null;
      box.style.cursor = "grabbing";
    });
    box.addEventListener("pointermove", function (event) {
      if (!pointers[event.pointerId]) { return; }
      var ids = Object.keys(pointers);
      if (ids.length === 2) {
        var other = pointers[ids[0] === String(event.pointerId) ? ids[1] : ids[0]];
        var before = Math.hypot(pointers[event.pointerId].x - other.x, pointers[event.pointerId].y - other.y);
        var after = Math.hypot(event.clientX - other.x, event.clientY - other.y);
        if (before > 0 && after > 0) { zoomPano(before / after); }
      } else if (pano.drag) {
        turnPano(event.clientX - pano.drag.x, event.clientY - pano.drag.y);
        pano.drag = { x: event.clientX, y: event.clientY };
      }
      pointers[event.pointerId] = { x: event.clientX, y: event.clientY };
      schedulePano(true);
    });
    function release(event) {
      delete pointers[event.pointerId];
      pano.drag = null;
      box.style.cursor = "";
      schedulePano(false);
    }
    box.addEventListener("pointerup", release);
    box.addEventListener("pointercancel", release);
    box.addEventListener("wheel", function (event) {
      event.preventDefault();
      zoomPano(event.deltaY > 0 ? 1.1 : 0.9);
      schedulePano(false);
    }, { passive: false });
    box.addEventListener("keydown", function (event) {
      var keys = { ArrowLeft: [-40, 0], ArrowRight: [40, 0], ArrowUp: [0, -40], ArrowDown: [0, 40] };
      if (keys[event.key]) {
        event.preventDefault();
        turnPano(keys[event.key][0], keys[event.key][1]);
        schedulePano(false);
      } else if (event.key === "+" || event.key === "-") {
        zoomPano(event.key === "+" ? 0.9 : 1.1);
        schedulePano(false);
      }
    });
    window.addEventListener("resize", function () { if ($("dlg-360").open) { sizePano(); drawPano(false); } });
    $("dlg-360").addEventListener("close", function () { pano.pixels = null; });
  })();


  // ================================================================ Historis

  var historyData = null;
  var historyPart = "komsos";
  var DIRECTION = {
    membaik: { label: "Membaik", color: "#1a7f37" },
    memburuk: { label: "Memburuk", color: "#cf222e" },
    teridentifikasi: { label: "Teridentifikasi", color: "#0b5fcc" },
    lainnya: { label: "Lainnya", color: "#8c959f" }
  };

  function renderHistory() {
    var data = historyData;
    if (!data) { return; }
    var range = "<p class='small muted'>" + fmtDate(data.start) + " – " + fmtDate(data.end) + "</p>";
    var html = "";
    if (historyPart === "komsos") {
      html = range + "<div class='table-wrap'><table class='table'><thead><tr><th>#</th><th>Petugas</th><th>Komsos</th><th>Warga baru</th><th>Berulang</th><th>Warga unik</th></tr></thead><tbody>" +
        (data.komsos.map(function (r) {
          return "<tr><td>" + r.rank + "</td><td>" + escapeHtml(r.user) + "</td><td><b>" + r.activities + "</b></td><td>" + r.new + "</td><td>" + r.repeat + "</td><td>" + r.unique + "</td></tr>";
        }).join("") || "<tr><td colspan='6' class='muted'>Belum ada komsos pada periode ini.</td></tr>") + "</tbody></table></div>" +
        "<p class='small muted'>Warga baru = warga yang pertama kali didata lewat komsos itu; berulang = kunjungan ke warga yang sudah terdata.</p>";
    } else if (historyPart === "sikap") {
      var st = data.stance;
      html = range + "<div class='metrics four'>" + ["membaik", "memburuk", "teridentifikasi", "lainnya"].map(function (key) {
        return "<div class='metric'><b style='color:" + DIRECTION[key].color + "'>" + st.totals[key] + "</b><span>" + DIRECTION[key].label + "</span></div>";
      }).join("") + "</div>";
      if (st.per_korwil.length) {
        html += "<h3>Per Korwil</h3><div class='table-wrap'><table class='table'><thead><tr><th>Korwil</th><th>Membaik</th><th>Memburuk</th><th>Teridentifikasi</th><th>Bersih</th></tr></thead><tbody>" +
          st.per_korwil.map(function (r) {
            return "<tr><td>" + escapeHtml(r.korwil) + "</td><td>" + r.membaik + "</td><td>" + r.memburuk + "</td><td>" + r.teridentifikasi + "</td><td><b style='color:" + (r.net > 0 ? "#1a7f37" : r.net < 0 ? "#cf222e" : "inherit") + "'>" + (r.net > 0 ? "+" : "") + r.net + "</b></td></tr>";
          }).join("") + "</tbody></table></div>";
      }
      html += "<h3>Rincian</h3><ul class='list compact'>" + (st.items.map(function (i) {
        var dir = DIRECTION[i.direction] || DIRECTION.lainnya;
        return "<li class='clickable' data-warga='" + i.resident_id + "'><b>" + escapeHtml(i.resident) + "</b> <span class='badge' style='background:" + dir.color + "'>" + dir.label + "</span>" +
          "<div class='sub'>" + escapeHtml(i.old_label) + " → " + escapeHtml(i.new_label) + (i.korwil ? " · Korwil " + escapeHtml(i.korwil) : "") + " · " + escapeHtml(i.by) + " · " + fmtDate(i.at, true) + "</div></li>";
      }).join("") || "<li class='muted'>Tidak ada perubahan sikap.</li>") + "</ul>";
    } else {
      var land = data.land;
      html = range + "<div class='metrics four'>" +
        "<div class='metric'><b style='color:#1a7f37'>" + land.increased + "</b><span>Bertambah</span></div>" +
        "<div class='metric'><b style='color:#cf222e'>" + land.decreased + "</b><span>Berkurang</span></div>" +
        "<div class='metric'><b>" + (land.net_m2 > 0 ? "+" : "") + fmtNum(land.net_m2, 2) + " m²</b><span>Perubahan bersih</span></div></div>" +
        "<ul class='list compact'>" + (land.items.map(function (i) {
          return "<li class='clickable' data-warga='" + i.resident_id + "'><b>" + escapeHtml(i.resident) + "</b> <b style='color:" + (i.delta >= 0 ? "#1a7f37" : "#cf222e") + "'>" + (i.delta > 0 ? "+" : "") + fmtNum(i.delta, 2) + " m²</b>" +
            "<div class='sub'>" + fmtNum(i.old, 2) + " → " + fmtNum(i.new, 2) + " m²" + (i.korwil ? " · Korwil " + escapeHtml(i.korwil) : "") + " · " + escapeHtml(i.by) + " · " + fmtDate(i.at, true) + "</div></li>";
        }).join("") || "<li class='muted'>Tidak ada perubahan luas lahan.</li>") + "</ul>";
    }
    $("historis-isi").innerHTML = html;
  }

  function loadHistory() {
    if ($("historis-korwil").options.length <= 1) {
      fillSelect($("historis-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code }; }), "Semua Korwil");
    }
    var params = "?periode=" + $("historis-periode").value + ($("historis-korwil").value ? "&korwil=" + $("historis-korwil").value : "");
    $("historis-isi").innerHTML = "<p class='muted'>Memuat…</p>";
    request(urls.history + params).then(function (data) { historyData = data; renderHistory(); })
      .catch(function (error) { $("historis-isi").textContent = error.message; });
  }

  $("historis-periode").addEventListener("change", loadHistory);
  $("historis-korwil").addEventListener("change", loadHistory);
  $("historis-bagian").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-bagian]");
    if (!button) { return; }
    historyPart = button.getAttribute("data-bagian");
    this.querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b === button); });
    renderHistory();
  });
  $("historis-isi").addEventListener("click", function (event) {
    var resident = event.target.closest("[data-warga]");
    if (resident) { openResident(parseInt(resident.getAttribute("data-warga"), 10)); }
  });

  function loadFeed() {
    var korwil = $("feed-korwil").value;
    request(urls.feed + (korwil ? "?korwil=" + korwil : "")).then(function (data) {
      var ICON = { kegiatan: "📝", tanah: "🧪", sikap: "🔄", sos: "🆘" };
      $("feed-isi").innerHTML = data.results.map(function (item) {
        return "<li><b>" + (ICON[item.kind] || "•") + " " + escapeHtml(item.title) + "</b>" +
          "<br><span class='muted small'>Korwil " + escapeHtml(item.korwil || "—") + " · " + escapeHtml(item.by) + " · " + fmtDate(item.at, true) + "</span></li>";
      }).join("") || "<li class='muted'>Belum ada aktivitas.</li>";
    }).catch(function (error) { $("feed-isi").innerHTML = "<li class='muted'>" + escapeHtml(error.message) + "</li>"; });
  }

  $("feed-korwil").addEventListener("change", loadFeed);

  $("form-ai").addEventListener("submit", function (event) {
    event.preventDefault();
    var input = $("ai-teks");
    var question = (input.value || "").trim();
    if (!question) { return; }
    var list = $("ai-pesan");
    list.insertAdjacentHTML("beforeend", "<li><b>Anda:</b> " + escapeHtml(question) + "</li>");
    input.value = "";
    list.insertAdjacentHTML("beforeend", "<li id='ai-loading' class='muted'>Menyusun jawaban…</li>");
    request(urls.aiChat, { method: "POST", body: form({ tanya: question }) }).then(function (data) {
      var loading = $("ai-loading"); if (loading) { loading.remove(); }
      list.insertAdjacentHTML("beforeend", "<li><b>🤖</b> " + escapeHtml(data.answer).replace(/\n/g, "<br>") + "</li>");
      list.scrollTop = list.scrollHeight;
    }).catch(function (error) {
      var loading = $("ai-loading"); if (loading) { loading.remove(); }
      list.insertAdjacentHTML("beforeend", "<li class='muted'>" + escapeHtml(error.message) + "</li>");
    });
  });
  $("kinerja-tim-isi").addEventListener("click", function (event) {
    var row = event.target.closest("[data-petugas]");
    if (row) { openPerformance(row.getAttribute("data-petugas")); }
  });

  // ================================================================ Chat

  var chatChannel = store("kanal") || "umum";
  var chatLastId = 0;
  var chatSeen = store("chatTerbaca") || {};

  function renderMessages(messages, append) {
    var list = $("chat-pesan");
    var html = messages.map(function (m) {
      return "<li class='" + (m.mine ? "mine" : "") + (m.system ? " system" : "") + "'><div class='who'>" + escapeHtml(m.sender) + "</div>" +
        escapeHtml(m.body) + (m.lat !== null ? " <button type='button' class='btn-small' data-lihat='" + m.lat + "," + m.lng + "'>📍 lokasi</button>" : "") +
        "<div class='when'>" + fmtDate(m.at, true) + "</div></li>";
    }).join("");
    if (append) { list.insertAdjacentHTML("beforeend", html); } else { list.innerHTML = html || "<li class='system'>Belum ada pesan.</li>"; }
    if (messages.length) { chatLastId = messages[messages.length - 1].id; }
    list.scrollTop = list.scrollHeight;
  }

  function loadChat(reset) {
    if (!perms.chat || !navigator.onLine) { return; }
    var url = urls.chat + "?kanal=" + encodeURIComponent(chatChannel) + (!reset && chatLastId ? "&setelah=" + chatLastId : "");
    request(url).then(function (data) {
      renderMessages(data.results, !reset);
      if (currentTab === "chat") {
        chatSeen[chatChannel] = chatLastId;
        store("chatTerbaca", chatSeen);
        $("chat-dot").hidden = true;
        $("tab-chat-dot").hidden = true;
      } else if (data.results.some(function (m) { return !m.mine && m.id > (chatSeen[chatChannel] || 0); })) {
        $("chat-dot").hidden = false;
        $("tab-chat-dot").hidden = false;
      }
    }).catch(function () {});
  }

  $("chat-kanal").addEventListener("change", function () {
    chatChannel = this.value;
    store("kanal", chatChannel);
    chatLastId = 0;
    loadChat(true);
  });
  $("chat-pesan").addEventListener("click", flyFromButton);
  $("form-chat").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!perms.kirimChat) { toast("Anda tidak berhak mengirim pesan.", "error"); return; }
    var text = $("chat-teks").value.trim();
    if (!text) { return; }
    var ready = $("chat-lokasi").checked ? currentPosition(8000) : Promise.resolve(null);
    ready.then(function (fix) {
      return request(urls.chat, { method: "POST", body: form({ pesan: text, kanal: chatChannel, lat: fix && fix.lat, lng: fix && fix.lng }) });
    }).then(function () {
      $("chat-teks").value = "";
      $("chat-lokasi").checked = false;
      loadChat(false);
    }).catch(function (error) { toast(error.message, "error"); });
  });

  // ================================================================ SOS

  var knownSos = {};
  var sosCollapsed = false;

  function beep() {
    try {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      var audio = new Ctx();
      [0, 0.35, 0.7].forEach(function (offset) {
        var osc = audio.createOscillator();
        var gain = audio.createGain();
        osc.frequency.value = 880;
        osc.connect(gain);
        gain.connect(audio.destination);
        gain.gain.setValueAtTime(0.25, audio.currentTime + offset);
        osc.start(audio.currentTime + offset);
        osc.stop(audio.currentTime + offset + 0.2);
      });
    } catch (e) { /* audio diblokir sebelum interaksi */ }
    var activated = !navigator.userActivation || navigator.userActivation.hasBeenActive;
    if (navigator.vibrate && activated) { navigator.vibrate([300, 150, 300, 150, 300]); }
  }

  // Ruang kosong di bawah lembar menu HP agar isi terakhir tidak tertutup daftar SOS.
  function syncSosSpace() {
    document.documentElement.style.setProperty("--sos-h", $("sos-daftar").offsetHeight + "px");
  }

  function loadSos() {
    if (!perms.lihatSos || !navigator.onLine) { return; }
    request(urls.sos).then(function (data) {
      var fresh = false;
      var html = data.results.map(function (s) {
        if (!knownSos[s.id] && s.status === "aktif" && !s.mine) { fresh = true; }
        knownSos[s.id] = true;
        return "<div class='sos-item " + escapeHtml(s.status) + "'><b>🆘 " + escapeHtml(s.number) + " · " + escapeHtml(s.by) + (s.korwil ? " (Korwil " + escapeHtml(s.korwil) + ")" : "") + "</b><br>" +
          escapeHtml(s.status_label) + (s.handler ? " oleh " + escapeHtml(s.handler) : "") + " · " + fmtDate(s.at, true) + (s.message ? "<br>" + escapeHtml(s.message) : "") +
          "<div class='row'>" + (s.lat !== null ? "<button type='button' class='btn-small' data-lihat='" + s.lat + "," + s.lng + "'>📍 Lihat</button>" : "") +
          (perms.tanganiSos && s.status === "aktif" ? "<button type='button' class='btn-small' data-sos='" + s.id + "' data-aksi='tangani'>Tangani</button>" : "") +
          (perms.tanganiSos || s.mine ? "<button type='button' class='btn-small' data-sos='" + s.id + "' data-aksi='selesai'>Selesai</button><button type='button' class='btn-small' data-sos='" + s.id + "' data-aksi='palsu'>Alarm palsu</button>" : "") +
          "</div></div>";
      }).join("");
      if (fresh) { sosCollapsed = false; }
      var head = "<div class='sos-head'><b>🆘 " + data.results.length + " SOS aktif</b><button type='button' class='btn-small' data-ciutkan='1'>" +
        (sosCollapsed ? "Tampilkan" : "Sembunyikan") + "</button></div>";
      $("sos-daftar").innerHTML = head + (sosCollapsed ? "" : html);
      $("sos-daftar").classList.toggle("collapsed", sosCollapsed);
      $("sos-daftar").hidden = !data.results.length;
      syncSosSpace();
      if (fresh) { beep(); loadLayer("sos"); }
    }).catch(function () {});
  }

  $("sos-daftar").addEventListener("click", function (event) {
    if (event.target.getAttribute("data-ciutkan")) { sosCollapsed = !sosCollapsed; loadSos(); return; }
    flyFromButton(event);
    var id = event.target.getAttribute("data-sos");
    if (!id) { return; }
    var action = event.target.getAttribute("data-aksi");
    var note = action === "tangani" ? "" : window.prompt("Catatan penanganan (opsional):", "") || "";
    request(urls.sosAction.replace("/0/", "/" + id + "/").replace("__aksi__", action), { method: "POST", body: form({ catatan: note }) })
      .then(function () { toast("SOS diperbarui.", "ok"); loadSos(); loadLayer("sos"); })
      .catch(function (error) { toast(error.message, "error"); });
  });

  $("sos-tombol").addEventListener("click", function () {
    if (!perms.sos) { toast("Akun Anda tidak dapat mengirim SOS.", "error"); return; }
    $("sos-pesan").value = "";
    $("dlg-sos").showModal();
  });
  $("sos-kirim").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    currentPosition(8000).then(function (fix) {
      var fields = { pesan: $("sos-pesan").value.trim() };
      if (fix) { fields.lat = fix.lat; fields.lng = fix.lng; fields.accuracy = fix.accuracy; }
      return enqueue(urls.sos, "🆘 SOS " + fmtDate(new Date().toISOString(), true), fields, []);
    }).then(function () {
      $("dlg-sos").close();
      button.disabled = false;
      toast(navigator.onLine ? "SOS dikirim. Tetap di lokasi aman bila memungkinkan." : "Tanpa sinyal: SOS disimpan dan dikirim begitu ada sinyal. Coba telepon darurat 112.", navigator.onLine ? "ok" : "error");
      sync(true).then(loadSos);
    }).catch(function (error) { button.disabled = false; toast(error.message, "error"); });
  });

  // ================================================================ Pencarian & perintah

  var COMMANDS = [
    { label: "Absen masuk", words: ["absen masuk"], run: function () { showTab("absen"); doAttendance("masuk"); } },
    { label: "Absen pulang", words: ["absen pulang"], run: function () { showTab("absen"); doAttendance("pulang"); } },
    { label: "Buka absen", words: ["absen"], run: function () { showTab("absen"); } },
    { label: "Lapor kegiatan", words: ["lapor", "kegiatan"], run: function () { showTab("korwil"); } },
    { label: "Uji tanah", words: ["uji tanah", "tanah"], run: function () { showTab("korwil"); document.querySelector('[data-sub="tanah"]').click(); } },
    { label: "Data warga", words: ["warga"], run: function () { showTab("warga"); } },
    { label: "Tugas saya", words: ["tugas"], run: function () { showTab("tasks"); } },
    { label: "Kinerja saya", words: ["kinerja", "performa", "kpi"], run: function () { showTab("perf"); } },
    { label: "Buka chat", words: ["chat", "pesan"], run: function () { showTab("chat"); } },
    { label: "Citra satelit / peta biasa", words: ["satelit", "peta biasa"], run: function () { runTool("satellite"); } },
    { label: "Lokasi saya", words: ["lokasi saya", "posisi saya", "di mana saya"], run: function () { runTool("locate"); } },
    { label: "Perbesar peta", words: ["perbesar", "zoom masuk", "zoom in"], run: function () { map.zoomIn(); } },
    { label: "Perkecil peta", words: ["perkecil", "zoom keluar", "zoom out"], run: function () { map.zoomOut(); } },
    { label: "Ukur jarak", words: ["ukur"], run: function () { runTool("measure"); } },
    { label: "AI Satelit", words: ["ai satelit", "analisis area"], run: function () { runTool("ai"); } },
    { label: "Cetak / export peta", words: ["cetak", "print", "export"], run: function () { runTool("print"); } },
    { label: "Mode Live", words: ["live", "lacak"], run: function () { $("live").click(); } },
    { label: "Legenda & lapisan", words: ["legenda", "lapisan"], run: function () { runTool("legend"); } },
    { label: "Layar penuh", words: ["layar penuh", "fullscreen"], run: function () { toggleFullscreen(); } },
    { label: "Kirim SOS", words: ["sos", "darurat", "tolong"], run: function () { $("sos-tombol").click(); } },
    { label: "Muat ulang data", words: ["muat ulang", "refresh"], run: function () { reloadData(); } },
    { label: "Panel petugas (admin)", words: ["panel admin"], run: function () { window.location.href = urls.admin; } }
  ];

  var searchItems = [];
  var searchIndex = 0;
  var searchTimer = null;

  function openSearch(text) {
    var dialog = $("dlg-cari");
    if (!dialog.open) { dialog.showModal(); }
    $("cari-teks").value = text || "";
    $("power-mode").checked = !!store("powerMode");
    $("cari-teks").focus();
    updateSearch();
  }

  function renderSearch() {
    $("cari-hasil").innerHTML = searchItems.map(function (item, index) {
      return "<li role='option' data-index='" + index + "' class='" + (index === searchIndex ? "active" : "") + "'><span class='kind'>" + escapeHtml(item.kind) + "</span><div><div>" +
        escapeHtml(item.label) + "</div><div class='small muted'>" + escapeHtml(item.sub || "") + "</div></div></li>";
    }).join("") || "<li class='muted'>Ketik untuk mencari. Awali dengan &gt; untuk perintah.</li>";
    var active = $("cari-hasil").querySelector("li.active");
    if (active) { active.scrollIntoView({ block: "nearest" }); }
  }

  function updateSearch() {
    var text = $("cari-teks").value.trim();
    var power = $("power-mode").checked || text.charAt(0) === ">";
    var query = text.replace(/^>\s*/, "").toLowerCase();
    var commands = power ? COMMANDS.filter(function (c) {
      return !query || c.label.toLowerCase().indexOf(query) !== -1 || c.words.some(function (w) { return w.indexOf(query) !== -1; });
    }).map(function (c) { return { kind: "perintah", label: c.label, run: c.run }; }) : [];
    var korwils = query ? config.korwils.filter(function (k) {
      return k.code.toLowerCase() === query.replace("korwil ", "") || k.name.toLowerCase().indexOf(query) !== -1;
    }).map(function (k) { return { kind: "korwil", label: "Korwil " + k.code + " – " + k.name, id: k.id, local: true }; }) : [];
    searchItems = commands.concat(korwils);
    searchIndex = 0;
    renderSearch();
    clearTimeout(searchTimer);
    if (text.charAt(0) === ">" || query.length < 2 || !navigator.onLine) { return; }
    searchTimer = setTimeout(function () {
      request(urls.search + "?q=" + encodeURIComponent(query)).then(function (data) {
        if ($("cari-teks").value.trim().toLowerCase().replace(/^>\s*/, "") !== query) { return; }
        var remote = data.results.filter(function (r) { return r.kind !== "korwil"; });
        searchItems = commands.concat(korwils, remote);
        renderSearch();
      }).catch(function () {});
    }, 250);
  }

  function chooseSearch(item) {
    $("dlg-cari").close();
    if (!item) { return; }
    if (item.run) { item.run(); return; }
    if (item.kind === "korwil") { focusKorwil(item.id); return; }
    if (item.kind === "warga") { openResident(item.id); }
    if (item.kind === "tugas") { showTab("tasks"); return; }
    if (item.bounds) {
      showTab("peta");
      map.fitBounds(item.bounds, { padding: [30, 30], maxZoom: 18 });
    } else if (item.lat !== undefined) {
      if (item.kind !== "warga") { showTab("peta"); }
      map.setView([item.lat, item.lng], 18);
      L.popup().setLatLng([item.lat, item.lng]).setContent("<b>" + escapeHtml(item.label) + "</b><br>" + escapeHtml(item.sub || "")).openOn(map);
    }
  }

  $("cari-teks").addEventListener("input", updateSearch);
  $("power-mode").addEventListener("change", function () { store("powerMode", this.checked); updateSearch(); $("cari-teks").focus(); });
  $("cari-teks").addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown") { event.preventDefault(); searchIndex = Math.min(searchIndex + 1, searchItems.length - 1); renderSearch(); }
    else if (event.key === "ArrowUp") { event.preventDefault(); searchIndex = Math.max(searchIndex - 1, 0); renderSearch(); }
    else if (event.key === "Enter") { event.preventDefault(); chooseSearch(searchItems[searchIndex]); }
  });
  $("cari-hasil").addEventListener("click", function (event) {
    var li = event.target.closest("li[data-index]");
    if (li) { chooseSearch(searchItems[parseInt(li.getAttribute("data-index"), 10)]); }
  });
  document.addEventListener("keydown", function (event) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openSearch(); }
    else if (event.key === "/" && !typing && !document.querySelector("dialog[open]")) { event.preventDefault(); openSearch(); }
    else if (event.key === "Escape") {
      var openDialog = document.querySelector("dialog[open]");
      if (openDialog) { event.preventDefault(); openDialog.close(); }
      else if (toolMode === "measure") { $("ukur-tutup").click(); }
      else if (toolMode === "ai") { $("ai-batal").click(); }
    }
  });
  // Klik di luar dialog menutupnya.
  document.querySelectorAll("dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (event) { if (event.target === dialog) { dialog.close(); } });
  });

  // ================================================================ Kunci sistem

  function startLockBanner() {
    var lock = config.lock;
    if (!lock.armed) { return; }
    var target = new Date(lock.shutdown_at);
    $("kunci-banner").hidden = false;
    $("kunci-waktu").textContent = fmtDate(lock.shutdown_at, true);
    $("kunci-buka").hidden = !lock.canDefuse;
    var tick = function () {
      var left = Math.max(0, target.getTime() - Date.now());
      var s = Math.floor(left / 1000);
      var pad = function (n) { return ("0" + n).slice(-2); };
      $("kunci-hitung").textContent = Math.floor(s / 86400) + ":" + pad(Math.floor(s / 3600) % 24) + ":" + pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60);
      if (left <= 0 && !lock.canDefuse) { window.location.reload(); }
    };
    tick();
    setInterval(tick, 1000);
  }

  $("kunci-buka").addEventListener("click", function () { $("kunci-pesan").textContent = ""; $("kunci-kode").value = ""; $("dlg-kunci").showModal(); });
  $("form-kunci").addEventListener("submit", function (event) {
    if (event.submitter && event.submitter.value === "batal") { return; }
    event.preventDefault();
    $("kunci-kirim").click();
  });
  $("kunci-kirim").addEventListener("click", function () {
    request(urls.lock, { method: "POST", body: form({ passcode: $("kunci-kode").value }) }).then(function () {
      $("dlg-kunci").close();
      $("kunci-banner").hidden = true;
      config.lock.armed = false;
      toast("Kunci sistem dinonaktifkan.", "ok");
    }).catch(function (error) { $("kunci-pesan").textContent = error.message; });
  });

  // ================================================================ Status jaringan, PWA & pemuatan

  function updateNetwork() {
    var el = $("net");
    el.textContent = navigator.onLine ? "Daring" : "Luring";
    el.className = "pill " + (navigator.onLine ? "ok" : "off");
    if (navigator.onLine) { sync(true); }
  }
  window.addEventListener("online", updateNetwork);
  window.addEventListener("offline", updateNetwork);

  var installPrompt = null;
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    installPrompt = event;
    $("pasang").hidden = false;
  });
  $("pasang").addEventListener("click", function () {
    if (!installPrompt) { return; }
    installPrompt.prompt();
    installPrompt.userChoice.finally(function () { installPrompt = null; $("pasang").hidden = true; });
  });

  $("keluar").addEventListener("click", function () {
    myQueue().catch(function () { return []; }).then(function (items) {
      if (items.length && !window.confirm(items.length + " laporan di antrean belum terkirim dan akan dihapus dari perangkat. Tetap keluar?")) { return; }
      Promise.all([purgeOfflineData(true), queueClear()]).then(function () {
        // Keluar di sini juga mengakhiri aplikasi utama di perangkat ini: token
        // tersimpannya dikirim untuk dicabut lalu dihapus.
        var mainToken = "";
        try {
          mainToken = localStorage.getItem(MAIN_REFRESH_TOKEN_KEY) || "";
          localStorage.removeItem(STORAGE_PREFIX + "pengguna");
          localStorage.removeItem(MAIN_REFRESH_TOKEN_KEY);
        } catch (e) { /* abaikan */ }
        var logout = document.createElement("form");
        logout.method = "post";
        logout.action = urls.logout;
        [["csrfmiddlewaretoken", csrf()], ["refresh", mainToken]].forEach(function (pair) {
          var input = document.createElement("input");
          input.type = "hidden";
          input.name = pair[0];
          input.value = pair[1];
          logout.appendChild(input);
        });
        document.body.appendChild(logout);
        logout.submit();
      });
    });
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(urls.serviceWorker, { scope: urls.scope }).catch(function () { /* HTTP biasa / mode privat */ });
  }

  function reloadData() {
    loadSummary();
    LAYER_SPECS.forEach(function (spec) { if (layerState[spec.key] || spec.key === "korwil") { loadLayer(spec.key); } });
    if (currentTab === "korwil") { loadMyReports(); }
  }

  function init() {
    fillSelect($("kg-jenis"), config.choices.activityType);
    fillSelect($("ti-aktivitas"), config.choices.illegalKind);
    // "Belum diketahui" di depan supaya warga baru tidak otomatis tercatat "Tempatan".
    var residency = config.choices.residency.filter(function (c) { return !c.value; }).concat(config.choices.residency.filter(function (c) { return c.value; }));
    document.querySelectorAll(".pilih-residency").forEach(function (s) { fillSelect(s, residency); });
    document.querySelectorAll(".pilih-permit").forEach(function (s) { fillSelect(s, config.choices.permit); });
    document.querySelectorAll(".pilih-business").forEach(function (s) { fillSelect(s, config.choices.business); });
    document.querySelectorAll(".pilih-patrol-input").forEach(function (s) { fillSelect(s, config.choices.patrolInput); });
    document.querySelectorAll(".pilih-situation").forEach(function (s) { fillSelect(s, config.choices.situation); });
    document.querySelectorAll(".pilih-personnel").forEach(function (s) { fillSelect(s, config.choices.personnel); });
    document.querySelectorAll(".pilih-materiel").forEach(function (s) { fillSelect(s, config.choices.materiel); });
    document.querySelectorAll(".pilih-weather").forEach(function (s) { fillSelect(s, config.choices.weather); });
    document.querySelectorAll(".pilih-impact-scope").forEach(function (s) { fillSelect(s, config.choices.impactScope, "— pilih —"); });
    document.querySelectorAll(".pilih-impact-risk").forEach(function (s) { fillSelect(s, config.choices.impactRisk, "— pilih —"); });
    document.querySelectorAll(".pilih-impact-result").forEach(function (s) { fillSelect(s, config.choices.impactResult, "— pilih —"); });
    renderRoutes();
    document.querySelector('#ti-mode [data-ti-mode="baru"]').hidden = !perms.tambahTemuan;
    document.querySelector('#ti-mode [data-ti-mode="berulang"]').hidden = !perms.temuan;
    fillSelect($("kg-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code + " – " + k.name }; }), "Otomatis dari lokasi");
    if (config.myKorwils.length === 1) { $("kg-korwil").value = String(config.myKorwils[0]); }
    fillSelect($("tn-tekstur"), config.choices.texture, "—");
    fillSelect($("tn-kelayakan"), config.choices.suitability);
    $("tn-kelayakan").value = "belum";
    fillSelect($("izin-jenis"), config.choices.leave);
    fillSelect($("warga-korwil"), config.korwils.map(function (k) { return { value: k.id, label: "Korwil " + k.code }; }), "Semua Korwil");
    fillSelect($("warga-sikap"), config.choices.stance, "Semua sikap");
    document.querySelectorAll(".pilih-sikap").forEach(function (s) { fillSelect(s, config.choices.stance); s.value = "belum"; });
    document.querySelectorAll(".pilih-lahan").forEach(function (s) { fillSelect(s, config.choices.land); });
    document.querySelectorAll(".pilih-rtrw").forEach(function (s) { fillSelect(s, config.choices.rtrw); s.value = "belum"; });
    document.querySelectorAll(".pilih-zona").forEach(function (s) { fillSelect(s, config.choices.zone); s.value = "belum"; });
    document.querySelectorAll(".pilih-relokasi").forEach(function (s) { fillSelect(s, config.choices.relocation); });
    document.querySelectorAll(".pilih-gender").forEach(function (s) { fillSelect(s, config.choices.gender); });
    document.querySelectorAll(".pilih-penggarapan").forEach(function (s) { fillSelect(s, config.choices.cultivation); });
    $("chat-kanal").innerHTML = '<option value="umum">Kanal umum</option>' + config.korwils.map(function (k) {
      return '<option value="' + k.id + '">Korwil ' + escapeHtml(k.code) + "</option>";
    }).join("");
    $("chat-kanal").value = config.korwils.some(function (k) { return String(k.id) === String(chatChannel); }) ? chatChannel : "umum";
    chatChannel = $("chat-kanal").value;
    $("kg-waktu").value = localInputValue();
    resetTypeParts();
    $("foto-wajib").textContent = config.settings.requirePhoto ? "(wajib)" : "(opsional)";
    $("form-chat").hidden = !perms.kirimChat;
    $("sos-tombol").hidden = !perms.sos;
    document.querySelector('[data-tool="ai"]').hidden = !perms.aiSatelit;
    setTactical(store("taktis") === true);
    renderLayerList();
    renderLegend();
    updateNetwork();
    startLockBanner();
    startGps();
    reloadData();
    refreshQueue();
    loadSos();
    loadChat(true);
    setInterval(loadSummary, 60000);
    loadBadges();
    setInterval(loadBadges, 60000);
    setInterval(loadSos, 20000);
    setInterval(function () { loadChat(false); }, 10000);
    setInterval(function () { if (layerState.petugas) { loadLayer("petugas"); } }, 30000);
    setInterval(function () { if (layerState.sos) { loadLayer("sos"); } }, 30000);
    setInterval(function () { sync(true); }, 45000);
    setInterval(function () { if (navigator.onLine) { loadLayer("korwil"); loadLayer("warga"); } }, 300000);
    applyTabPermissions();
    showTab(config.initialTab);
  }

  init();
})();
