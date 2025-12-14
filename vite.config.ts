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
    port: 5173,  // 开发服务器端口
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18080',  // 后端统一使用 18080
        changeOrigin: true,
        secure: false,
      }
    }
  }
});