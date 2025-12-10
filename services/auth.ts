
const AUTH_KEY = '115_BOT_AUTH_TOKEN';
const ATTEMPTS_KEY = '115_BOT_LOGIN_ATTEMPTS';
const TWO_FA_KEY = '115_BOT_2FA_SESSION';
const MAX_ATTEMPTS = 5;

const MOCK_CREDENTIALS = {
  username: 'admin',
  password: 'password',
  twoFaCode: '123456' // Mock 2FA code
};

export const checkAuth = (): boolean => {
  return localStorage.getItem(AUTH_KEY) === 'true';
};

export const check2FA = (): boolean => {
  // Simple session based 2FA check
  return sessionStorage.getItem(TWO_FA_KEY) === 'true';
};

export const verify2FA = (code: string): boolean => {
  if (code === MOCK_CREDENTIALS.twoFaCode) {
    sessionStorage.setItem(TWO_FA_KEY, 'true');
    return true;
  }
  return false;
};

export const login = (username: string, pass: string): { success: boolean; locked: boolean } => {
  const attempts = getFailedAttempts();
  
  if (attempts >= MAX_ATTEMPTS) {
    return { success: false, locked: true };
  }

  if (username === MOCK_CREDENTIALS.username && pass === MOCK_CREDENTIALS.password) {
    localStorage.setItem(AUTH_KEY, 'true');
    resetAttempts();
    return { success: true, locked: false };
  } else {
    incrementAttempts();
    return { success: false, locked: getFailedAttempts() >= MAX_ATTEMPTS };
  }
};

export const logout = () => {
  localStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(TWO_FA_KEY);
};

export const getFailedAttempts = (): number => {
  return parseInt(localStorage.getItem(ATTEMPTS_KEY) || '0', 10);
};

export const isLocked = (): boolean => {
  return getFailedAttempts() >= MAX_ATTEMPTS;
};

const incrementAttempts = () => {
  const current = getFailedAttempts();
  localStorage.setItem(ATTEMPTS_KEY, (current + 1).toString());
};

const resetAttempts = () => {
  localStorage.removeItem(ATTEMPTS_KEY);
};
