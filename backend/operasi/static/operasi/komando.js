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

  function enqueue(url, label, fields, files) {
    var item = {
      client_id: fields.client_id || uuid(),
      url: url,
      label: label,
      fields: fields,
      files: files || [],
      created_at: new Date().toISOString(),
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
    return queueAll().then(function (items) {
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
    return queueAll().then(function (items) {
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
    { key: "sos", name: "SOS aktif", perm: perms.lihatSos }
  ].filter(function (spec) { return spec.perm; });

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
    if (modes.korwil === "color") { return props.color || "#10b981"; }
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
    if (props.url) { html += '<br><a href="' + encodeURI(props.url) + '" target="_blank" rel="noopener">Buka data</a>'; }
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
    return L.geoJSON(data, {
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
    if (layerState.kegiatan) {
      Object.keys(config.colors.activity).forEach(function (key) {
        entries.push({ color: config.colors.activity[key], label: "Kegiatan: " + choiceLabel("activityType", key), round: true });
      });
    }
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
    var button = event.popup.getElement().querySelector("[data-warga]");
    if (button) { button.addEventListener("click", function () { openResident(parseInt(button.getAttribute("data-warga"), 10)); }); }
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
    aiRect = L.rectangle([aiStart, aiStart], { color: "#10b981", weight: 2, dashArray: "4 4", fillOpacity: 0.1 }).addTo(map);
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
    ctx.fillStyle = "#0a0f1a";
    ctx.fillRect(0, 0, width, header);
    ctx.fillRect(0, height - footer, width, footer);
    ctx.fillStyle = "#10b981";
    ctx.font = "bold " + Math.round(30 * unit) + "px sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(config.appName + " · Peta " + (korwil ? "Korwil " + korwil.code + " – " + korwil.name : "Seluruh Korwil"), 24 * unit, header / 2);
    ctx.textAlign = "right";
    ctx.fillStyle = "#e6edf3";
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
    ctx.fillStyle = "#fff";
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
      ctx.fillStyle = "#e6edf3";
      ctx.fillText(fitText(ctx, entry.label, textWidth, unit), ex + 20 * unit, ey);
    });
    ctx.fillStyle = "#8b949e";
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
    var dirs = ["U", "TL", "T", "TG", "S", "BD", "B", "BL"];
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
      liveMarker = L.circleMarker(latlng, { radius: 9, color: "#fff", weight: 3, fillColor: "#10b981", fillOpacity: 1 }).addTo(map);
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
  function showTab(name) {
    currentTab = name;
    document.querySelectorAll(".tab-view").forEach(function (view) {
      if (view.id === "tab-peta") { return; }
      view.hidden = view.id !== "tab-" + name;
    });
    document.querySelectorAll(".tabbar button").forEach(function (button) {
      button.classList.toggle("active", button.getAttribute("data-tab") === name);
    });
    if (name === "absen") { loadAttendance(); }
    if (name === "korwil") { loadMyReports(); loadTaskOptions(); }
    if (name === "warga") { loadResidents(); }
    if (name === "tasks") { loadTasks(); }
    if (name === "perf") { loadPerformance(); }
    if (name === "chat") { loadChat(true); }
    setTimeout(function () { map.invalidateSize(); }, 50);
  }

  document.querySelector(".tabbar").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-tab]");
    if (button) { showTab(button.getAttribute("data-tab")); }
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
      toast("Pengajuan tersimpan.", "ok");
      event.target.reset();
      loadAttendance();
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

  function reportPoint(useTap) {
    if (useTap) {
      if (!tappedPoint) { return Promise.reject(new ApiError("Ketuk titik di peta terlebih dahulu.", 0)); }
      return Promise.resolve({ lat: tappedPoint.lat, lng: tappedPoint.lng, accuracy: "" });
    }
    return currentPosition(10000);
  }

  $("form-kegiatan").addEventListener("submit", function (event) {
    event.preventDefault();
    if (!perms.lapor) { toast("Anda tidak berhak melapor kegiatan.", "error"); return; }
    var formEl = this;
    var data = new FormData(formEl);
    var fields = {
      jenis: data.get("jenis"), judul: (data.get("judul") || "").trim(), uraian: data.get("uraian"),
      waktu: data.get("waktu") ? new Date(data.get("waktu")).toISOString() : new Date().toISOString(),
      durasi: data.get("durasi"), peserta: data.get("peserta"), hasil: data.get("hasil"),
      korwil: data.get("korwil"), tugas: data.get("tugas"),
      warga: Object.keys(chosenResidents).join(",")
    };
    var stances = {};
    Object.keys(chosenResidents).forEach(function (id) { if (chosenResidents[id].newStance) { stances[id] = chosenResidents[id].newStance; } });
    if (Object.keys(stances).length) { fields.sikap = JSON.stringify(stances); }
    if (!fields.judul) { toast("Judul wajib diisi.", "error"); return; }
    reportPoint($("kg-titik").checked).then(function (point) {
      if (point) { fields.lat = point.lat; fields.lng = point.lng; fields.accuracy = point.accuracy; }
      return photoFiles(formEl.querySelector('[name="foto"]'), "foto", 5);
    }).then(function (files) {
      return enqueue(urls.activities, "Kegiatan: " + fields.judul, fields, files);
    }).then(function () {
      formEl.reset();
      chosenResidents = {};
      renderChosen();
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

  document.querySelectorAll(".segmented button").forEach(function (button) {
    button.addEventListener("click", function () {
      var sub = button.getAttribute("data-sub");
      document.querySelectorAll(".segmented button").forEach(function (b) { b.classList.toggle("active", b === button); });
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
        return "<li><div class='title'>" + escapeHtml(a.title) + (a.verified ? " ✅" : "") + "</div><div class='sub'>" + escapeHtml(a.number + " · " + a.type_label + " · " + fmtDate(a.started_at, true) +
          (a.korwil ? " · Korwil " + a.korwil : "") + " · " + a.reporter) + "</div>" +
          (a.photos.length ? "<div class='row wrap'>" + a.photos.map(function (url) { return "<a href='" + escapeHtml(url) + "' target='_blank' rel='noopener'>📷</a>"; }).join(" ") + "</div>" : "") +
          (perms.verifikasi && !a.verified ? "<div class='row'><button type='button' class='btn-small' data-verifikasi='" + a.id + "'>Verifikasi</button></div>" : "") +
          (a.lat !== null ? "<div class='row'><button type='button' class='btn-small' data-lihat='" + a.lat + "," + a.lng + "'>Lihat di peta</button></div>" : "") + "</li>";
      }).join("") || "<li class='muted'>Belum ada laporan.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }
  $("riwayat-lingkup").addEventListener("change", loadMyReports);
  $("daftar-kegiatan").addEventListener("click", function (event) {
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
        "<label class='field'>Pilihan " + selectHtml("pilihan", "relocation", r.relocation) + "</label>" +
        "<label class='field'>Catatan baru <input name='catatan' maxlength='2000'></label></div>" +
        "<div class='row wrap'><button type='button' class='btn primary' id='wd-simpan'>Simpan</button>" +
        "<button type='button' class='btn' id='wd-gps'>📍 Set lokasi dari GPS</button></div>";
    } else {
      html += "<p>Sikap: <b>" + escapeHtml(choiceLabel("stance", r.stance)) + "</b> · " + escapeHtml(choiceLabel("land", r.land)) + " · " + escapeHtml(choiceLabel("rtrw", r.rtrw)) + "</p>";
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
      if (formEl) { formEl.querySelectorAll("select, input").forEach(function (input) { data.append(input.name, input.value); }); }
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
        $("kg-jenis").value = "kunjungan";
        document.querySelector('#form-kegiatan [name="judul"]').value = "Kunjungan ke " + r.name;
        showTab("korwil");
      });
    }
  }

  // ================================================================ Tugas

  function loadTasks() {
    if (!perms.tugas) { $("tugas-daftar").innerHTML = "<li class='muted'>Anda tidak berhak melihat tugas.</li>"; return; }
    request(urls.tasks + ($("tugas-filter").value ? "?status=semua" : "")).then(function (data) {
      $("tugas-daftar").innerHTML = data.results.map(function (t) {
        var statusSelect = perms.ubahTugas ? '<select data-status="' + t.id + '">' + config.choices.taskStatus.map(function (c) {
          return '<option value="' + escapeHtml(c.value) + '"' + (c.value === t.status ? " selected" : "") + ">" + escapeHtml(c.label) + "</option>";
        }).join("") + "</select>" : "<span class='badge'>" + escapeHtml(t.status_label) + "</span>";
        return "<li><div class='title'>" + escapeHtml(t.title) + (t.overdue ? " <span class='badge' style='background:#cf222e'>terlambat</span>" : "") + "</div>" +
          "<div class='sub'>" + escapeHtml([t.number, t.priority_label, t.due_date ? "tenggat " + fmtDate(t.due_date) : "", t.korwil ? "Korwil " + t.korwil : "", t.mine ? "" : t.assignee].filter(Boolean).join(" · ")) + "</div>" +
          (t.description ? "<p class='small'>" + escapeHtml(t.description) + "</p>" : "") +
          "<div class='progress'><i style='width:" + t.progress + "%'></i></div>" +
          "<div class='row wrap'>" + statusSelect +
          (perms.ubahTugas ? "<input type='range' min='0' max='100' step='10' value='" + t.progress + "' data-progres='" + t.id + "' aria-label='Progres'><span class='small' id='pg-" + t.id + "'>" + t.progress + "%</span>" +
            "<button type='button' class='btn-small' data-simpan-tugas='" + t.id + "'>Simpan</button>" : "") +
          (perms.lapor ? "<button type='button' class='btn-small' data-lapor-tugas='" + t.id + "' data-judul='" + escapeHtml(t.title) + "'>📝 Lapor</button>" : "") + "</div></li>";
      }).join("") || "<li class='muted'>Tidak ada tugas.</li>";
    }).catch(function (error) { toast(error.message, "error"); });
  }

  $("tugas-filter").addEventListener("change", loadTasks);
  $("tugas-daftar").addEventListener("input", function (event) {
    var id = event.target.getAttribute("data-progres");
    if (id) { $("pg-" + id).textContent = event.target.value + "%"; }
  });
  $("tugas-daftar").addEventListener("click", function (event) {
    var id = event.target.getAttribute("data-simpan-tugas");
    if (id) {
      var data = form({
        status: document.querySelector('[data-status="' + id + '"]').value,
        progress: document.querySelector('[data-progres="' + id + '"]').value
      });
      request(urls.task.replace("/0/", "/" + id + "/"), { method: "POST", body: data })
        .then(function () { toast("Tugas diperbarui.", "ok"); loadTasks(); })
        .catch(function (error) { toast(error.message, "error"); });
    }
    var lapor = event.target.getAttribute("data-lapor-tugas");
    if (lapor) {
      loadTaskOptions();
      showTab("korwil");
      setTimeout(function () { $("kg-tugas").value = lapor; }, 400);
      document.querySelector('#form-kegiatan [name="judul"]').value = event.target.getAttribute("data-judul");
    }
  });

  // ================================================================ Kinerja

  var DAY_CLASS = { hadir: "hadir", terlambat: "terlambat", izin: "izin", sakit: "sakit", cuti: "cuti", dinas: "dinas" };

  function renderPerformance(me) {
    var calendar = "";
    if (me.days.length) {
      var first = new Date(me.days[0].date + "T00:00:00");
      var offset = (first.getDay() + 6) % 7;
      for (var i = 0; i < offset; i += 1) { calendar += "<div style='visibility:hidden'></div>"; }
      var today = new Date().toISOString().slice(0, 10);
      me.days.forEach(function (d) {
        var cls = DAY_CLASS[d.status] || (d.workday && d.date < today ? "alpa" : "");
        if (!d.workday) { cls += " libur"; }
        calendar += "<div class='" + cls + "' title='" + escapeHtml(d.date + (d.status ? " · " + d.status : "") + " · " + d.activities + " kegiatan") + "'>" +
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
      "</div><h3>Kalender</h3><div class='calendar'>" + ["Sn", "Sl", "Rb", "Km", "Jm", "Sb", "Mg"].map(function (d) { return "<div class='muted' style='background:none'>" + d + "</div>"; }).join("") + calendar + "</div>";
  }

  function loadPerformance() {
    var params = "?periode=" + $("kinerja-periode").value + ($("kinerja-petugas").value ? "&petugas=" + $("kinerja-petugas").value : "");
    request(urls.performance + params).then(function (data) {
      $("kinerja-isi").innerHTML = renderPerformance(data.me);
      if (data.team) {
        $("kinerja-tim").hidden = false;
        var select = $("kinerja-petugas");
        var current = select.value;
        select.hidden = false;
        fillSelect(select, data.team.map(function (row) { return { value: row.user_id, label: row.user }; }), "Kinerja saya");
        select.value = current;
        $("kinerja-tim-isi").innerHTML = data.team.map(function (row, index) {
          return "<tr class='clickable' data-petugas='" + row.user_id + "'><td>" + (index + 1) + "</td><td>" + escapeHtml(row.user) + "</td><td><b>" + row.score + "</b> " + row.grade +
            "</td><td>" + row.attendance_pct + "%</td><td>" + row.activities + "/" + row.activity_target + "</td><td>" + row.task_pct + "%</td></tr>";
        }).join("");
      }
    }).catch(function (error) { $("kinerja-isi").textContent = error.message; });
  }

  $("kinerja-periode").addEventListener("change", loadPerformance);
  $("kinerja-petugas").addEventListener("change", loadPerformance);
  $("kinerja-tim-isi").addEventListener("click", function (event) {
    var row = event.target.closest("[data-petugas]");
    if (row) { $("kinerja-petugas").value = row.getAttribute("data-petugas"); loadPerformance(); }
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
    document.querySelectorAll(".pilih-relokasi").forEach(function (s) { fillSelect(s, config.choices.relocation); });
    $("chat-kanal").innerHTML = '<option value="umum">Kanal umum</option>' + config.korwils.map(function (k) {
      return '<option value="' + k.id + '">Korwil ' + escapeHtml(k.code) + "</option>";
    }).join("");
    $("chat-kanal").value = config.korwils.some(function (k) { return String(k.id) === String(chatChannel); }) ? chatChannel : "umum";
    chatChannel = $("chat-kanal").value;
    $("kg-waktu").value = localInputValue();
    $("foto-wajib").textContent = config.settings.requirePhoto ? "(wajib)" : "(opsional)";
    $("form-chat").hidden = !perms.kirimChat;
    $("sos-tombol").hidden = !perms.sos;
    document.querySelector('[data-tool="ai"]').hidden = !perms.aiSatelit;
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
    setInterval(loadSos, 20000);
    setInterval(function () { loadChat(false); }, 10000);
    setInterval(function () { if (layerState.petugas) { loadLayer("petugas"); } }, 30000);
    setInterval(function () { if (layerState.sos) { loadLayer("sos"); } }, 30000);
    setInterval(function () { sync(true); }, 45000);
    setInterval(function () { if (navigator.onLine) { loadLayer("korwil"); loadLayer("warga"); } }, 300000);
    showTab(config.initialTab);
  }

  init();
})();
