"""Peta isian geometri di panel admin.

Widget peta bawaan Django:

* memuat OpenLayers dari cdn.jsdelivr.net, sehingga bila CDN itu lambat atau
  diblokir jaringan peta tidak muncul (``ol is not defined``) dan geometri
  tidak bisa diubah;
* membuka peta di Eropa (OSMWidget: bujur 5, lintang 47) atau di titik 0,0
  dengan latar citra NASA (OpenLayersWidget, dipakai setiap kolom geometri
  pada form admin biasa).

Di sini OpenLayers 7.2.2 (BSD-2) disajikan dari berkas statis SimLahan
sendiri, semua kolom geometri memakai peta OpenStreetMap, dan peta dibuka di
pusat peta yang dikonfigurasi (MAP_CENTER_LAT/LNG, MAP_DEFAULT_ZOOM; bawaan
Pulau Rempang).
"""

from django.conf import settings
from django.contrib.gis import forms as gis_forms

OL_CSS = "simlahan/vendor/ol/ol.css"
OL_JS = "simlahan/vendor/ol/ol.js"


class LocalOpenLayersMedia:
    css = {"all": (OL_CSS, "gis/css/ol3.css")}
    js = (OL_JS, "gis/js/OLMapWidget.js")


def install() -> None:
    # Media dibaca saat ``widget.media`` diakses, jadi berlaku untuk semua
    # turunan (OSMWidget, GISModelAdmin, form biasa).
    gis_forms.OpenLayersWidget.Media = LocalOpenLayersMedia
    # OSMWidget menyalin atribut kelas ini ke ``attrs`` saat dibuat.
    gis_forms.OSMWidget.default_lon = settings.MAP_CENTER_LNG
    gis_forms.OSMWidget.default_lat = settings.MAP_CENTER_LAT
    gis_forms.OSMWidget.default_zoom = settings.MAP_DEFAULT_ZOOM
    # Kolom geometri di form admin biasa (bukan GISModelAdmin) ikut memakai
    # peta OpenStreetMap, bukan citra NASA tanpa pusat.
    gis_forms.GeometryField.widget = gis_forms.OSMWidget
