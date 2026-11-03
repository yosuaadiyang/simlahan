from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.forms import OSMWidget
from django.contrib.staticfiles import finders
from django.test import RequestFactory

from utils.gis_widgets import OL_JS


def _media_paths(media):
    return list(media._js) + [path for paths in media._css.values() for path in paths]


def test_map_widget_media_is_local_and_files_exist():
    """Peta isian geometri tidak boleh bergantung pada CDN luar."""
    paths = _media_paths(OSMWidget().media)
    assert OL_JS in paths
    for path in paths:
        assert "://" not in path
        found = finders.find(path)
        assert found, path
        # Tanpa rujukan source map: berkas .map tidak disertakan.
        if path.endswith(".js"):
            assert "sourceMappingURL" not in Path(found).read_text()


def _geometry_admin_forms(request):
    for model, model_admin in admin.site._registry.items():
        geometry_fields = [
            field.name
            for field in model._meta.get_fields()
            if isinstance(field, gis_models.GeometryField)
        ]
        if geometry_fields and model_admin.has_add_permission(request):
            yield model, model_admin.get_form(request)(), geometry_fields


def test_every_admin_map_is_local_osm_centred_on_configured_area(admin_user):
    request = RequestFactory().get("/")
    request.user = admin_user
    checked = 0
    for model, form, geometry_fields in _geometry_admin_forms(request):
        external = [path for path in _media_paths(form.media) if "://" in path]
        assert external == [], model.__name__
        for name in geometry_fields:
            if name not in form.fields:
                continue
            widget = form.fields[name].widget
            label = f"{model.__name__}.{name}"
            assert isinstance(widget, OSMWidget), label
            assert widget.attrs["default_lat"] == settings.MAP_CENTER_LAT, label
            assert widget.attrs["default_lon"] == settings.MAP_CENTER_LNG, label
            assert widget.attrs["default_zoom"] == settings.MAP_DEFAULT_ZOOM, label
            checked += 1
    assert checked
