// src/services/api.ts
import axios from 'axios';
import { AppConfig } from '../types';

type ApiResponse<T> = {
  success: boolean;
  data: T;
  error?: string;
};

type CloudDirectoryEntry = {
  id: string;
  name: string;
  children?: boolean;
  date?: string;
};

const apiClient = axios.create({
  // 必须是 /api，配合 vite.config.ts 的 proxy 转发到 8000 端口
  baseURL: '/api',
  timeout: 15000,
});

// 请求拦截器：自动携带 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理 401 过期
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      console.warn('Token expired or unauthorized');
      // 可选：这里可以触发自动登出逻辑
    }
    return Promise.reject(error);
  }
);

export const api = {
  // --- 基础配置与认证 ---
  getConfig: async () => {
    const res = await apiClient.get<ApiResponse<AppConfig>>('/config');
    return (res.data as any).data ?? (res.data as any);
  },

  saveConfig: async (config: AppConfig) => {
    const res = await apiClient.post<ApiResponse<AppConfig>>('/config', config);
    return res.data;
  },

  updatePassword: async (password: string) => {
    const res = await apiClient.put<ApiResponse<unknown>>('/auth/password', { password });
    return res.data;
  },

  setup2FA: async () => {
    const res = await apiClient.post<ApiResponse<{ secret: string; qrCodeUri: string }>>('/auth/setup-2fa');
    return res.data.data;
  },

  verify2FA: async (code: string) => {
    const res = await apiClient.post<ApiResponse<unknown>>('/auth/verify-otp', { code });
    return res.data;
  },

  // --- 115 网盘相关接口 ---

  /**
   * 获取 115 支持的登录终端列表
   * 参考 EmbyNginxDK 项目的 /v1/get_115_clients
   */
  get115LoginApps: async () => {
    const res = await apiClient.get<ApiResponse<Array<{ key: string; ssoent: string; name: string }>>>('/115/login/apps');
    return res.data.data;
  },

  /**
   * 获取 115 登录二维码
   * @param appType 模拟的终端类型 (如 android, ios, tv 等)
   * @param loginMethod 登录方式 ('qrcode' 或 'open_app')
   */
  /**
   * 获取 115 登录二维码
   * @param appType 模拟的终端类型 (如 android, ios, tv 等)
   * @param loginMethod 登录方式 ('qrcode' 或 'open_app')
   * @param appId 可选，第三方 App ID (仅 open_app 模式需要)
   */
  get115QrCode: async (appType: string, loginMethod: string, appId?: string) => {
    const payload: Record<string, any> = {
      loginApp: appType,
      loginMethod: loginMethod,
    };

    // 第三方 App ID 模式需要传递 appId
    if (loginMethod === 'open_app' && appId) {
      payload.appId = appId;
    }

    const res = await apiClient.post<
      ApiResponse<{ sessionId: string; qrcode: string; loginMethod: string; loginApp: string }>
    >('/115/login/qrcode', payload);

    return res.data.data;
  },

  check115QrStatus: async (sessionId: string, _time: number, _sign: string) => {
    try {
      const res = await apiClient.get<ApiResponse<{ status: string; message?: string }>>(
        `/115/login/status/${encodeURIComponent(sessionId)}`
      );

      return res.data;
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const payload = err.response.data as any;
        if (payload?.status) {
          return {
            success: false,
            data: { status: payload.status, message: payload.error || payload.message },
            error: payload.error,
          };
        }
      }
      throw err;
    }
  },

  get115Files: async (cid: string = '0') => {
    const res = await apiClient.get<ApiResponse<CloudDirectoryEntry[]>>('/115/directories', {
      params: { cid },
    });

    const entries = res.data.data || [];

    return {
      currentCid: cid,
      files: entries.map((e) => ({
        id: e.id,
        cid: e.id,
        name: e.name,
        n: e.name,
        is_dir: !!e.children,
        file_type: e.children ? 0 : 1,
        time: e.date || '',
        t: e.date || '',
      })),
    };
  },

  list115Directories: async (cid: string = '0') => {
    const res = await apiClient.get<ApiResponse<CloudDirectoryEntry[]>>('/115/directories', {
      params: { cid },
    });
    return res.data.data;
  },

  rename115File: async (fileId: string, newName: string) => {
    const res = await apiClient.post<ApiResponse<{ fileId: string; newName: string }>>('/115/files/rename', {
      fileId,
      newName,
    });
    return res.data;
  },

  move115File: async (fileId: string, targetCid: string) => {
    const res = await apiClient.post<ApiResponse<{ fileId: string; targetCid: string }>>('/115/files/move', {
      fileId,
      targetCid,
    });
    return res.data;
  },

  delete115File: async (fileId: string) => {
    const res = await apiClient.delete<ApiResponse<{ fileId: string }>>('/115/files', {
      data: { fileId },
    });
    return res.data;
  },

  create115OfflineTask: async (sourceUrl: string, saveCid: string) => {
    const res = await apiClient.post<ApiResponse<{ p115TaskId: string; sourceUrl: string; saveCid: string }>>(
      '/115/files/offline',
      {
        sourceUrl,
        saveCid,
      }
    );
    return res.data;
  },

  // --- 115 Share Interface ---

  get115ShareFiles: async (shareCode: string, accessCode?: string, cid?: string) => {
    const res = await apiClient.post<ApiResponse<{ id: string; name: string; size: number; is_directory: boolean; time: string }[]>>(
      '/115/share/files',
      {
        shareCode,
        accessCode,
        cid: cid || '0',
      }
    );
    return res.data;
  },

  save115Share: async (shareCode: string, accessCode?: string, saveCid?: string, fileIds?: string[]) => {
    const res = await apiClient.post<ApiResponse<{ message: string; count: number }>>('/115/share/save', {
      shareCode,
      accessCode,
      saveCid,
      fileIds,
    });
    return res.data;
  },

  // --- 123 云盘接口 ---

  /**
   * 123 云盘密码登录
   * @param passport 手机号或邮箱
   * @param password 密码
   */
  login123WithPassword: async (passport: string, password: string) => {
    const res = await apiClient.post<ApiResponse<{ message: string; login_method: string }>>(
      '/123/login/password',
      { passport, password }
    );
    return res.data;
  },

  // --- 123 Share Interface ---

  get123ShareFiles: async (shareCode: string, accessCode?: string) => {
    const res = await apiClient.post<ApiResponse<{ id: string; name: string; size: number; is_directory: boolean }[]>>(
      '/123/share/files',
      {
        shareCode,
        accessCode,
      }
    );
    return res.data;
  },

  save123Share: async (shareCode: string, accessCode?: string, savePath?: string, fileIds?: string[]) => {
    const res = await apiClient.post<ApiResponse<{ message: string; count: number }>>('/123/share/save', {
      shareCode,
      accessCode,
      savePath,
      fileIds,
    });
    return res.data;
  },

  list123Directories: async (dirId: string = '/') => {
    const res = await apiClient.get<ApiResponse<CloudDirectoryEntry[]>>('/123/directories', {
      params: { dirId },
    });
    return res.data.data;
  },

  rename123File: async (fileId: string, newName: string) => {
    const res = await apiClient.post<ApiResponse<{ fileId: string; newName: string }>>('/123/files/rename', {
      fileId,
      newName,
    });
    return res.data;
  },

  move123File: async (fileId: string, targetDirId: string) => {
    const res = await apiClient.post<ApiResponse<{ fileId: string; targetDirId: string }>>('/123/files/move', {
      fileId,
      targetDirId,
    });
    return res.data;
  },

  delete123File: async (fileId: string) => {
    const res = await apiClient.delete<ApiResponse<{ fileId: string }>>('/123/files', {
      data: { fileId },
    });
    return res.data;
  },

  create123OfflineTask: async (sourceUrl: string, saveDirId: string) => {
    const res = await apiClient.post<ApiResponse<{ p123TaskId: string; sourceUrl: string; saveDirId: string }>>(
      '/123/offline/tasks',
      {
        sourceUrl,
        saveDirId,
      }
    );
    return res.data;
  },

  get123OfflineTaskStatus: async (taskId: string) => {
    const res = await apiClient.get<ApiResponse<{ status: string; progress: number; speed: number }>>(
      `/123/offline/tasks/${encodeURIComponent(taskId)}`
    );
    return res.data;
  },

  // --- Bot 接口 ---

  getBotConfig: async () => {
    const res = await apiClient.get<ApiResponse<any>>('/bot/config');
    return res.data.data;
  },

  saveBotConfig: async (config: any) => {
    const res = await apiClient.post<ApiResponse<any>>('/bot/config', config);
    return res.data;
  },

  getBotCommands: async () => {
    const res = await apiClient.get<ApiResponse<any[]>>('/bot/commands');
    return res.data.data;
  },

  putBotCommands: async (commands: any[]) => {
    const res = await apiClient.put<ApiResponse<any[]>>('/bot/commands', { commands });
    return res.data;
  },

  testBotMessage: async (targetType: string = 'admin', targetId?: string) => {
    const res = await apiClient.post<ApiResponse<any>>('/bot/test-message', {
      target_type: targetType,
      target_id: targetId,
    });
    return res.data;
  },

  // --- Emby 接口 ---

  testEmbyConnection: async () => {
    const res = await apiClient.post<ApiResponse<{ success: boolean; latency: number; msg?: string }>>(
      '/emby/test-connection',
      {}
    );
    return res.data;
  },

  scanEmbyMissing: async () => {
    const res = await apiClient.post<ApiResponse<any[]>>('/emby/scan-missing', {});
    return res.data;
  },

  // --- STRM 接口 ---

  generateStrmJob: async (type: string, config: any) => {
    const res = await apiClient.post<ApiResponse<{ jobId: string; status: string }>>('/strm/generate', {
      type,
      config,
    });
    return res.data;
  },

  listStrmJobs: async () => {
    const res = await apiClient.get<ApiResponse<any[]>>('/strm/tasks');
    return res.data.data;
  },

  // --- Logs ---

  fetchLogs: async (limit: number = 100, since?: number) => {
    const params: any = { limit };
    if (since) params.since = since;
    const res = await apiClient.get<ApiResponse<any[]>>('/logs', { params });
    return res.data.data;
  },

  // --- Wallpaper ---
  getTrendingWallpaper: async () => {
    const res = await apiClient.get<ApiResponse<{ url: string; source: string }>>('/wallpaper/trending');
    return res.data;
  },

  // --- Resource Search ---
  searchResources: async (query: string) => {
    const res = await apiClient.post<ApiResponse<any[]>>('/resource-search/search', { query });
    return res.data;
  },

  getTrendingResources: async () => {
    const res = await apiClient.get<ApiResponse<any[]>>('/resource-search/trending');
    return res.data;
  },

  getResourceDetail: async (resourceId: string) => {
    const res = await apiClient.get<ApiResponse<any>>(`/resource-search/resource/${encodeURIComponent(resourceId)}`);
    return res.data;
  },

  // --- Subscription ---
  getSubscriptions: async () => {
    const res = await apiClient.get<ApiResponse<any[]>>('/subscription/list');
    return res.data.data;
  },

  addSubscription: async (data: { keyword: string; cloud_type: string; filter_config: any }) => {
    const res = await apiClient.post<ApiResponse<any>>('/subscription/add', data);
    return res.data;
  },

  deleteSubscription: async (subId: string) => {
    const res = await apiClient.delete<ApiResponse<any>>(`/subscription/delete/${subId}`);
    return res.data;
  },

  runSubscriptionChecks: async () => {
    const res = await apiClient.post<ApiResponse<any>>('/subscription/run');
    return res.data;
  },

  updateSubscription: async (subId: string, data: any) => {
    const res = await apiClient.put<ApiResponse<any>>(`/subscription/update/${subId}`, data);
    return res.data;
  },

  getSubscriptionHistory: async (subId: string) => {
    const res = await apiClient.get<ApiResponse<any[]>>(`/subscription/${subId}/history`);
    return res.data;
  },

  checkSubscriptionAvailability: async (subId: string, params: { date?: string; episode?: string }) => {
    const res = await apiClient.post<ApiResponse<any>>(`/subscription/${subId}/check`, params);
    return res.data;
  },

  saveCheckResult: async (data: any) => {
    const res = await apiClient.post<ApiResponse<any>>('/subscription/save_check_result', data);
    return res.data;
  },

  getSubscriptionSettings: async () => {
    const res = await apiClient.get<ApiResponse<any>>('/subscription/settings');
    return res.data;
  },

  updateSubscriptionSettings: async (settings: any) => {
    const res = await apiClient.post<ApiResponse<any>>('/subscription/settings', settings);
    return res.data;
  },

  // --- 来源管理相关接口 ---

  getSources: async () => {
    const res = await apiClient.get<ApiResponse<any[]>>('/sources');
    return res.data;
  },

  addSource: async (type: 'telegram' | 'website', url: string, name?: string) => {
    const res = await apiClient.post<ApiResponse<any>>('/sources', { type, url, name });
    return res.data;
  },

  deleteSource: async (id: string) => {
    const res = await apiClient.delete<ApiResponse<any>>(`/sources/${id}`);
    return res.data;
  },

  updateSource: async (id: string, data: { enabled?: boolean; name?: string }) => {
    const res = await apiClient.put<ApiResponse<any>>(`/sources/${id}`, data);
    return res.data;
  },

  crawlSources: async () => {
    const res = await apiClient.post<ApiResponse<any>>('/sources/crawl');
    return res.data;
  },

  crawlSingleSource: async (id: string) => {
    const res = await apiClient.post<ApiResponse<any>>(`/sources/crawl/${id}`);
    return res.data;
  },

  getCrawlResults: async (keyword?: string) => {
    const res = await apiClient.get<ApiResponse<any>>('/sources/results', { params: { keyword } });
    return res.data;
  },
};
