import { AppConfig, ClassificationRule } from '../types';
import { api } from './api';

const STORAGE_KEY = '115_BOT_CONFIG';

// ==========================================
// 1. 默认预设规则 (Constants)
// ==========================================

// DEFAULT PRESETS - MOVIES
export const DEFAULT_MOVIE_RULES: ClassificationRule[] = [
  {
    id: 'm_anim',
    name: '动画电影',
    targetCid: '',
    conditions: {
      genre_ids: '16'
    }
  },
  {
    id: 'm_cn',
    name: '华语电影',
    targetCid: '',
    conditions: {
      origin_country: 'CN,TW,HK'
    }
  },
  {
    id: 'm_foreign',
    name: '外语电影',
    targetCid: '',
    conditions: {
      origin_country: '!CN,TW,HK'
    }
  },
];

// DEFAULT PRESETS - TV SHOWS
export const DEFAULT_TV_RULES: ClassificationRule[] = [
  {
    id: 't_cn',
    name: '华语剧集',
    targetCid: '',
    conditions: {
      origin_country: 'CN,TW,HK'
    }
  },
  {
    id: 't_western',
    name: '欧美剧集',
    targetCid: '',
    conditions: {
      origin_country: '!CN,TW,HK,JP,KR'
    }
  },
  {
    id: 't_asia',
    name: '日韩剧集',
    targetCid: '',
    conditions: {
      origin_country: 'JP,KR'
    }
  },
  {
    id: 't_cn_anim',
    name: '国漫',
    targetCid: '',
    conditions: {
      genre_ids: '16',
      origin_country: 'CN,TW,HK'
    }
  },
  {
    id: 't_jp_anim',
    name: '日漫',
    targetCid: '',
    conditions: {
      genre_ids: '16',
      origin_country: 'JP'
    }
  },
  {
    id: 't_doc',
    name: '纪录片',
    targetCid: '',
    conditions: {
      genre_ids: '99'
    }
  },
  {
    id: 't_show',
    name: '综艺',
    targetCid: '',
    conditions: {
      genre_ids: '10764,10767'
    }
  },
  {
    id: 't_kids',
    name: '儿童',
    targetCid: '',
    conditions: {
      genre_ids: '10762'
    }
  },
];

// ==========================================
// 2. 默认应用配置 (Default Config)
// ==========================================

const DEFAULT_CONFIG: AppConfig = {
  telegram: {
    botToken: '',
    adminUserId: '',
    whitelistMode: true,
    notificationChannelId: '',
  },
  cloud115: {
    loginMethod: 'cookie',
    loginApp: 'web',
    cookies: '',
    appId: '',
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    downloadPath: '0',
    downloadDirName: '根目录',
    autoDeleteMsg: true,
    qps: 0.8,
  },
  cloud123: {
    enabled: false,
    clientId: '',
    clientSecret: '',
    downloadPath: '0',
    downloadDirName: '根目录',
    qps: 1.0,
  },
  openList: {
    enabled: false,
    url: 'http://localhost:5244',
    mountPath: '/d',
    username: '',
    password: ''
  },
  proxy: {
    enabled: false,
    type: 'http',
    host: '127.0.0.1',
    port: '7890',
  },
  tmdb: {
    apiKey: '',
    language: 'zh-CN',
    includeAdult: false,
  },
  emby: {
    enabled: false,
    serverUrl: 'http://localhost:8096',
    apiKey: '',
    refreshAfterOrganize: true,
    notifications: {
      enabled: true,
      forwardToTelegram: true,
      includePosters: true,
      playbackReportingFreq: 'weekly'
    },
    missingEpisodes: {
      enabled: false,
      cronSchedule: '0 0 * * *'
    }
  },
  strm: {
    enabled: false,
    outputDir: '/strm/bot',
    sourceCid115: '0',
    urlPrefix115: 'http://127.0.0.1:9527/d/115',
    sourceDir123: '/',
    urlPrefix123: 'http://127.0.0.1:9527/d/123',
    sourcePathOpenList: '/',
    urlPrefixOpenList: 'http://127.0.0.1:5244/d',
    webdav: {
      enabled: false,
      port: '5005',
      username: 'admin',
      password: 'password',
      readOnly: true
    }
  },
  organize: {
    enabled: true,
    sourceCid: '0',
    sourceDirName: '根目录',
    targetCid: '0',
    targetDirName: '根目录',
    ai: {
      enabled: false,
      provider: 'openai',
      baseUrl: 'https://api.openai.com/v1',
      apiKey: '',
      model: 'gpt-3.5-turbo'
    },
    rename: {
      enabled: true,
      movieTemplate: '{title} ({year})',
      seriesTemplate: '{title} - S{season}E{episode}',
      addTmdbIdToFolder: true,
    },
    movieRules: DEFAULT_MOVIE_RULES,
    tvRules: DEFAULT_TV_RULES
  },
  twoFactorSecret: ''
};

// ==========================================
// 3. 逻辑处理 (Logic)
// ==========================================

/**
 * 辅助函数：将传入的配置与默认配置深度合并
 * 确保即使本地缓存了旧版本的配置，新版本增加的字段也能从 DEFAULT_CONFIG 中补全
 */
const mergeWithDefaults = (parsed: any): AppConfig => {
  return {
    ...DEFAULT_CONFIG,
    ...parsed,
    cloud115: { ...DEFAULT_CONFIG.cloud115, ...(parsed.cloud115 || {}) },
    cloud123: { ...DEFAULT_CONFIG.cloud123, ...(parsed.cloud123 || {}) },
    openList: { ...DEFAULT_CONFIG.openList, ...(parsed.openList || {}) },
    proxy: { ...DEFAULT_CONFIG.proxy, ...(parsed.proxy || {}) },
    tmdb: { ...DEFAULT_CONFIG.tmdb, ...(parsed.tmdb || {}) },
    emby: {
      ...DEFAULT_CONFIG.emby,
      ...(parsed.emby || {}),
      notifications: { ...DEFAULT_CONFIG.emby.notifications, ...(parsed.emby?.notifications || {}) },
      missingEpisodes: { ...DEFAULT_CONFIG.emby.missingEpisodes, ...(parsed.emby?.missingEpisodes || {}) }
    },
    organize: {
      ...DEFAULT_CONFIG.organize,
      ...(parsed.organize || {}),
      ai: { ...DEFAULT_CONFIG.organize.ai, ...(parsed.organize?.ai || {}) },
      rename: { ...DEFAULT_CONFIG.organize.rename, ...(parsed.organize?.rename || {}) },
      movieRules: parsed.organize?.movieRules || DEFAULT_CONFIG.organize.movieRules,
      tvRules: parsed.organize?.tvRules || DEFAULT_CONFIG.organize.tvRules,
    },
    strm: {
      ...DEFAULT_CONFIG.strm,
      ...(parsed.strm || {}),
      webdav: { ...DEFAULT_CONFIG.strm.webdav, ...(parsed.strm?.webdav || {}) }
    }
  };
};

/**
 * 从本地存储加载配置
 * 用于 React State 的同步初始化
 */
export const loadConfig = (): AppConfig => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      return mergeWithDefaults(parsed);
    } catch (e) {
      console.error("Failed to parse local config, using default", e);
    }
  }
  return DEFAULT_CONFIG;
};

/**
 * 保存配置：
 * 1. 更新本地缓存
 * 2. 异步推送给后端 API
 */
export const saveConfig = async (config: AppConfig): Promise<void> => {
  // Save to local
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));

  // Save to backend using the real API service
  try {
    await api.saveConfig(config);
  } catch (e) {
    console.error("Failed to sync config with backend", e);
    // 这里不抛出错误，因为本地保存已经成功，可以让用户感知是成功的
    // 实际项目中可以加个 Toast 提示“云端同步失败”
  }
};

/**
 * 从后端拉取最新配置并更新本地缓存
 * 通常在 App 初始化时调用
 */
export const syncConfig = async (): Promise<AppConfig | null> => {
  try {
    const remoteConfig = await api.getConfig(); // 使用 api.ts 中封装好的方法

    if (remoteConfig && Object.keys(remoteConfig).length > 0) {
      const merged = mergeWithDefaults(remoteConfig);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
      return merged;
    }
  } catch (e) {
    console.warn("Could not fetch remote config, using local cache.", e);
  }
  return null;
};