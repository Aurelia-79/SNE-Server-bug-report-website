import { computed, reactive } from 'vue';

import { apiClient, getTokenStorageKey } from '../api/client';
import type { User } from '../types';

const TOKEN_KEY = getTokenStorageKey();
const USER_KEY = 'nls-admin-user';

const state = reactive<{
  token: string | null;
  user: User | null;
}>({
  token: localStorage.getItem(TOKEN_KEY),
  user: (() => {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  })(),
});

async function login(username: string, password: string) {
  const { data } = await apiClient.post('/api/auth/login', { username, password });
  state.token = data.access_token;
  state.user = data.user as User;
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

async function fetchMe() {
  const { data } = await apiClient.get('/api/auth/me');
  state.user = data as User;
  localStorage.setItem(USER_KEY, JSON.stringify(data));
}

function setSession(token: string, user: User) {
  state.token = token;
  state.user = user;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function setUser(user: User) {
  state.user = user;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

const isAuthenticated = computed(() => Boolean(state.token));
const isSuperAdmin = computed(() => state.user?.system_role === 'super_admin');
const isSupervisor = computed(() => state.user?.system_role === 'supervisor' || state.user?.system_role === 'super_admin');
const isHrDepartment = computed(() => state.user?.profile.department === '人事部门');
const isEmployed = computed(() => state.user?.profile.employment_status === '在职');
const canViewAnalytics = computed(() => {
  if (!state.user) return false;
  if (isSupervisor.value || isHrDepartment.value) return true;
  return state.user.profile.department === '游戏管理员部门'
    && ['高级管理员', '总管'].includes(state.user.profile.game_admin_rank ?? '');
});
const canReviewExam = computed(() => {
  if (!state.user) return false;
  return isSuperAdmin.value || isHrDepartment.value;
});
const canManageExamPaper = computed(() => Boolean(state.user) && (isHrDepartment.value || isSupervisor.value));
const canTakeExam = computed(() => {
  return Boolean(state.user);
});
const canViewServerControl = computed(() => Boolean(state.user));

export function useAuth() {
  return {
    state,
    login,
    fetchMe,
    setSession,
    setUser,
    logout,
    isAuthenticated,
    isSuperAdmin,
    isSupervisor,
    isEmployed,
    canViewServerControl,
    canViewAnalytics,
    canReviewExam,
    canManageExamPaper,
    canTakeExam,
  };
}

