"""Utilitas geometri bersama untuk semua impor peta."""


def force_2d(geom):
    """Buang koordinat Z (ketinggian) dari KML/GPS; kolom geometri basis data 2D."""
    if geom is None or not geom.hasz:
        return geom
    srid = geom.srid
    ogr = geom.ogr
    ogr.coord_dim = 2
    flat = ogr.geos
    flat.srid = srid
    return flat
