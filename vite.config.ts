import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 3000, // 前端开发服务器端口
    host: '0.0.0.0', // 允许局域网访问（可选，方便手机调试）
    // [关键修改] 添加反向代理，解决开发环境跨域和接口连接问题
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // 必须与 Flask 后端的运行端口一致
        changeOrigin: true,
        secure: false,
        // 如果后端接口没有 /api 前缀，需要用 rewrite 去掉，但你的后端是有 /api 前缀的，所以不需要 rewrite
        // rewrite: (path) => path.replace(/^\/api/, '') 
      }
    }
  }
});