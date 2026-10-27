/*
 * Portal investasi: peta peluang (filter instan), perbandingan lahan, simpan
 * lahan, simulasi biaya, dan peta gambar usulan lokasi pada formulir minat.
 * Nominal dikirim server sebagai teks dan dihitung dengan BigInt agar tepat.
 */
(function () {
  "use strict";

  var COMPARE_KEY = "simlahan-bandingkan";
  var MAX_COMPARE = 4;
  var EARTH_RADIUS = 6378137;

  // ------------------------------------------------------------ Utilitas
  function $(selector, root) { return (root || document).querySelector(selector); }
  function $$(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function groupDigits(intPart) {
    return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  // "1234567.50" → "1.234.567,5" (desimal opsional, tanpa pembulatan float).
  function formatDecimal(text, maxDecimals) {
    if (text === null || text === undefined || text === "") { return "-"; }
    var str = String(text);
    var negative = str.charAt(0) === "-";
    if (negative) { str = str.slice(1); }
    var parts = str.split(".");
    var frac = (parts[1] || "").slice(0, maxDecimals || 0).replace(/0+$/, "");
    return (negative ? "-" : "") + groupDigits(parts[0] || "0") + (frac ? "," + frac : "");
  }

  function rupiah(text) {
    if (text === null || text === undefined || text === "") { return "-"; }
    return "Rp" + formatDecimal(roundDecimal(String(text)), 0);
  }

  function roundDecimal(text) {
    var parts = text.split(".");
    var whole = BigInt(parts[0] || "0");
    if (parts[1] && parts[1].charAt(0) >= "5") { whole += whole < BigInt(0) ? BigInt(-1) : BigInt(1); }
    return whole.toString();
  }

  // Desimal teks → BigInt berskala 10^scale.
  function toScaled(text, scale) {
    var str = String(text || "0");
    var parts = str.split(".");
    var frac = (parts[1] || "").slice(0, scale);
    while (frac.length < scale) { frac += "0"; }
    return BigInt((parts[0] || "0") + frac);
  }

  // Luas (2 desimal) × tarif (2 desimal) × tahun → rupiah bulat (teks).
  function multiplyMoney(area, rate, years) {
    var product = toScaled(area, 2) * toScaled(rate, 2) * BigInt(years || 0);
    var scale = BigInt(10000);
    var whole = product / scale;
    if ((product % scale) * BigInt(2) >= scale) { whole += BigInt(1); }
    return whole.toString();
  }

  function hectare(areaText) {
    var ha = Number(areaText) / 10000;
    if (!isFinite(ha)) { return "-"; }
    return ha.toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " ha";
  }

  function storageGet(key) {
    try { return JSON.parse(window.localStorage.getItem(key) || "null"); } catch (e) { return null; }
  }

  function storageSet(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* mode privat */ }
  }

  function csrfToken() {
    var input = $("input[name=csrfmiddlewaretoken]");
    if (input) { return input.value; }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function geodesicArea(latlngs) {
    // Luas poligon di permukaan bola (m²), cukup akurat untuk usulan lokasi.
    var area = 0;
    var n = latlngs.length;
    if (n < 3) { return 0; }
    for (var i = 0; i < n; i++) {
      var p1 = latlngs[i];
      var p2 = latlngs[(i + 1) % n];
      area += ((p2.lng - p1.lng) * Math.PI / 180) *
        (2 + Math.sin(p1.lat * Math.PI / 180) + Math.sin(p2.lat * Math.PI / 180));
    }
    return Math.abs(area * EARTH_RADIUS * EARTH_RADIUS / 2);
  }

  function baseLayers() {
    return {
      "Peta jalan": L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
      }),
      "Citra satelit": L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19, attribution: "Tiles &copy; Esri" }
      )
    };
  }

  function createMap(el, options) {
    var center = [parseFloat(el.dataset.lat || "0.87"), parseFloat(el.dataset.lng || "104.15")];
    var map = L.map(el, Object.assign({ scrollWheelZoom: true }, options || {}))
      .setView(center, parseInt(el.dataset.zoom || "12", 10));
    var layers = baseLayers();
    layers["Peta jalan"].addTo(map);
    map._slBaseLayers = layers;
    L.control.scale({ imperial: false }).addTo(map);
    return map;
  }

  function loadData(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    });
  }

  // ------------------------------------------------------------ Bandingkan
  var compare = {
    list: function () {
      var value = storageGet(COMPARE_KEY);
      return Array.isArray(value) ? value.filter(function (c) { return typeof c === "string"; }).slice(0, MAX_COMPARE) : [];
    },
    has: function (code) { return compare.list().indexOf(code) !== -1; },
    toggle: function (code) {
      var list = compare.list();
      var index = list.indexOf(code);
      if (index !== -1) {
        list.splice(index, 1);
      } else {
        if (list.length >= MAX_COMPARE) {
          window.alert("Maksimal " + MAX_COMPARE + " lahan dapat dibandingkan sekaligus.");
          return;
        }
        list.push(code);
      }
      storageSet(COMPARE_KEY, list);
      compare.refresh();
    },
    clear: function () { storageSet(COMPARE_KEY, []); compare.refresh(); },
    refresh: function () {
      var list = compare.list();
      $$("[data-compare]").forEach(function (button) {
        var on = list.indexOf(button.dataset.compare) !== -1;
        button.setAttribute("aria-pressed", on ? "true" : "false");
      });
      var bar = $("#compare-bar");
      if (!bar) { return; }
      bar.hidden = list.length === 0;
      document.body.classList.toggle("has-compare", !bar.hidden);
      var count = $("[data-compare-count]", bar);
      if (count) { count.textContent = String(list.length); }
      var go = $("[data-compare-go]", bar);
      if (go) { go.href = bar.dataset.url + "?lahan=" + encodeURIComponent(list.join(",")); }
    }
  };

  // ------------------------------------------------------------ Simpan lahan
  function toggleSave(button) {
    var url = button.dataset.saveUrl;
    if (!url) { return; }
    button.disabled = true;
    var body = new FormData();
    body.append("csrfmiddlewaretoken", csrfToken());
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch", "X-CSRFToken": csrfToken() },
      body: body
    }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    }).then(function (data) {
      $$('[data-save="' + data.code + '"]').forEach(function (b) {
        b.setAttribute("aria-pressed", data.saved ? "true" : "false");
        var label = $("span", b);
        if (label) { label.textContent = data.saved ? "Tersimpan" : "Simpan"; }
      });
      document.dispatchEvent(new CustomEvent("sl:saved", { detail: data }));
    }).catch(function () {
      window.alert("Lahan tidak dapat disimpan. Muat ulang halaman lalu coba lagi.");
    }).then(function () { button.disabled = false; });
  }

  document.addEventListener("click", function (event) {
    var compareButton = event.target.closest("[data-compare]");
    if (compareButton) {
      event.preventDefault();
      compare.toggle(compareButton.dataset.compare);
      if (compareButton.closest("[data-compare-sync]")) {
        // Halaman perbandingan: tampilkan ulang dengan daftar terbaru.
        var bar = $("#compare-bar");
        var list = compare.list();
        window.location.href = bar.dataset.url + (list.length ? "?lahan=" + encodeURIComponent(list.join(",")) : "");
      }
      return;
    }
    var saveButton = event.target.closest("[data-save]");
    if (saveButton) {
      event.preventDefault();
      toggleSave(saveButton);
      return;
    }
    if (event.target.closest("[data-compare-clear]")) {
      compare.clear();
    }
  });

  // ------------------------------------------------------------ Peta penjelajah
  function initExplorer(root) {
    var listEl = $("#result-list", root);
    var countEl = $("[data-count]", root);
    var mapEl = $("#inv-map", root);
    var saved = (root.dataset.saved || "").split(",").filter(Boolean);
    var isApplicant = root.dataset.applicant === "1";
    var requestUrl = root.dataset.requestUrl;
    var params = new URLSearchParams(window.location.search);
    var state = {
      q: params.get("q") || "",
      scheme: params.get("skema") || "",
      sectors: (params.get("sektor") || "").split(",").filter(Boolean),
      kawasan: params.get("kawasan") || "",
      kecamatan: params.get("kecamatan") || "",
      min: params.get("min") || "",
      max: params.get("max") || "",
      siap: params.get("siap") === "1",
      dokumen: params.get("dokumen") === "1",
      semua: params.get("semua") === "1",
      simpan: params.get("simpan") === "1",
      urut: params.get("urut") || "",
      selected: params.get("lahan") || ""
    };
    var features = [];
    var layersByCode = {};
    var map = createMap(mapEl);
    var plotLayer = L.featureGroup().addTo(map);
    var zoneLayer = L.featureGroup().addTo(map);
    L.control.layers(map._slBaseLayers, { "Batas kawasan": zoneLayer, "Lahan": plotLayer }, { position: "topright" }).addTo(map);

    // Isi kontrol dari state awal (tautan bersama).
    $("[data-filter=q]", root).value = state.q;
    $("[data-filter=kawasan]", root).value = state.kawasan;
    $("[data-filter=kecamatan]", root).value = state.kecamatan;
    $("[data-filter=min]", root).value = state.min;
    $("[data-filter=max]", root).value = state.max;
    $("[data-filter=urut]", root).value = state.urut;
    ["siap", "dokumen", "semua", "simpan"].forEach(function (key) {
      var box = $("[data-filter=" + key + "]", root);
      if (box) { box.checked = state[key]; }
    });
    if (state.kawasan || state.kecamatan || state.min || state.max || state.siap || state.dokumen || state.semua || state.simpan) {
      $("details.more-filters", root).open = true;
    }

    function syncButtons() {
      $$("[data-scheme]", root).forEach(function (b) {
        b.setAttribute("aria-pressed", b.dataset.scheme === state.scheme ? "true" : "false");
      });
      $$("[data-sector]", root).forEach(function (b) {
        b.setAttribute("aria-pressed", state.sectors.indexOf(b.dataset.sector) !== -1 ? "true" : "false");
      });
      var extra = ["kawasan", "kecamatan", "min", "max"].filter(function (k) { return state[k]; }).length +
        ["siap", "dokumen", "semua", "simpan"].filter(function (k) { return state[k]; }).length;
      var counter = $("[data-filter-count]", root);
      if (counter) { counter.textContent = extra ? "(" + extra + " aktif)" : ""; }
    }

    function writeUrl() {
      var out = new URLSearchParams();
      if (state.q) { out.set("q", state.q); }
      if (state.scheme) { out.set("skema", state.scheme); }
      if (state.sectors.length) { out.set("sektor", state.sectors.join(",")); }
      ["kawasan", "kecamatan", "min", "max", "urut"].forEach(function (k) { if (state[k]) { out.set(k, state[k]); } });
      ["siap", "dokumen", "semua", "simpan"].forEach(function (k) { if (state[k]) { out.set(k, "1"); } });
      if (state.selected) { out.set("lahan", state.selected); }
      var query = out.toString();
      try {
        window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : ""));
      } catch (e) { /* abaikan */ }
    }

    function matches(p) {
      if (!state.semua && !(p.available && (p.lease || p.allocation))) { return false; }
      if (state.scheme === "sewa" && !p.lease) { return false; }
      if (state.scheme === "alokasi" && !p.allocation) { return false; }
      if (state.sectors.length && state.sectors.indexOf(p.sector) === -1) { return false; }
      if (state.kawasan && p.zone !== state.kawasan) { return false; }
      if (state.kecamatan && p.district !== state.kecamatan) { return false; }
      var ha = Number(p.area_m2) / 10000;
      if (state.min !== "" && ha < Number(state.min)) { return false; }
      if (state.max !== "" && ha > Number(state.max)) { return false; }
      if (state.siap && !p.ready) { return false; }
      if (state.dokumen && !p.docs) { return false; }
      if (state.simpan && saved.indexOf(p.code) === -1) { return false; }
      if (state.q) {
        var hay = [p.code, p.name, p.village, p.district, p.intended_use, p.zoning, p.sector_name, p.zone_name].join(" ").toLowerCase();
        var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
        for (var i = 0; i < terms.length; i++) { if (hay.indexOf(terms[i]) === -1) { return false; } }
      }
      return true;
    }

    function rateOf(p) {
      var rate = p.lease && state.scheme !== "alokasi" ? p.lease_rate : (p.allocation ? p.uwt_rate : "");
      return rate === "" ? Infinity : Number(rate);
    }

    function sorted(list) {
      var copy = list.slice();
      var by = state.urut;
      copy.sort(function (a, b) {
        var p = a.properties;
        var q = b.properties;
        if (by === "luas-desc") { return Number(q.area_m2) - Number(p.area_m2); }
        if (by === "luas-asc") { return Number(p.area_m2) - Number(q.area_m2); }
        if (by === "tarif-asc") { return rateOf(p) - rateOf(q); }
        if (by === "kode") { return p.code < q.code ? -1 : 1; }
        if (p.available !== q.available) { return p.available ? -1 : 1; }
        if (p.featured !== q.featured) { return p.featured ? -1 : 1; }
        return p.code < q.code ? -1 : 1;
      });
      return copy;
    }

    function priceLine(p) {
      var parts = [];
      if (p.lease && p.lease_rate !== "") { parts.push("Sewa <strong>" + rupiah(p.lease_rate) + "</strong>/m²/thn"); }
      if (p.allocation && p.uwt_rate !== "" && Number(p.uwt_rate) > 0) { parts.push("UWT <strong>" + rupiah(p.uwt_rate) + "</strong>/m²/thn"); }
      return parts.join(" · ");
    }

    function chips(p) {
      var html = "";
      if (p.sector_name) { html += '<span class="chip chip-sector" style="--c:' + escapeHtml(p.color) + '">' + escapeHtml(p.sector_icon + " " + p.sector_name) + "</span>"; }
      if (p.lease) { html += '<span class="chip chip-sewa">Sewa</span>'; }
      if (p.allocation) { html += '<span class="chip chip-alokasi">Alokasi</span>'; }
      if (p.ready) { html += '<span class="chip chip-ready">Siap bangun</span>'; }
      if (!p.available) { html += '<span class="badge badge-' + escapeHtml(p.status) + '">' + escapeHtml(p.status_label) + "</span>"; }
      return '<div class="chips">' + html + "</div>";
    }

    function popupHtml(p) {
      var html = '<div class="plot-popup">';
      if (p.photo) { html += '<img src="' + encodeURI(p.photo) + '" alt="" loading="lazy">'; }
      html += '<div class="p-code">' + escapeHtml(p.code) + '</div><div class="p-name">' + escapeHtml(p.name) + "</div>";
      html += chips(p);
      html += "<dl><dt>Luas</dt><dd>" + hectare(p.area_m2) + "</dd>";
      if (p.lease && p.lease_rate !== "") { html += "<dt>Sewa</dt><dd>" + rupiah(p.lease_rate) + "/m²/thn</dd>"; }
      if (p.allocation && p.uwt_rate !== "" && Number(p.uwt_rate) > 0) { html += "<dt>UWT</dt><dd>" + rupiah(p.uwt_rate) + "/m²/thn</dd>"; }
      if (p.zone_name) { html += "<dt>Kawasan</dt><dd>" + escapeHtml(p.zone_name) + "</dd>"; }
      html += "</dl>";
      html += '<div class="p-actions"><a class="btn btn-small" href="' + encodeURI(p.url) + '">Lihat detail</a>';
      if (p.available) {
        html += '<a class="btn btn-small btn-accent" href="' + encodeURI(requestUrl) + "?lahan=" + encodeURIComponent(p.code) + '">Ajukan minat</a>';
      }
      html += '<button type="button" class="btn-icon" data-compare="' + escapeHtml(p.code) + '" aria-pressed="' + (compare.has(p.code) ? "true" : "false") + '">Bandingkan</button>';
      html += "</div></div>";
      return html;
    }

    function styleFor(p, highlighted) {
      var color = p.available ? p.color : "#94a3b8";
      return {
        color: highlighted ? "#0f172a" : color,
        weight: highlighted ? 4 : 2,
        fillColor: color,
        fillOpacity: highlighted ? 0.55 : (p.available ? 0.38 : 0.18),
        dashArray: p.available ? null : "4 4"
      };
    }

    function highlight(code, on) {
      var layer = layersByCode[code];
      if (layer) {
        layer.setStyle(styleFor(layer.feature.properties, on || code === state.selected));
        if (on && layer.bringToFront) { layer.bringToFront(); }
      }
      var item = listEl.querySelector('[data-code="' + CSS.escape(code) + '"]');
      if (item) { item.classList.toggle("hover", !!on); }
    }

    function select(code, fly) {
      var previous = state.selected;
      state.selected = code;
      if (previous && layersByCode[previous]) { highlight(previous, false); }
      $$(".result.active", listEl).forEach(function (el) { el.classList.remove("active"); });
      var item = listEl.querySelector('[data-code="' + CSS.escape(code) + '"]');
      if (item) { item.classList.add("active"); }
      var layer = layersByCode[code];
      if (layer) {
        highlight(code, true);
        if (fly) { map.flyToBounds(layer.getBounds(), { padding: [60, 60], maxZoom: 16, duration: 0.6 }); }
        layer.openPopup(layer.getBounds().getCenter());
        if (window.matchMedia("(max-width: 900px)").matches && fly) {
          mapEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
      writeUrl();
    }

    function render(fit) {
      var shown = sorted(features.filter(function (f) { return matches(f.properties); }));
      plotLayer.clearLayers();
      layersByCode = {};
      shown.forEach(function (feature) {
        if (!feature.geometry) { return; }
        var p = feature.properties;
        var layer = L.geoJSON(feature, { style: function () { return styleFor(p, p.code === state.selected); } });
        layer.eachLayer(function (child) { child.feature = feature; });
        layer.feature = feature;
        layer.bindPopup(function () { return popupHtml(p); }, { maxWidth: 280, autoPanPadding: [24, 24] });
        layer.bindTooltip(escapeHtml(p.code + " · " + hectare(p.area_m2)), { sticky: true, direction: "top" });
        layer.on("click", function () { select(p.code, false); });
        layer.on("mouseover", function () { highlight(p.code, true); });
        layer.on("mouseout", function () { highlight(p.code, false); });
        layer.addTo(plotLayer);
        layersByCode[p.code] = layer;
      });
      countEl.textContent = String(shown.length);
      if (!shown.length) {
        listEl.innerHTML = '<li class="empty-state">Tidak ada lahan yang cocok dengan filter.<br><button type="button" class="btn btn-small btn-outline" data-reset style="margin-top:10px">Atur ulang filter</button></li>';
      } else {
        listEl.innerHTML = shown.map(function (feature) {
          var p = feature.properties;
          return '<li><div class="result' + (p.available ? "" : " unavailable") + (p.code === state.selected ? " active" : "") +
            '" role="button" tabindex="0" data-code="' + escapeHtml(p.code) + '" style="--c:' + escapeHtml(p.available ? p.color : "#94a3b8") + '">' +
            '<div class="r-top"><div><div class="r-code">' + escapeHtml(p.code) + "</div>" +
            '<div class="r-name">' + escapeHtml(p.name) + '</div></div><span class="dot" aria-hidden="true"></span></div>' +
            chips(p) +
            '<div class="r-facts"><span><strong>' + hectare(p.area_m2) + "</strong></span>" +
            (priceLine(p) ? "<span>" + priceLine(p) + "</span>" : "") +
            (p.village || p.district ? "<span>" + escapeHtml([p.village, p.district].filter(Boolean).join(", ")) + "</span>" : "") +
            (feature.geometry ? "" : '<span class="muted">Batas belum dipetakan</span>') +
            "</div></div></li>";
        }).join("");
      }
      if (fit) {
        var bounds = plotLayer.getBounds();
        if (bounds.isValid()) { map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 }); }
      }
      syncButtons();
      writeUrl();
    }

    function legend(zonesCount) {
      var seen = {};
      var html = "";
      features.forEach(function (f) {
        var p = f.properties;
        if (p.sector && !seen[p.sector]) {
          seen[p.sector] = true;
          html += '<span style="--c:' + escapeHtml(p.color) + '">' + escapeHtml(p.sector_name) + "</span>";
        }
      });
      html += '<span style="--c:#94a3b8">Sudah terikat / belum ditawarkan</span>';
      if (zonesCount) { html += '<span class="zone">Batas kawasan</span>'; }
      $("#map-legend").innerHTML = html;
      var box = $("#map-legend-box");
      // Di ponsel legenda dilipat agar tidak menutupi peta.
      if (box && window.matchMedia && window.matchMedia("(max-width: 900px)").matches) { box.open = false; }
    }

    listEl.addEventListener("click", function (event) {
      if (event.target.closest("[data-reset]")) { return; }
      var item = event.target.closest("[data-code]");
      if (!item) { return; }
      var code = item.dataset.code;
      if (layersByCode[code]) {
        select(code, true);
      } else {
        var feature = features.filter(function (f) { return f.properties.code === code; })[0];
        if (feature) { window.location.href = feature.properties.url; }
      }
    });
    listEl.addEventListener("keydown", function (event) {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-code]")) {
        event.preventDefault();
        event.target.click();
      }
    });
    listEl.addEventListener("mouseover", function (event) {
      var item = event.target.closest("[data-code]");
      if (item) { highlight(item.dataset.code, true); }
    });
    listEl.addEventListener("mouseout", function (event) {
      var item = event.target.closest("[data-code]");
      if (item) { highlight(item.dataset.code, false); }
    });

    var typing;
    $("[data-filter=q]", root).addEventListener("input", function (event) {
      clearTimeout(typing);
      typing = setTimeout(function () { state.q = event.target.value.trim(); render(false); }, 150);
    });
    ["kawasan", "kecamatan", "urut"].forEach(function (key) {
      $("[data-filter=" + key + "]", root).addEventListener("change", function (event) {
        state[key] = event.target.value;
        render(key !== "urut");
      });
    });
    ["min", "max"].forEach(function (key) {
      $("[data-filter=" + key + "]", root).addEventListener("input", function (event) {
        var value = event.target.value;
        state[key] = value === "" || isNaN(Number(value)) ? "" : value;
        render(false);
      });
    });
    ["siap", "dokumen", "semua", "simpan"].forEach(function (key) {
      var box = $("[data-filter=" + key + "]", root);
      if (box) {
        box.addEventListener("change", function () { state[key] = box.checked; render(true); });
      }
    });
    $$("[data-scheme]", root).forEach(function (button) {
      button.addEventListener("click", function () { state.scheme = button.dataset.scheme; render(true); });
    });
    $$("[data-sector]", root).forEach(function (button) {
      button.addEventListener("click", function () {
        var slug = button.dataset.sector;
        var index = state.sectors.indexOf(slug);
        if (index === -1) { state.sectors.push(slug); } else { state.sectors.splice(index, 1); }
        render(true);
      });
    });
    root.addEventListener("click", function (event) {
      if (!event.target.closest("[data-reset]")) { return; }
      state = { q: "", scheme: "", sectors: [], kawasan: "", kecamatan: "", min: "", max: "", siap: false, dokumen: false, semua: false, simpan: false, urut: "", selected: "" };
      $$("[data-filter]", root).forEach(function (el) {
        if (el.type === "checkbox") { el.checked = false; } else { el.value = ""; }
      });
      map.closePopup();
      render(true);
    });
    document.addEventListener("sl:saved", function (event) {
      var code = event.detail.code;
      var index = saved.indexOf(code);
      if (event.detail.saved && index === -1) { saved.push(code); }
      if (!event.detail.saved && index !== -1) { saved.splice(index, 1); }
      if (state.simpan) { render(false); }
    });
    map.on("popupopen", function () { compare.refresh(); });

    loadData(root.dataset.url).then(function (data) {
      features = (data.plots && data.plots.features) || [];
      var zones = (data.zones && data.zones.features) || [];
      L.geoJSON(zones, {
        style: function () { return { color: "#0f172a", weight: 2, dashArray: "6 6", fill: true, fillOpacity: 0.03, interactive: true }; },
        onEachFeature: function (feature, layer) {
          var z = feature.properties;
          layer.bindTooltip(escapeHtml(z.name), { permanent: true, direction: "center", className: "zone-label" });
          layer.bindPopup('<strong>' + escapeHtml(z.name) + "</strong>" + (z.summary ? "<br>" + escapeHtml(z.summary) : "") +
            '<br><a href="' + encodeURI(z.url) + '">Profil kawasan</a>');
        }
      }).eachLayer(function (layer) { layer.addTo(zoneLayer); });
      zoneLayer.bringToBack();
      legend(zones.length);
      render(true);
      if (!plotLayer.getBounds().isValid() && zoneLayer.getBounds().isValid()) {
        map.fitBounds(zoneLayer.getBounds(), { padding: [30, 30] });
      }
      if (state.selected && layersByCode[state.selected]) { select(state.selected, true); }
    }).catch(function () {
      listEl.innerHTML = '<li class="empty-state">Data peta tidak dapat dimuat. Periksa koneksi lalu muat ulang halaman.</li>';
      countEl.textContent = "0";
    });
  }

  // ------------------------------------------------------------ Peta kawasan
  function initZoneMap(el) {
    var map = createMap(el, { scrollWheelZoom: false });
    L.control.layers(map._slBaseLayers, null, { position: "topright" }).addTo(map);
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    map.on("blur", function () { map.scrollWheelZoom.disable(); });
    var group = L.featureGroup().addTo(map);
    if (el.dataset.geometry) {
      try {
        L.geoJSON(JSON.parse(el.dataset.geometry), {
          style: { color: "#0f172a", weight: 2, dashArray: "6 6", fillOpacity: 0.04 }
        }).eachLayer(function (layer) { layer.addTo(group); });
      } catch (e) { /* batas tidak valid */ }
    }
    loadData(el.dataset.url).then(function (data) {
      var zone = el.dataset.zone;
      (data.plots.features || []).forEach(function (feature) {
        var p = feature.properties;
        if (p.zone !== zone || !feature.geometry) { return; }
        var color = p.available ? p.color : "#94a3b8";
        L.geoJSON(feature, { style: { color: color, weight: 2, fillColor: color, fillOpacity: 0.4 } })
          .bindTooltip(escapeHtml(p.code + " · " + p.name), { sticky: true })
          .on("click", function () { window.location.href = p.url; })
          .addTo(group);
      });
      if (group.getBounds().isValid()) { map.fitBounds(group.getBounds(), { padding: [20, 20], maxZoom: 16 }); }
    }).catch(function () { /* peta dasar tetap tampil */ });
  }

  // ------------------------------------------------------------ Simulasi biaya
  function initSimulator(el) {
    var scheme = $("[data-sim=scheme]", el);
    var years = $("[data-sim=years]", el);
    var total = $("[data-sim=total]", el);
    var perYear = $("[data-sim=per-year]", el);
    var hint = $("[data-sim=hint]", el);
    var area = el.dataset.area;
    var adminFee = el.dataset.adminFee || "0";

    function limits() {
      if (scheme.value === "sewa") {
        return { min: parseInt(el.dataset.leaseMin || "1", 10), max: parseInt(el.dataset.leaseMax || "99", 10), rate: el.dataset.leaseRate };
      }
      var term = parseInt(el.dataset.uwtTerm || "30", 10);
      return { min: term, max: term, rate: el.dataset.uwtRate };
    }

    function update(resetYears) {
      var lim = limits();
      years.min = String(lim.min);
      years.max = String(lim.max);
      years.readOnly = lim.min === lim.max;
      var value = parseInt(years.value, 10);
      if (resetYears || isNaN(value)) { value = lim.min; }
      value = Math.min(Math.max(value, lim.min), lim.max);
      years.value = String(value);
      var amount = multiplyMoney(area, lim.rate, value);
      var yearly = multiplyMoney(area, lim.rate, 1);
      total.textContent = rupiah(amount);
      perYear.textContent = rupiah(yearly) + " per tahun";
      if (hint) {
        hint.textContent = scheme.value === "sewa"
          ? "Masa sewa " + lim.min + (lim.max !== lim.min ? "–" + lim.max : "") + " tahun. Perkiraan, belum termasuk pajak."
          : "UWT untuk " + lim.min + " tahun" + (Number(adminFee) > 0 ? " + biaya administrasi " + rupiah(adminFee) : "") + ". Perkiraan.";
      }
    }

    scheme.addEventListener("change", function () { update(true); });
    years.addEventListener("input", function () { update(false); });
    update(true);
  }

  // ------------------------------------------------------------ Formulir minat
  function initPlotPicker(root) {
    var search = $("input[type=search]", root);
    var items = $$(".plot-option", root);
    if (!search) { return; }
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      items.forEach(function (item) {
        item.hidden = q !== "" && item.textContent.toLowerCase().indexOf(q) === -1;
      });
    });
  }

  function initDrawMap(el) {
    var input = document.getElementById(el.dataset.input);
    var status = $("[data-draw=status]");
    var startBtn = $("[data-draw=start]");
    var finishBtn = $("[data-draw=finish]");
    var undoBtn = $("[data-draw=undo]");
    var clearBtn = $("[data-draw=clear]");
    var map = createMap(el, { scrollWheelZoom: false, doubleClickZoom: false });
    L.control.layers(map._slBaseLayers, null, { position: "topright" }).addTo(map);
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    map.on("blur", function () { map.scrollWheelZoom.disable(); });
    var reference = L.featureGroup().addTo(map);
    var drawn = L.featureGroup().addTo(map);
    var points = [];
    var drawing = false;
    var line = null;
    var polygon = null;

    function setStatus(html) { if (status) { status.innerHTML = html; } }

    function redraw() {
      drawn.clearLayers();
      polygon = null;
      line = null;
      if (points.length >= 3 && !drawing) {
        polygon = L.polygon(points, { color: "#d97706", weight: 3, fillOpacity: 0.25 }).addTo(drawn);
      } else if (points.length) {
        line = L.polyline(points, { color: "#d97706", weight: 3, dashArray: "6 4" }).addTo(drawn);
        points.forEach(function (pt) { L.circleMarker(pt, { radius: 5, color: "#d97706", fillColor: "#fff", fillOpacity: 1, weight: 2 }).addTo(drawn); });
      }
      finishBtn.disabled = !drawing || points.length < 3;
      undoBtn.disabled = !drawing || !points.length;
      clearBtn.disabled = !points.length;
      startBtn.disabled = drawing;
    }

    function save() {
      if (points.length < 3) { input.value = ""; return; }
      var ring = points.map(function (pt) { return [Number(pt.lng.toFixed(7)), Number(pt.lat.toFixed(7))]; });
      ring.push(ring[0]);
      input.value = JSON.stringify({ type: "Polygon", coordinates: [ring] });
      var area = geodesicArea(points);
      setStatus("Usulan lokasi tergambar: sekitar <strong>" + (area / 10000).toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " ha</strong>. Kebutuhan luas diisi otomatis dari gambar bila dikosongkan.");
    }

    startBtn.addEventListener("click", function () {
      drawing = true;
      points = [];
      input.value = "";
      el.classList.add("is-drawing");
      setStatus("Klik di peta untuk menambah titik sudut, lalu tekan <strong>Selesai</strong> (minimal 3 titik).");
      redraw();
    });
    finishBtn.addEventListener("click", function () {
      drawing = false;
      el.classList.remove("is-drawing");
      redraw();
      save();
      if (polygon) { map.fitBounds(polygon.getBounds(), { padding: [30, 30], maxZoom: 17 }); }
    });
    undoBtn.addEventListener("click", function () { points.pop(); redraw(); });
    clearBtn.addEventListener("click", function () {
      drawing = false;
      points = [];
      input.value = "";
      el.classList.remove("is-drawing");
      setStatus("Belum ada usulan lokasi yang digambar.");
      redraw();
    });
    map.on("click", function (event) {
      if (!drawing) { return; }
      if (points.length >= 500) { return; }
      points.push(event.latlng);
      redraw();
    });

    // Gambar yang sudah ada (formulir dikirim ulang karena ada kesalahan).
    if (input.value) {
      try {
        var geometry = JSON.parse(input.value);
        var ring = geometry.type === "Polygon" ? geometry.coordinates[0] : geometry.coordinates[0][0];
        points = ring.slice(0, -1).map(function (c) { return L.latLng(c[1], c[0]); });
        redraw();
        save();
        if (polygon) { map.fitBounds(polygon.getBounds(), { padding: [30, 30], maxZoom: 17 }); }
      } catch (e) { input.value = ""; }
    } else {
      redraw();
    }

    // Lahan tersedia sebagai acuan; klik lahan untuk mencentangnya di daftar.
    if (el.dataset.url) {
      loadData(el.dataset.url).then(function (data) {
        (data.plots.features || []).forEach(function (feature) {
          var p = feature.properties;
          if (!feature.geometry) { return; }
          var color = p.available ? p.color : "#94a3b8";
          L.geoJSON(feature, { style: { color: color, weight: 1.5, fillColor: color, fillOpacity: 0.25 } })
            .bindTooltip(escapeHtml(p.code + " · " + p.name + (p.available ? "" : " (" + p.status_label + ")")), { sticky: true })
            .on("click", function (event) {
              if (drawing) { points.push(event.latlng); redraw(); return; }
              var box = document.querySelector('.plot-option input[data-code="' + CSS.escape(p.code) + '"]');
              if (box && !box.disabled) {
                box.checked = !box.checked;
                box.dispatchEvent(new Event("change", { bubbles: true }));
              }
            })
            .addTo(reference);
        });
        if (!points.length && reference.getBounds().isValid()) {
          map.fitBounds(reference.getBounds(), { padding: [20, 20], maxZoom: 15 });
        }
      }).catch(function () { /* peta dasar tetap tampil */ });
    }
  }

  function initOriginToggle() {
    var origin = document.getElementById("id_capital_origin");
    var country = document.getElementById("field-origin_country");
    if (!origin || !country) { return; }
    function toggle() { country.hidden = origin.value !== "pma"; }
    origin.addEventListener("change", toggle);
    toggle();
  }

  function initSelectedCount() {
    var counter = $("[data-selected-count]");
    if (!counter) { return; }
    function update() {
      counter.textContent = String($$(".plot-option input:checked").length);
    }
    document.addEventListener("change", function (event) {
      if (event.target.closest(".plot-option")) { update(); }
    });
    update();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sync = $("[data-compare-sync]");
    if (sync) {
      // Tautan perbandingan yang dibagikan menjadi daftar bandingkan pengunjung.
      storageSet(COMPARE_KEY, sync.dataset.compareSync.split(",").filter(Boolean).slice(0, MAX_COMPARE));
    }
    compare.refresh();
    $$("[data-simulator]").forEach(initSimulator);
    $$(".plot-picker").forEach(initPlotPicker);
    initOriginToggle();
    initSelectedCount();
    if (typeof L === "undefined") { return; }
    L.Icon.Default.imagePath = document.body.dataset.leafletImages || "";
    var explorer = document.getElementById("explorer");
    if (explorer) { initExplorer(explorer); }
    $$("[data-map=zone]").forEach(initZoneMap);
    $$("[data-map=draw]").forEach(initDrawMap);
  });

  window.addEventListener("storage", function (event) {
    if (event.key === COMPARE_KEY) { compare.refresh(); }
  });
})();
