/* Peta tematik & pembanding citra modul aset lahan (Leaflet). */
(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function readConfig() {
    var el = document.getElementById("map-config");
    return el ? JSON.parse(el.textContent) : null;
  }

  function tileLayer(spec) {
    if (spec.wms) {
      return L.tileLayer.wms(spec.wms, {
        layers: spec.layers, format: "image/png", transparent: true, attribution: spec.attribution || ""
      });
    }
    return L.tileLayer(spec.url, { maxZoom: spec.maxZoom || 20, attribution: spec.attribution || "" });
  }

  function popup(props) {
    var html = "<strong>" + escapeHtml(props.title) + "</strong>";
    (props.rows || []).forEach(function (row) {
      html += "<br>" + escapeHtml(row[0]) + ": " + escapeHtml(row[1]);
    });
    if (props.url) {
      html += '<br><a href="' + encodeURI(props.url) + '" target="_blank" rel="noopener">Buka data</a>';
    }
    return html;
  }

  function geoJsonLayer(data) {
    return L.geoJSON(data, {
      style: function (feature) {
        var p = feature.properties || {};
        return { color: p.color || "#0969da", weight: 2, fillColor: p.color || "#0969da",
                 fillOpacity: p.outline ? 0 : 0.35 };
      },
      pointToLayer: function (feature, latlng) {
        var color = (feature.properties || {}).color || "#cf222e";
        return L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 });
      },
      onEachFeature: function (feature, layer) { layer.bindPopup(popup(feature.properties || {})); }
    });
  }

  function initThematic(el, config) {
    var map = L.map(el).setView(config.center, config.zoom);
    var bases = {};
    config.basemaps.forEach(function (spec, index) {
      var layer = tileLayer(spec);
      bases[spec.name] = layer;
      if (index === 0) { layer.addTo(map); }
    });
    var overlays = {};
    config.overlays.forEach(function (spec) { overlays[spec.name] = tileLayer(spec); });
    var control = L.control.layers(bases, overlays, { collapsed: false }).addTo(map);
    L.control.scale({ imperial: false }).addTo(map);
    var bounds = L.latLngBounds([]);
    var pending = config.layers.length;
    config.layers.forEach(function (spec) {
      fetch(spec.url, { credentials: "same-origin" })
        .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
        .then(function (data) {
          var layer = geoJsonLayer(data);
          control.addOverlay(layer, spec.name + " (" + data.features.length + ")");
          if (spec.visible) {
            layer.addTo(map);
            if (data.features.length) { bounds.extend(layer.getBounds()); }
          }
        })
        .catch(function () {
          el.insertAdjacentHTML("afterend", '<p class="errornote">Lapisan ' + escapeHtml(spec.name) +
            " tidak dapat dimuat.</p>");
        })
        .finally(function () {
          pending -= 1;
          if (pending === 0 && bounds.isValid()) { map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17 }); }
        });
    });
  }

  function clip(map, layer, side, ratio) {
    var container = layer.getContainer && layer.getContainer();
    if (!container) { return; }
    var nw = map.containerPointToLayerPoint([0, 0]);
    var se = map.containerPointToLayerPoint(map.getSize());
    var x = nw.x + (se.x - nw.x) * ratio;
    container.style.clip = side === "left"
      ? "rect(" + [nw.y, x, se.y, nw.x].join("px,") + "px)"
      : "rect(" + [nw.y, se.x, se.y, x].join("px,") + "px)";
  }

  function initCompare(el, config) {
    var map = L.map(el).setView(config.center, config.zoom);
    var left = tileLayer(config.left).addTo(map);
    var right = tileLayer(config.right).addTo(map);
    var slider = document.getElementById("swipe");
    function update() {
      var ratio = slider ? Number(slider.value) / 100 : 0.5;
      clip(map, left, "left", ratio);
      clip(map, right, "right", ratio);
    }
    map.on("move zoom resize", update);
    left.on("load", update);
    right.on("load", update);
    if (slider) { slider.addEventListener("input", update); }
    if (config.focus && config.focus.features.length) {
      var focus = L.geoJSON(config.focus, {
        style: function () { return { color: "#ffd33d", weight: 3, fillOpacity: 0 }; },
        pointToLayer: function (f, latlng) { return L.circleMarker(latlng, { radius: 8, color: "#ffd33d" }); }
      }).addTo(map);
      map.fitBounds(focus.getBounds(), { padding: [40, 40], maxZoom: 18 });
    }
    update();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var config = readConfig();
    var el = document.getElementById("peta");
    if (!config || !el || typeof L === "undefined") { return; }
    L.Icon.Default.imagePath = el.dataset.leafletImages || "";
    if (el.dataset.mode === "compare") { initCompare(el, config); } else { initThematic(el, config); }
  });
})();
