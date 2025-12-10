# 阶段 1: 构建环境
FROM node:18-alpine as builder
WORKDIR /app

# 复制依赖文件
COPY package.json package-lock.json* ./

# 安装依赖 (强制忽略版本冲突)
RUN npm install --legacy-peer-deps

# 复制所有源码
COPY . .

# 执行构建
RUN npm run build

# 阶段 2: 生产环境 (Nginx)
FROM nginx:alpine
# 复制 Nginx 配置 (如果有的话)
COPY nginx.conf /etc/nginx/conf.d/default.conf
# 从构建阶段复制编译好的文件到 Nginx 目录
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
