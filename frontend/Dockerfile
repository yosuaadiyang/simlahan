# syntax=docker/dockerfile:1
# ==============================================================
# SimLahan frontend – build Vite lalu disajikan oleh nginx yang
# juga meneruskan /v1, /admin, /static dst. ke backend.
# ==============================================================
FROM node:24-alpine AS build

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

FROM nginx:1.27-alpine AS production
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_URL=http://backend:8080
EXPOSE 80
