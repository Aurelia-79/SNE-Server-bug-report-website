<script setup lang="ts">
import { reactive, ref, watchEffect } from 'vue';
import { ElMessage } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type { User as UserType } from '../types';

const auth = useAuth();
const saving = ref(false);
const uploading = ref(false);

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  current_password: '',
  new_password: '',
  confirm_password: '',
});

watchEffect(() => {
  if (!auth.state.user) return;
  form.username = auth.state.user.username;
  form.display_name = auth.state.user.display_name;
  form.email = auth.state.user.email ?? '';
});

async function saveProfile() {
  if (form.new_password && form.new_password !== form.confirm_password) {
    ElMessage.error('两次输入的新密码不一致');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      username: form.username,
      display_name: form.display_name,
      email: form.email || null,
      current_password: form.new_password ? form.current_password : null,
      new_password: form.new_password || null,
    };
    const { data } = await apiClient.patch('/api/auth/me', payload);
    auth.setSession(data.access_token, data.user as UserType);
    form.email = (data.user as UserType).email ?? '';
    form.current_password = '';
    form.new_password = '';
    form.confirm_password = '';
    ElMessage.success('个人信息已保存');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '保存失败');
  } finally {
    saving.value = false;
  }
}

async function uploadAvatar(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await apiClient.post('/api/auth/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    auth.setUser(data as UserType);
    ElMessage.success('头像已更新');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '上传失败');
  } finally {
    uploading.value = false;
    input.value = '';
  }
}
</script>

<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <p class="page-caption">Profile</p>
        <h3>编辑个人信息</h3>
        <p>可修改头像、用户名、邮箱、显示名和登录密码。</p>
      </div>
    </div>

    <section class="panel-card profile-editor">
      <!-- Avatar Section -->
      <div class="profile-avatar-block">
        <img
          v-if="auth.state.user?.avatar_url"
          class="profile-avatar"
          :src="`${auth.state.user.avatar_url}${auth.state.user.avatar_url.includes('?') ? '&' : '?'}v=${Date.now()}`"
          alt="头像"
        />
        <div v-else class="profile-avatar">
          <el-icon :size="36"><User /></el-icon>
        </div>
        <label class="secondary-action avatar-upload" style="text-align: center; width: 100%">
          {{ uploading ? '上传中...' : '更换头像' }}
          <input type="file" accept="image/*" :disabled="uploading" @change="uploadAvatar" />
        </label>
        <p style="margin: 0; font-size: var(--font-size-xs); color: var(--color-text-muted); text-align: center;">
          支持常见图片格式，最大 2MB。
        </p>
      </div>

      <!-- Form Section -->
      <div>
        <el-form label-position="top">
          <div class="two-column-form">
            <el-form-item label="用户名">
              <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
            </el-form-item>
            <el-form-item label="显示名">
              <el-input v-model="form.display_name" placeholder="显示名" />
            </el-form-item>
            <el-form-item label="电子邮箱" class="full-span">
              <el-input v-model="form.email" placeholder="电子邮箱" />
            </el-form-item>
            <el-form-item label="当前密码">
              <el-input v-model="form.current_password" type="password" show-password placeholder="改密码时必填" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="form.new_password" type="password" show-password placeholder="留空不修改" :prefix-icon="Lock" />
            </el-form-item>
            <el-form-item label="确认新密码" class="full-span">
              <el-input v-model="form.confirm_password" type="password" show-password placeholder="再次输入新密码" :prefix-icon="Lock" />
            </el-form-item>
          </div>
        </el-form>

        <div class="toolbar" style="margin-top: var(--space-5)">
          <button class="primary-action" :disabled="saving" @click="saveProfile">
            <el-icon><User /></el-icon>保存个人信息
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
