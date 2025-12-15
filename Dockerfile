FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    dos2unix \
    gcc \
    python3-dev \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn

RUN pip install --no-cache-dir p115client p123client

COPY backend/ .
COPY --from=frontend-builder /app-frontend/dist /app/static
COPY start.sh /start.sh
RUN dos2unix /start.sh && chmod +x /start.sh
RUN mkdir -p /data/strm /data/logs

VOLUME ["/data"]
EXPOSE 18080

LABEL maintainer="HQSxcj"
LABEL description="Boot - 云盘媒体管理工具"

CMD ["/start.sh"]