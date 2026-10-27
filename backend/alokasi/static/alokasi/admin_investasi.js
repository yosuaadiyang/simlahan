/* Panel petugas: peta lahan diminati & area yang digambar investor. */
(function () {
  "use strict";

  function init() {
    var el = document.getElementById("inv-map");
    if (!el || typeof L === "undefined") { return; }
    var plots = [];
    var source = document.getElementById("inv-map-plots");
    if (source) {
      try { plots = JSON.parse(source.textContent) || []; } catch (e) { plots = []; }
    }
    var map = L.map(el, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
    L.control.scale({ imperial: false }).addTo(map);
    var group = L.featureGroup().addTo(map);
    plots.forEach(function (plot) {
      if (!plot.geometry) { return; }
      try {
        L.geoJSON(JSON.parse(plot.geometry), {
          style: { color: "#1f6feb", weight: 2, fillOpacity: 0.25 }
        }).bindTooltip(plot.code + " · " + plot.name, { sticky: true }).addTo(group);
      } catch (e) { /* abaikan geometri rusak */ }
    });
    if (el.dataset.area) {
      try {
        L.geoJSON(JSON.parse(el.dataset.area), {
          style: { color: "#d97706", weight: 3, dashArray: "6 4", fillOpacity: 0.2 }
        }).bindTooltip("Area usulan investor", { sticky: true }).addTo(group);
      } catch (e) { /* abaikan geometri rusak */ }
    }
    if (group.getLayers().length && group.getBounds().isValid()) {
      map.fitBounds(group.getBounds(), { padding: [20, 20], maxZoom: 17 });
    } else {
      map.setView([0.87, 104.15], 11);
      el.insertAdjacentHTML("afterend", '<p class="help">Lokasi belum dipetakan.</p>');
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
