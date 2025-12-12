// src/services/api.ts
import axios from 'axios';
import { AppConfig } from '../types'; // 确保你有定义这个类型

// 创建 axios 实例，配置基础路径
const apiClient = axios.create({
  baseURL: '/api', // 这里会通过 vite.config.ts 的 proxy 转发到 8000 端口
  timeout: 15000,  // 稍微调大一点超时，防止网盘请求慢导致断开
});

// 添加拦截器处理 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 (可选：统一处理 401 token 过期跳转)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // 如果后端返回 401，说明 token 过期，可以在这里处理跳转登录页
      console.warn('Token expired or unauthorized');
    }
    return Promise.reject(error);
  }
);

export const api = {
  // --- 基础配置与认证 ---

  // 1. 获取全局配置
  getConfig: async () => {
    const res = await apiClient.get<{ success: boolean; data: AppConfig }>('/config');
    // 兼容后端返回结构，如果后端直接返回对象则用 res.data
    // 假设后端返回格式为 { success: true, data: { ... } }
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
  },

  // --- 新增：115 网盘相关接口 ---

  /**
   * 6. 获取 115 登录二维码
   * @param appType - 登录类型: 'web', 'ios', 'android', 'tv', 'mini' 等
   */
  get115QrCode: async (appType: string) => {
    const res = await apiClient.post('/cloud115/qr/generate', { appType });
    // 预期后端返回: { success: true, data: { qrCodeUrl, uid, time, sign } }
    return res.data.data; 
  },

  /**
   * 7. 检查二维码扫描状态
   * @param uid - 二维码唯一 ID
   * @param time - 时间戳
   * @param sign - 签名
   */
  check115QrStatus: async (uid: string, time: number, sign: string) => {
    const res = await apiClient.post('/cloud115/qr/status', { uid, time, sign });
    // 预期后端返回: { status: 'waiting'|'scanned'|'success'|'expired', cookie: '...' }
    return res.data; 
  },

  /**
   * 8. 获取文件列表 (用于文件选择器)
   * @param cid - 文件夹 ID，默认为 '0' (根目录)
   */
  get115Files: async (cid: string = '0') => {
    const res = await apiClient.get('/cloud115/files', { params: { cid } });
    // 预期后端返回: { success: true, data: { currentCid, files: [...] } }
    return res.data.data; 
  }
};