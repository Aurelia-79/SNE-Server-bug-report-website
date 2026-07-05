<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { Plus, Edit } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type { Department, GameAdminRank, StaffHistory, User } from '../types';
import { formatDate, formatDateTime, toIsoDateTime } from '../utils/format';

const auth = useAuth();
const departments = ref<Department[]>([]);
const ranks = ref<GameAdminRank[]>([]);
const users = ref<User[]>([]);
const loading = ref(false);
const historyLoading = ref(false);
const drawerVisible = ref(false);
const editVisible = ref(false);
const createVisible = ref(false);
const selectedUser = ref<User | null>(null);
const history = ref<StaffHistory | null>(null);

const filters = reactive({
  department: '',
  rank: '',
});

const GAME_ADMIN_DEPARTMENT = '游戏管理员部门';

const createForm = reactive({
  username: '',
  password: '',
  display_name: '',
  email: '',
  system_role: 'member',
  department: '',
  position_title: '',
  employment_status: '待入职',
  game_admin_rank: '',
  join_date: '',
  leave_date: '',
  notes: '',
  is_active: true,
});

const actionForm = reactive({
  employment: {
    record_type: 'join',
    new_status: '在职',
    reason: '',
    remark: '',
    effective_at: '',
  },
  rank: {
    change_type: 'promote',
    new_rank: '管理员',
    reason: '',
    remark: '',
    effective_at: '',
  },
  punishment: {
    level: '警告',
    reason: '',
    remark: '',
    effective_at: '',
  },
});

const canCreateUser = computed(() => auth.isSuperAdmin.value);
const canSetGameAdminRank = computed(() => (
  createForm.system_role !== 'super_admin' && createForm.department === GAME_ADMIN_DEPARTMENT
));
const canManageSelected = computed(() => {
  if (!selectedUser.value || !auth.state.user) return false;
  if (auth.isSupervisor.value) return true;
  return auth.state.user.profile.department === '游戏管理员部门'
    && auth.state.user.profile.game_admin_rank === '总管'
    && selectedUser.value.profile.department === '游戏管理员部门';
});

watch(
  () => [createForm.system_role, createForm.department],
  () => {
    if (!canSetGameAdminRank.value) {
      createForm.game_admin_rank = '';
    }
  },
);

async function loadMeta() {
  const { data } = await apiClient.get('/api/staff/meta');
  departments.value = data.departments;
  ranks.value = data.game_admin_ranks;
}

async function loadUsers() {
  loading.value = true;
  try {
    const { data } = await apiClient.get('/api/staff/users', { params: filters });
    users.value = data as User[];
  } finally {
    loading.value = false;
  }
}

async function openDetail(user: User) {
  selectedUser.value = user;
  drawerVisible.value = true;
  history.value = null;
  historyLoading.value = true;
  try {
    const { data } = await apiClient.get(`/api/personnel/staff/${user.id}/history`);
    history.value = data as StaffHistory;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取历史失败');
  } finally {
    historyLoading.value = false;
  }
}

function openCreate() {
  Object.assign(createForm, {
    username: '',
    password: '',
    display_name: '',
    email: '',
    system_role: 'member',
    department: '',
    position_title: '',
    employment_status: '待入职',
    game_admin_rank: '',
    join_date: '',
    leave_date: '',
    notes: '',
    is_active: true,
  });
  createVisible.value = true;
}

function openEdit(user: User) {
  Object.assign(createForm, {
    username: user.username,
    password: '',
    display_name: user.display_name,
    email: user.email ?? '',
    system_role: user.system_role,
    department: user.profile.department ?? '',
    position_title: user.profile.position_title,
    employment_status: user.profile.employment_status,
    game_admin_rank: user.profile.game_admin_rank ?? '',
    join_date: user.profile.join_date ?? '',
    leave_date: user.profile.leave_date ?? '',
    notes: user.profile.notes ?? '',
    is_active: user.is_active,
  });
  editVisible.value = true;
}

async function saveUser(mode: 'create' | 'edit') {
  const department = createForm.system_role === 'super_admin' ? null : (createForm.department || null);
  const payload = {
    username: createForm.username,
    password: createForm.password || undefined,
    display_name: createForm.display_name,
    email: createForm.email || null,
    system_role: createForm.system_role,
    department,
    position_title: createForm.position_title,
    employment_status: createForm.employment_status,
    game_admin_rank: department === GAME_ADMIN_DEPARTMENT ? (createForm.game_admin_rank || null) : null,
    join_date: createForm.join_date || null,
    leave_date: createForm.leave_date || null,
    notes: createForm.notes || null,
    is_active: createForm.is_active,
  };
  try {
    if (mode === 'create') {
      await apiClient.post('/api/staff/users', payload);
      ElMessage.success('账号已创建');
      createVisible.value = false;
    } else if (selectedUser.value) {
      await apiClient.patch(`/api/staff/users/${selectedUser.value.id}`, payload);
      ElMessage.success('账号已更新');
      editVisible.value = false;
    }
    await loadUsers();
    if (selectedUser.value) {
      const refreshed = users.value.find((item) => item.id === selectedUser.value?.id);
      if (refreshed) {
        selectedUser.value = refreshed;
      }
      await openDetail(selectedUser.value);
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '保存失败');
  }
}

async function submitEmployment() {
  if (!selectedUser.value) return;
  await apiClient.post('/api/personnel/employment-records', {
    user_id: selectedUser.value.id,
    record_type: actionForm.employment.record_type,
    new_status: actionForm.employment.new_status,
    reason: actionForm.employment.reason,
    remark: actionForm.employment.remark || null,
    effective_at: toIsoDateTime(actionForm.employment.effective_at),
  });
  ElMessage.success('入离职记录已保存');
  await openDetail(selectedUser.value);
  await loadUsers();
}

async function submitRankChange() {
  if (!selectedUser.value) return;
  await apiClient.post('/api/personnel/promotion-records', {
    user_id: selectedUser.value.id,
    change_type: actionForm.rank.change_type,
    new_rank: actionForm.rank.new_rank,
    reason: actionForm.rank.reason,
    remark: actionForm.rank.remark || null,
    effective_at: toIsoDateTime(actionForm.rank.effective_at),
  });
  ElMessage.success('升降级记录已保存');
  await openDetail(selectedUser.value);
  await loadUsers();
}

async function submitPunishment() {
  if (!selectedUser.value) return;
  await apiClient.post('/api/personnel/punishments', {
    user_id: selectedUser.value.id,
    level: actionForm.punishment.level,
    reason: actionForm.punishment.reason,
    remark: actionForm.punishment.remark || null,
    effective_at: toIsoDateTime(actionForm.punishment.effective_at),
  });
  ElMessage.success('处罚记录已保存');
  await openDetail(selectedUser.value);
}

onMounted(async () => {
  await loadMeta();
  await loadUsers();
});
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Staff Ops</p>
        <h3>人员与人事管理</h3>
        <p>覆盖入职、离职、升降级、处罚与人员档案查看；超级管理员可创建和更新账号。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="filters.department" placeholder="部门筛选" clearable style="min-width: 160px" @change="loadUsers">
          <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.rank" placeholder="等级筛选" clearable style="min-width: 160px" @change="loadUsers">
          <el-option v-for="item in ranks" :key="item" :label="item" :value="item" />
        </el-select>
        <button v-if="canCreateUser" class="primary-action" @click="openCreate">
          <el-icon><Plus /></el-icon>新增账号
        </button>
      </div>
    </div>

    <!-- User Table -->
    <section class="panel-card">
      <h4>人员列表</h4>
      <el-table :data="users" v-loading="loading" style="width: 100%" stripe @row-click="openDetail">
        <el-table-column prop="display_name" label="姓名" min-width="140" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column label="部门" min-width="140">
          <template #default="{ row }">{{ row.profile.department ?? '无部门' }}</template>
        </el-table-column>
        <el-table-column label="职位" min-width="140">
          <template #default="{ row }">{{ row.profile.position_title }}</template>
        </el-table-column>
        <el-table-column label="等级" min-width="140">
          <template #default="{ row }">{{ row.profile.game_admin_rank ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <span class="status-chip" :class="row.profile.employment_status === '在职' ? 'status-chip--success' : row.profile.employment_status === '离职' ? 'status-chip--danger' : 'status-chip--warning'">
              {{ row.profile.employment_status }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="系统角色" min-width="120">
          <template #default="{ row }">{{ row.system_role }}</template>
        </el-table-column>
      </el-table>
    </section>

    <!-- Detail Drawer -->
    <el-drawer v-model="drawerVisible" size="min(52%, 720px)" :with-header="false">
      <div v-if="selectedUser" class="drawer-stack">
        <!-- User Header -->
        <div class="page-header" style="margin-bottom: 0">
          <div>
            <p class="page-caption">Profile</p>
            <h3 style="margin: 0 0 var(--space-1)">{{ selectedUser.display_name }}</h3>
            <div class="chip-row">
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">{{ selectedUser.username }}</span>
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">{{ selectedUser.profile.department ?? '无部门' }}</span>
              <span class="status-chip" :class="selectedUser.profile.employment_status === '在职' ? 'status-chip--success' : selectedUser.profile.employment_status === '离职' ? 'status-chip--danger' : 'status-chip--warning'">
                {{ selectedUser.profile.employment_status }}
              </span>
            </div>
          </div>
          <button v-if="canManageSelected" class="secondary-action" @click="openEdit(selectedUser)">
            <el-icon><Edit /></el-icon>编辑账号
          </button>
        </div>

        <!-- Basic Info -->
        <div class="grid-2">
          <section class="section-block">
            <h4>基础信息</h4>
            <div style="display: grid; gap: var(--space-1-5)">
              <p style="margin: 0; font-size: var(--font-size-sm)"><strong>职位：</strong>{{ selectedUser.profile.position_title }}</p>
              <p style="margin: 0; font-size: var(--font-size-sm)"><strong>管理等级：</strong>{{ selectedUser.profile.game_admin_rank ?? '-' }}</p>
              <p style="margin: 0; font-size: var(--font-size-sm)"><strong>入职日期：</strong>{{ formatDate(selectedUser.profile.join_date) }}</p>
              <p style="margin: 0; font-size: var(--font-size-sm)"><strong>离职日期：</strong>{{ formatDate(selectedUser.profile.leave_date) }}</p>
            </div>
          </section>
          <section class="section-block">
            <h4>最近备注</h4>
            <p style="margin: 0; font-size: var(--font-size-sm); color: var(--color-text-secondary)">{{ selectedUser.profile.notes ?? '暂无备注' }}</p>
          </section>
        </div>

        <!-- Employment History -->
        <section class="section-block">
          <h4>入离职记录</h4>
          <div v-if="historyLoading" style="text-align: center; padding: var(--space-6); color: var(--color-text-muted)">加载中...</div>
          <div v-else class="history-grid">
            <div v-for="item in history?.employment_records ?? []" :key="item.id" class="history-item">
              <p><strong>{{ item.record_type === 'join' ? '入职' : '离职' }}</strong></p>
              <p>{{ item.reason }}</p>
              <p style="color: var(--color-text-muted); font-size: var(--font-size-xs)">{{ formatDateTime(item.effective_at) }}</p>
            </div>
            <div v-if="!(history?.employment_records?.length)" class="empty-state">暂无记录。</div>
          </div>
        </section>

        <!-- Rank History -->
        <section class="section-block">
          <h4>升降级记录</h4>
          <div class="history-grid">
            <div v-for="item in history?.promotion_records ?? []" :key="item.id" class="history-item">
              <p><strong>{{ item.change_type === 'promote' ? '晋升' : '降级' }}</strong></p>
              <p>{{ item.previous_rank ?? '-' }} → <strong>{{ item.new_rank }}</strong></p>
              <p style="color: var(--color-text-secondary)">{{ item.reason }}</p>
              <p style="color: var(--color-text-muted); font-size: var(--font-size-xs)">{{ formatDateTime(item.effective_at) }}</p>
            </div>
            <div v-if="!(history?.promotion_records?.length)" class="empty-state">暂无记录。</div>
          </div>
        </section>

        <!-- Punishment History -->
        <section class="section-block">
          <h4>处罚记录</h4>
          <div class="history-grid">
            <div v-for="item in history?.punishments ?? []" :key="item.id" class="history-item">
              <p><strong>{{ item.level }}</strong></p>
              <p>{{ item.reason }}</p>
              <p style="color: var(--color-text-muted); font-size: var(--font-size-xs)">{{ formatDateTime(item.effective_at) }}</p>
            </div>
            <div v-if="!(history?.punishments?.length)" class="empty-state">暂无记录。</div>
          </div>
        </section>

        <!-- Management Actions -->
        <section v-if="canManageSelected" class="grid-2">
          <div class="section-block">
            <h4>登记入离职</h4>
            <el-form label-position="top">
              <div class="two-column-form">
                <el-form-item label="类型">
                  <el-select v-model="actionForm.employment.record_type" placeholder="类型" style="width: 100%">
                    <el-option label="入职" value="join" />
                    <el-option label="离职" value="leave" />
                  </el-select>
                </el-form-item>
                <el-form-item label="状态">
                  <el-select v-model="actionForm.employment.new_status" placeholder="状态" style="width: 100%">
                    <el-option label="待入职" value="待入职" />
                    <el-option label="在职" value="在职" />
                    <el-option label="离职" value="离职" />
                  </el-select>
                </el-form-item>
                <el-form-item label="原因" class="full-span">
                  <el-input v-model="actionForm.employment.reason" placeholder="原因" />
                </el-form-item>
                <el-form-item label="备注" class="full-span">
                  <el-input v-model="actionForm.employment.remark" placeholder="备注" />
                </el-form-item>
                <el-form-item label="生效日期" class="full-span">
                  <el-input v-model="actionForm.employment.effective_at" type="datetime-local" style="width: 100%" />
                </el-form-item>
              </div>
            </el-form>
            <button class="primary-action" style="margin-top: var(--space-3)" @click="submitEmployment">
              <el-icon><Edit /></el-icon>保存入离职
            </button>
          </div>

          <div class="section-block">
            <h4>登记升降级</h4>
            <el-form label-position="top">
              <div class="two-column-form">
                <el-form-item label="变更类型">
                  <el-select v-model="actionForm.rank.change_type" placeholder="变更类型" style="width: 100%">
                    <el-option label="晋升" value="promote" />
                    <el-option label="降级" value="demote" />
                  </el-select>
                </el-form-item>
                <el-form-item label="新等级">
                  <el-select v-model="actionForm.rank.new_rank" placeholder="新等级" style="width: 100%">
                    <el-option v-for="item in ranks" :key="item" :label="item" :value="item" />
                  </el-select>
                </el-form-item>
                <el-form-item label="原因" class="full-span">
                  <el-input v-model="actionForm.rank.reason" placeholder="升降级原因" />
                </el-form-item>
                <el-form-item label="备注" class="full-span">
                  <el-input v-model="actionForm.rank.remark" placeholder="升降级备注" />
                </el-form-item>
                <el-form-item label="生效日期" class="full-span">
                  <el-input v-model="actionForm.rank.effective_at" type="datetime-local" style="width: 100%" />
                </el-form-item>
              </div>
            </el-form>
            <button class="primary-action" style="margin-top: var(--space-3)" @click="submitRankChange">
              <el-icon><Edit /></el-icon>保存升降级
            </button>

            <div style="margin-top: var(--space-5); border-top: 1px solid var(--color-border-light); padding-top: var(--space-4)">
              <h4 style="font-size: var(--font-size-base)">登记处罚</h4>
              <el-form label-position="top">
                <div class="two-column-form">
                  <el-form-item label="处罚等级">
                    <el-input v-model="actionForm.punishment.level" placeholder="处罚等级" />
                  </el-form-item>
                  <el-form-item label="生效日期">
                    <el-input v-model="actionForm.punishment.effective_at" type="datetime-local" />
                  </el-form-item>
                  <el-form-item label="原因" class="full-span">
                    <el-input v-model="actionForm.punishment.reason" placeholder="处罚原因" />
                  </el-form-item>
                  <el-form-item label="备注" class="full-span">
                    <el-input v-model="actionForm.punishment.remark" placeholder="处罚备注" />
                  </el-form-item>
                </div>
              </el-form>
              <button class="primary-action" style="margin-top: var(--space-3)" @click="submitPunishment">
                <el-icon><Edit /></el-icon>保存处罚
              </button>
            </div>
          </div>
        </section>
      </div>
    </el-drawer>

    <!-- Create Dialog -->
    <el-dialog v-model="createVisible" title="新增账号" width="min(92vw, 680px)" :close-on-click-modal="false">
      <el-form label-position="top">
        <div class="two-column-form">
          <el-form-item label="用户名">
            <el-input v-model="createForm.username" placeholder="用户名" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="createForm.password" type="password" show-password placeholder="初始密码" />
          </el-form-item>
          <el-form-item label="显示名">
            <el-input v-model="createForm.display_name" placeholder="显示名" />
          </el-form-item>
          <el-form-item label="电子邮箱">
            <el-input v-model="createForm.email" placeholder="电子邮箱" />
          </el-form-item>
          <el-form-item label="系统角色">
            <el-select v-model="createForm.system_role" placeholder="系统角色" style="width: 100%">
              <el-option label="member" value="member" />
              <el-option label="supervisor" value="supervisor" />
              <el-option label="super_admin" value="super_admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="部门">
            <el-select v-model="createForm.department" placeholder="部门" clearable style="width: 100%">
              <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="职位名称">
            <el-input v-model="createForm.position_title" placeholder="职位名称" />
          </el-form-item>
          <el-form-item label="入职状态">
            <el-select v-model="createForm.employment_status" placeholder="入职状态" style="width: 100%">
              <el-option label="待入职" value="待入职" />
              <el-option label="在职" value="在职" />
              <el-option label="离职" value="离职" />
            </el-select>
          </el-form-item>
          <el-form-item label="管理等级">
            <el-select
              v-model="createForm.game_admin_rank"
              placeholder="仅游戏管理员部门需要"
              clearable
              :disabled="!canSetGameAdminRank"
              style="width: 100%"
            >
              <el-option v-for="item in ranks" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="入职日期">
            <el-input v-model="createForm.join_date" type="date" />
          </el-form-item>
          <el-form-item label="离职日期">
            <el-input v-model="createForm.leave_date" type="date" />
          </el-form-item>
          <el-form-item label="备注" class="full-span">
            <el-input v-model="createForm.notes" placeholder="备注" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createVisible = false">取消</el-button>
          <el-button type="primary" @click="saveUser('create')">保存账号</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Edit Dialog -->
    <el-dialog v-model="editVisible" title="编辑账号" width="min(92vw, 680px)" :close-on-click-modal="false">
      <el-form label-position="top">
        <div class="two-column-form">
          <el-form-item label="显示名">
            <el-input v-model="createForm.display_name" placeholder="显示名" />
          </el-form-item>
          <el-form-item label="电子邮箱">
            <el-input v-model="createForm.email" placeholder="电子邮箱" />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="createForm.password" type="password" show-password placeholder="留空不改" />
          </el-form-item>
          <el-form-item label="系统角色">
            <el-select v-model="createForm.system_role" placeholder="系统角色" style="width: 100%">
              <el-option label="member" value="member" />
              <el-option label="supervisor" value="supervisor" />
              <el-option label="super_admin" value="super_admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="部门">
            <el-select v-model="createForm.department" placeholder="部门" clearable style="width: 100%">
              <el-option v-for="item in departments" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="职位名称">
            <el-input v-model="createForm.position_title" placeholder="职位名称" />
          </el-form-item>
          <el-form-item label="入职状态">
            <el-select v-model="createForm.employment_status" placeholder="入职状态" style="width: 100%">
              <el-option label="待入职" value="待入职" />
              <el-option label="在职" value="在职" />
              <el-option label="离职" value="离职" />
            </el-select>
          </el-form-item>
          <el-form-item label="管理等级">
            <el-select
              v-model="createForm.game_admin_rank"
              placeholder="仅游戏管理员部门需要"
              clearable
              :disabled="!canSetGameAdminRank"
              style="width: 100%"
            >
              <el-option v-for="item in ranks" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="入职日期">
            <el-input v-model="createForm.join_date" type="date" />
          </el-form-item>
          <el-form-item label="离职日期">
            <el-input v-model="createForm.leave_date" type="date" />
          </el-form-item>
          <el-form-item label="备注" class="full-span">
            <el-input v-model="createForm.notes" placeholder="备注" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editVisible = false">取消</el-button>
          <el-button type="primary" @click="saveUser('edit')">保存修改</el-button>
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
