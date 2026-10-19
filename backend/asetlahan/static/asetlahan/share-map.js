/* Peta berbagi baca-saja (tautan publik). */
(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("peta-berbagi");
    var configEl = document.getElementById("share-map-config");
    if (!el || !configEl || typeof L === "undefined") { return; }
    var config = JSON.parse(configEl.textContent);
    L.Icon.Default.imagePath = document.body.dataset.leafletImages || "";
    var map = L.map(el).setView(config.center, config.zoom);
    var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
    var satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Tiles &copy; Esri" });
    L.control.layers({ "Peta jalan": osm, "Citra satelit": satellite }, null).addTo(map);
    L.control.scale({ imperial: false }).addTo(map);
    fetch(config.data, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (data) {
        var layer = L.geoJSON(data, {
          style: function (feature) {
            var p = feature.properties || {};
            return { color: p.color || "#0969da", weight: 2, fillColor: p.color || "#0969da",
                     fillOpacity: p.outline ? 0 : 0.35 };
          },
          onEachFeature: function (feature, lyr) {
            var p = feature.properties || {};
            var html = "<strong>" + escapeHtml(p.title) + "</strong>";
            (p.rows || []).forEach(function (row) {
              html += "<br>" + escapeHtml(row[0]) + ": " + escapeHtml(row[1]);
            });
            lyr.bindPopup(html);
          }
        }).addTo(map);
        if (data.features.length) { map.fitBounds(layer.getBounds(), { padding: [20, 20], maxZoom: 17 }); }
      })
      .catch(function () {
        el.insertAdjacentHTML("afterend", '<p class="muted small">Peta tidak dapat dimuat.</p>');
      });
  });
})();
