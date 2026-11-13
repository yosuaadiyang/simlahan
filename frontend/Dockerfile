# syntax=docker/dockerfile:1
# ==============================================================
# SimLahan frontend – build Vite lalu disajikan oleh nginx yang
# juga meneruskan /v1, /admin, /static dst. ke backend.
# ==============================================================
# Base image dipin digest agar build selalu menarik bit yang sama (tag bisa
# diarahkan ulang hulu). Perbarui digest saat naik versi/rilis keamanan.
FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS build

WORKDIR /app
RUN corepack enable

COPY package.json yarn.lock .yarnrc.yml ./
COPY apps/leasing/package.json apps/leasing/
RUN yarn install --immutable

COPY . .
# Variabel VITE_* dibaca saat build (lihat apps/leasing/.env.example).
ARG VITE_API_URL=""
ARG VITE_APP_NAME="SimLahan"
ARG VITE_ORGANIZATION_NAME="Sistem Informasi Manajemen Lahan"
ARG VITE_MAP_CENTER_LAT=""
ARG VITE_MAP_CENTER_LNG=""
ARG VITE_MAP_DEFAULT_ZOOM=""
ARG VITE_PRIMARY_MUNICIPALITY=""
ARG VITE_MAP_WMS_URL=""
ARG VITE_MAP_WMS_LAYERS=""
ARG VITE_MAP_WMS_NAME=""
ARG VITE_FLAG_PLOTSEARCH="false"
ARG VITE_SENTRY_DSN=""
ENV VITE_API_URL=$VITE_API_URL \
    VITE_APP_NAME=$VITE_APP_NAME \
    VITE_ORGANIZATION_NAME=$VITE_ORGANIZATION_NAME \
    VITE_MAP_CENTER_LAT=$VITE_MAP_CENTER_LAT \
    VITE_MAP_CENTER_LNG=$VITE_MAP_CENTER_LNG \
    VITE_MAP_DEFAULT_ZOOM=$VITE_MAP_DEFAULT_ZOOM \
    VITE_PRIMARY_MUNICIPALITY=$VITE_PRIMARY_MUNICIPALITY \
    VITE_MAP_WMS_URL=$VITE_MAP_WMS_URL \
    VITE_MAP_WMS_LAYERS=$VITE_MAP_WMS_LAYERS \
    VITE_MAP_WMS_NAME=$VITE_MAP_WMS_NAME \
    VITE_FLAG_PLOTSEARCH=$VITE_FLAG_PLOTSEARCH \
    VITE_SENTRY_DSN=$VITE_SENTRY_DSN
RUN yarn build

# Nginx non-root: kontainer tidak berjalan sebagai root. Template & envsubst
# tetap didukung; port internal 8080 (non-root tak boleh memakai port < 1024),
# dipetakan compose ke HTTP_PORT.
FROM nginxinc/nginx-unprivileged:1.30-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03 AS production
USER nginx
COPY --chown=nginx:nginx docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8080
EXPOSE 8080
