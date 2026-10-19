# Web Studio: static Vite build served by nginx, which also proxies /v1 to the orchestrator.
FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Empty base URL = same origin: the browser calls /v1/... and nginx forwards it to the orchestrator
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine
ENV ORCHESTRATOR_UPSTREAM=http://orchestrator:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 80
