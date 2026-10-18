"""Asisten AI: tanya jawab data lahan dalam bahasa sehari-hari.

Bila ``ANTHROPIC_API_KEY`` diisi, Claude menjawab dengan memanggil fungsi
kueri di bawah ini (hanya baca, mengikuti izin & unit layanan pengguna).
Tanpa kunci API, pertanyaan dicocokkan dengan pola kalimat umum.
"""

import logging
import re

from django.db.models import Count, Q, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from asetlahan import ai, enums, monitoring, scope
from asetlahan.models import EncroachmentCase, Grievance, LandAsset, LandTransaction, LegalCase, ModuleSettings, Task

LOG = logging.getLogger(__name__)

MAX_ROWS = 50
MAX_TURNS = 6

EXAMPLES = [
    "Sewa mana saja yang berakhir dalam 6 bulan ke depan?",
    "Tampilkan kasus okupasi yang belum ditindaklanjuti 30 hari",
    "Jadwal sidang minggu ini",
    "Pajak yang jatuh tempo 30 hari lagi",
    "Tugas saya yang terlambat",
    "Ringkasan portofolio aset",
    "Aset di Kelurahan Sembulang",
]


def _link(name, pk) -> str:
    try:
        return reverse(name, args=[pk])
    except NoReverseMatch:
        return ""


def _table(title, headers, items, row, url_name="") -> dict:
    items = list(items[:MAX_ROWS])
    return {
        "title": title,
        "headers": headers,
        "rows": [[str(v) if v not in (None, "") else "-" for v in row(o)] for o in items],
        "links": [_link(url_name, o.pk) if url_name else "" for o in items],
    }


def _denied(title) -> dict:
    return {"title": title, "headers": [], "rows": [], "links": [], "note": "Anda tidak memiliki akses ke data ini."}


def _flag(name) -> bool:
    return getattr(ModuleSettings.load(), name)


# --------------------------------------------------------------------------
# Fungsi kueri (dipakai Claude dan pencocok pola)
# --------------------------------------------------------------------------


def leases_ending(user, days=180):
    title = f"Sewa berakhir dalam {days} hari"
    if not user.has_perm("leasing.view_lease"):
        return _denied(title)
    return _table(title, ["Nomor sewa", "Jenis", "Kab/kota", "Berakhir"], monitoring.leases_ending(days, user),
                  lambda o: [o.identifier, o.type, o.municipality, o.end_date], "admin:leasing_lease_change")


def encroachments(user, stale_days=0):
    title = "Okupasi terbuka" + (f" tanpa tindak lanjut > {stale_days} hari" if stale_days else "")
    if not user.has_perm("asetlahan.view_encroachmentcase") or not _flag("enable_encroachment"):
        return _denied(title)
    if stale_days:
        queryset = monitoring.stale_encroachments(stale_days, user)
    else:
        queryset = scope.scoped(EncroachmentCase.objects.filter(status__in=enums.OPEN_ENCROACHMENT_STATUSES),
                                user).select_related("asset")
    return _table(title, ["Nomor", "Temuan", "Aset", "Status", "Ditemukan", "Luas (m²)"], queryset,
                  lambda o: [o.number, o.title, o.asset.code if o.asset_id else "", o.get_status_display(),
                             o.detected_on, o.encroached_area_m2], "admin:asetlahan_encroachmentcase_change")


def hearings(user, days=7):
    title = f"Sidang dalam {days} hari"
    if not user.has_perm("asetlahan.view_casehearing") or not _flag("enable_litigation"):
        return _denied(title)
    return _table(title, ["Jadwal", "Perkara", "Agenda", "Tempat"], monitoring.hearings_upcoming(days, user),
                  lambda o: [timezone.localtime(o.scheduled_at).strftime("%d-%m-%Y %H:%M"), o.case, o.agenda,
                             o.location])


def taxes(user, days=30):
    title = f"Pajak jatuh tempo ≤ {days} hari (termasuk terlambat)"
    if not user.has_perm("asetlahan.view_taxobligation") or not _flag("enable_valuation"):
        return _denied(title)
    return _table(title, ["Aset", "Jenis", "Periode", "Jumlah", "Jatuh tempo"], monitoring.taxes_due(days, user),
                  lambda o: [o.asset.code, o.get_tax_type_display(), o.period, o.amount, o.due_date],
                  "admin:asetlahan_taxobligation_change")


def tasks(user, mine=False, overdue=False):
    title = "Tugas" + (" saya" if mine else "") + (" lewat tenggat" if overdue else " terbuka")
    if not user.has_perm("asetlahan.view_task") or not _flag("enable_tasks"):
        return _denied(title)
    queryset = scope.scoped(Task.objects.filter(status__in=enums.OPEN_TASK_STATUSES), user).select_related("assignee")
    if mine:
        queryset = queryset.filter(assignee=user)
    if overdue:
        queryset = queryset.filter(due_date__lt=timezone.localdate())
    return _table(title, ["Nomor", "Judul", "Petugas", "Status", "Tenggat", "Progres"], queryset,
                  lambda o: [o.number, o.title, o.assignee, o.get_status_display(), o.due_date, f"{o.progress}%"],
                  "admin:asetlahan_task_change")


def grievances(user, overdue=False):
    title = "Pengaduan " + ("lewat batas" if overdue else "terbuka")
    if not user.has_perm("asetlahan.view_grievance") or not _flag("enable_grievance"):
        return _denied(title)
    queryset = scope.scoped(Grievance.objects.filter(status__in=enums.OPEN_GRIEVANCE_STATUSES), user)
    if overdue:
        queryset = queryset.filter(due_date__lt=timezone.localdate())
    return _table(title, ["Nomor", "Perihal", "Pelapor", "Status", "Batas"], queryset,
                  lambda o: [o.number, o.subject, o.complainant_name, o.get_status_display(), o.due_date],
                  "admin:asetlahan_grievance_change")


def legal_cases(user, open_only=True, keyword=""):
    title = "Perkara " + ("aktif" if open_only else "")
    if not user.has_perm("asetlahan.view_legalcase") or not _flag("enable_litigation"):
        return _denied(title)
    queryset = scope.scoped(LegalCase.objects.all(), user)
    if open_only:
        queryset = queryset.filter(status__in=enums.OPEN_CASE_STATUSES)
    if keyword:
        queryset = queryset.filter(Q(title__icontains=keyword) | Q(opposing_party__icontains=keyword)
                                   | Q(court_case_number__icontains=keyword))
    return _table(title.strip(), ["Nomor", "Nomor perkara", "Pokok perkara", "Status", "Hasil"], queryset,
                  lambda o: [o.number, o.court_case_number, o.title, o.get_status_display(), o.get_outcome_display()],
                  "admin:asetlahan_legalcase_change")


ASSET_FILTERS = {"status": "status", "village": "village__icontains", "district": "district__icontains",
                 "category": "category__name__icontains", "owner": "registered_owner__icontains"}


def assets(user, title_expiring_days=0, **filters):
    title = "Aset lahan"
    if not user.has_perm("asetlahan.view_landasset"):
        return _denied(title)
    queryset = scope.scoped(LandAsset.objects.all(), user).select_related("category")
    for key, lookup in ASSET_FILTERS.items():
        if filters.get(key):
            queryset = queryset.filter(**{lookup: filters[key]})
    if title_expiring_days:
        title = f"Aset dengan hak berakhir ≤ {title_expiring_days} hari"
        queryset = monitoring.titles_expiring(title_expiring_days, user)
    summary = queryset.aggregate(n=Count("id"), area=Sum("area_m2"))
    table = _table(title, ["Kode", "Nama", "Status", "Luas (m²)", "Alas hak", "Hak berakhir", "Kelurahan"], queryset,
                   lambda o: [o.code, o.name, o.get_status_display(), o.area_m2,
                              f"{o.get_title_type_display()} {o.title_number}".strip(), o.title_expiry, o.village],
                   "admin:asetlahan_landasset_change")
    table["note"] = f"Jumlah {summary['n']} aset, total luas {summary['area'] or 0:,.2f} m²."
    return table


def portfolio(user):
    title = "Ringkasan portofolio"
    if not user.has_perm("asetlahan.view_landasset"):
        return _denied(title)
    rows = []
    queryset = scope.scoped(LandAsset.objects.all(), user)
    labels = dict(enums.AssetStatus.choices)
    for row in queryset.values("status").annotate(n=Count("id"), area=Sum("area_m2")).order_by("-n"):
        rows.append([str(labels.get(row["status"], row["status"])), str(row["n"]), f"{row['area'] or 0:,.2f}"])
    total = queryset.aggregate(n=Count("id"), area=Sum("area_m2"))
    rows.append(["Total", str(total["n"]), f"{total['area'] or 0:,.2f}"])
    return {"title": title, "headers": ["Status", "Jumlah", "Luas (m²)"], "rows": rows, "links": [""] * len(rows)}


def finance(user, year=None):
    year = year or timezone.localdate().year
    title = f"Keuangan lahan {year}"
    if not user.has_perm("asetlahan.view_landtransaction") or not _flag("enable_valuation"):
        return _denied(title)
    labels = dict(enums.TransactionType.choices)
    queryset = scope.scoped(LandTransaction.objects.filter(date__year=year), user)
    rows = [
        [str(labels[r["transaction_type"]]), "Masuk" if r["transaction_type"] in enums.INCOME_TYPES else "Keluar",
         f"{r['s']:,.0f}"]
        for r in queryset.values("transaction_type").annotate(s=Sum("amount")).order_by("-s")
    ]
    return {"title": title, "headers": ["Jenis", "Arah", "Jumlah (Rp)"], "rows": rows, "links": [""] * len(rows)}


def search(user, keyword):
    from asetlahan.admin_views import search_all

    groups = search_all(user, keyword, limit=10)
    rows, links = [], []
    for group in groups:
        for item in group["items"]:
            rows.append([group["label"], item["text"], item["snippet"][:160]])
            links.append(item["url"])
    return {"title": f"Hasil pencarian “{keyword}”", "headers": ["Data", "Judul", "Kutipan"], "rows": rows[:MAX_ROWS],
            "links": links[:MAX_ROWS]}


# --------------------------------------------------------------------------
# Definisi alat untuk Claude
# --------------------------------------------------------------------------


def _schema(properties: dict | None = None) -> dict:
    return {"type": "object", "properties": properties or {}, "additionalProperties": False}


INT = {"type": "integer", "minimum": 1, "maximum": 3650}
BOOL = {"type": "boolean"}
STR = {"type": "string", "maxLength": 200}

TOOLS = [
    {"name": "sewa_berakhir", "description": "Kontrak sewa yang berakhir dalam sejumlah hari ke depan.",
     "input_schema": _schema({"hari": INT})},
    {"name": "okupasi", "description": "Kasus okupasi/perambahan terbuka; isi tanpa_tindak_lanjut_hari untuk yang "
                                       "tidak ada tindakan selama N hari.",
     "input_schema": _schema({"tanpa_tindak_lanjut_hari": INT})},
    {"name": "jadwal_sidang", "description": "Jadwal sidang perkara dalam N hari ke depan.",
     "input_schema": _schema({"hari": INT})},
    {"name": "pajak_jatuh_tempo", "description": "Pajak/retribusi belum dibayar yang jatuh tempo dalam N hari "
                                                 "atau sudah terlambat.",
     "input_schema": _schema({"hari": INT})},
    {"name": "tugas", "description": "Tugas terbuka; milik_saya untuk tugas pengguna ini, terlambat untuk yang lewat "
                                     "tenggat.",
     "input_schema": _schema({"milik_saya": BOOL, "terlambat": BOOL})},
    {"name": "pengaduan", "description": "Pengaduan masyarakat terbuka; terlambat untuk yang lewat batas waktu.",
     "input_schema": _schema({"terlambat": BOOL})},
    {"name": "perkara", "description": "Perkara/litigasi; hanya_aktif untuk yang masih berjalan, kata_kunci opsional.",
     "input_schema": _schema({"hanya_aktif": BOOL, "kata_kunci": STR})},
    {"name": "aset", "description": "Daftar aset lahan dengan filter opsional (status kode: "
                                    + ", ".join(enums.AssetStatus.values) + "), kelurahan, kecamatan, kategori, "
                                    "pemegang hak, atau hak yang berakhir dalam N hari.",
     "input_schema": _schema({"status": {"type": "string", "enum": list(enums.AssetStatus.values)},
                              "kelurahan": STR, "kecamatan": STR, "kategori": STR, "pemegang_hak": STR,
                              "hak_berakhir_hari": INT})},
    {"name": "ringkasan_portofolio", "description": "Jumlah dan luas aset per status penguasaan.",
     "input_schema": _schema()},
    {"name": "keuangan", "description": "Penerimaan & pengeluaran lahan per jenis transaksi dalam satu tahun.",
     "input_schema": _schema({"tahun": {"type": "integer", "minimum": 2000, "maximum": 2100}})},
    {"name": "cari", "description": "Pencarian teks lintas modul (aset, dokumen termasuk isi OCR, perkara, okupasi, "
                                    "pengaduan, pengadaan, alokasi, sewa).",
     "input_schema": {**_schema({"kata_kunci": STR}), "required": ["kata_kunci"]}},
]


def _int(value, default, low=1, high=3650):
    try:
        return min(max(int(value), low), high)
    except (TypeError, ValueError):
        return default


def run_tool(user, name: str, args: dict) -> dict:
    args = args if isinstance(args, dict) else {}
    handlers = {
        "sewa_berakhir": lambda: leases_ending(user, _int(args.get("hari"), 180)),
        "okupasi": lambda: encroachments(user, _int(args.get("tanpa_tindak_lanjut_hari"), 0, 0)),
        "jadwal_sidang": lambda: hearings(user, _int(args.get("hari"), 7)),
        "pajak_jatuh_tempo": lambda: taxes(user, _int(args.get("hari"), 30)),
        "tugas": lambda: tasks(user, bool(args.get("milik_saya")), bool(args.get("terlambat"))),
        "pengaduan": lambda: grievances(user, bool(args.get("terlambat"))),
        "perkara": lambda: legal_cases(user, args.get("hanya_aktif", True) is not False,
                                       str(args.get("kata_kunci") or "")[:200]),
        "aset": lambda: assets(
            user, _int(args.get("hak_berakhir_hari"), 0, 0), status=args.get("status") or "",
            village=args.get("kelurahan") or "", district=args.get("kecamatan") or "",
            category=args.get("kategori") or "", owner=args.get("pemegang_hak") or ""),
        "ringkasan_portofolio": lambda: portfolio(user),
        "keuangan": lambda: finance(user, _int(args.get("tahun"), None, 2000, 2100)),
        "cari": lambda: search(user, str(args.get("kata_kunci") or "")[:200]),
    }
    if name not in handlers:
        return {"title": name, "headers": [], "rows": [], "links": [], "note": "Fungsi tidak dikenal."}
    return handlers[name]()


def _table_text(table: dict) -> str:
    lines = [table["title"]]
    if table.get("note"):
        lines.append(table["note"])
    if table["headers"]:
        lines.append(" | ".join(table["headers"]))
    lines.extend(" | ".join(row) for row in table["rows"])
    if not table["rows"] and not table.get("note"):
        lines.append("(tidak ada data)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Jawaban dengan Claude
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """Anda adalah asisten sistem informasi manajemen lahan (SimLahan) untuk petugas instansi \
pengelola lahan. Jawab dalam bahasa Indonesia yang ringkas dan jelas.

Gunakan fungsi yang tersedia untuk mengambil data; jangan mengarang angka, nama, atau tanggal. Jika data tidak \
ditemukan atau pengguna tidak memiliki akses, katakan apa adanya. Tabel hasil fungsi sudah ditampilkan kepada \
pengguna di bawah jawaban Anda, jadi cukup rangkum temuan utama dan tindak lanjut yang disarankan. \
Tanggal hari ini: {today}."""


def _history_messages(history) -> list:
    messages = []
    for turn in history[-5:]:
        if turn.get("q") and turn.get("answer"):
            messages.append({"role": "user", "content": turn["q"]})
            messages.append({"role": "assistant", "content": turn["answer"]})
    return messages


def _answer_with_ai(user, question: str, history) -> dict:
    messages = _history_messages(history) + [{"role": "user", "content": question}]
    tables = []
    system = SYSTEM_PROMPT.format(today=timezone.localdate().isoformat())
    for _turn in range(MAX_TURNS):
        response = ai.create(max_tokens=8000, system=system, tools=TOOLS, messages=messages)
        if response.stop_reason != "tool_use":
            return {"answer": ai.text_of(response), "tables": tables, "source": "ai"}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            table = run_tool(user, block.name, block.input)
            tables.append(table)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": _table_text(table)})
        messages.append({"role": "user", "content": results})
    return {"answer": "Pertanyaan terlalu kompleks; silakan persempit pertanyaan.", "tables": tables, "source": "ai"}


# --------------------------------------------------------------------------
# Pencocok pola (tanpa AI)
# --------------------------------------------------------------------------

UNITS = {"hari": 1, "minggu": 7, "pekan": 7, "bulan": 30, "tahun": 365}


def _days(text: str, default: int) -> int:
    if match := re.search(r"(\d+)\s*(hari|minggu|pekan|bulan|tahun)", text):
        return int(match[1]) * UNITS[match[2]]
    if match := re.search(r"(minggu|pekan|bulan|tahun)\s+(ini|depan)", text):
        return UNITS[match[1]]
    return default


RULES = (
    (r"\bsewa\b", lambda u, t: leases_ending(u, _days(t, 180))),
    (r"okupasi|perambahan|penyerobotan|diserobot",
     lambda u, t: encroachments(u, _days(t, 30) if re.search(r"tindak\s*lanjut|lama|belum", t) else 0)),
    (r"sidang", lambda u, t: hearings(u, _days(t, 7))),
    (r"pajak|pbb|retribusi|bphtb", lambda u, t: taxes(u, _days(t, 30))),
    (r"tugas|pekerjaan", lambda u, t: tasks(u, "saya" in t, bool(re.search(r"terlambat|lewat", t)))),
    (r"pengaduan|keluhan|aduan", lambda u, t: grievances(u, bool(re.search(r"terlambat|lewat", t)))),
    (r"perkara|gugatan|litigasi|sengketa", lambda u, t: legal_cases(u, "semua" not in t)),
    (r"(hak|sertipikat|sertifikat|hgb|hgu).*(berakhir|habis)",
     lambda u, t: assets(u, _days(t, 180))),
    (r"keuangan|transaksi|penerimaan|pengeluaran|pendapatan|biaya", lambda u, t: finance(u)),
    (r"ringkasan|portofolio|total aset|berapa (banyak )?aset|jumlah aset", lambda u, t: portfolio(u)),
    (r"(kelurahan|desa)\s+([a-z][a-z .'-]+)", lambda u, t: assets(
        u, village=re.search(r"(?:kelurahan|desa)\s+([a-z][a-z .'-]+)", t)[1].strip())),
    (r"kecamatan\s+([a-z][a-z .'-]+)", lambda u, t: assets(
        u, district=re.search(r"kecamatan\s+([a-z][a-z .'-]+)", t)[1].strip())),
)

STOPWORDS = {"cari", "carikan", "tampilkan", "daftar", "apa", "yang", "mana", "saja", "di", "ke", "dari", "dan",
             "untuk", "data", "tolong", "dong", "ada", "berapa", "semua", "dengan"}


def _answer_with_rules(user, question: str) -> dict:
    text = question.lower()
    for pattern, handler in RULES:
        if re.search(pattern, text):
            table = handler(user, text)
            break
    else:
        words = [w for w in re.findall(r"[\w./-]+", text) if w not in STOPWORDS]
        table = search(user, " ".join(words[:4]) or question[:50])
    count = len(table["rows"])
    answer = table.get("note") or (f"Ditemukan {count} data." if count else "Tidak ada data yang cocok.")
    if count == MAX_ROWS:
        answer += f" Ditampilkan {MAX_ROWS} teratas."
    return {"answer": answer, "tables": [table], "source": "aturan"}


def answer(user, question: str, history=None) -> dict:
    history = history or []
    if ai.enabled():
        try:
            return _answer_with_ai(user, question, history)
        except ai.AIError as error:
            result = _answer_with_rules(user, question)
            result["error"] = f"{error} Jawaban di bawah memakai pencocokan pola."
            return result
    return _answer_with_rules(user, question)

