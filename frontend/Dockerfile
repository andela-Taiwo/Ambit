# syntax=docker/dockerfile:1.7
# The SPA is compiled at build time, so VITE_* values are baked into the
# bundle -- each environment builds its own image from the same Dockerfile.

FROM node:22-alpine AS builder
WORKDIR /app

COPY package.json yarn.lock ./
# --frozen-lockfile fails the build rather than silently resolving new versions.
RUN yarn install --frozen-lockfile

COPY . .
ARG VITE_API_BASE_URL
ARG VITE_SENTRY_DSN=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
RUN yarn build

# ---- runtime: static files behind nginx ------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
