#!/usr/bin/env bash
# Perkecil gambar HP (lebar 1170 px -> 585 px) dan kompres semua PNG.
# Butuh: python3 + Pillow, pngquant.
set -euo pipefail
cd "$(dirname "$0")/../gambar"
python3 - <<'PY'
import glob
from PIL import Image
for f in glob.glob("*/*.png"):
    im = Image.open(f)
    if 1100 <= im.width <= 1200:  # gambar HP (iPhone 13, skala 3)
        im.resize((im.width // 2, round(im.height / 2)), Image.LANCZOS).save(f)
PY
find . -name '*.png' -print0 | xargs -0 -n 20 pngquant --force --skip-if-larger --strip --quality 70-95 --ext .png || true
