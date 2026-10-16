# syntax=docker/dockerfile:1
# ==============================================================
# SimLahan backend (Django + GeoDjango) – image produksi
# ==============================================================
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin libgdal32 libgeos-c1v5 libproj25 \
        gettext libpq5 \
        build-essential libpcre3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-prod.txt /app/
RUN pip install -r requirements.txt -r requirements-prod.txt \
    && apt-get purge -y --auto-remove build-essential libpcre3-dev

COPY . /app

# Kompilasi terjemahan & kumpulkan berkas statis saat build.
RUN DEBUG=1 SECRET_KEY=build-only DATABASE_URL=postgis://build@localhost/build \
        python manage.py compilemessages -l id -v0 \
    && DEBUG=1 SECRET_KEY=build-only DATABASE_URL=postgis://build@localhost/build \
        python manage.py collectstatic --noinput -v0

RUN useradd --system --uid 1000 --home /app simlahan \
    && mkdir -p /app/private_files /app/media \
    && chown -R simlahan /app/private_files /app/media

USER simlahan
EXPOSE 8080
ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
CMD ["api"]
