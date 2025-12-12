// src/types.ts

export interface TelegramConfig {
  botToken: string;
  adminUserId: string;
  whitelistMode: boolean;
  notificationChannelId: string;
}

export type LoginMethod = 'cookie' | 'qrcode' | 'open_app';
export type P115LoginApp = 'web' | 'ios' | 'android' | 'tv' | 'qandroid' | 'mini';

export interface Cloud115Config {
  loginMethod: LoginMethod;
  loginApp: P115LoginApp;
  cookies: string;
  appId?: string;
  userAgent: string;
  downloadPath: string; // CID
  downloadDirName: string; // Display name for UI
  autoDeleteMsg: boolean;
  qps: number;
}

export interface Cloud123Config {
  enabled: boolean;
  clientId: string;
  clientSecret: string;
  downloadPath: string; // Offline Download Dir ID
  downloadDirName: string; // Display name
  qps: number;
}

export interface ProxyConfig {
  enabled: boolean;
  type: 'http' | 'socks5';
  host: string;
  port: string;
  username?: string;
  password?: string;
}

export interface TmdbConfig {
  apiKey: string;
  language: string;
  includeAdult: boolean;
}

export interface MissingEpisodesConfig {
  enabled: boolean;
  cronSchedule: string;
}

export interface EmbyNotificationConfig {
  enabled: boolean;
  forwardToTelegram: boolean;
  includePosters: boolean;
  playbackReportingFreq: 'daily' | 'weekly' | 'monthly';
}

export interface EmbyConfig {
  enabled: boolean;
  serverUrl: string;
  apiKey: string;
  refreshAfterOrganize: boolean;
  notifications: EmbyNotificationConfig;
  missingEpisodes: MissingEpisodesConfig;
}

export interface OpenListConfig {
  enabled: boolean;
  url: string;      
  mountPath: string; 
  username?: string;
  password?: string;
}

export interface WebdavConfig {
  enabled: boolean;
  port: string;
  username: string;
  password: string;
  readOnly: boolean;
}

export interface StrmConfig {
  enabled: boolean;
  outputDir: string;
  sourceCid115: string;
  urlPrefix115: string;
  sourceDir123: string;
  urlPrefix123: string;
  sourcePathOpenList: string;
  urlPrefixOpenList: string;
  webdav: WebdavConfig;
}

export interface RenameRule {
  enabled: boolean;
  movieTemplate: string;
  seriesTemplate: string;
  addTmdbIdToFolder: boolean;
}

// Complex Classification Types
export type MatchConditionType = 'genre_ids' | 'original_language' | 'origin_country' | 'release_year';

export interface ClassificationRule {
  id: string;
  name: string; 
  targetCid: string; 
  conditions: {
    [key in MatchConditionType]?: string; 
  };
}

export interface AiConfig {
  enabled: boolean;
  provider: 'openai' | 'gemini' | 'custom';
  baseUrl: string;
  apiKey: string;
  model: string;
}

export interface OrganizeConfig {
  enabled: boolean;
  sourceCid: string;
  sourceDirName: string;
  targetCid: string;
  targetDirName: string;
  ai: AiConfig;
  rename: RenameRule;
  // Split strategies
  movieRules: ClassificationRule[];
  tvRules: ClassificationRule[];
}

export interface AppConfig {
  telegram: TelegramConfig;
  cloud115: Cloud115Config;
  cloud123: Cloud123Config;
  openList: OpenListConfig;
  proxy: ProxyConfig;
  tmdb: TmdbConfig;
  emby: EmbyConfig;
  strm: StrmConfig;
  organize: OrganizeConfig;
  // Global Auth Config
  twoFactorSecret?: string;
}

export enum ViewState {
  USER_CENTER = 'USER_CENTER',
  BOT_SETTINGS = 'BOT_SETTINGS',
  CLOUD_ORGANIZE = 'CLOUD_ORGANIZE',
  EMBY_INTEGRATION = 'EMBY_INTEGRATION',
  STRM_GENERATION = 'STRM_GENERATION',
  LOGS = 'LOGS'
}

export interface AuthState {
  isAuthenticated: boolean;
  is2FAVerified: boolean;
  isLocked: boolean;
  failedAttempts: number;
}