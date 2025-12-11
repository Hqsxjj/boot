// 文件路径: src/services/auth.ts

const AUTH_KEY = '115_BOT_AUTH_TOKEN';
const ATTEMPTS_KEY = '115_BOT_LOGIN_ATTEMPTS';
const TWO_FA_KEY = '115_BOT_2FA_SESSION';
const MAX_ATTEMPTS = 5;

// === 在这里修改默认账号和密码 ===
const MOCK_CREDENTIALS = {
  username: 'admin',
  password: 'password',
  twoFaCode: '123456' // 模拟的 2FA 验证码
};

/**
 * 检查是否已登录
 */
export const checkAuth = (): boolean => {
  return localStorage.getItem(AUTH_KEY) === 'true';
};

/**
 * 检查是否通过了 2FA (如果有需要)
 */
export const check2FA = (): boolean => {
  return sessionStorage.getItem(TWO_FA_KEY) === 'true';
};

/**
 * 验证 2FA 验证码
 */
export const verify2FA = (code: string): boolean => {
  if (code === MOCK_CREDENTIALS.twoFaCode) {
    sessionStorage.setItem(TWO_FA_KEY, 'true');
    return true;
  }
  return false;
};

/**
 * 核心登录逻辑
 */
export const login = (username: string, pass: string): { success: boolean; locked: boolean } => {
  const attempts = getFailedAttempts();
  
  // 如果尝试次数过多，直接锁定
  if (attempts >= MAX_ATTEMPTS) {
    return { success: false, locked: true };
  }

  // 比对账号密码
  if (username === MOCK_CREDENTIALS.username && pass === MOCK_CREDENTIALS.password) {
    // 登录成功
    localStorage.setItem(AUTH_KEY, 'true');
    resetAttempts(); // 重置失败次数
    return { success: true, locked: false };
  } else {
    // 登录失败
    incrementAttempts(); // 增加失败次数
    return { success: false, locked: getFailedAttempts() >= MAX_ATTEMPTS };
  }
};

/**
 * 退出登录
 */
export const logout = () => {
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(TWO_FA_KEY);
};

/**
 * 获取当前失败尝试次数
 */
export const getFailedAttempts = (): number => {
  return parseInt(localStorage.getItem(ATTEMPTS_KEY) || '0', 10);
};

/**
 * 检查系统是否锁定
 */
export const isLocked = (): boolean => {
  return getFailedAttempts() >= MAX_ATTEMPTS;
};

// === 内部辅助函数 ===

const incrementAttempts = () => {
  const current = getFailedAttempts();
  localStorage.setItem(ATTEMPTS_KEY, (current + 1).toString());
};

const resetAttempts = () => {
  localStorage.removeItem(ATTEMPTS_KEY);
};