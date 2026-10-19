/* Portal alokasi lahan: peta (Leaflet), menu ponsel, dan konfirmasi aksi. */
(function () {
  "use strict";

  var STATUS_COLORS = {
    tersedia: "#1a7f37",
    dipesan: "#d4a72c",
    dialokasikan: "#8250df",
    ditutup: "#6e7781"
  };

  function baseLayers() {
    var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    });
    var satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Tiles &copy; Esri" }
    );
    return { "Peta jalan": osm, "Citra satelit": satellite };
  }

  function createMap(el) {
    var center = [parseFloat(el.dataset.lat || "0.87"), parseFloat(el.dataset.lng || "104.15")];
    var map = L.map(el, { scrollWheelZoom: false }).setView(center, parseInt(el.dataset.zoom || "11", 10));
    var layers = baseLayers();
    layers["Peta jalan"].addTo(map);
    L.control.layers(layers, null, { position: "topright" }).addTo(map);
    L.control.scale({ imperial: false }).addTo(map);
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    map.on("blur", function () { map.scrollWheelZoom.disable(); });
    return map;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function formatArea(value) {
    return Number(value).toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " m²";
  }

  function styleFor(feature) {
    var color = STATUS_COLORS[feature.properties.status] || "#0b4f8a";
    return { color: color, weight: 2, fillColor: color, fillOpacity: 0.35 };
  }

  function initListMap(el) {
    var map = createMap(el);
    fetch(el.dataset.geojson, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var layer = L.geoJSON(data, {
          style: styleFor,
          onEachFeature: function (feature, lyr) {
            var p = feature.properties;
            lyr.bindPopup(
              "<strong>" + escapeHtml(p.code) + "</strong> " + escapeHtml(p.name) +
              "<br>" + escapeHtml(p.allocation_type) +
              "<br>Luas: " + formatArea(p.area_m2) +
              "<br>Status: " + escapeHtml(p.status_label) +
              (p.intended_use ? "<br>Arahan: " + escapeHtml(p.intended_use) : "") +
              '<br><a href="' + encodeURI(p.url) + '">Lihat detail</a>'
            );
          }
        }).addTo(map);
        if (data.features && data.features.length) {
          map.fitBounds(layer.getBounds(), { padding: [20, 20], maxZoom: 16 });
        }
      })
      .catch(function () {
        el.insertAdjacentHTML("afterend", '<p class="muted small">Peta tidak dapat dimuat.</p>');
      });
  }

  function initShapeMap(el) {
    var map = createMap(el);
    var geometry = el.dataset.geometry ? JSON.parse(el.dataset.geometry) : null;
    if (!geometry) {
      el.insertAdjacentHTML("afterend", '<p class="muted small">Batas lahan belum dipetakan.</p>');
      return;
    }
    var layer = L.geoJSON(geometry, {
      style: function () {
        var color = STATUS_COLORS[el.dataset.status] || "#0b4f8a";
        return { color: color, weight: 3, fillColor: color, fillOpacity: 0.3 };
      }
    }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [20, 20], maxZoom: 17 });
  }

  function initPickMap(el) {
    var map = createMap(el);
    var lat = document.getElementById("id_latitude");
    var lng = document.getElementById("id_longitude");
    var marker = null;
    function place(latlng, zoom) {
      if (marker) { marker.setLatLng(latlng); } else { marker = L.marker(latlng).addTo(map); }
      lat.value = latlng.lat.toFixed(7);
      lng.value = latlng.lng.toFixed(7);
      if (zoom) { map.setView(latlng, zoom); }
    }
    if (lat && lng && lat.value && lng.value) {
      place(L.latLng(parseFloat(lat.value), parseFloat(lng.value)), 16);
    }
    map.on("click", function (event) { place(event.latlng); });
    var locate = document.querySelector("[data-locate]");
    if (locate && navigator.geolocation) {
      locate.addEventListener("click", function () {
        navigator.geolocation.getCurrentPosition(function (pos) {
          place(L.latLng(pos.coords.latitude, pos.coords.longitude), 17);
        }, function () { locate.insertAdjacentHTML("afterend", ' <span class="small muted">Lokasi tidak tersedia.</span>'); },
        { enableHighAccuracy: true, timeout: 15000 });
      });
    } else if (locate) {
      locate.hidden = true;
    }
    var clear = document.querySelector("[data-clear-location]");
    if (clear) {
      clear.addEventListener("click", function () {
        if (marker) { map.removeLayer(marker); marker = null; }
        lat.value = "";
        lng.value = "";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("site-nav");
    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm(form.dataset.confirm)) {
          event.preventDefault();
        }
      });
    });

    if (typeof L === "undefined") { return; }
    L.Icon.Default.imagePath = (document.body.dataset.leafletImages || "");
    document.querySelectorAll("[data-map=list]").forEach(initListMap);
    document.querySelectorAll("[data-map=shape]").forEach(initShapeMap);
    document.querySelectorAll("[data-map=pick]").forEach(initPickMap);
  });
})();
