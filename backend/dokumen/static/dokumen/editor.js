/* Editor dokumen sederhana (contenteditable) untuk templat & dokumen tanda tangan.
   Textarea asli tetap menjadi sumber yang dikirim; isi dibersihkan ulang di server. */
(function () {
  "use strict";

  var BUTTONS = [
    ["bold", "B", "Tebal"],
    ["italic", "I", "Miring"],
    ["underline", "U", "Garis bawah"],
    ["h2", "H2", "Judul"],
    ["h3", "H3", "Subjudul"],
    ["p", "¶", "Paragraf"],
    ["insertUnorderedList", "• Daftar", "Daftar berbutir"],
    ["insertOrderedList", "1. Daftar", "Daftar bernomor"],
    ["justifyLeft", "Kiri", "Rata kiri"],
    ["justifyCenter", "Tengah", "Rata tengah"],
    ["justifyFull", "Rata", "Rata kiri-kanan"],
    ["table", "Tabel", "Sisipkan tabel 2×2"],
    ["hr", "—", "Garis pemisah"],
    ["source", "HTML", "Lihat/ubah kode HTML"]
  ];

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text) node.textContent = text;
    return node;
  }

  function setup(textarea) {
    if (textarea.dataset.dkReady) return;
    textarea.dataset.dkReady = "1";
    var readonly = textarea.disabled || textarea.readOnly;
    var wrap = el("div", { "class": "dk-editor" });
    var bar = el("div", { "class": "dk-editor-bar", role: "toolbar", "aria-label": "Format dokumen" });
    var area = el("div", { "class": "dk-editor-area dk-paper", contenteditable: readonly ? "false" : "true", role: "textbox", "aria-multiline": "true", "aria-label": "Isi dokumen" });
    area.innerHTML = textarea.value;
    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(bar);
    wrap.appendChild(area);
    wrap.appendChild(textarea);
    textarea.classList.add("dk-editor-hidden");
    var sourceMode = false;

    function sync() {
      if (!sourceMode) textarea.value = area.innerHTML;
    }

    function insertHtml(html) {
      area.focus();
      document.execCommand("insertHTML", false, html);
      sync();
    }

    if (!readonly) {
      BUTTONS.forEach(function (b) {
        var btn = el("button", { type: "button", title: b[2], "aria-label": b[2], "data-cmd": b[0] }, b[1]);
        bar.appendChild(btn);
      });
      var fields = [];
      try { fields = JSON.parse(textarea.getAttribute("data-fields") || "[]"); } catch (e) { fields = []; }
      if (fields.length) {
        var select = el("select", { "aria-label": "Sisipkan isian otomatis" });
        select.appendChild(el("option", { value: "" }, "＋ Sisipkan isian…"));
        fields.forEach(function (group) {
          var og = el("optgroup", { label: group.label });
          group.fields.forEach(function (f) { og.appendChild(el("option", { value: f.key }, f.label)); });
          select.appendChild(og);
        });
        var custom = el("option", { value: "__isian" }, "Isian bebas (diisi saat membuat dokumen)…");
        select.appendChild(custom);
        select.addEventListener("change", function () {
          var key = select.value;
          select.value = "";
          if (!key) return;
          if (key === "__isian") {
            var name = window.prompt("Nama isian (huruf kecil, angka, garis bawah), mis. batas_waktu:");
            if (!name) return;
            name = name.trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
            if (!name) return;
            key = "isian." + name;
          }
          if (sourceMode) {
            var pos = textarea.selectionStart || textarea.value.length;
            textarea.value = textarea.value.slice(0, pos) + "{{ " + key + " }}" + textarea.value.slice(pos);
          } else {
            insertHtml("{{ " + key + " }}");
          }
        });
        bar.appendChild(select);
      }
      bar.addEventListener("click", function (event) {
        var btn = event.target.closest("button[data-cmd]");
        if (!btn) return;
        var cmd = btn.getAttribute("data-cmd");
        if (cmd === "source") {
          sourceMode = !sourceMode;
          if (sourceMode) {
            textarea.value = area.innerHTML;
          } else {
            area.innerHTML = textarea.value;
          }
          textarea.classList.toggle("dk-editor-hidden", !sourceMode);
          area.hidden = sourceMode;
          btn.classList.toggle("active", sourceMode);
          bar.querySelectorAll("button[data-cmd]:not([data-cmd=source])").forEach(function (b) { b.disabled = sourceMode; });
          return;
        }
        area.focus();
        if (cmd === "h2" || cmd === "h3" || cmd === "p") {
          document.execCommand("formatBlock", false, cmd === "p" ? "P" : cmd.toUpperCase());
        } else if (cmd === "table") {
          insertHtml('<table style="width:100%;border-collapse:collapse"><tbody><tr><td style="border:1px solid #999;padding:4px">&nbsp;</td><td style="border:1px solid #999;padding:4px">&nbsp;</td></tr><tr><td style="border:1px solid #999;padding:4px">&nbsp;</td><td style="border:1px solid #999;padding:4px">&nbsp;</td></tr></tbody></table><p><br></p>');
        } else if (cmd === "hr") {
          insertHtml("<hr><p><br></p>");
        } else {
          document.execCommand(cmd, false, null);
        }
        sync();
      });
    }
    area.addEventListener("input", sync);
    area.addEventListener("blur", sync);
    var form = textarea.form;
    if (form) {
      form.addEventListener("submit", function () {
        if (!sourceMode) textarea.value = area.innerHTML;
      });
    }
  }

  function init() {
    document.querySelectorAll("textarea.dk-editor-source").forEach(setup);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
