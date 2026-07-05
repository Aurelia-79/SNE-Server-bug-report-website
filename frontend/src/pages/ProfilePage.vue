<script setup lang="ts">
import { reactive, ref, watchEffect } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { User, Lock, Delete } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type { User as UserType } from '../types';

const auth = useAuth();
const router = useRouter();
const saving = ref(false);
const uploading = ref(false);
const deleting = ref(false);

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

async function confirmDeleteAccount() {
  try {
    await ElMessageBox.confirm(
      '注销后将无法恢复所有数据（包括档案、答卷、工单等），确定要继续吗？',
      '确认注销账号',
      {
        confirmButtonText: '确认注销',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
        type: 'warning',
      }
    );
  } catch {
    return;
  }

  try {
    await ElMessageBox.prompt(
      '请输入当前密码以确认注销',
      '密码确认',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '请输入当前密码',
      }
    );
  } catch {
    return;
  }

  deleting.value = true;
  try {
    await apiClient.delete('/api/auth/me');
    auth.logout();
    router.replace('/login');
    ElMessage.success('账号已成功注销');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '注销失败');
  } finally {
    deleting.value = false;
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

    <!-- Danger Zone -->
    <section class="panel-card" style="border: 1px solid rgba(220, 38, 38, 0.2);">
      <h4 style="color: var(--color-danger); display: flex; align-items: center; gap: 8px;">
        <el-icon><Delete /></el-icon>危险操作
      </h4>
      <p style="margin: 0 0 var(--space-3); color: var(--color-text-secondary); font-size: var(--font-size-sm);">
        注销账号后，所有数据将被永久删除且无法恢复，包括人员档案、答卷记录、工单和评论等。
      </p>
      <button class="danger-action" :disabled="deleting" @click="confirmDeleteAccount">
        <el-icon><Delete /></el-icon>{{ deleting ? '注销中...' : '注销账号' }}
      </button>
    </section>
  </div>
</template>
