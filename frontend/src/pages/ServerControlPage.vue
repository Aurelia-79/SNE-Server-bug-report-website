<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Refresh, CaretRight, WarningFilled } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type {
  GameServerChatMessage,
  GameServerEmergency,
  GameServerLogResponse,
  GameServerPlayer,
  GameServerStatus,
} from '../types';

const auth = useAuth();

const loading = ref(false);
const logsLoading = ref(false);
const chatLoading = ref(false);
const actionLoading = ref('');
const status = ref<GameServerStatus | null>(null);
const players = ref<GameServerPlayer[]>([]);
const emergency = ref<GameServerEmergency | null>(null);
const logs = ref<GameServerLogResponse | null>(null);
const chat = ref<GameServerChatMessage[]>([]);
const raCommand = ref('');
const logLines = ref(200);

const canRunAnyRa = computed(() => auth.isSuperAdmin.value);
const canRunDangerAction = computed(() => auth.isEmployed.value);

const whitelistCommands = [
  { label: '清理尸体', command: 'cleanup corpses' },
  { label: '清理物品', command: 'cleanup items' },
  { label: '开启核弹', command: 'warhead start' },
  { label: '停止核弹', command: 'warhead stop' },
  { label: '开启紧急撤离', command: 'emergency_escape start' },
];

async function loadOverview() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/server/overview');
    status.value = data.status as GameServerStatus;
    players.value = data.players?.players ?? [];
    emergency.value = data.emergency as GameServerEmergency;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '无法连接游戏服务器桥接插件');
  } finally {
    loading.value = false;
  }
}

async function loadLogs() {
  logsLoading.value = true;
  try {
    const { data } = await apiClient.get('/api/server/logs', { params: { lines: logLines.value } });
    logs.value = data as GameServerLogResponse;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取服务器日志失败');
  } finally {
    logsLoading.value = false;
  }
}

async function loadChat() {
  chatLoading.value = true;
  try {
    const { data } = await apiClient.get('/api/server/chat', { params: { limit: 100 } });
    chat.value = data.messages ?? [];
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取聊天记录失败');
  } finally {
    chatLoading.value = false;
  }
}

async function runRa(command: string) {
  const text = command.trim();
  if (!text) {
    ElMessage.warning('请输入 RA 指令');
    return;
  }
  actionLoading.value = `ra:${text}`;
  try {
    const { data } = await apiClient.post('/api/server/ra', { command: text });
    ElMessage.success(data.message ?? 'RA 指令已执行');
    raCommand.value = '';
    await loadOverview();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? 'RA 指令执行失败');
  } finally {
    actionLoading.value = '';
  }
}

async function runDangerAction(action: 'restart' | 'rnr' | 'shutdown', label: string) {
  try {
    await ElMessageBox.confirm(`确认要${label}吗？该操作会影响当前服务器。`, '危险操作确认', {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: 'warning',
    });
  } catch {
    return;
  }
  actionLoading.value = action;
  try {
    const { data } = await apiClient.post(`/api/server/actions/${action}`, { reason: label });
    ElMessage.success(data.message ?? `${label}指令已发送`);
    await loadOverview();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? `${label}失败`);
  } finally {
    actionLoading.value = '';
  }
}

onMounted(async () => {
  await loadOverview();
  await Promise.all([loadLogs(), loadChat()]);
});
</script>

<template>
  <div class="page-stack server-console-page">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Server Control</p>
        <h3>服务器控制</h3>
        <p>所有登录用户都可以查看；已入职人员可执行服务器操作、白名单 RA、重启、RNR 和关服。</p>
      </div>
      <button class="secondary-action" :disabled="loading" @click="loadOverview">
        <el-icon><Refresh /></el-icon>刷新状态
      </button>
    </div>

    <!-- Status Metrics -->
    <section class="summary-grid" v-loading="loading">
      <div class="metric-card">
        <p class="metric-card__label">在线人数</p>
        <div class="metric-card__value">
          {{ status?.online_count ?? 0 }}<span style="font-size: var(--font-size-lg); color: var(--color-text-muted)"> / {{ status?.max_players ?? '-' }}</span>
        </div>
        <p class="metric-card__hint">{{ status ? '当前服务器在线人数' : '桥接插件未连接' }}</p>
      </div>
      <div class="metric-card">
        <p class="metric-card__label">对局时间</p>
        <div class="metric-card__value">{{ status?.round_time_text ?? '--:--' }}</div>
        <p class="metric-card__hint">
          <span class="status-chip" :class="{ 'status-chip--success': status?.round_in_progress }">
            {{ status?.round_in_progress ? '对局进行中' : '等待/未开局' }}
          </span>
        </p>
      </div>
      <div class="metric-card">
        <p class="metric-card__label">内存占用</p>
        <div class="metric-card__value">{{ status?.memory_working_set_mb ?? 0 }}<span style="font-size: var(--font-size-lg); color: var(--color-text-muted)"> MB</span></div>
        <p class="metric-card__hint">
          Private {{ status?.memory_private_mb ?? 0 }} MB
          <span v-if="status?.memory_gc_mb"> / GC {{ status.memory_gc_mb }} MB</span>
        </p>
      </div>
    </section>

    <!-- Server Status & Actions -->
    <section class="grid-2">
      <div class="panel-card">
        <h4>紧急撤离状态</h4>
        <div class="chip-row">
          <span class="status-chip" :class="{ 'status-chip--success': emergency?.plugin_loaded }">
            {{ emergency?.plugin_loaded ? '插件已加载' : '插件不可用' }}
          </span>
          <span class="status-chip" :class="{ 'status-chip--warning': emergency?.is_active }">
            {{ emergency?.is_active ? '撤离进行中' : '未进行中' }}
          </span>
          <span class="status-chip" :class="{ 'status-chip--success': emergency?.has_started_this_round }">
            {{ emergency?.has_started_this_round ? '本局已触发' : '本局未触发' }}
          </span>
        </div>
        <p class="server-muted" style="margin-top: var(--space-2)">{{ emergency?.message ?? '暂无状态' }}</p>
        <p class="server-muted">撤离时间：{{ emergency?.started_at_round_time_text || '未触发' }}</p>
      </div>

      <div class="panel-card" v-if="canRunDangerAction">
        <h4>服务器操作</h4>
        <div class="toolbar">
          <button class="secondary-action" :disabled="Boolean(actionLoading)" @click="runDangerAction('rnr', '重开本局')">
            <el-icon><CaretRight /></el-icon>RNR
          </button>
          <button class="secondary-action" :disabled="Boolean(actionLoading)" @click="runDangerAction('restart', '重启服务器')">
            <el-icon><Refresh /></el-icon>重启
          </button>
          <button class="secondary-action danger-action" :disabled="Boolean(actionLoading)" @click="runDangerAction('shutdown', '关闭服务器')">
            <el-icon><WarningFilled /></el-icon>关服
          </button>
        </div>
      </div>
    </section>

    <!-- RA Commands -->
    <section v-if="canRunDangerAction || canRunAnyRa" class="panel-card">
      <h4>RA 白名单指令</h4>
      <div class="toolbar">
        <button
          v-for="item in whitelistCommands"
          :key="item.command"
          class="secondary-action"
          :disabled="Boolean(actionLoading)"
          @click="runRa(item.command)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="toolbar server-ra-row" v-if="canRunAnyRa" style="margin-top: var(--space-3)">
        <el-input v-model="raCommand" placeholder="超管任意 RA 指令，例如：broadcast 10 text" clearable style="flex: 1; min-width: 280px" @keyup.enter="runRa(raCommand)" />
        <button class="primary-action" :disabled="Boolean(actionLoading)" @click="runRa(raCommand)">
          <el-icon><CaretRight /></el-icon>发送 RA
        </button>
      </div>
    </section>

    <!-- Player Table -->
    <section class="panel-card">
      <h4>当前玩家</h4>
      <el-table :data="players" style="width: 100%" max-height="360" stripe>
        <el-table-column prop="nickname" label="昵称" min-width="150" />
        <el-table-column prop="player_id" label="人员ID" width="80" />
        <el-table-column prop="steam64" label="Steam64" min-width="160" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" min-width="120" />
        <el-table-column prop="team" label="队伍" min-width="100" />
        <el-table-column label="管理员" width="100">
          <template #default="{ row }">
            <span class="status-chip" :class="{ 'status-chip--success': row.is_admin }" style="font-size: var(--font-size-xs)">
              {{ row.is_admin ? (row.admin_group || '管理员') : '否' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- Logs & Chat -->
    <section class="grid-2">
      <div class="panel-card">
        <div class="server-card-title">
          <h4>控制台输出 / 日志</h4>
          <div class="toolbar">
            <el-input-number v-model="logLines" :min="1" :max="1000" size="small" style="width: 110px" />
            <button class="secondary-action" :disabled="logsLoading" @click="loadLogs">
              <el-icon><Refresh /></el-icon>刷新
            </button>
          </div>
        </div>
        <pre class="server-log-box" v-loading="logsLoading">{{ logs?.available ? logs.lines.join('\n') : (logs?.message ?? '暂无日志') }}</pre>
      </div>

      <div class="panel-card">
        <div class="server-card-title">
          <h4>TextChatMeow 聊天记录</h4>
          <button class="secondary-action" :disabled="chatLoading" @click="loadChat">
            <el-icon><Refresh /></el-icon>刷新
          </button>
        </div>
        <div class="server-chat-list" v-loading="chatLoading">
          <div v-if="!chat.length" class="empty-state">暂无聊天记录或聊天插件不可用</div>
          <div v-for="(item, index) in chat" :key="index" class="history-item">
            <p><strong>{{ item.sender_nickname || '系统' }}</strong>
              <span class="server-muted" style="font-size: var(--font-size-xs)"> [{{ item.type }} / {{ item.sender_role }}]</span>
            </p>
            <p style="margin-top: var(--space-1)">{{ item.text }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
