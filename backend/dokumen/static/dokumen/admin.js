/* Muat ulang formulir saat templat diganti agar isian khusus templat itu muncul. */
(function () {
  "use strict";
  var form = document.querySelector("form[data-reload-field]");
  if (!form) return;
  var field = form.querySelector('[name="' + form.getAttribute("data-reload-field") + '"]');
  if (!field) return;
  field.addEventListener("change", function () {
    if (!field.value) return;
    var url = new URL(window.location.href);
    url.searchParams.set("templat", field.value);
    window.location.assign(url.toString());
  });
})();
