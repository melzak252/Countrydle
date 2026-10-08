# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

RUN apk add --no-cache python3 chromium
ENV CHROME_BIN=/usr/bin/chromium-browser

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build args
ARG VITE_API_URL=/api
ARG VITE_RYBBIT_SCRIPT_URL
ARG VITE_RYBBIT_SITE_ID
ARG VITE_GOOGLE_ADSENSE_ID
# CI images render static destinations without requiring a live backend.
# Opt into post snapshots with PRERENDER_STATIC_ONLY=0 and a matched local build-network API.
ARG PRERENDER_STATIC_ONLY=1
ARG PRERENDER_API_TARGET

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_RYBBIT_SCRIPT_URL=$VITE_RYBBIT_SCRIPT_URL
ENV VITE_RYBBIT_SITE_ID=$VITE_RYBBIT_SITE_ID
ENV VITE_GOOGLE_ADSENSE_ID=$VITE_GOOGLE_ADSENSE_ID
ENV PRERENDER_STATIC_ONLY=$PRERENDER_STATIC_ONLY
ENV PRERENDER_API_TARGET=$PRERENDER_API_TARGET

RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
