"""Bantuan service worker (PWA) pusat komando dan aplikasi lapangan."""

import functools
import hashlib

from django.contrib.staticfiles import finders


@functools.lru_cache(maxsize=None)
def shell_version(base: str, *paths: str) -> str:
    """Versi cache cangkang PWA: ``base`` ditambah sidik isi berkas statis.

    Cangkang (JS/CSS) disajikan cache-first oleh service worker, jadi versinya
    harus berganti setiap kali isi berkasnya berubah; bila tidak, perangkat
    yang sudah memasang aplikasi terus memakai JS lama setelah pembaruan.
    """
    digest = hashlib.sha256()
    for path in paths:
        found = finders.find(path)
        if found:
            with open(found, "rb") as handle:
                digest.update(handle.read())
    return f"{base}-{digest.hexdigest()[:12]}"
