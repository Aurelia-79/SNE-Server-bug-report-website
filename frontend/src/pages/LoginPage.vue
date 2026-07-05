<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock, CirclePlus } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';

const router = useRouter();
const auth = useAuth();

const form = reactive({
  username: '',
  password: '',
});
const loading = ref(false);
const registerVisible = ref(false);
const registerLoading = ref(false);
const registerForm = reactive({
  username: '',
  display_name: '',
  email: '',
  password: '',
});

async function submit() {
  loading.value = true;
  try {
    await auth.login(form.username, form.password);
    ElMessage.success('登录成功');
    router.replace('/dashboard');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '登录失败');
  } finally {
    loading.value = false;
  }
}

async function submitRegister() {
  registerLoading.value = true;
  try {
    await apiClient.post('/api/auth/register', {
      username: registerForm.username,
      display_name: registerForm.display_name,
      email: registerForm.email,
      password: registerForm.password,
    });
    await auth.login(registerForm.username, registerForm.password);
    ElMessage.success('注册成功');
    registerVisible.value = false;
    router.replace('/dashboard');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '注册失败');
  } finally {
    registerLoading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-panel">
      <!-- Hero Section -->
      <section class="login-hero">
        <p class="page-caption">Server Ops Command</p>
        <h1>非礼勿视<br />服务器管理系统</h1>
        <p class="muted-text">
          用一套后台处理管理成员入职、离职、升降级、处罚、试卷阅卷、成绩图表和 Bug Report。
        </p>
      </section>

      <!-- Login Form -->
      <section class="login-form-card">
        <div>
          <p class="page-caption">Sign In</p>
          <h3 style="margin: var(--space-1) 0 var(--space-1-5); font-size: var(--font-size-xl); font-weight: var(--font-weight-bold);">进入管理后台</h3>
          <p style="margin: 0 0 var(--space-5); color: var(--color-text-secondary); font-size: var(--font-size-sm);">请输入正式管理员账号和密码登录系统。</p>
        </div>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="请输入密码"
              :prefix-icon="Lock"
              size="large"
            />
          </el-form-item>
          <el-button type="primary" :loading="loading" size="large" style="width: 100%" @click="submit">
            登录系统
          </el-button>
          <el-button style="width: 100%; margin-top: var(--space-3)" @click="registerVisible = true">
            <el-icon><CirclePlus /></el-icon>注册账号
          </el-button>
        </el-form>
      </section>
    </div>

    <!-- Register Dialog -->
    <el-dialog v-model="registerVisible" title="注册账号" width="min(92vw, 500px)" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="registerForm.username" placeholder="用于登录的唯一用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="registerForm.display_name" placeholder="前端展示的名称" />
        </el-form-item>
        <el-form-item label="电子邮箱">
          <el-input v-model="registerForm.email" placeholder="用于接收系统邮件的邮箱" type="email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="registerForm.password" type="password" show-password placeholder="初始密码" :prefix-icon="Lock" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="registerVisible = false">取消</el-button>
          <el-button type="primary" :loading="registerLoading" @click="submitRegister">注册</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
