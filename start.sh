#!/bin/bash

set -e

echo "================================================"
echo "🚀 Boot 服务启动中..."
echo "================================================"

# 0. 确保数据目录存在并设置权限
echo "📁 检查数据目录..."
mkdir -p /data/strm /data/logs
chmod -R 755 /data

# 1. 检查前端文件是否存在
echo "📦 检查前端静态文件..."
if [ -f /usr/share/nginx/html/index.html ]; then
    echo "✅ 前端文件存在"
    ls -la /usr/share/nginx/html/
else
    echo "❌ 前端文件缺失！"
    echo "创建占位页面..."
    echo "<html><body><h1>前端构建失败</h1><p>请检查 Docker 构建日志</p></body></html>" > /usr/share/nginx/html/index.html
fi

# 2. 检查 nginx 配置
echo "🔧 检查 Nginx 配置..."
nginx -t

# 3. 启动 Gunicorn (Python 后端)
echo "🐍 启动后端服务 (Gunicorn)..."
cd /app
gunicorn -w 4 -b 127.0.0.1:8000 "main:create_app()" --daemon \
    --access-logfile /data/logs/gunicorn_access.log \
    --error-logfile /data/logs/gunicorn_error.log \
    --capture-output

# 等待并检查 Gunicorn 是否存活
sleep 3
if pgrep gunicorn > /dev/null; then
    echo "✅ 后端服务启动成功"
else
    echo "❌ 后端服务启动失败！"
    echo "--- Gunicorn 错误日志 ---"
    cat /data/logs/gunicorn_error.log 2>/dev/null || echo "无日志"
    exit 1
fi

# 4. 启动 Nginx (前台)
echo "🌐 启动前端服务 (Nginx)..."
echo "================================================"
echo "✅ 服务启动完成！访问 http://localhost:18080"
echo "================================================"
nginx -g "daemon off;"