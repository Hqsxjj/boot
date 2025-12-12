# ==========================================
# 第一阶段：构建前端 (Builder)
# ==========================================
FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend

# 1. 前端依赖
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

# 2. 复制根目录所有文件 (包含前端源码)
COPY . .

# 3. 构建前端
RUN npm run build

# ==========================================
# 第二阶段：构建后端 (Runtime)
# ==========================================
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. 安装 Nginx 和系统依赖
# [关键修改] 在安装完后，立即删除 Nginx 的默认配置文件
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    procps \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/nginx/sites-enabled/default

# 2. 从 backend 子目录复制依赖清单
COPY backend/requirements.txt .

# 3. 安装 Python 依赖
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn

# 4. 复制代码 (main.py 等)
COPY backend/ .

# 5. 部署前端静态文件
RUN rm -rf /usr/share/nginx/html/*
COPY --from=frontend-builder /app-frontend/dist /usr/share/nginx/html

# 6. 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 7. 启动脚本
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80

CMD ["/start.sh"]