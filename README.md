# 115 Telegram Bot Admin Panel

A web configuration interface for the Telegram to 115 Cloud Drive bot.

## Backend Dependencies

- **[p115client](https://github.com/ChenyangGao/p115client)**: Installed from main branch.
- **Python 3.11**: Runtime environment.
- **Nginx**: Web server.

## Docker Build Instructions

You can build this image locally and push to Docker Hub.

### 1. Build and Push (Multi-Arch)

```bash
# Enable Buildx
docker buildx create --use

# Build for AMD64 and ARM64
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t <your-dockerhub-username>/115-bot-admin:latest \
  --push .
```

### 2. Run Container

```bash
docker run -d \
  --name 115-bot \
  -p 12808:80 \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/logs \
  <your-dockerhub-username>/115-bot-admin:latest
```

### 3. Access

Open your browser and visit: `http://localhost:12808`

## Features

- **Configuration**: 115 Cookies, Proxy, Telegram Token.
- **Organization**: Complex Classification Rules (Movie/TV) & Smart Renaming.
- **Modules**: Emby, STRM, 123 Cloud, OpenList.
- **Security**: 2FA & Lockout protection.
