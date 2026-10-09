# Build only the immutable SPA. Public data is required at runtime, never faked
# during an image build or fetched using production credentials.
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
COPY . .

ARG VITE_API_URL=/api
ARG VITE_RYBBIT_SCRIPT_URL
ARG VITE_RYBBIT_SITE_ID
ARG VITE_GOOGLE_ADSENSE_ID
ARG VITE_ADSENSE_ENABLED=false
ARG VITE_ADSENSE_SLOTS={}

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_RYBBIT_SCRIPT_URL=$VITE_RYBBIT_SCRIPT_URL
ENV VITE_RYBBIT_SITE_ID=$VITE_RYBBIT_SITE_ID
ENV VITE_GOOGLE_ADSENSE_ID=$VITE_GOOGLE_ADSENSE_ID
ENV VITE_ADSENSE_ENABLED=$VITE_ADSENSE_ENABLED
ENV VITE_ADSENSE_SLOTS=$VITE_ADSENSE_SLOTS

RUN npm run build && cp dist/index.html dist/spa-shell.html

FROM nginx:alpine
RUN apk add --no-cache python3 py3-websocket-client chromium
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV PUBLISHER_BACKEND_URL=http://backend:8080
ENV PUBLISHER_ORIGIN=https://countrydle.online
ENV PUBLISHER_POLL_SECONDS=60
ENV PUBLISHER_CAPTURE_TIMEOUT=45

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY scripts/prerender.py scripts/publisher-runtime.py /usr/local/lib/countrydle/
COPY scripts/publisher-entrypoint.sh /usr/local/bin/publisher-entrypoint.sh

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
ENTRYPOINT ["/bin/sh", "/usr/local/bin/publisher-entrypoint.sh"]
