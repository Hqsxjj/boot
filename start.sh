#!/bin/bash

set -e

echo "================================================"
echo "🚀 Boot 服务启动中 (单体架构)..."
echo "================================================"

# 0. 确保数据目录存在并设置权限
echo "📁 检查数据目录..."
mkdir -p /data/strm /data/logs
chmod -R 755 /data

# 检查 /data 目录的写入权限
if [ ! -w /data ]; then
    echo "⚠️  警告: /data 目录无写入权限，尝试修复权限..."
    chmod -R 755 /data || {
        echo "❌ 无法修复 /data 权限！"
        echo "请确保 Docker 容器有足够权限访问挂载的数据卷"
        echo "提示: 检查宿主机上 /your/data 目录的权限"
        exit 1
    }
fi

# 初始化配置文件（如果不存在）
if [ ! -f /data/config.yml ]; then
    echo "📋 初始化配置文件..."
    cat > /data/config.yml << 'EOF'
telegram:
  botToken: ''
  adminUserId: ''
  whitelistMode: true
  notificationChannelId: ''
cloud115:
  loginMethod: cookie
  loginApp: web
  cookies: ''
  userAgent: ''
  downloadPath: ''
  downloadDirName: ''
  autoDeleteMsg: false
  qps: 1
cloud123:
  enabled: false
  clientId: ''
  clientSecret: ''
  downloadPath: ''
  downloadDirName: ''
  autoDeleteMsg: false
  qps: 1
emby:
  enabled: false
  baseUrl: ''
  apiKey: ''
  mediaLibraryNames: []
strm:
  enabled: false
  outputDir: ''
  webdavUrl: ''
  webdavPort: 8080
  webdavPath: ''
  concurrency: 5
EOF
    echo "✅ 配置文件已创建: /data/config.yml"
    echo "⚠️  请启动后通过 Web UI (http://localhost:18080) 进行配置"
fi

# 1. 检查前端静态文件
echo "📦 检查前端静态文件..."
if [ -f /app/static/index.html ]; then
    echo "✅ 前端文件存在: /app/static/index.html"
else
    echo "⚠️  前端文件缺失！将以 API-only 模式运行"
fi

# 2. 初始化数据库
echo "💾 初始化数据库..."
cd /app
python << 'PYEOF' 2>&1 || echo "⚠️  数据库初始化完成或有非致命警告"
try:
    from models.database import init_all_databases
    init_all_databases()
    print("✅ 数据库初始化完成")
except Exception as e:
    print(f"⚠️  数据库初始化注意: {e}")
    # 不退出，因为表可能已存在
PYEOF

# 3. 启动 Gunicorn（前台运行，直接绑定 18080）
echo "🐍 启动 Gunicorn 服务..."
echo "================================================"
echo "✅ Boot 服务启动完成"
echo "📱 Web UI: http://localhost:18080"
echo "📡 API: http://localhost:18080/api"
echo "================================================"

cd /app
exec gunicorn -w 4 -b 0.0.0.0:18080 "main:create_app()" \
    --access-logfile /data/logs/gunicorn_access.log \
    --error-logfile /data/logs/gunicorn_error.log \
    --capture-output \
    --timeout 300