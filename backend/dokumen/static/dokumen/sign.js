/* Kotak tanda tangan: gambar (jari/tetikus/pena) atau ketik nama. Hasil PNG ke input tersembunyi. */
(function () {
  "use strict";
  var pad = document.querySelector("[data-sigpad]");
  if (!pad) return;
  var canvas = pad.querySelector("canvas");
  var ctx = canvas.getContext("2d");
  var input = pad.querySelector('input[name="signature"]');
  var useSaved = pad.querySelector('input[name="use_saved"]');
  var hint = pad.querySelector("[data-hint]");
  var form = document.getElementById("dk-sign-form");
  var nameInput = form ? form.querySelector('input[name="name"]') : null;
  var mode = "gambar";
  var drawing = false;
  var dirty = false;
  var last = null;

  function reset() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#0b1f4d";
    ctx.fillStyle = "#0b1f4d";
    dirty = false;
    input.value = "";
    if (useSaved) useSaved.value = "";
  }

  function saved(btn) {
    reset();
    var img = new Image();
    img.onload = function () {
      var scale = Math.min(canvas.width / img.width, canvas.height / img.height, 1);
      var w = img.width * scale;
      var h = img.height * scale;
      ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
    };
    img.src = btn.getAttribute("data-saved-src");
    dirty = true;
    if (useSaved) useSaved.value = "1";
  }

  function point(event) {
    var rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (canvas.width / rect.width),
      y: (event.clientY - rect.top) * (canvas.height / rect.height)
    };
  }

  function typed() {
    reset();
    var text = nameInput ? nameInput.value.trim() : "";
    if (!text) return;
    var size = 64;
    do {
      ctx.font = "italic " + size + "px 'Segoe Script', 'Brush Script MT', 'Lucida Handwriting', cursive";
      size -= 4;
    } while (ctx.measureText(text).width > canvas.width - 40 && size > 18);
    ctx.fillStyle = "#0b1f4d";
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);
    dirty = true;
  }

  canvas.addEventListener("pointerdown", function (event) {
    if (mode !== "gambar") return;
    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);
    drawing = true;
    last = point(event);
    ctx.beginPath();
    ctx.arc(last.x, last.y, 1.4, 0, Math.PI * 2);
    ctx.fill();
    dirty = true;
  });
  canvas.addEventListener("pointermove", function (event) {
    if (!drawing) return;
    var p = point(event);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach(function (name) {
    canvas.addEventListener(name, function () { drawing = false; });
  });

  pad.querySelector("[data-clear]").addEventListener("click", function () {
    reset();
    if (mode === "ketik") typed();
    if (mode === "tersimpan") {
      // Hapus berarti kembali menggambar sendiri.
      var draw = pad.querySelector('[data-mode="gambar"]');
      if (draw) draw.click();
    }
  });
  pad.querySelectorAll("[data-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      mode = btn.getAttribute("data-mode");
      pad.querySelectorAll("[data-mode]").forEach(function (b) {
        var on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      if (hint) {
        hint.textContent = mode === "ketik" ? "Tanda tangan dibuat dari nama lengkap Anda."
          : mode === "tersimpan" ? "Memakai tanda tangan tersimpan di akun Anda."
          : "Gambar tanda tangan di kotak di atas.";
      }
      canvas.style.cursor = mode === "gambar" ? "crosshair" : "default";
      if (mode === "ketik") { typed(); } else if (mode === "tersimpan") { saved(btn); } else { reset(); }
    });
  });
  if (nameInput) {
    nameInput.addEventListener("input", function () { if (mode === "ketik") typed(); });
  }
  if (form) {
    form.addEventListener("submit", function (event) {
      if (!dirty) {
        event.preventDefault();
        if (hint) { hint.textContent = "Bubuhkan tanda tangan terlebih dahulu."; hint.style.color = "#b91c1c"; }
        canvas.focus();
        return;
      }
      input.value = mode === "tersimpan" ? "" : canvas.toDataURL("image/png");
    });
  }
  reset();
})();
