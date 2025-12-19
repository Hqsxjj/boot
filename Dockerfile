FROM node:18-alpine as frontend-builder
WORKDIR /app-frontend
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    dos2unix \
    gcc \
    python3-dev \
    libc-dev \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

# Upgrade pip and install build tools for ARM64 compatibility
RUN pip install --upgrade pip setuptools wheel

# Install main requirements (excluding p115client/p123client for separate handling)
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    pip install gunicorn

# Install httpx with http2 support AND h2 explicitly (required for 123 cloud)
RUN pip install --no-cache-dir "httpx[http2]" h2

# Verify each package individually with detailed error output
RUN echo "=== Verifying httpx ===" && python -c "import httpx; print('httpx OK')" || echo "httpx FAILED"
RUN echo "=== Verifying h2 ===" && python -c "import h2; print('h2 OK')" || echo "h2 FAILED"
RUN echo "=== Verifying p115client ===" && python -c "import p115client; print('p115client OK')" || \
    (echo "p115client import failed, showing pip list:" && pip list | grep -i p115 && echo "Trying reinstall..." && pip install --no-cache-dir --verbose p115client 2>&1 || echo "p115client REINSTALL ALSO FAILED")
RUN echo "=== Verifying p123client ===" && python -c "import p123client; print('p123client OK')" || \
    (echo "p123client import failed, showing pip list:" && pip list | grep -i p123 && echo "Trying reinstall..." && pip install --no-cache-dir --verbose p123client 2>&1 || echo "p123client REINSTALL ALSO FAILED")

# Final verification - check each package and show detailed errors
RUN echo "=== Final Package Check ===" && pip list | grep -E "(p115|p123|httpx|h2)" || true
RUN python -c "import httpx; print('httpx OK')"
RUN python -c "import h2; print('h2 OK')"
# Show actual p115client import error with full traceback
RUN python -c "import traceback; exec('try:\\n    import p115client\\n    print(\"p115client OK\")\\nexcept Exception as e:\\n    print(\"p115client IMPORT ERROR:\")\\n    traceback.print_exc()\\n    raise')"
RUN python -c "import p123client; print('p123client OK')"
RUN echo "=== All dependencies verified ==="

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