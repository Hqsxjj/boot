// src/services/api.ts
import axios from 'axios';
import { AppConfig } from '../types'; // 确保你有定义这个类型

// 创建 axios 实例，配置基础路径
const apiClient = axios.create({
  baseURL: '/api', // 这里会通过 vite.config.ts 的 proxy 转发到 8000 端口
  timeout: 10000,
});

// 添加拦截器处理 Token (如果有 JWT 登录的话，这里预留位置)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // 1. 获取全局配置
  getConfig: async () => {
    const res = await apiClient.get<{ success: boolean; data: AppConfig }>('/config');
    // 兼容后端返回结构，如果后端直接返回对象则用 res.data
    return res.data.data || res.data; 
  },

  // 2. 保存配置
  saveConfig: async (config: AppConfig) => {
    const res = await apiClient.post('/config', config);
    return res.data;
  },

  // 3. 修改管理员密码
  updatePassword: async (password: string) => {
    const res = await apiClient.put('/auth/password', { password });
    return res.data;
  },

  // 4. 开始 2FA 设置 (获取密钥和二维码)
  setup2FA: async () => {
    const res = await apiClient.post('/auth/setup-2fa');
    return res.data.data; // 预期返回 { secret: '...', qrCodeUri: '...' }
  },

  // 5. 验证 2FA 验证码
  verify2FA: async (code: string) => {
    const res = await apiClient.post('/auth/verify-otp', { code });
    return res.data;
  }
};