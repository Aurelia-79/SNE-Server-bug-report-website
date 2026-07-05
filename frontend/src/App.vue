<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuth } from './stores/auth';
import { useTheme } from './stores/theme';
import {
  Monitor,
  UserFilled,
  Document,
  WarningFilled,
  DataAnalysis,
  Setting,
  List,
  Edit,
  Upload,
  SwitchButton,
  Message,
} from '@element-plus/icons-vue';

const route = useRoute();
const router = useRouter();
const auth = useAuth();
const { toggle: toggleTheme } = useTheme();

const isLoginPage = computed(() => route.name === 'login');
const activeNavPath = computed(() => (
  route.path.startsWith('/exams') ? '/exams' : route.path
));
const isDark = computed(() => document.documentElement.classList.contains('theme-dark'));

const navigation = computed(() => {
  const user = auth.state.user;
  if (!user) return [];

  const items: Array<{ label: string; path: string; icon: any }> = [
    { label: '总览', path: '/dashboard', icon: Monitor },
    { label: '人员与人事', path: '/staff', icon: UserFilled },
    { label: '试卷与阅卷', path: '/exams', icon: Document },
    { label: 'Bug Report', path: '/bugs', icon: WarningFilled },
  ];

  if (auth.canViewAnalytics.value) {
    items.push({ label: '成绩图表', path: '/analytics', icon: DataAnalysis });
  }
  if (auth.canViewServerControl.value) {
    items.push({ label: '服务器控制', path: '/server', icon: Setting });
  }
  if (auth.isSuperAdmin.value) {
    items.push({ label: '审计日志', path: '/audit', icon: List });
    items.push({ label: '邮件配置', path: '/mail', icon: Message });
  }
  return items;
});

const currentDepartmentLabel = computed(() => auth.state.user?.profile.department ?? '无部门');

async function bootstrap() {
  if (!auth.state.user && auth.state.token) {
    try {
      await auth.fetchMe();
    } catch {
      router.replace('/login');
    }
  }
}

function handleLogout() {
  auth.logout();
  router.replace('/login');
}

function handleUserCommand(command: string) {
  if (command === 'profile') {
    router.push('/profile');
  }
  if (command === 'logout') {
    handleLogout();
  }
}

onMounted(bootstrap);
</script>

<template>
  <!-- Skip to main content link (accessibility) -->
  <a href="#main-content" class="skip-link">跳到主内容</a>

  <router-view v-if="isLoginPage" />

  <div v-else class="shell">
    <aside class="shell__sidebar" role="navigation" aria-label="主导航">
      <div class="brand-card">
        <p class="brand-card__eyebrow">非礼勿视</p>
        <h1>服务器管理系统</h1>
        <p class="brand-card__copy">
          统一管理入职、离职、试卷、阅卷、升降级、处罚与工单处理。
        </p>
      </div>

      <!-- User Identity Panel -->
      <div class="sidebar-panel">
        <p class="sidebar-panel__title">当前身份</p>
        <div class="identity-chip">
          <span>{{ auth.state.user?.display_name }}</span>
          <small>{{ auth.state.user?.system_role }}</small>
        </div>
        <div>
          <span class="department-chip">{{ currentDepartmentLabel }}</span>
          <span v-if="auth.state.user?.profile.game_admin_rank" class="rank-chip">
            {{ auth.state.user?.profile.game_admin_rank }}
          </span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="nav-panel">
        <button
          v-for="item in navigation"
          :key="item.path"
          class="nav-link"
          :class="{ 'nav-link--active': activeNavPath.startsWith(item.path) }"
          @click="router.push(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <!-- Spacer -->
      <div style="flex: 1" />

      <!-- Profile & Logout -->
      <div class="sidebar-panel" style="margin-top: auto">
        <button class="nav-link" @click="router.push('/profile')">
          <el-icon><Edit /></el-icon>
          <span>编辑信息</span>
        </button>
        <button class="nav-link" @click="handleLogout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <main class="shell__main" id="main-content">
      <header class="topbar">
        <h2>{{ route.meta.title ?? '管理系统' }}</h2>
        <div style="display: flex; align-items: center; gap: 12px">
          <!-- Theme Toggle -->
          <button
            class="theme-toggle-btn"
            :title="isDark ? '切换到浅色模式' : '切换到深色模式'"
            @click="toggleTheme"
          >
            <svg class="toggle-icon toggle-icon--sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
            </svg>
            <svg class="toggle-icon toggle-icon--moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
          </button>
          <el-dropdown trigger="click" @command="handleUserCommand">
          <button class="user-menu-button">
            <img
              v-if="auth.state.user?.avatar_url"
              class="topbar-avatar"
              :src="auth.state.user.avatar_url"
              alt="头像"
            />
            <span v-else class="topbar-avatar">
              {{ auth.state.user?.display_name?.slice(0, 1) ?? 'U' }}
            </span>
            <span>{{ auth.state.user?.username }}</span>
            <el-icon style="margin-left: 2px; font-size: 12px"><component :is="Upload" style="transform: rotate(180deg)" /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><Edit /></el-icon>编辑信息
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <section class="content-surface">
        <router-view />
      </section>
    </main>
  </div>
</template>

<style scoped>
.skip-link {
  position: absolute;
  top: -100px;
  left: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--color-primary);
  color: #fff;
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  z-index: 9999;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  text-decoration: none;
  transition: top var(--transition-fast);
}

.skip-link:focus {
  top: 0;
}
</style>
