<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import * as echarts from 'echarts';

import { apiClient } from '../api/client';
import type { GameAdminRank, ScoreOverview } from '../types';

const overview = ref<ScoreOverview | null>(null);
const rankFilter = ref('');
const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

function getChartColors() {
  const isDark = document.documentElement.classList.contains('theme-dark');
  return {
    tooltipBg: isDark ? 'rgba(22, 32, 50, 0.95)' : 'rgba(255, 255, 255, 0.95)',
    tooltipBorder: isDark ? '#334155' : '#E2E8F0',
    tooltipText: isDark ? '#E2E8F0' : '#0F172A',
    axisLabel: isDark ? '#64748B' : '#94A3B8',
    axisLine: isDark ? '#334155' : '#E2E8F0',
    splitLine: isDark ? '#1E293B' : '#F1F5F9',
    labelColor: isDark ? '#CBD5E1' : '#0F172A',
    barAboveAvg: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: '#3B82F6' },
      { offset: 1, color: '#2563EB' },
    ]),
    barBelowAvg: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: '#64748B' },
      { offset: 1, color: '#475569' },
    ]),
  };
}

const ranks: Array<{ label: string; value: GameAdminRank | '' }> = [
  { label: '全部', value: '' },
  { label: '审查期管理员', value: '审查期管理员' },
  { label: '管理员', value: '管理员' },
  { label: '高级管理员', value: '高级管理员' },
  { label: '总管', value: '总管' },
];

async function loadOverview() {
  try {
    const { data } = await apiClient.get('/api/analytics/exams/score-overview', {
      params: rankFilter.value ? { rank: rankFilter.value } : {},
    });
    overview.value = data as ScoreOverview;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取统计失败');
  }
}

function renderChart() {
  if (!chartRef.value || !overview.value) return;
  chartInstance ??= echarts.init(chartRef.value);
  const colors = getChartColors();
  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: colors.tooltipBg,
      borderColor: colors.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: colors.tooltipText, fontSize: 12 },
    },
    grid: { left: 12, right: 12, bottom: 24, top: 36, containLabel: true },
    xAxis: {
      type: 'category',
      data: overview.value.chart_items.map((item) => item.name),
      axisLabel: { interval: 0, rotate: 22, fontSize: 11, color: colors.axisLabel },
      axisLine: { lineStyle: { color: colors.axisLine } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { fontSize: 11, color: colors.axisLabel },
      splitLine: { lineStyle: { color: colors.splitLine, type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        data: overview.value.chart_items.map((item) => ({
          value: item.score,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: item.score >= (overview.value?.summary.average_score ?? 0)
              ? colors.barAboveAvg
              : colors.barBelowAvg,
          },
        })),
        barWidth: '60%',
        label: {
          show: true,
          position: 'top',
          fontSize: 11,
          fontWeight: 600,
          color: colors.labelColor,
          formatter: (params: any) => `${params.value}分`,
        },
      },
    ],
  });
}

watch(overview, () => renderChart());
watch(rankFilter, () => loadOverview());

onMounted(async () => {
  await loadOverview();
  renderChart();

  // Watch for theme changes and re-render chart
  const observer = new MutationObserver(() => renderChart());
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

  onBeforeUnmount(() => {
    observer.disconnect();
    chartInstance?.dispose();
  });
});

// (removed — moved into onMounted)
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Analytics</p>
        <h3>成绩图表</h3>
        <p>查看游戏管理员部门的最新答卷得分、平均分和及格率。</p>
      </div>
      <el-select v-model="rankFilter" placeholder="按等级筛选" clearable style="min-width: 200px">
        <el-option v-for="item in ranks" :key="item.label" :label="item.label" :value="item.value" />
      </el-select>
    </div>

    <!-- Metrics -->
    <div class="summary-grid">
      <article class="metric-card">
        <p class="metric-card__label">答卷数量</p>
        <p class="metric-card__value">{{ overview?.summary.submission_count ?? 0 }}</p>
      </article>
      <article class="metric-card">
        <p class="metric-card__label">平均分</p>
        <p class="metric-card__value">{{ overview?.summary.average_score ?? 0 }}</p>
      </article>
      <article class="metric-card">
        <p class="metric-card__label">及格率</p>
        <p class="metric-card__value" :style="{ color: (overview?.summary.pass_rate ?? 0) >= 60 ? 'var(--color-success)' : 'var(--color-warning)' }">
          {{ overview?.summary.pass_rate ?? 0 }}%
        </p>
      </article>
    </div>

    <!-- Chart -->
    <section class="panel-card">
      <h4>答卷柱状图</h4>
      <div ref="chartRef" class="chart-box" />
    </section>

    <!-- Score Table -->
    <section class="panel-card">
      <h4>成绩明细</h4>
      <el-table :data="overview?.chart_items ?? []" style="width: 100%" stripe>
        <el-table-column prop="name" label="成员" min-width="140" />
        <el-table-column prop="rank" label="等级" min-width="130" />
        <el-table-column prop="score" label="总分" min-width="100">
          <template #default="{ row }">
            <span :style="{ fontWeight: 600, color: row.score >= (overview?.summary.average_score ?? 0) ? 'var(--color-success)' : 'var(--color-text-secondary)' }">
              {{ row.score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="120">
          <template #default="{ row }">
            <span class="status-chip" :class="row.status === 'graded' ? 'status-chip--success' : 'status-chip--warning'">
              {{ row.status === 'graded' ? '已批改' : '待阅卷' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
