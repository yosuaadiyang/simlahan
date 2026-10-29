/* Halaman masuk pusat komando: lihat sandi, peringatan Caps Lock, cegah kirim ganda. */
(function () {
  "use strict";
  var sandi = document.getElementById("id_password");
  var lihat = document.getElementById("lihat-sandi");
  var caps = document.getElementById("capslock");
  if (sandi && lihat) {
    lihat.addEventListener("click", function () {
      var tampil = sandi.type === "password";
      sandi.type = tampil ? "text" : "password";
      lihat.textContent = tampil ? "Sembunyikan" : "Lihat";
      lihat.setAttribute("aria-pressed", tampil ? "true" : "false");
      sandi.focus();
    });
  }
  if (sandi && caps) {
    var cek = function (event) {
      if (event.getModifierState) { caps.hidden = !event.getModifierState("CapsLock"); }
    };
    sandi.addEventListener("keydown", cek);
    sandi.addEventListener("keyup", cek);
    sandi.addEventListener("blur", function () { caps.hidden = true; });
  }
  var form = document.querySelector("form");
  if (form) {
    form.addEventListener("submit", function () {
      var tombol = form.querySelector(".tombol");
      if (tombol) { tombol.disabled = true; tombol.textContent = "Memproses…"; }
    });
  }
})();
