const TOKEN_KEY = 'token';
const ATTEMPTS_KEY = '115_BOT_LOGIN_ATTEMPTS';
const TWO_FA_KEY = '115_BOT_2FA_SESSION';
const MAX_ATTEMPTS = 5;

export interface LoginResult {
  success: boolean;
  locked: boolean;
  error?: string;
}

export const checkAuth = (): boolean => {
  return !!localStorage.getItem(TOKEN_KEY);
};

export const check2FA = (): boolean => {
  return sessionStorage.getItem(TWO_FA_KEY) === 'true';
};

export const verify2FA = (code: string): boolean => {
  if (code === '123456') {
    sessionStorage.setItem(TWO_FA_KEY, 'true');
    return true;
  }
  return false;
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

export const login = async (username: string, password: string): Promise<LoginResult> => {
  if (isLocked()) {
    return { success: false, locked: true };
  }

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });

    const payload = await resp.json().catch(() => null);

    if (resp.ok && payload?.success && payload?.data?.token) {
      localStorage.setItem(TOKEN_KEY, payload.data.token);
      resetAttempts();
      sessionStorage.removeItem(TWO_FA_KEY);
      return { success: true, locked: false };
    }

    if (resp.status === 423) {
      localStorage.setItem(ATTEMPTS_KEY, MAX_ATTEMPTS.toString());
      return { success: false, locked: true, error: payload?.error || 'locked' };
    }

    incrementAttempts();
    return { success: false, locked: isLocked(), error: payload?.error || 'invalid_credentials' };
  } catch {
    return { success: false, locked: false, error: 'network' };
  }
};

export const logout = () => {
  const token = localStorage.getItem(TOKEN_KEY);

  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TWO_FA_KEY);

  void fetch('/api/auth/logout', {
    method: 'POST',
    headers: token
      ? {
          Authorization: `Bearer ${token}`
        }
      : undefined
  }).catch(() => undefined);
};
