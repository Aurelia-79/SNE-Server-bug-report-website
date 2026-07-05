<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Refresh, Connection, Promotion, Message } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import type { MailConfig, User } from '../types';

const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const sendingSelected = ref(false);
const testRecipient = ref('');
const sendSubject = ref('');
const sendBody = ref('');

// Users for recipient selection
const users = ref<User[]>([]);
const selectedUserIds = ref<number[]>([]);

const form = reactive<MailConfig>({
  enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_username: '',
  smtp_password: '',
  smtp_use_tls: true,
  smtp_use_ssl: false,
  mail_from: '',
  mail_admin_reply_to: '',
  mail_timeout_seconds: 10,
  updated_at: null,
});

async function loadConfig() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/mail/config');
    Object.assign(form, data as MailConfig);
    form.smtp_password = '';
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取邮件配置失败');
  } finally {
    loading.value = false;
  }
}

async function loadUsers() {
  try {
    const { data } = await apiClient.get('/api/staff/users');
    users.value = (data as User[]).filter((u) => u.email);
  } catch {
    // silently fail
  }
}

async function saveConfig() {
  saving.value = true;
  try {
    const payload = { ...form };
    // Only include password if changed
    if (!payload.smtp_password) {
      delete payload.smtp_password;
    }
    const { data } = await apiClient.put('/api/mail/config', payload);
    Object.assign(form, data as MailConfig);
    form.smtp_password = '';
    ElMessage.success('邮件配置已保存');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '保存失败');
  } finally {
    saving.value = false;
  }
}

async function testMail() {
  if (!testRecipient.value.trim()) {
    ElMessage.warning('请输入测试邮箱地址');
    return;
  }
  testing.value = true;
  try {
    const { data } = await apiClient.post('/api/mail/test', { recipient: testRecipient.value.trim() });
    ElMessage.success(data.message);
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '测试发送失败');
  } finally {
    testing.value = false;
  }
}

async function sendToUsers() {
  if (!selectedUserIds.value.length) {
    ElMessage.warning('请选择至少一位收件人');
    return;
  }
  if (!sendSubject.value.trim()) {
    ElMessage.warning('请填写邮件主题');
    return;
  }
  if (!sendBody.value.trim()) {
    ElMessage.warning('请填写邮件正文');
    return;
  }
  sendingSelected.value = true;
  try {
    const { data } = await apiClient.post('/api/mail/send', {
      user_ids: selectedUserIds.value,
      subject: sendSubject.value.trim(),
      body: sendBody.value.trim(),
    });
    ElMessage.success(data.message);
    sendSubject.value = '';
    sendBody.value = '';
    selectedUserIds.value = [];
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '发送失败');
  } finally {
    sendingSelected.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadUsers()]);
});
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Mail Server</p>
        <h3>邮件配置</h3>
        <p>配置 SMTP 邮件服务器，可发送系统邮件至用户邮箱。所有配置存储在数据库中，无需重启服务器。</p>
      </div>
      <button class="secondary-action" :disabled="loading" @click="loadConfig">
        <el-icon><Refresh /></el-icon>刷新
      </button>
    </div>

    <!-- Email Config Card -->
    <section class="panel-card" v-loading="loading">
      <h4>SMTP 配置</h4>
      <el-form label-position="top">
        <div class="two-column-form">
          <el-form-item label="启用邮件服务">
            <el-switch v-model="form.enabled" active-text="已启用" inactive-text="已停用" />
          </el-form-item>
          <el-form-item label="连接超时 (秒)">
            <el-input-number v-model="form.mail_timeout_seconds" :min="1" :max="60" style="width: 100%" />
          </el-form-item>
          <el-form-item label="SMTP 服务器" class="full-span">
            <el-input v-model="form.smtp_host" placeholder="例如：smtp.gmail.com" :prefix-icon="Connection" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.smtp_port" :min="1" :max="65535" style="width: 100%" />
          </el-form-item>
          <el-form-item label="使用 TLS">
            <el-switch v-model="form.smtp_use_tls" :disabled="form.smtp_use_ssl" />
          </el-form-item>
          <el-form-item label="使用 SSL">
            <el-switch v-model="form.smtp_use_ssl" :disabled="form.smtp_use_tls" />
          </el-form-item>
          <el-form-item label="发件账号" class="full-span">
            <el-input v-model="form.smtp_username" placeholder="SMTP 登录用户名" />
          </el-form-item>
          <el-form-item label="SMTP 密码 / 授权码" class="full-span">
            <el-input v-model="form.smtp_password" type="password" show-password placeholder="留空则不修改" />
          </el-form-item>
          <el-form-item label="发件人地址" class="full-span">
            <el-input v-model="form.mail_from" placeholder="例如：noreply@example.com" />
          </el-form-item>
          <el-form-item label="回复地址 (可选)" class="full-span">
            <el-input v-model="form.mail_admin_reply_to" placeholder="例如：admin@example.com" />
          </el-form-item>
        </div>
      </el-form>

      <div class="toolbar" style="margin-top: var(--space-4)">
        <button class="primary-action" :disabled="saving" @click="saveConfig">
          <el-icon><Promotion /></el-icon>保存配置
        </button>
      </div>
    </section>

    <!-- Test Email Section -->
    <section class="panel-card">
      <h4>发送测试邮件</h4>
      <p style="font-size: var(--font-size-sm); color: var(--color-text-secondary); margin: 0 0 var(--space-3)">
        配置完成后，发送一封测试邮件以验证 SMTP 配置是否正确。
      </p>
      <div class="toolbar">
        <el-input v-model="testRecipient" placeholder="收件人邮箱" style="min-width: 260px" @keyup.enter="testMail">
          <template #prefix>
            <el-icon><Message /></el-icon>
          </template>
        </el-input>
        <button class="primary-action" :disabled="testing" @click="testMail">
          <el-icon><Promotion /></el-icon>发送测试
        </button>
      </div>
    </section>

    <!-- Send to Users Section -->
    <section class="panel-card">
      <h4>群发邮件至用户</h4>
      <p style="font-size: var(--font-size-sm); color: var(--color-text-secondary); margin: 0 0 var(--space-3)">
        选择有邮箱的用户并发送邮件。仅显示已填写邮箱的用户。
      </p>

      <el-form label-position="top">
        <el-form-item label="收件人">
          <el-select
            v-model="selectedUserIds"
            multiple
            filterable
            placeholder="选择收件人"
            style="width: 100%"
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="`${user.display_name} (${user.email})`"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="sendSubject" placeholder="邮件主题" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="sendBody" type="textarea" :rows="5" placeholder="纯文本邮件正文" />
        </el-form-item>
      </el-form>

      <div class="toolbar" style="margin-top: var(--space-3)">
        <button class="primary-action" :disabled="sendingSelected" @click="sendToUsers">
          <el-icon><Promotion /></el-icon>发送邮件
        </button>
      </div>
    </section>
  </div>
</template>
