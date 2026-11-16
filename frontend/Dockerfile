# Сборка: Node 20 (в проекте зафиксированы версии, совместимые с 20.x)
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# Раздача: nginx со статикой и проксированием /api на бэкенд
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
