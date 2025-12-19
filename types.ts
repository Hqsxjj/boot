// src/types.ts

export interface TelegramConfig {
  botToken: string;
  adminUserId: string;
  whitelistMode: boolean;
  notificationChannelId: string;
}

export type LoginMethod = 'cookie' | 'qrcode' | 'open_app';

/**  
 * ⭐⭐⭐ 这里是唯一修改的地方 —— 补齐 22 个端 ⭐⭐⭐
 */
export type P115LoginApp =
  | 'web'
  | 'pcweb'
  | 'android'
  | 'android_tv'
  | 'ios'
  | 'ipad'
  | 'applet'
  | 'mini'
  | 'qandroid'
  | 'desktop'
  | 'windows'
  | 'mac'
  | 'linux'
  | 'harmony'
  | 'xiaomi'
  | 'huawei'
  | 'oppo'
  | 'vivo'
  | 'samsung'
  | 'browser'
  | 'client'
  | 'open_app';
/**  
 * ⭐⭐⭐ 修改结束，其余全部保持原样 ⭐⭐⭐
 */

export interface Cloud115Config {
  loginMethod: LoginMethod;
  loginApp: P115LoginApp;
  cookies: string;
  appId?: string;
  userAgent: string;
  downloadPath: string;
  downloadDirName: string;
  autoDeleteMsg: boolean;
  qps: number;
  useChinaRedirect?: boolean;  // 回国登录
  hasValidSession?: boolean;   // 由后端返回，表示是否有有效的115会话
}

export interface Cloud123Config {
  enabled: boolean;
  loginMethod?: 'password' | 'oauth';  // 登录方式
  passport?: string;                    // 账号（手机号或邮箱）
  password?: string;                    // 密码
  clientId: string;
  clientSecret: string;
  downloadPath: string;
  downloadDirName: string;
  qps: number;
  useChinaRedirect?: boolean;           // 回国登录
  hasValidSession?: boolean;  // 由后端返回，表示是否有有效的123云盘会话
}

export interface ProxyConfig {
  enabled: boolean;
  type: 'http' | 'socks5';
  host: string;
  port: string;
  username?: string;
  password?: string;
  noProxyHosts?: string;  // 不走代理的地址，逗号分隔
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
  provider: 'openai' | 'gemini' | 'deepseek' | 'zhipu' | 'moonshot' | 'groq' | 'qwen' | 'siliconflow' | 'openrouter' | 'custom';
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
  twoFactorSecret?: string;
}

export enum ViewState {
  USER_CENTER = 'USER_CENTER',
  BOT_SETTINGS = 'BOT_SETTINGS',
  CLOUD_ORGANIZE = 'CLOUD_ORGANIZE',
  EMBY_INTEGRATION = 'EMBY_INTEGRATION',
  RESOURCE_SEARCH = 'RESOURCE_SEARCH',
  LOGS = 'LOGS'
}

export interface AuthState {
  isAuthenticated: boolean;
  is2FAVerified: boolean;
  isLocked: boolean;
  failedAttempts: number;
}