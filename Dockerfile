# ==========================================
# 第一阶段：构建前端 (Builder)
# ==========================================
FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend

# 1. 前端依赖文件在项目根目录，直接复制
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

# 2. 复制根目录下所有文件（包含前端源码）
# 注意：这也会把 backend 文件夹拷进去，但没关系，npm run build 只会处理前端
COPY . .

# 3. 构建前端，生成 dist 目录
RUN npm run build

# ==========================================
# 第二阶段：构建后端 (Runtime)
# ==========================================
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. 安装 Nginx 和系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    procps \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. [关键] 从 backend 子目录复制依赖清单
# 这里的源路径是 backend/requirements.txt
COPY backend/requirements.txt .

# 3. 安装 Python 依赖 (强制安装 gunicorn)
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn

# 4. [关键] 将 backend 子目录下的所有代码，复制到容器的 /app 根目录
# 这样 main.py 就会变成 /app/main.py，而不是 /app/backend/main.py
# 这样 Gunicorn 才能直接找到 main:create_app()
COPY backend/ .

# 5. 部署前端静态文件 (从第一阶段复制)
RUN rm -rf /usr/share/nginx/html/*
COPY --from=frontend-builder /app-frontend/dist /usr/share/nginx/html

# 6. [关键] 复制根目录下的配置文件
# 因为 nginx.conf 和 start.sh 都在根目录，所以直接 COPY
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY start.sh /start.sh

# 7. 赋予脚本执行权限
RUN chmod +x /start.sh

# 8. 暴露端口
EXPOSE 80

# 9. 启动
CMD ["/start.sh"]
