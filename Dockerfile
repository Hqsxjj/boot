FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# 安装依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    procps \
    dos2unix \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/nginx/sites-enabled/default

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn && \
    echo "Verifying p115client installation..." && \
    python -c "import p115client; print('p115client version:', p115client.__version__)" || echo "Warning: p115client not installed"

# 复制后端代码
COPY backend/ .

# 设置前端静态文件
RUN rm -rf /usr/share/nginx/html/*
COPY --from=frontend-builder /app-frontend/dist /usr/share/nginx/html

# 配置 Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制启动脚本
COPY start.sh /start.sh
RUN dos2unix /start.sh && chmod +x /start.sh

# 创建必要的目录
RUN mkdir -p /data/strm /data/logs

# 设置数据卷
VOLUME ["/data"]

# 暴露端口
EXPOSE 18080

# 元数据
LABEL maintainer="HQSxcj"
LABEL description="Boot - 云盘媒体管理工具"

# 启动脚本
CMD ["/start.sh"]