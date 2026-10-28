"""Data contoh lahan alokasi di Pulau Rempang (fiktif, untuk uji coba portal).

python manage.py alokasi_contoh_rempang          # buat/perbarui
python manage.py alokasi_contoh_rempang --hapus  # hapus lahan contoh yang belum dimohonkan

Termasuk profil portal investasi: sektor, dua kawasan investasi contoh, lahan
yang dapat disewa, insentif, jarak, dan utilitas.
"""

from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction

from alokasi import enums
from alokasi.importers import area_m2
from alokasi.models import InvestmentSector, InvestmentZone, LandPlot

PREFIX = "CONTOH-RMP-"

# (kode, nama, jenis, lon, lat, ukuran derajat, kecamatan, kelurahan, arahan, tarif UWT/m²/tahun)
PLOTS = [
    (
        "01",
        "Kawasan Industri Rempang Blok A",
        "reguler",
        104.150,
        0.830,
        0.004,
        "Galang",
        "Rempang Cate",
        "Industri",
        1500,
    ),
    (
        "02",
        "Kawasan Industri Rempang Blok B",
        "reguler",
        104.156,
        0.830,
        0.003,
        "Galang",
        "Rempang Cate",
        "Industri",
        1500,
    ),
    (
        "03",
        "Kawasan Pariwisata Pantai Rempang",
        "terbuka",
        104.205,
        0.815,
        0.003,
        "Galang",
        "Sembulang",
        "Pariwisata",
        2000,
    ),
    (
        "04",
        "Kawasan Pergudangan dan Logistik",
        "reguler",
        104.140,
        0.860,
        0.0025,
        "Galang",
        "Rempang Cate",
        "Pergudangan",
        1200,
    ),
    (
        "05",
        "Fasilitas Umum dan Sosial",
        "langsung",
        104.175,
        0.845,
        0.0015,
        "Galang",
        "Sembulang",
        "Fasilitas umum",
        0,
    ),
    (
        "06",
        "Kawasan Perdagangan dan Jasa",
        "terbuka",
        104.165,
        0.800,
        0.002,
        "Galang",
        "Sembulang",
        "Perdagangan dan jasa",
        1800,
    ),
    (
        "07",
        "Gudang Sewa Logistik Rempang",
        "terbuka",
        104.146,
        0.866,
        0.0015,
        "Galang",
        "Rempang Cate",
        "Pergudangan",
        0,
    ),
    (
        "08",
        "Lahan Sewa Resor Pantai Sembulang",
        "terbuka",
        104.212,
        0.809,
        0.002,
        "Galang",
        "Sembulang",
        "Pariwisata",
        0,
    ),
]

ZONE_INDUSTRY = "contoh-kawasan-industri-logistik-rempang"
ZONE_TOURISM = "contoh-kawasan-pariwisata-pantai-rempang"

ZONES = {
    ZONE_INDUSTRY: {
        "name": "Kawasan Industri & Logistik Rempang (CONTOH)",
        "summary": "Kawasan industri ringan, pergudangan, dan logistik dekat jalan utama.",
        "description": "Data fiktif untuk uji coba portal investasi.",
        "incentives": "Perizinan terpadu daring\nTarif sewa awal untuk 2 tahun pertama\n"
        "Pendampingan petugas sampai kontrak",
        "infrastructure": "Jalan kawasan 2 lajur\nJaringan listrik 20 kV\nAir bersih",
        "box": (104.135, 0.825, 104.165, 0.872),
        "sectors": ("Industri", "Logistik & pergudangan"),
        "order": 1,
    },
    ZONE_TOURISM: {
        "name": "Kawasan Pariwisata Pantai Rempang (CONTOH)",
        "summary": "Pesisir pantai untuk resor, perhotelan, dan perdagangan pendukung.",
        "description": "Data fiktif untuk uji coba portal investasi.",
        "incentives": "Perizinan terpadu daring\nPromosi kawasan bersama",
        "infrastructure": "Jalan akses pantai\nJaringan listrik\nTelekomunikasi 4G",
        "box": (104.160, 0.795, 104.220, 0.822),
        "sectors": ("Pariwisata & perhotelan", "Perdagangan & jasa"),
        "order": 2,
    },
}

# kode → profil investasi (sektor, kawasan, sewa: (tarif, min, maks) atau None,
# alokasi dibuka?, keunggulan, jarak (pelabuhan, bandara, jalan, kota), unggulan)
PROFILES = {
    "01": (
        "Industri",
        ZONE_INDUSTRY,
        (9000, 5, 30),
        True,
        "Dekat jalan utama Trans-Barelang\nKontur datar",
        (12, 35, 0.5, 30),
        True,
    ),
    "02": (
        "Industri",
        ZONE_INDUSTRY,
        None,
        True,
        "Bersebelahan dengan Blok A",
        (12.5, 35, 0.8, 30),
        False,
    ),
    "03": (
        "Pariwisata & perhotelan",
        ZONE_TOURISM,
        (12000, 10, 30),
        True,
        "Garis pantai berpasir putih\nPemandangan laut lepas",
        (20, 45, 2, 40),
        True,
    ),
    "04": (
        "Logistik & pergudangan",
        ZONE_INDUSTRY,
        (7500, 3, 20),
        True,
        "Akses truk kontainer",
        (8, 32, 0.3, 28),
        False,
    ),
    "05": ("Fasilitas umum & sosial", None, None, True, "", (15, 40, 1, 35), False),
    "06": (
        "Perdagangan & jasa",
        ZONE_TOURISM,
        (10000, 2, 15),
        True,
        "Simpul permukiman baru",
        (18, 42, 0.2, 38),
        False,
    ),
    "07": (
        "Logistik & pergudangan",
        ZONE_INDUSTRY,
        (6500, 1, 10),
        False,
        "Siap pakai untuk gudang sementara",
        (7, 31, 0.2, 27),
        True,
    ),
    "08": (
        "Pariwisata & perhotelan",
        ZONE_TOURISM,
        (11000, 5, 25),
        False,
        "Teluk tenang untuk dermaga wisata",
        (21, 46, 1.5, 41),
        False,
    ),
}

SECTOR_STYLE = {
    "Industri": ("🏭", "#2563eb"),
    "Pariwisata & perhotelan": ("🏝️", "#0891b2"),
    "Perdagangan & jasa": ("🏬", "#d97706"),
    "Logistik & pergudangan": ("🚚", "#7c3aed"),
    "Fasilitas umum & sosial": ("🏫", "#64748b"),
}


def _box(x1, y1, x2, y2):
    return MultiPolygon(
        Polygon(((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1))), srid=4326
    )


def _sector(name):
    icon, color = SECTOR_STYLE[name]
    sector, _created = InvestmentSector.objects.get_or_create(
        name=name, defaults={"icon": icon, "color": color}
    )
    return sector


class Command(BaseCommand):
    help = "Buat atau hapus data contoh lahan alokasi Pulau Rempang (fiktif)"

    def add_arguments(self, parser):
        parser.add_argument("--hapus", action="store_true", help="Hapus lahan contoh")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["hapus"]:
            samples = LandPlot.objects.filter(code__startswith=PREFIX)
            plots = samples.filter(
                applications__isnull=True,
                investment_requests__isnull=True,
                investment_offers__isnull=True,
                land_uses__isnull=True,
            )
            pks = list(plots.values_list("pk", flat=True).distinct())
            kept = samples.exclude(pk__in=pks).count()
            LandPlot.objects.filter(pk__in=pks).delete()
            count = len(pks)
            zones = (
                InvestmentZone.objects.filter(slug__in=ZONES)
                .delete()[1]
                .get("alokasi.InvestmentZone", 0)
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{count} lahan contoh dan {zones} kawasan contoh dihapus."
                )
            )
            if kept:
                self.stdout.write(
                    self.style.WARNING(
                        f"{kept} lahan contoh dilewati karena masih dipakai permohonan, "
                        "permintaan investasi, atau pemanfaatan lahan (hapus "
                        "dokumen_contoh_rempang --hapus dahulu bila itu data contoh)."
                    )
                )
            return
        zones = {}
        for slug, data in ZONES.items():
            zone, _created = InvestmentZone.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": data["name"],
                    "summary": data["summary"],
                    "description": data["description"],
                    "incentives": data["incentives"],
                    "infrastructure": data["infrastructure"],
                    "geometry": _box(*data["box"]),
                    "order": data["order"],
                    "is_featured": True,
                    "is_published": True,
                },
            )
            zone.sectors.set([_sector(name) for name in data["sectors"]])
            zones[slug] = zone
        created = 0
        for code, name, kind, lon, lat, size, district, village, use, rate in PLOTS:
            geom = MultiPolygon(
                Polygon(
                    (
                        (lon, lat),
                        (lon + size, lat),
                        (lon + size, lat + size),
                        (lon, lat + size),
                        (lon, lat),
                    )
                ),
                srid=4326,
            )
            is_open = kind == enums.AllocationType.OPEN
            sector, zone, lease, allocation, highlights, dist, featured = PROFILES[code]
            port, airport, road, city = dist
            plot, was_created = LandPlot.objects.update_or_create(
                code=f"{PREFIX}{code}",
                defaults={
                    "name": f"{name} (CONTOH)",
                    "allocation_type": kind,
                    "district": district,
                    "village": village,
                    "area_m2": area_m2(geom),
                    "zoning": use,
                    "intended_use": use,
                    "uwt_rate_per_m2_year": Decimal(rate),
                    "has_technical_documents": is_open,
                    "land_preparation_done": is_open,
                    "description": "Data fiktif untuk uji coba portal. Hapus dengan --hapus.",
                    "geometry": geom,
                    "is_published": True,
                    "sector": _sector(sector),
                    "zone": zones.get(zone),
                    "offer_allocation": allocation,
                    "offer_lease": lease is not None,
                    "lease_rate_per_m2_year": Decimal(lease[0] if lease else 0),
                    "lease_min_years": lease[1] if lease else None,
                    "lease_max_years": lease[2] if lease else None,
                    "highlights": highlights,
                    "distance_port_km": Decimal(str(port)),
                    "distance_airport_km": Decimal(str(airport)),
                    "distance_road_km": Decimal(str(road)),
                    "distance_city_km": Decimal(str(city)),
                    "has_road_access": True,
                    "has_power": True,
                    "has_water": code != "05",
                    "has_telecom": code in ("03", "06", "08"),
                    "is_featured": featured,
                },
            )
            created += was_created
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} lahan contoh dibuat, {len(PLOTS) - created} diperbarui."
            )
        )
