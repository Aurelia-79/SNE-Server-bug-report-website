<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type { DashboardSummary } from '../types';

const auth = useAuth();
const summary = ref<DashboardSummary | null>(null);
const loading = ref(false);

async function loadDashboard() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/analytics/dashboard');
    summary.value = data as DashboardSummary;
  } finally {
    loading.value = false;
  }
}

onMounted(loadDashboard);
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Overview</p>
        <h3>系统总览</h3>
        <p>查看当前账号覆盖的数据范围，以及人员、待阅卷和工单处理的整体状态。</p>
      </div>
      <button class="secondary-action" :disabled="loading" @click="loadDashboard">
        <el-icon><Refresh /></el-icon>刷新数据
      </button>
    </div>

    <!-- Metric Cards -->
    <div v-loading="loading" class="summary-grid">
      <article class="metric-card">
        <p class="metric-card__label">可见人员总数</p>
        <p class="metric-card__value">{{ summary?.staff_total ?? 0 }}</p>
        <p class="metric-card__hint">按当前账号权限计算</p>
      </article>
      <article class="metric-card">
        <p class="metric-card__label">待人工阅卷</p>
        <p class="metric-card__value">{{ summary?.pending_review_count ?? 0 }}</p>
        <p class="metric-card__hint">主观题答卷仍待处理</p>
      </article>
      <article class="metric-card">
        <p class="metric-card__label">未关闭工单</p>
        <p class="metric-card__value">{{ summary?.open_bug_count ?? 0 }}</p>
        <p class="metric-card__hint">包含新建、处理中、重开状态</p>
      </article>
    </div>

    <!-- Detail Grid -->
    <div class="grid-2">
      <section class="panel-card">
        <h4>部门分布</h4>
        <div v-if="summary?.department_breakdown?.length" class="history-grid">
          <div v-for="item in summary.department_breakdown" :key="item.department" class="history-item">
            <p><strong>{{ item.department }}</strong></p>
            <p>人数：<strong>{{ item.count }}</strong></p>
          </div>
        </div>
        <div v-else class="empty-state">暂无可展示的部门数据。</div>
      </section>

      <section class="panel-card">
        <h4>当前账号摘要</h4>
        <div class="history-grid">
          <div class="history-item">
            <p><strong>姓名</strong></p>
            <p>{{ auth.state.user?.display_name }}</p>
          </div>
          <div class="history-item">
            <p><strong>系统角色</strong></p>
            <p>{{ auth.state.user?.system_role }}</p>
          </div>
          <div class="history-item">
            <p><strong>所属部门</strong></p>
            <p>{{ auth.state.user?.profile.department ?? '无部门' }}</p>
          </div>
          <div v-if="auth.state.user?.profile.game_admin_rank" class="history-item">
            <p><strong>管理等级</strong></p>
            <p>{{ auth.state.user?.profile.game_admin_rank }}</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
