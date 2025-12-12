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

const LOCAL_CONFIG_KEY = '115_BOT_CONFIG';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      console.warn('Token expired or unauthorized');
    }
    return Promise.reject(error);
  }
);

const readLocalConfig = (): AppConfig | null => {
  const raw = localStorage.getItem(LOCAL_CONFIG_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as AppConfig;
  } catch {
    return null;
  }
};

const normalize115LoginMethod = (method: unknown): 'cookie' | 'open_app' => {
  if (method === 'open_app') return 'open_app';
  return 'cookie';
};

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

  get115QrCode: async (appType: string) => {
    const localConfig = readLocalConfig();
    const loginMethod = normalize115LoginMethod(localConfig?.cloud115?.loginMethod);

    const res = await apiClient.post<
      ApiResponse<{ sessionId: string; qrcode: string; loginMethod: string; loginApp: string }>
    >('/115/login/qrcode', {
      loginApp: appType,
      loginMethod,
    });

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

  // --- 123 云盘接口 ---

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
      '/emby/test-connection'
    );
    return res.data;
  },

  scanEmbyMissing: async () => {
    const res = await apiClient.post<ApiResponse<any[]>>('/emby/scan-missing');
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

  // =======================================================
  // 🚀 新增接口：获取全部 loginApp（22 个端）
  // =======================================================
  get115LoginApps: async () => {
    const res = await apiClient.get<ApiResponse<{ key: string; appId: number }[]>>('/115/login/apps');
    return res.data.data;
  },
};