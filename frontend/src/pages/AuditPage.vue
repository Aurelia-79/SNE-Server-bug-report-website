<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Refresh } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { formatDateTime } from '../utils/format';

const logs = ref<any[]>([]);
const loading = ref(false);

async function loadLogs() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/audit/logs');
    logs.value = data as any[];
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '无权查看审计日志');
  } finally {
    loading.value = false;
  }
}

onMounted(loadLogs);
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Audit</p>
        <h3>审计日志</h3>
        <p>仅超管可查看完整审计轨迹，包括登录、人事变更、阅卷与工单处理动作。</p>
      </div>
      <button class="secondary-action" :disabled="loading" @click="loadLogs">
        <el-icon><Refresh /></el-icon>刷新
      </button>
    </div>

    <!-- Log Table -->
    <section class="panel-card">
      <h4>日志列表</h4>
      <el-table :data="logs" v-loading="loading" style="width: 100%" stripe max-height="660">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="操作人" min-width="150">
          <template #default="{ row }">{{ row.actor?.display_name ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" min-width="200" show-overflow-tooltip />
        <el-table-column prop="target_type" label="目标类型" min-width="120" />
        <el-table-column prop="target_id" label="目标ID" min-width="90" />
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
