#!/bin/bash
# Titik masuk kontainer backend SimLahan.
#   api       : migrasi (opsional) + bootstrap + uWSGI
#   qcluster  : pekerja tugas latar (laporan, email)
#   batchrun  : penjadwal tugas berkala (mis. notifikasi tenggat pengadaan)
#   manage    : jalankan perintah manage.py, mis. `manage createsuperuser`
set -e

wait_for_db() {
    python - <<'PY'
import os, sys, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvj.settings")
django.setup()
from django.db import connection
for attempt in range(60):
    try:
        connection.ensure_connection()
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Menunggu basis data… ({exc.__class__.__name__})", flush=True)
        time.sleep(2)
sys.exit("Basis data tidak dapat dihubungi.")
PY
}

case "$1" in
    api)
        wait_for_db
        if [[ "${APPLY_MIGRATIONS:-1}" = "1" ]]; then
            python manage.py migrate --noinput
        fi
        # Tabel cache bersama (pembatas percobaan login, kunci darurat komando).
        python manage.py createcachetable
        if [[ "${RUN_BOOTSTRAP:-1}" = "1" ]]; then
            python manage.py simlahan_bootstrap
        fi
        exec uwsgi --ini deploy/uwsgi.ini
        ;;
    qcluster)
        wait_for_db
        exec python manage.py qcluster
        ;;
    batchrun)
        wait_for_db
        exec python manage.py batchrun_scheduler
        ;;
    manage)
        shift
        exec python manage.py "$@"
        ;;
    *)
        exec "$@"
        ;;
esac
