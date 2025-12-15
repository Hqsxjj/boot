# 使用多阶段构建
# 阶段1: 构建前端
FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

# 阶段2: Python 运行环境（单体架构，无 Nginx）
FROM python:3.11-slim
WORKDIR /app

# 安装必要依赖（包含编译工具，用于安装某些 Python 包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    dos2unix \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn

# 尝试安装 p115client 和 p123client（可选，部分平台可能不支持）
RUN pip install --no-cache-dir p115client p123client || \
    echo "⚠️ Warning: p115client/p123client installation failed. 115/123 cloud features may be limited."

# 验证安装状态（仅打印日志，不中断构建）
RUN python -c "import p115client; print('✅ p115client version:', p115client.__version__)" || echo "❌ p115client not available"
RUN python -c "import p123client; print('✅ p123client installed')" || echo "❌ p123client not available"

# 复制后端代码
COPY backend/ .

# 前端静态文件 → /app/static（Flask 直接服务）
COPY --from=frontend-builder /app-frontend/dist /app/static

# 复制启动脚本
COPY start.sh /start.sh
RUN dos2unix /start.sh && chmod +x /start.sh

# 创建必要的目录
RUN mkdir -p /data/strm /data/logs

# 设置数据卷
VOLUME ["/data"]

# 暴露端口（Gunicorn 直接服务）
EXPOSE 18080

# 元数据
LABEL maintainer="HQSxcj"
LABEL description="Boot - 云盘媒体管理工具 (单体架构)"

# 启动脚本
CMD ["/start.sh"]