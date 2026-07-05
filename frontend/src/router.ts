import { createRouter, createWebHistory } from 'vue-router';

import AnalyticsPage from './pages/AnalyticsPage.vue';
import AuditPage from './pages/AuditPage.vue';
import BugPage from './pages/BugPage.vue';
import DashboardPage from './pages/DashboardPage.vue';
import ExamPage from './pages/ExamPage.vue';
import ExamPaperPage from './pages/ExamPaperPage.vue';
import LoginPage from './pages/LoginPage.vue';
import MailConfigPage from './pages/MailConfigPage.vue';
import ProfilePage from './pages/ProfilePage.vue';
import ServerControlPage from './pages/ServerControlPage.vue';
import StaffPage from './pages/StaffPage.vue';
import { useAuth } from './stores/auth';

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'login', component: LoginPage, meta: { title: '登录' } },
  { path: '/dashboard', name: 'dashboard', component: DashboardPage, meta: { title: '总览' } },
  { path: '/profile', name: 'profile', component: ProfilePage, meta: { title: '个人信息' } },
  { path: '/staff', name: 'staff', component: StaffPage, meta: { title: '人员与人事' } },
  { path: '/exams', name: 'exams', component: ExamPage, meta: { title: '试卷与阅卷' } },
  { path: '/exams/take', name: 'exam-take', component: ExamPaperPage, meta: { title: '正式答题' } },
  { path: '/exams/preview', name: 'exam-preview', component: ExamPaperPage, meta: { title: '试卷预览' } },
  { path: '/analytics', name: 'analytics', component: AnalyticsPage, meta: { title: '成绩图表' } },
  { path: '/server', name: 'server', component: ServerControlPage, meta: { title: '服务器控制' } },
  { path: '/bugs', name: 'bugs', component: BugPage, meta: { title: 'Bug Report' } },
  { path: '/audit', name: 'audit', component: AuditPage, meta: { title: '审计日志' } },
  { path: '/mail', name: 'mail-config', component: MailConfigPage, meta: { title: '邮件配置' } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuth();
  if (to.name !== 'login' && !auth.isAuthenticated.value) {
    return '/login';
  }
  if (to.name === 'login' && auth.isAuthenticated.value) {
    return '/dashboard';
  }
  return true;
});

export default router;
