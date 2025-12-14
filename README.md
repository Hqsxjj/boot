# Boot - 云盘媒体管理工具

一站式云盘媒体管理解决方案，支持 115 网盘、123 云盘和 OpenList 集成。

## 功能

- **云盘整理** - 支持 115/123 网盘文件自动识别和整理
- **STRM 生成** - 自动生成串流文件，支持 Emby/Jellyfin
- **离线下载** - Telegram Bot 接收链接，自动转存
- **Emby 集成** - 缺集检测、媒体库刷新
- **WebDAV** - 挂载 STRM 目录供播放器访问

## 部署

### 方式一：Docker Compose（推荐）
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方式二：Docker CLI
```bash
docker run -d \
  --name boot \
  -p 18080:18080 \
  -v /your/data:/data \
  -v /your/strm:/data/strm \
  boot:latest
```

**重要事项**：

1. **替换路径**: 将 `/your/data` 和 `/your/strm` 替换为本地实际路径
   ```bash
   # 示例 (Linux/Mac):
   mkdir -p ~/boot-data ~/boot-strm
   docker run -d --name boot -p 18080:18080 \
     -v ~/boot-data:/data \
     -v ~/boot-strm:/data/strm \
     boot:latest
   
   # 示例 (Windows):
   docker run -d --name boot -p 18080:18080 ^
     -v C:\boot-data:/data ^
     -v C:\boot-strm:/data/strm ^
     boot:latest
   ```

2. **首次启动**: 容器会自动初始化 `/data/config.yml` 配置文件
3. **访问应用**: 打开浏览器访问 `http://localhost:18080`
4. **配置**: 在 Web UI 中点击右下角**用户中心** → **设置**进行配置

### Docker Compose 运行

```bash
git clone https://github.com/HQSxcj/boot.git
cd boot
docker-compose up -d
```

然后访问 `http://localhost:18080`

### 故障排除

**问题：容器启动后无法访问**

1. 检查容器状态：
   ```bash
   docker ps | grep boot
   ```

2. 查看容器日志：
   ```bash
   docker logs boot -f
   ```

3. 常见原因：
   - **数据卷权限问题**: `/data` 目录无写入权限
     ```bash
     # 解决: 调整宿主机上 data 目录的权限
     chmod 755 /your/data
     ```
   
   - **端口占用**: 18080 端口已被其他服务占用
     ```bash
     # 解决: 使用其他端口
     docker run -d --name boot -p 8888:18080 -v /your/data:/data boot:latest
     ```
   
   - **磁盘空间不足**: 无法创建数据库或日志文件
     ```bash
     # 检查磁盘
     df -h /your/data
     ```

## 端口

| 端口 | 用途 |
|------|------|
| 18080 | Web UI + API + WebDAV |

## 数据目录

```
/data/
├── secrets.db      # 敏感数据(加密)
├── appdata.db      # 配置数据
├── config.yml      # 应用配置
├── strm/           # STRM 文件输出
└── logs/           # 应用日志
    └── app.log
```

## 技术栈

- **前端**: React + TypeScript + Tailwind CSS + Vite
- **后端**: Flask + SQLAlchemy + Gunicorn
- **部署**: Nginx + Docker

## 开发

```bash
# 前端
npm install
npm run dev

# 后端
cd backend
pip install -r requirements.txt
python main.py
```

## License

MIT
Last Sync Check: 12/14/2025 15:45:48
