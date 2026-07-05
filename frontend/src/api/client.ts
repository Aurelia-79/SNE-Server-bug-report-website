import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'nls-admin-token';

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

export function getTokenStorageKey() {
  return TOKEN_KEY;
}

export function buildAuthorizedFileUrl(path: string) {
  const token = localStorage.getItem(TOKEN_KEY) ?? '';
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  return `${normalizedBase}${path}?access_token=${encodeURIComponent(token)}`;
}
