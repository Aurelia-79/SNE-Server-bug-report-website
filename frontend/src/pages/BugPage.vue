<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  Plus,
  ChatDotSquare,
  Download,
  Edit,
  Upload,
} from '@element-plus/icons-vue';

import { apiClient, buildAuthorizedFileUrl } from '../api/client';
import { useAuth } from '../stores/auth';
import type { BugTicket } from '../types';
import { formatDateTime } from '../utils/format';

const auth = useAuth();
const tickets = ref<BugTicket[]>([]);
const loading = ref(false);
const detailVisible = ref(false);
const createVisible = ref(false);
const selectedTicket = ref<BugTicket | null>(null);
const createFiles = ref<File[]>([]);

const createForm = reactive({
  title: '',
  module: '',
  priority: 'medium',
  reproduce_steps: '',
  expected_result: '',
  actual_result: '',
});

const statusForm = reactive({
  status: 'processing',
  assignee_id: null as number | null,
  resolution: '',
  comment: '',
});

const commentForm = reactive({
  content: '',
  files: [] as File[],
});

const canManage = computed(() => auth.isSupervisor.value);

const priorityConfig: Record<string, { label: string; type: string }> = {
  low: { label: '低', type: 'info' },
  medium: { label: '中', type: 'warning' },
  high: { label: '高', type: 'danger' },
  critical: { label: '紧急', type: 'danger' },
};

const statusConfig: Record<string, { label: string; class: string }> = {
  new: { label: '新建', class: 'status-chip' },
  assigned: { label: '已指派', class: 'status-chip--warning' },
  processing: { label: '处理中', class: 'status-chip' },
  resolved: { label: '已解决', class: 'status-chip--success' },
  closed: { label: '已关闭', class: 'status-chip' },
  rejected: { label: '已拒绝', class: 'status-chip--danger' },
  reopened: { label: '重开', class: 'status-chip--warning' },
};

async function loadTickets() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/bugs/tickets');
    tickets.value = data as BugTicket[];
  } finally {
    loading.value = false;
  }
}

async function openTicket(ticket: BugTicket) {
  const { data } = await apiClient.get(`/api/bugs/tickets/${ticket.id}`);
  selectedTicket.value = data as BugTicket;
  statusForm.status = selectedTicket.value.status;
  statusForm.assignee_id = selectedTicket.value.assignee?.id ?? null;
  statusForm.resolution = selectedTicket.value.resolution ?? '';
  statusForm.comment = '';
  commentForm.content = '';
  detailVisible.value = true;
}

function setCreateFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  createFiles.value = Array.from(input.files ?? []);
}

function setCommentFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  commentForm.files = Array.from(input.files ?? []);
}

async function createTicket() {
  try {
    const { data } = await apiClient.post('/api/bugs/tickets', createForm);
    const ticket = data as BugTicket;
    if (createFiles.value.length) {
      const formData = new FormData();
      for (const file of createFiles.value) {
        formData.append('files', file);
      }
      await apiClient.post(`/api/bugs/tickets/${ticket.id}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    ElMessage.success('工单已提交');
    createVisible.value = false;
    await loadTickets();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '提交失败');
  }
}

async function addComment() {
  if (!selectedTicket.value || !commentForm.content) return;
  try {
    const { data } = await apiClient.post(`/api/bugs/tickets/${selectedTicket.value.id}/comments`, {
      content: commentForm.content,
    });
    selectedTicket.value = data as BugTicket;
    if (commentForm.files.length) {
      const formData = new FormData();
      for (const file of commentForm.files) {
        formData.append('files', file);
      }
      await apiClient.post(`/api/bugs/tickets/${selectedTicket.value.id}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    commentForm.content = '';
    commentForm.files = [];
    await openTicket(selectedTicket.value);
    await loadTickets();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '评论失败');
  }
}

async function saveStatus() {
  if (!selectedTicket.value) return;
  try {
    const { data } = await apiClient.patch(`/api/bugs/tickets/${selectedTicket.value.id}`, {
      status: statusForm.status,
      assignee_id: statusForm.assignee_id ? Number(statusForm.assignee_id) : null,
      resolution: statusForm.resolution || null,
      comment: statusForm.comment || null,
    });
    selectedTicket.value = data as BugTicket;
    ElMessage.success('工单已更新');
    await loadTickets();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '更新失败');
  }
}

function attachmentUrl(path: string) {
  return buildAuthorizedFileUrl(path);
}

onMounted(loadTickets);
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Bug Report</p>
        <h3>问题工单</h3>
        <p>成员可提交问题与附件，主管负责分配、处理、关闭和重开工单。</p>
      </div>
      <button class="primary-action" @click="createVisible = true">
        <el-icon><Plus /></el-icon>提交工单
      </button>
    </div>

    <!-- Ticket Table -->
    <section class="panel-card">
      <h4>工单列表</h4>
      <el-table :data="tickets" v-loading="loading" style="width: 100%" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="module" label="模块" min-width="120" />
        <el-table-column label="优先级" min-width="100">
          <template #default="{ row }">
            <span class="status-chip" :class="row.priority === 'critical' || row.priority === 'high' ? 'status-chip--danger' : row.priority === 'medium' ? 'status-chip--warning' : ''">
              {{ priorityConfig[row.priority]?.label ?? row.priority }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <span class="status-chip" :class="statusConfig[row.status]?.class ?? ''">
              {{ statusConfig[row.status]?.label ?? row.status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="提交人" min-width="140">
          <template #default="{ row }">{{ row.reporter.display_name }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openTicket(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- Detail Drawer -->
    <el-drawer v-model="detailVisible" size="min(56vw, 820px)" :with-header="false">
      <div v-if="selectedTicket" class="drawer-stack">
        <!-- Ticket Header -->
        <div class="page-header" style="margin-bottom: 0">
          <div>
            <p class="page-caption">Ticket · #{{ selectedTicket.id }}</p>
            <h3 style="margin: 0 0 var(--space-1)">{{ selectedTicket.title }}</h3>
            <div class="chip-row">
              <span class="status-chip" :class="selectedTicket.priority === 'critical' || selectedTicket.priority === 'high' ? 'status-chip--danger' : selectedTicket.priority === 'medium' ? 'status-chip--warning' : ''">
                {{ priorityConfig[selectedTicket.priority]?.label ?? selectedTicket.priority }}
              </span>
              <span class="status-chip" :class="statusConfig[selectedTicket.status]?.class ?? ''">
                {{ statusConfig[selectedTicket.status]?.label ?? selectedTicket.status }}
              </span>
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-muted)">
                {{ selectedTicket.module }}
              </span>
            </div>
          </div>
        </div>

        <!-- Detail Info -->
        <section class="section-block">
          <h4>问题详情</h4>
          <div style="display: grid; gap: var(--space-3)">
            <div>
              <p style="margin: 0 0 var(--space-1); font-weight: var(--font-weight-semibold); font-size: var(--font-size-sm); color: var(--color-text-secondary)">复现步骤</p>
              <p style="margin: 0;">{{ selectedTicket.reproduce_steps }}</p>
            </div>
            <div>
              <p style="margin: 0 0 var(--space-1); font-weight: var(--font-weight-semibold); font-size: var(--font-size-sm); color: var(--color-text-secondary)">期望结果</p>
              <p style="margin: 0;">{{ selectedTicket.expected_result }}</p>
            </div>
            <div>
              <p style="margin: 0 0 var(--space-1); font-weight: var(--font-weight-semibold); font-size: var(--font-size-sm); color: var(--color-text-secondary)">实际结果</p>
              <p style="margin: 0;">{{ selectedTicket.actual_result }}</p>
            </div>
            <div class="chip-row">
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">
                提单人：{{ selectedTicket.reporter.display_name }}
              </span>
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">
                处理人：{{ selectedTicket.assignee?.display_name ?? '未指派' }}
              </span>
            </div>
          </div>
        </section>

        <!-- Attachments -->
        <section class="section-block">
          <h4>附件</h4>
          <div v-if="selectedTicket.attachments.length" class="file-list">
            <a
              v-for="attachment in selectedTicket.attachments"
              :key="attachment.id"
              class="file-link"
              :href="attachmentUrl(attachment.download_path)"
              target="_blank"
            >
              <span><el-icon><Download /></el-icon> {{ attachment.original_name }}</span>
              <span style="color: var(--color-text-muted)">{{ attachment.mime_type }}</span>
            </a>
          </div>
          <div v-else class="empty-state">暂无附件。</div>
        </section>

        <!-- Comments -->
        <section class="section-block">
          <h4>评论记录</h4>
          <div v-if="selectedTicket.comments.length" style="display: flex; flex-direction: column; gap: var(--space-2)">
            <div v-for="item in selectedTicket.comments" :key="item.id" class="history-item">
              <p><strong>{{ item.author.display_name }}</strong> <span style="color: var(--color-text-muted); font-weight: var(--font-weight-normal)">· {{ formatDateTime(item.created_at) }}</span></p>
              <p style="margin-top: var(--space-1-5)">{{ item.content }}</p>
            </div>
          </div>
          <div v-else class="empty-state">暂无评论。</div>
        </section>

        <!-- Admin Actions -->
        <section v-if="canManage" class="section-block">
          <h4>主管处理</h4>
          <div class="two-column-form">
            <el-select v-model="statusForm.status" placeholder="状态">
              <el-option label="新建" value="new" />
              <el-option label="已指派" value="assigned" />
              <el-option label="处理中" value="processing" />
              <el-option label="已解决" value="resolved" />
              <el-option label="已关闭" value="closed" />
              <el-option label="已拒绝" value="rejected" />
              <el-option label="重开" value="reopened" />
            </el-select>
            <el-input v-model="statusForm.assignee_id" type="number" placeholder="指派人 ID" />
            <el-input v-model="statusForm.resolution" placeholder="处理结果" class="full-span" />
            <el-input v-model="statusForm.comment" placeholder="备注" class="full-span" />
          </div>
          <div class="toolbar" style="margin-top: var(--space-3)">
            <button class="primary-action" @click="saveStatus">
              <el-icon><Edit /></el-icon>保存处理
            </button>
          </div>
        </section>

        <!-- Add Comment -->
        <section class="section-block">
          <h4>添加评论</h4>
          <el-input v-model="commentForm.content" type="textarea" :rows="4" placeholder="补充说明" />
          <div class="upload-box" style="margin-top: var(--space-3)">
            <p><el-icon><Upload /></el-icon> 评论附件</p>
            <input type="file" multiple @change="setCommentFiles" />
          </div>
          <div class="toolbar" style="margin-top: var(--space-3)">
            <button class="primary-action" @click="addComment">
              <el-icon><ChatDotSquare /></el-icon>提交评论
            </button>
          </div>
        </section>
      </div>
    </el-drawer>

    <!-- Create Dialog -->
    <el-dialog v-model="createVisible" title="提交工单" width="min(92vw, 720px)" :close-on-click-modal="false">
      <el-form label-position="top">
        <div class="two-column-form">
          <el-form-item label="标题" class="full-span">
            <el-input v-model="createForm.title" placeholder="简要描述问题" />
          </el-form-item>
          <el-form-item label="所属模块">
            <el-input v-model="createForm.module" placeholder="例如：登录、权限" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="createForm.priority" placeholder="优先级" style="width: 100%">
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="critical" />
            </el-select>
          </el-form-item>
          <el-form-item label="复现步骤" class="full-span">
            <el-input v-model="createForm.reproduce_steps" type="textarea" :rows="3" placeholder="详细描述复现步骤" />
          </el-form-item>
          <el-form-item label="期望结果" class="full-span">
            <el-input v-model="createForm.expected_result" type="textarea" :rows="3" placeholder="描述期望的正确行为" />
          </el-form-item>
          <el-form-item label="实际结果" class="full-span">
            <el-input v-model="createForm.actual_result" type="textarea" :rows="3" placeholder="描述实际出现的错误行为" />
          </el-form-item>
        </div>
      </el-form>
      <div class="upload-box" style="margin-top: var(--space-4)">
        <p><el-icon><Upload /></el-icon> 附件（可选）</p>
        <input type="file" multiple @change="setCreateFiles" />
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createVisible = false">取消</el-button>
          <el-button type="primary" @click="createTicket">提交工单</el-button>
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
