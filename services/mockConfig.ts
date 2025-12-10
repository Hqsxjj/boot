
import { AppConfig } from '../types';
import { api } from './api';

const STORAGE_KEY = '115_BOT_CONFIG';

// DEFAULT PRESETS - MOVIES
export const DEFAULT_MOVIE_RULES = [
  { 
    id: 'm_anim', 
    name: '动画电影', 
    targetCid: '', 
    conditions: { 
      genre_ids: '16' 
      // Language: All, Region: All
    } 
  },
  { 
    id: 'm_cn', 
    name: '华语电影', 
    targetCid: '', 
    conditions: { 
      origin_country: 'CN,TW,HK' 
      // Language: All, Genre: All
    } 
  },
  { 
    id: 'm_foreign', 
    name: '外语电影', 
    targetCid: '', 
    conditions: { 
      origin_country: '!CN,TW,HK' // Exclude CN, TW, HK
      // Language: All, Genre: All
    } 
  },
];

// DEFAULT PRESETS - TV SHOWS
export const DEFAULT_TV_RULES = [
  { 
    id: 't_cn', 
    name: '华语剧集', 
    targetCid: '', 
    conditions: { 
      origin_country: 'CN,TW,HK' 
      // Language: All, Genre: All
    } 
  },
  { 
    id: 't_western', 
    name: '欧美剧集', 
    targetCid: '', 
    conditions: { 
      origin_country: '!CN,TW,HK,JP,KR' // Exclude CN, TW, HK, JP, KR
      // Language: All, Genre: All
    } 
  },
  { 
    id: 't_asia', 
    name: '日韩剧集', 
    targetCid: '', 
    conditions: { 
      origin_country: 'JP,KR' 
      // Language: All, Genre: All
    } 
  },
  { 
    id: 't_cn_anim', 
    name: '国漫', 
    targetCid: '', 
    conditions: { 
      genre_ids: '16', 
      origin_country: 'CN,TW,HK' 
      // Language: All
    } 
  },
  { 
    id: 't_jp_anim', 
    name: '日漫', 
    targetCid: '', 
    conditions: { 
      genre_ids: '16', 
      origin_country: 'JP' 
      // Language: All
    } 
  },
  { 
    id: 't_doc', 
    name: '纪录片', 
    targetCid: '', 
    conditions: { 
      genre_ids: '99' 
      // Region: All, Language: All
    } 
  },
  { 
    id: 't_show', 
    name: '综艺', 
    targetCid: '', 
    conditions: { 
      genre_ids: '10764,10767' 
      // Region: All, Language: All
    } 
  },
  { 
    id: 't_kids', 
    name: '儿童', 
    targetCid: '', 
    conditions: { 
      genre_ids: '10762' 
      // Region: All, Language: All
    } 
  },
];

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
    enabled: false,
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

// Sync Config with Backend
export const syncConfig = async () => {
  const remoteConfig = await api.get('/api/config');
  if (remoteConfig && Object.keys(remoteConfig).length > 0) {
    // Merge defaults to ensure new fields are present
    const merged = { ...DEFAULT_CONFIG, ...remoteConfig };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
    return merged;
  }
  return null;
};

export const loadConfig = (): AppConfig => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      // Deep merge logic
      return {
        ...DEFAULT_CONFIG,
        ...parsed,
        cloud115: { ...DEFAULT_CONFIG.cloud115, ...(parsed.cloud115 || {}) },
        cloud123: { ...DEFAULT_CONFIG.cloud123, ...(parsed.cloud123 || {}) },
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
            movieRules: parsed.organize?.movieRules || DEFAULT_CONFIG.organize.movieRules,
            tvRules: parsed.organize?.tvRules || DEFAULT_CONFIG.organize.tvRules,
        },
        strm: { 
            ...DEFAULT_CONFIG.strm, 
            ...(parsed.strm || {}),
            webdav: { ...DEFAULT_CONFIG.strm.webdav, ...(parsed.strm?.webdav || {}) }
        }
      };
    } catch (e) {
      console.error("Failed to parse config", e);
    }
  }
  return DEFAULT_CONFIG;
};

export const saveConfig = async (config: AppConfig): Promise<void> => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  // Background sync
  await api.post('/api/config', config);
};
