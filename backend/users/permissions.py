from users.models import User
from utils.group_permissions import UG, GroupModelPermissions

USERS_GROUP_MODEL_PERMISSIONS: GroupModelPermissions = {
    User: {
        "model": {
            UG.SELAILIJA: ("view",),
            UG.VALMISTELIJA: ("view",),
            UG.SOPIMUSVALMISTELIJA: ("view",),
            UG.SYOTTAJA: ("view",),
            UG.PERINTALAKIMIES: ("view",),
            UG.LASKUTTAJA: ("view",),
            UG.PAAKAYTTAJA: ("view",),
            UG.PELAKSANA_PENGADAAN: ("view",),
            UG.SATGAS_PENGADAAN: ("view",),
            UG.PENILAI: ("view",),
            UG.INSTANSI_PEMOHON: ("view",),
        },
        "fields": {},
    },
}
