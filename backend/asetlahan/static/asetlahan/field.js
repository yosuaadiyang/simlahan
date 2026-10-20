/* Aplikasi petugas lapangan: rekam laporan + foto + GPS luring, kirim saat daring. */
(function () {
  "use strict";

  var DB_NAME = "simlahan-lapangan";
  var STORE = "antrean";
  var MAX_PHOTO_SIDE = 1600;
  var config = JSON.parse(document.getElementById("field-config").textContent);
  var position = null;
  var tapped = null;
  var syncing = false;
  var map;
  var tapMarker = null;

  function $(id) { return document.getElementById(id); }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function message(text, kind) {
    var el = $("pesan");
    el.textContent = text || "";
    el.className = "small " + (kind || "");
  }

  // ---------------------------------------------------------------- IndexedDB

  function openDb() {
    return new Promise(function (resolve, reject) {
      var request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = function () {
        request.result.createObjectStore(STORE, { keyPath: "client_id" });
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
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

  function allReports() { return tx("readonly", function (store) { return store.getAll(); }); }
  function putReport(report) { return tx("readwrite", function (store) { store.put(report); }); }
  function deleteReport(id) { return tx("readwrite", function (store) { store.delete(id); }); }

  // ---------------------------------------------------------------- Utilitas

  function uuid() {
    if (window.crypto && crypto.randomUUID) { return crypto.randomUUID(); }
    var bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map.call(bytes, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) { return decodeURIComponent(match[1]); }
    var meta = document.querySelector("meta[name=csrf-token]");
    return meta ? meta.content : "";
  }

  function compressPhoto(file) {
    if (!file) { return Promise.resolve(null); }
    if (!window.createImageBitmap) { return Promise.resolve(file); }
    return createImageBitmap(file).then(function (bitmap) {
      var scale = Math.min(1, MAX_PHOTO_SIDE / Math.max(bitmap.width, bitmap.height));
      var canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      return new Promise(function (resolve) {
        canvas.toBlob(function (blob) { resolve(blob || file); }, "image/jpeg", 0.82);
      });
    }).catch(function () { return file; });
  }

  function formatTime(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString("id-ID") + " " + d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  }

  // ---------------------------------------------------------------- Peta & GPS

  function popup(props) {
    var html = "<strong>" + escapeHtml(props.title) + "</strong>";
    (props.rows || []).forEach(function (row) { html += "<br>" + escapeHtml(row[0]) + ": " + escapeHtml(row[1]); });
    return html;
  }

  function initMap() {
    L.Icon.Default.imagePath = document.body.dataset.leafletImages || "";
    map = L.map("peta").setView(config.center, config.zoom);
    var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(map);
    var satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "&copy; Esri" });
    var control = L.control.layers({ "Peta jalan": osm, "Citra satelit": satellite }, null).addTo(map);
    L.control.scale({ imperial: false }).addTo(map);
    fetch(config.boundaries, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (data) {
        var layer = L.geoJSON(data, {
          style: function (f) { var c = f.properties.color || "#0969da"; return { color: c, weight: 2, fillColor: c, fillOpacity: 0.25 }; },
          pointToLayer: function (f, latlng) {
            return L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2, fillColor: f.properties.color, fillOpacity: 0.9 });
          },
          onEachFeature: function (f, lyr) { lyr.bindPopup(popup(f.properties)); }
        }).addTo(map);
        control.addOverlay(layer, "Batas aset & okupasi");
        if (data.features.length && !position) { map.fitBounds(layer.getBounds(), { maxZoom: 16 }); }
      })
      .catch(function () { message("Batas bidang belum tersedia luring. Buka aplikasi saat ada sinyal sekali.", "error"); });

    map.on("click", function (event) {
      tapped = event.latlng;
      if (tapMarker) { tapMarker.setLatLng(tapped); } else { tapMarker = L.marker(tapped).addTo(map); }
      $("titik-manual").checked = true;
    });
  }

  function initGps() {
    var marker = null;
    var circle = null;
    if (!navigator.geolocation) { $("gps").textContent = "Perangkat tidak mendukung GPS; ketuk peta untuk menandai titik."; return; }
    navigator.geolocation.watchPosition(function (pos) {
      var first = !position;
      position = pos.coords;
      var latlng = [position.latitude, position.longitude];
      $("gps").textContent = "GPS: " + position.latitude.toFixed(6) + ", " + position.longitude.toFixed(6) +
        " (±" + Math.round(position.accuracy) + " m)";
      if (!marker) {
        circle = L.circle(latlng, { radius: position.accuracy, color: "#0969da", weight: 1, fillOpacity: 0.1 }).addTo(map);
        marker = L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2, fillColor: "#0969da", fillOpacity: 1 }).addTo(map);
      } else {
        marker.setLatLng(latlng);
        circle.setLatLng(latlng).setRadius(position.accuracy);
      }
      if (first) { map.setView(latlng, 17); }
    }, function (error) {
      var reason = { 1: "izin lokasi ditolak", 2: "posisi tidak ditemukan", 3: "waktu habis" }[error.code] || "galat perangkat";
      $("gps").textContent = "GPS tidak tersedia (" + reason + "). Ketuk peta untuk menandai titik.";
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
  }

  // ---------------------------------------------------------------- Antrean

  function renderQueue() {
    return allReports().then(function (items) {
      items.sort(function (a, b) { return a.captured_at < b.captured_at ? 1 : -1; });
      $("jumlah").textContent = items.length;
      var labels = {};
      config.reportTypes.forEach(function (t) { labels[t.value] = t.label; });
      $("antrean").innerHTML = items.map(function (item) {
        return "<li><strong>" + escapeHtml(labels[item.report_type] || item.report_type) + "</strong> · " +
          escapeHtml(formatTime(item.captured_at)) + (item.photo ? " · foto" : "") +
          (item.note ? "<br>" + escapeHtml(item.note.slice(0, 120)) : "") +
          (item.error ? '<span class="error">' + escapeHtml(item.error) + "</span>" +
            '<button type="button" data-hapus="' + escapeHtml(item.client_id) + '">Hapus</button>' : "") + "</li>";
      }).join("");
      return items;
    });
  }

  function errorText(body) {
    if (body && body.errors) {
      return Object.keys(body.errors).map(function (key) {
        var value = body.errors[key];
        return Array.isArray(value) ? value.join(" ") : String(value);
      }).join(" ");
    }
    return (body && body.error) || "Ditolak server.";
  }

  function send(item) {
    var form = new FormData();
    ["client_id", "report_type", "lat", "lng", "accuracy", "captured_at", "note"].forEach(function (key) {
      if (item[key] !== null && item[key] !== undefined) { form.append(key, item[key]); }
    });
    if (item.photo) { form.append("photo", item.photo, "foto.jpg"); }
    return fetch(config.sync, {
      method: "POST", body: form, credentials: "same-origin", redirect: "manual",
      headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" }
    }).then(function (response) {
      if (response.type === "opaqueredirect" || response.status === 401 || response.status === 403) {
        return { login: true };
      }
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (response.ok) { return deleteReport(item.client_id).then(function () { return { ok: true }; }); }
        if (response.status === 400) {
          item.error = errorText(body);
          return putReport(item).then(function () { return { failed: true }; });
        }
        throw new Error("HTTP " + response.status);
      });
    });
  }

  function sync() {
    if (syncing || !navigator.onLine) { return Promise.resolve(); }
    syncing = true;
    $("sinkron").disabled = true;
    var sent = 0;
    return allReports().then(function (items) {
      var pending = items.filter(function (item) { return !item.error; });
      if (!pending.length) { return null; }
      message("Mengirim " + pending.length + " laporan…");
      return pending.reduce(function (chain, item) {
        return chain.then(function (state) {
          if (state && state.login) { return state; }
          return send(item).then(function (result) {
            if (result.ok) { sent += 1; }
            return result;
          });
        });
      }, Promise.resolve(null));
    }).then(function (state) {
      if (state && state.login) {
        $("pesan").innerHTML = 'Sesi masuk berakhir. <a href="' + encodeURI(config.login) +
          '">Masuk lagi</a>; laporan tetap tersimpan di perangkat.';
        $("pesan").className = "small error";
      } else if (sent) {
        message(sent + " laporan terkirim.", "ok");
      }
    }).catch(function () {
      message("Pengiriman tertunda; akan dicoba lagi saat sinyal stabil.", "error");
    }).then(function () {
      syncing = false;
      $("sinkron").disabled = false;
      return renderQueue();
    });
  }

  function saveReport(event) {
    event.preventDefault();
    var useTap = $("titik-manual").checked && tapped;
    if (!useTap && !position) {
      message("Lokasi belum ada. Tunggu sinyal GPS atau ketuk titik di peta.", "error");
      return;
    }
    var button = event.target.querySelector("button[type=submit]");
    button.disabled = true;
    compressPhoto($("foto").files[0]).then(function (photo) {
      var report = {
        client_id: uuid(),
        report_type: $("jenis").value,
        lat: useTap ? tapped.lat : position.latitude,
        lng: useTap ? tapped.lng : position.longitude,
        accuracy: useTap ? null : position.accuracy,
        captured_at: new Date().toISOString(),
        note: $("catatan").value.trim(),
        photo: photo
      };
      return putReport(report);
    }).then(function () {
      event.target.reset();
      $("titik-manual").checked = false;
      if (tapMarker) { map.removeLayer(tapMarker); tapMarker = null; }
      tapped = null;
      message(navigator.onLine ? "Laporan tersimpan, mengirim…" : "Laporan tersimpan di perangkat; akan dikirim saat daring.", "ok");
      return renderQueue();
    }).then(sync).catch(function (error) {
      message("Laporan gagal disimpan di perangkat: " + error, "error");
    }).then(function () { button.disabled = false; });
  }

  // ---------------------------------------------------------------- Mulai

  function updateNet() {
    var net = $("net");
    net.textContent = navigator.onLine ? "Daring" : "Luring";
    net.className = "pill " + (navigator.onLine ? "online" : "offline");
  }

  document.addEventListener("DOMContentLoaded", function () {
    config.reportTypes.forEach(function (type) {
      var option = document.createElement("option");
      option.value = type.value;
      option.textContent = type.label;
      $("jenis").appendChild(option);
    });
    updateNet();
    window.addEventListener("online", function () { updateNet(); sync(); });
    window.addEventListener("offline", updateNet);
    $("lapor").addEventListener("submit", saveReport);
    $("sinkron").addEventListener("click", sync);
    $("antrean").addEventListener("click", function (event) {
      var id = event.target.getAttribute("data-hapus");
      if (id && window.confirm("Hapus laporan ini dari perangkat?")) { deleteReport(id).then(renderQueue); }
    });
    if (typeof L !== "undefined") { initMap(); initGps(); }
    renderQueue().then(sync);
    setInterval(sync, 60000);

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register(config.serviceWorker, { scope: config.scope }).catch(function () {});
    }
    var deferred = null;
    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferred = event;
      $("install").hidden = false;
    });
    $("install").addEventListener("click", function () {
      if (!deferred) { return; }
      deferred.prompt();
      deferred = null;
      $("install").hidden = true;
    });
  });
})();
