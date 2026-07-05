import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'nls-admin-token';
const USER_KEY = 'nls-admin-user';

let redirecting = false;

function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function redirectToLogin(): void {
  if (redirecting) return;
  redirecting = true;
  if (typeof window !== 'undefined') {
    window.location.replace('/login');
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail ?? '';

    if (status === 401) {
      // Token 过期、无效，或用户不存在/已停用
      const reasons = [
        '登录状态无效',
        '未提供登录凭证',
        '用户不存在或已停用',
        'Invalid token',
      ];
      if (reasons.some((r) => detail.includes(r)) || !localStorage.getItem(TOKEN_KEY)) {
        clearSession();
        redirectToLogin();
      }
    }

    if (status === 403) {
      // 账号已停用
      const reasons = ['账号已停用', 'Forbidden'];
      if (reasons.some((r) => detail.includes(r))) {
        clearSession();
        redirectToLogin();
      }
    }

    return Promise.reject(error);
  }
);

export function getTokenStorageKey() {
  return TOKEN_KEY;
}

export function buildAuthorizedFileUrl(path: string) {
  const token = localStorage.getItem(TOKEN_KEY) ?? '';
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  return `${normalizedBase}${path}?access_token=${encodeURIComponent(token)}`;
}
