# ==========================================
# 第一阶段：前端构建 (Builder)
# ==========================================
FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend

# 1. 复制 package.json 并安装依赖
COPY package.json package-lock.json* ./
# 使用国内源，防止 build 卡死
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --legacy-peer-deps

# 2. 复制源码并执行构建
COPY . .
# 这里会生成 dist 目录
RUN npm run build

# ==========================================
# 第二阶段：后端运行 (Runtime)
# ==========================================
FROM python:3.12-slim
WORKDIR /app

# 1. 安装系统依赖和 Nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx procps dos2unix \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/nginx/sites-enabled/default

# 2. 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && pip install gunicorn

# 3. 复制代码
COPY backend/ .

# 4. ★关键★：把第一阶段做好的 dist 放入 Nginx 目录
RUN rm -rf /usr/share/nginx/html/*
COPY --from=frontend-builder /app-frontend/dist /usr/share/nginx/html

# 5. 复制配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY start.sh /start.sh
RUN dos2unix /start.sh && chmod +x /start.sh

# 6. 设置目录权限
RUN mkdir -p /data/strm /data/logs
VOLUME ["/data", "/data/strm"]

EXPOSE 18080
CMD ["/start.sh"]