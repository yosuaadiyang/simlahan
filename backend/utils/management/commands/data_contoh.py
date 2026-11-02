"""Satu perintah untuk seluruh data contoh SimLahan.

python manage.py data_contoh                 # buat semua (aman diulang)
python manage.py data_contoh --sandi '...'   # sama, dengan satu sandi akun contoh
python manage.py data_contoh --cek           # periksa tabel yang masih kosong
python manage.py data_contoh --hapus         # = hapus_data_contoh

Menjalankan perintah data contoh tiap modul dengan urutan yang benar (lahan &
proyek dulu, lalu akun contoh beserta permohonannya, lalu dokumen izin yang
merujuk akun & alokasi). Setiap perintah idempoten: bagian yang sudah ada
dilewati, bagian yang belum ada dilengkapi.

Semua data fiktif dan bertanda jelas (``[CONTOH]``, ``[contoh]``,
``CONTOH-...``, surel ``@contoh.simlahan.invalid``). ``cek_produksi``
mendeteksinya dan ``hapus_data_contoh`` menghapusnya.
"""

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

SAMPLE_COMMANDS = (
    "pengadaan_contoh_rempang",
    "alokasi_contoh_rempang",
    "asetlahan_contoh_rempang",
    "operasi_contoh_rempang",
    "sewa_contoh_rempang",
    "pengguna_contoh",
    "dokumen_contoh_rempang",
)

# Aplikasi SimLahan yang diperiksa --cek.
CHECKED_APPS = (
    "users",
    "forms",
    "leasing",
    "plotsearch",
    "audittrail",
    "field_permissions",
    "batchrun",
    "utils",
    "file_operations",
    "pengadaan",
    "alokasi",
    "asetlahan",
    "operasi",
    "dokumen",
)

PLOTSEARCH_OFF = (
    "fitur pencarian kavling & kompetisi nonaktif (FLAG_PLOTSEARCH=False); "
    "menunya tidak tampil"
)

# Tabel yang sengaja tidak diisi data contoh, beserta alasannya.
NOT_SAMPLED = {
    # Data acuan resmi / konfigurasi: mengisinya dengan angka fiktif akan
    # mengubah perhitungan atau tampilan data sungguhan.
    "leasing.Index": "indeks biaya hidup resmi, dipakai perhitungan sewa",
    "leasing.LegacyIndex": "indeks biaya hidup lama (resmi)",
    "leasing.IndexPointFigureYearly": "angka indeks tahunan resmi",
    "leasing.OldDwellingsInHousingCompaniesPriceIndex": "indeks harga resmi",
    "leasing.InterestRate": "suku bunga resmi untuk denda keterlambatan",
    "leasing.CollectionLetterTemplate": "templat surat resmi instansi",
    "leasing.ServiceUnitGroupMapping": "konfigurasi pemetaan grup unit layanan",
    "leasing.VipunenMapLayer": "konfigurasi lapisan peta",
    "leasing.UiData": "teks bantuan antarmuka yang ditulis admin",
    "operasi.ActivityWeight": "bobot poin resmi; contoh akan mengubah peringkat",
    "operasi.SystemLock": "tombol darurat; tidak boleh dinyalakan contoh",
    "operasi.ImportedRecord": "jejak impor_komando; terisi saat data lama dipindah",
    # Hasil impor dari sistem lain (tidak dibuat lewat aplikasi).
    "leasing.Area": "hasil impor batas wilayah dari sistem GIS",
    "leasing.AreaSource": "sumber impor batas wilayah",
    "leasing.DetailedPlan": "hasil impor rencana detail tata ruang",
    "leasing.LeaseholdTransfer": "hasil impor peralihan hak dari kantor pertanahan",
    "leasing.LeaseholdTransferParty": "hasil impor peralihan hak",
    "leasing.LeaseholdTransferProperty": "hasil impor peralihan hak",
    "leasing.LeaseholdTransferImportLog": "log impor peralihan hak",
    # Dihitung/ditulis sistem saat berjalan.
    "leasing.PayableRent": "tabel lama; sewa terhutang kini disimpan di sewa",
    "leasing.EqualizedRent": "tabel lama perataan sewa",
    "leasing.IndexAdjustedRent": "dihitung untuk sewa berindeks; contoh memakai sewa tetap",
    "leasing.EmailLog": "log surel terkirim; data contoh tidak mengirim surel",
    "leasing.ReportStorage": "berkas laporan yang dibuat saat laporan diminta",
    "batchrun.JobRun": "log tugas terjadwal, terisi saat tugas berjalan",
    "batchrun.JobRunLog": "log tugas terjadwal",
    "batchrun.JobRunLogEntry": "log tugas terjadwal",
    "users.LoginOTP": "kode masuk sekali pakai, berlaku beberapa menit",
    "file_operations.FileScanStatus": "pemindaian virus nonaktif (FLAG_FILE_SCAN)",
    "file_operations.GenericAttachmentTestModel": "model khusus pengujian",
    "file_operations.GenericSafeDeleteAttachmentTestModel": "model khusus pengujian",
    # Pencarian kavling & kompetisi (nonaktif).
    "plotsearch.PlotSearch": PLOTSEARCH_OFF,
    "plotsearch.PlotSearchTarget": PLOTSEARCH_OFF,
    "plotsearch.TargetStatus": PLOTSEARCH_OFF,
    "plotsearch.TargetInfoLink": PLOTSEARCH_OFF,
    "plotsearch.MeetingMemo": PLOTSEARCH_OFF,
    "plotsearch.ProposedFinancingManagement": PLOTSEARCH_OFF,
    "plotsearch.DirectReservationLink": PLOTSEARCH_OFF,
    "plotsearch.Favourite": PLOTSEARCH_OFF,
    "plotsearch.FavouriteTarget": PLOTSEARCH_OFF,
    "plotsearch.FAQ": PLOTSEARCH_OFF,
    "plotsearch.RelatedPlotApplication": PLOTSEARCH_OFF,
    "forms.Attachment": PLOTSEARCH_OFF,
    "forms.AnswerOpeningRecord": PLOTSEARCH_OFF,
}


def _manager(model):
    return getattr(model, "all_objects", model._base_manager)


def coverage():
    """(kosong, dikecualikan) – daftar label model."""
    empty, excluded = [], []
    for label in CHECKED_APPS:
        for model in apps.get_app_config(label).get_models():
            if model._meta.proxy or not model._meta.managed:
                continue
            name = model._meta.label
            if _manager(model).exists():
                continue
            (excluded if name in NOT_SAMPLED else empty).append(name)
    return sorted(empty), sorted(excluded)


class Command(BaseCommand):
    help = (
        "Buat seluruh data contoh SimLahan (fiktif) di semua modul, periksa "
        "cakupannya (--cek), atau hapus semuanya (--hapus)."
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--hapus", action="store_true", help="Hapus data contoh")
        group.add_argument(
            "--cek",
            action="store_true",
            help="Daftar tabel yang masih kosong (gagal bila ada yang belum terisi)",
        )
        parser.add_argument(
            "--sandi",
            help="Satu sandi untuk semua akun contoh (diteruskan ke pengguna_contoh).",
        )

    def handle(self, *args, **options):
        if options["hapus"]:
            call_command("hapus_data_contoh", stdout=self.stdout, stderr=self.stderr)
            return
        if options["cek"]:
            self._check()
            return
        for command in SAMPLE_COMMANDS:
            self.stdout.write(self.style.MIGRATE_HEADING(command))
            arguments = []
            if command == "pengguna_contoh" and options["sandi"]:
                arguments = ["--sandi", options["sandi"]]
            call_command(command, *arguments, stdout=self.stdout, stderr=self.stderr)
        self.stdout.write(
            self.style.SUCCESS(
                "Data contoh lengkap. Periksa cakupan: python manage.py data_contoh "
                "--cek. Sebelum dibuka untuk publik: python manage.py "
                "hapus_data_contoh"
            )
        )

    def _check(self):
        empty, excluded = coverage()
        if excluded:
            self.stdout.write("Sengaja tanpa data contoh:")
            for name in excluded:
                self.stdout.write(f"  - {name}: {NOT_SAMPLED[name]}")
        if getattr(settings, "FLAG_PLOTSEARCH", False):
            self.stdout.write(
                self.style.WARNING(
                    "FLAG_PLOTSEARCH aktif: pencarian kavling belum punya data contoh."
                )
            )
        if empty:
            raise CommandError(
                "Tabel tanpa data: "
                + ", ".join(empty)
                + ". Jalankan: python manage.py data_contoh"
            )
        self.stdout.write(self.style.SUCCESS("Semua tabel SimLahan berisi data."))
