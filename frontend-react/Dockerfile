# ── Build stage: produce the static Vite bundle ──
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
# VITE_API_URL is baked into the bundle at build time. The browser calls this
# origin for every REST/SSE request; it must be the same origin the app is
# served from so the nginx layer can reverse-proxy /auth, /chat, /topics, … to
# the gateway (single-origin → no CORS).
ARG VITE_API_URL=http://localhost:89
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Serve stage: nginx serves the SPA and proxies the API to the gateway ──
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# nginx.conf is mounted from ./gateway/frontend-react.conf via docker-compose.
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
