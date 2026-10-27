"""Matriks hak akses modul dokumen & perizinan per grup pengguna.

Diterapkan lewat ``set_group_model_permissions`` (otomatis oleh
``simlahan_bootstrap``). Pemegang hak tidak masuk grup mana pun; mereka memakai
portal /portal/dokumen/ yang memeriksa kepemilikan data sendiri.

- Administrator: semua, termasuk pengaturan, persetujuan dokumen sebelum dikirim,
  dan persetujuan unduhan dokumen rahasia.
- Petugas Alokasi Lahan: mengelola pemanfaatan lahan, jenis dokumen, templat,
  verifikasi, dokumen tanda tangan, dan menyetujui unduhan dokumen biasa.
- Tim Verifikasi Teknis: membaca dan memverifikasi dokumen perizinan.
- Petugas Hukum: menyusun templat dan dokumen tanda tangan (kontrak), membaca
  dokumen perizinan.
Siapa pun yang boleh melihat dokumen dapat mengajukan permintaan unduh; tidak ada
yang dapat mengunduh tanpa persetujuan orang lain.
"""

from dokumen.models import (
    Activity,
    ContentBlock,
    DocumentComment,
    DocumentRecipient,
    DocumentSettings,
    DocumentTemplate,
    DocumentVersion,
    DownloadLog,
    DownloadRequest,
    LandUse,
    PermitRecord,
    PermitType,
    SigningDocument,
)
from utils.group_permissions import UG, GroupModelPermissions

V = ("view",)
VC = ("view", "change")
VAC = ("view", "add", "change")
ALL = ("view", "add", "change", "delete")


def _roles(admin, officer, verifier, legal):
    return {
        "model": {
            UG.PAAKAYTTAJA: admin,
            UG.PETUGAS_ALOKASI: officer,
            UG.TIM_VERIFIKASI: verifier,
            UG.PETUGAS_HUKUM: legal,
        },
        "fields": {},
    }


VERIFY = ("verify_permitrecord",)
SEND = ("send_signingdocument",)

DOKUMEN_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    DocumentSettings: _roles(VC, V, None, None),
    ContentBlock: _roles(ALL, ALL, V, ALL),
    DocumentTemplate: _roles(ALL, ALL, V, ALL),
    PermitType: _roles(ALL, ALL, V, V),
    # Pemanfaatan lahan tidak dihapus dari panel: riwayat dokumennya ikut hilang.
    LandUse: _roles(VAC, VAC, V, V),
    PermitRecord: _roles(VAC + VERIFY, VAC + VERIFY, V + VERIFY, V),
    DocumentVersion: _roles(V, V, V, V),
    SigningDocument: _roles(
        ALL + SEND + ("approve_signingdocument",), ALL + SEND, V, ALL + SEND
    ),
    DocumentRecipient: _roles(ALL, ALL, V, ALL),
    DocumentComment: _roles(V, V, V, V),
    DownloadRequest: _roles(
        V + ("approve_downloadrequest", "approve_confidential_download"),
        V + ("approve_downloadrequest",),
        V,
        V,
    ),
    DownloadLog: _roles(V, V, None, None),
    Activity: _roles(V, V, V, V),
}
