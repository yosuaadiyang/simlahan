#!/usr/bin/env bash
# Perkecil gambar HP baru (lebar 1170 px -> 585 px) lalu kompres dengan pngquant.
# Hanya gambar yang belum dikompres (PNG non-palet) yang diproses, jadi aman
# dijalankan berulang setelah mengambil ulang sebagian gambar.
# Butuh: python3 + Pillow, pngquant.
set -euo pipefail
cd "$(dirname "$0")/../gambar"
python3 - <<'PY' | xargs -0 -r -n 20 pngquant --force --skip-if-larger --strip --quality 70-95 --ext .png || true
import glob
import sys
from PIL import Image
for f in sorted(glob.glob("*/*.png")):
    im = Image.open(f)
    if im.mode == "P":
        continue  # sudah dikompres
    if 1100 <= im.width <= 1200:  # gambar HP (iPhone 13, skala 3)
        im = im.resize((im.width // 2, round(im.height / 2)), Image.LANCZOS)
        im.save(f)
    sys.stdout.write(f + "\0")
PY
