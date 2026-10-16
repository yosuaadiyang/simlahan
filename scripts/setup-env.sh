#!/usr/bin/env sh
# Membuat berkas .env dari .env.example dengan rahasia acak.
# Pemakaian: ./scripts/setup-env.sh   (tidak menimpa .env yang sudah ada)
set -eu
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env sudah ada – tidak diubah."
  exit 0
fi

rand() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-"$1"; }
fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

SECRET_KEY=$(rand 60)
FIELD_KEY=$(fernet)
DB_PASSWORD=$(rand 32)
ADMIN_PASSWORD=$(rand 16)

sed \
  -e "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" \
  -e "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=${FIELD_KEY}|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" \
  -e "s|^DJANGO_SUPERUSER_PASSWORD=.*|DJANGO_SUPERUSER_PASSWORD=${ADMIN_PASSWORD}|" \
  .env.example > .env
chmod 600 .env

echo "Berkas .env dibuat."
echo "  Admin awal : admin"
echo "  Kata sandi : ${ADMIN_PASSWORD}"
echo "Simpan FIELD_ENCRYPTION_KEY di .env dengan aman – tanpa kunci ini data NIK/rekening tidak dapat dibaca."
