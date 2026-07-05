<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Delete, View, Refresh, Edit } from '@element-plus/icons-vue';

import { apiClient, buildAuthorizedFileUrl } from '../api/client';
import { useAuth } from '../stores/auth';
import type {
  AvailableExamPaper,
  ExamPaper,
  ExamPaperDraft,
  ExamPaperDraftQuestion,
  ExamSubmission,
  ManagedExamPaper,
  QuestionType,
} from '../types';
import { formatDateTime } from '../utils/format';

const auth = useAuth();
const router = useRouter();

const activePaper = ref<ExamPaper | null>(null);
const availablePapers = ref<AvailableExamPaper[]>([]);
const managedPapers = ref<ManagedExamPaper[]>([]);
const managedPaper = ref<ExamPaper | null>(null);
const submissions = ref<ExamSubmission[]>([]);
const selectedSubmission = ref<ExamSubmission | null>(null);
const loading = ref(false);
const savingPaper = ref(false);
const reviewVisible = ref(false);
const managePaperHint = ref('');

const reviewScores = reactive<Record<number, { manual_score: number; grader_comment: string }>>({});
const overallComment = ref('');

const draft = reactive<ExamPaperDraft>({
  title: '游戏管理员入职考核卷',
  description: '用于人事部创建和维护游戏管理员入职考核试卷。',
  pass_score: 60,
  questions: [],
});

const canTakeExam = computed(() => auth.canTakeExam.value);
const canManagePaper = computed(() => auth.canManageExamPaper.value);
const canReview = computed(() => auth.canReviewExam.value);

function emptyDraftQuestion(type: 'single_choice' | 'text', index: number): ExamPaperDraftQuestion {
  return type === 'single_choice'
    ? {
        order_no: index,
        prompt: '',
        question_type: 'single_choice',
        score: 10,
        options: [
          { label: 'A', text: '选项 A' },
          { label: 'B', text: '选项 B' },
        ],
        correct_answer: 'A',
      }
    : {
        order_no: index,
        prompt: '',
        question_type: 'text',
        score: 20,
        options: [],
        correct_answer: '',
      };
}

function resetDraft() {
  draft.title = '游戏管理员入职考核卷';
  draft.description = '用于人事部创建和维护游戏管理员入职考核试卷。';
  draft.pass_score = 60;
  draft.questions.splice(0, draft.questions.length);
}

function hydrateDraftFromPaper(paper: ExamPaper) {
  resetDraft();
  const supported = paper.questions.every((question) => question.question_type === 'single_choice' || question.question_type === 'text');
  if (!supported) {
    managePaperHint.value = '当前最新试卷包含旧题型，建议重新创建一套只包含选择题和简答题的新试卷。';
    return;
  }

  managePaperHint.value = '';
  draft.title = paper.title;
  draft.description = paper.description ?? '';
  draft.pass_score = paper.pass_score;
  for (const question of paper.questions) {
    draft.questions.push({
      order_no: question.order_no,
      prompt: question.prompt,
      question_type: question.question_type as 'single_choice' | 'text',
      score: question.score,
      options:
        question.question_type === 'single_choice'
          ? (question.options ?? []).map((item) => ({ label: item.label, text: item.text }))
          : [],
      correct_answer:
        question.question_type === 'single_choice'
          ? String(question.correct_answer ?? '')
          : '',
    });
  }
}

function addDraftQuestion(type: 'single_choice' | 'text') {
  draft.questions.push(emptyDraftQuestion(type, draft.questions.length + 1));
}

function removeDraftQuestion(index: number) {
  draft.questions.splice(index, 1);
  draft.questions.forEach((question, idx) => {
    question.order_no = idx + 1;
  });
}

function addOption(questionIndex: number) {
  const question = draft.questions[questionIndex];
  const nextLabel = String.fromCharCode(65 + question.options.length);
  question.options.push({ label: nextLabel, text: `选项 ${nextLabel}` });
}

function removeOption(questionIndex: number, optionIndex: number) {
  const question = draft.questions[questionIndex];
  question.options.splice(optionIndex, 1);
  question.options.forEach((option, idx) => {
    option.label = String.fromCharCode(65 + idx);
  });
  if (!question.options.some((option) => option.label === question.correct_answer)) {
    question.correct_answer = question.options[0]?.label ?? '';
  }
}

async function loadActivePaper() {
  if (!canTakeExam.value) return;
  const { data } = await apiClient.get('/api/exams/papers/available');
  availablePapers.value = data as AvailableExamPaper[];
  activePaper.value = null;
}

async function loadManagedPaper() {
  if (!canManagePaper.value) return;
  const [{ data: paperData }, { data: listData }] = await Promise.all([
    apiClient.get('/api/exams/manage/paper'),
    apiClient.get('/api/exams/manage/papers'),
  ]);
  managedPapers.value = listData as ManagedExamPaper[];
  managedPaper.value = (paperData as ExamPaper | null) ?? null;
  if (managedPaper.value) {
    hydrateDraftFromPaper(managedPaper.value);
  }
}

async function loadPaperIntoEditor(paperId: number) {
  const { data } = await apiClient.get(`/api/exams/manage/papers/${paperId}`);
  managedPaper.value = data as ExamPaper;
  hydrateDraftFromPaper(managedPaper.value);
  ElMessage.success('试卷已载入编辑区');
}

async function loadSubmissions() {
  if (!canReview.value && !canTakeExam.value) return;
  const { data } = await apiClient.get('/api/exams/submissions');
  submissions.value = data as ExamSubmission[];
}

async function saveManagedPaper() {
  if (!draft.questions.length) {
    ElMessage.warning('请至少添加一道题目');
    return;
  }

  savingPaper.value = true;
  try {
    const payload = {
      title: draft.title,
      description: draft.description || null,
      pass_score: draft.pass_score,
      questions: draft.questions.map((question) => ({
        order_no: question.order_no,
        prompt: question.prompt,
        question_type: question.question_type,
        score: question.score,
        options:
          question.question_type === 'single_choice'
            ? question.options.map((option) => ({ label: option.label, text: option.text }))
            : null,
        correct_answer: question.question_type === 'single_choice' ? question.correct_answer : null,
      })),
    };
    const { data } = await apiClient.post('/api/exams/manage/paper', payload);
    managedPaper.value = data as ExamPaper;
    hydrateDraftFromPaper(managedPaper.value);
    ElMessage.success('试卷已保存并发布');
    await loadActivePaper();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '保存失败');
  } finally {
    savingPaper.value = false;
  }
}

async function deleteManagedPaper() {
  if (!managedPaper.value) return;
  try {
    await ElMessageBox.confirm(
      `确定删除试卷"${managedPaper.value.title}"吗？已有答卷记录的试卷不会被允许删除。`,
      '删除试卷',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    );
    await apiClient.delete(`/api/exams/manage/paper/${managedPaper.value.id}`);
    ElMessage.success('试卷已删除');
    managedPaper.value = null;
    resetDraft();
    await loadAll();
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return;
    ElMessage.error(error?.response?.data?.detail ?? '删除失败');
  }
}

function openReview(submission: ExamSubmission) {
  selectedSubmission.value = submission;
  overallComment.value = submission.overall_comment ?? '';
  for (const key of Object.keys(reviewScores)) {
    delete reviewScores[Number(key)];
  }
  for (const answer of submission.answers) {
    if (answer.question.question_type === 'text') {
      reviewScores[answer.id] = {
        manual_score: answer.manual_score ?? 0,
        grader_comment: answer.grader_comment ?? '',
      };
    }
  }
  reviewVisible.value = true;
}

async function saveReview() {
  if (!selectedSubmission.value) return;
  const answers = selectedSubmission.value.answers
    .filter((item) => item.question.question_type === 'text')
    .map((item) => ({
      answer_id: item.id,
      manual_score: reviewScores[item.id]?.manual_score ?? 0,
      grader_comment: reviewScores[item.id]?.grader_comment ?? '',
    }));

  try {
    const { data } = await apiClient.post(`/api/exams/submissions/${selectedSubmission.value.id}/grade`, {
      answers,
      overall_comment: overallComment.value || null,
    });
    selectedSubmission.value = data as ExamSubmission;
    ElMessage.success('阅卷已保存');
    await loadSubmissions();
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '保存失败');
  }
}

function previewUrl(path: string) {
  return buildAuthorizedFileUrl(path);
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([loadActivePaper(), loadManagedPaper(), loadSubmissions()]);
  } finally {
    loading.value = false;
  }
}

function normalizedQuestionTypeLabel(type: QuestionType) {
  if (type === 'single_choice') return '选择题';
  if (type === 'text') return '简答题';
  return type;
}

onMounted(loadAll);
</script>

<template>
  <div class="page-stack">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">Exams</p>
        <h3>试卷与阅卷</h3>
        <p>所有登录用户都可以作答试卷；选择题自动判分，简答题由人事部或系统超管手动批改。</p>
      </div>
      <button class="secondary-action" :disabled="loading" @click="loadAll">
        <el-icon><Refresh /></el-icon>刷新数据
      </button>
    </div>

    <!-- Paper Management -->
    <section v-if="canManagePaper" class="panel-card">
      <h4>试卷管理</h4>
      <p style="font-size: var(--font-size-sm); color: var(--color-text-secondary); margin: 0 0 var(--space-4)">
        当前会把你保存的试卷设为最新可用试卷。只保留选择题与简答题。
      </p>

      <!-- Current Paper Info -->
      <div v-if="managedPaper" class="history-item" style="margin-bottom: var(--space-4)">
        <strong>最新试卷：</strong>{{ managedPaper.title }} · {{ managedPaper.questions.length }} 题 · 及格线 {{ managedPaper.pass_score }} 分
      </div>

      <!-- Paper List -->
      <div class="section-block" style="margin-bottom: var(--space-4)">
        <h4>试卷列表（共 {{ managedPapers.length }} 份）</h4>
        <div v-if="managedPapers.length" class="history-grid" style="margin-top: var(--space-3)">
          <article v-for="paper in managedPapers" :key="paper.id" class="history-item">
            <p><strong>#{{ paper.id }} · {{ paper.title }}</strong></p>
            <p>{{ paper.question_count }} 题 · 及格线 {{ paper.pass_score }} 分 · 答卷 {{ paper.submission_count }} 份</p>
            <span v-if="paper.is_active" class="status-chip status-chip--success" style="margin-top: var(--space-1)">启用中</span>
            <span v-else class="status-chip" style="margin-top: var(--space-1)">已停用</span>
            <div class="toolbar" style="margin-top: var(--space-2)">
              <button class="secondary-action" @click="loadPaperIntoEditor(paper.id)">
                <el-icon><Edit /></el-icon>载入编辑
              </button>
              <button class="secondary-action" @click="router.push(`/exams/preview?paper_id=${paper.id}`)">
                <el-icon><View /></el-icon>预览
              </button>
              <button
                class="secondary-action danger-action"
                :disabled="!paper.can_delete"
                @click="loadPaperIntoEditor(paper.id).then(deleteManagedPaper)"
              >
                <el-icon><Delete /></el-icon>{{ paper.can_delete ? '删除' : '已有答卷不可删' }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="empty-state">还没有创建任何试卷。</div>
      </div>

      <!-- Hint -->
      <div v-if="managePaperHint" class="empty-state" style="text-align: left; margin-bottom: var(--space-4)">
        {{ managePaperHint }}
      </div>

      <!-- Draft Editor -->
      <div class="two-column-form" style="margin-bottom: var(--space-4)">
        <el-input v-model="draft.title" placeholder="试卷标题" class="full-span" size="large" />
        <el-input v-model="draft.description" type="textarea" :rows="2" placeholder="试卷说明" class="full-span" />
        <el-input v-model="draft.pass_score" type="number" placeholder="及格线分数">
          <template #prefix>及格线</template>
        </el-input>
      </div>

      <!-- Draft Actions -->
      <div class="toolbar" style="margin-bottom: var(--space-4)">
        <button class="secondary-action" @click="addDraftQuestion('single_choice')">
          <el-icon><Plus /></el-icon>添加选择题
        </button>
        <button class="secondary-action" @click="addDraftQuestion('text')">
          <el-icon><Plus /></el-icon>添加简答题
        </button>
        <button class="secondary-action" :disabled="!managedPaper" @click="router.push(`/exams/preview?paper_id=${managedPaper?.id}`)">
          <el-icon><View /></el-icon>预览试卷
        </button>
        <button class="secondary-action danger-action" :disabled="!managedPaper" @click="deleteManagedPaper">
          <el-icon><Delete /></el-icon>删除当前
        </button>
        <button class="primary-action" :disabled="savingPaper" @click="saveManagedPaper">
          <el-icon><Edit /></el-icon>保存并发布
        </button>
      </div>

      <!-- Question List -->
      <div class="history-grid">
        <article v-for="(question, index) in draft.questions" :key="index" class="question-card">
          <div class="question-card__meta">
            <span>第 {{ question.order_no }} 题</span>
            <span class="status-chip" style="background: var(--color-primary-light); color: var(--color-primary)">
              {{ question.question_type === 'single_choice' ? '选择题' : '简答题' }}
            </span>
            <span>{{ question.score }} 分</span>
          </div>

          <div class="two-column-form">
            <el-select v-model="question.question_type" placeholder="题型" style="width: 100%">
              <el-option label="选择题" value="single_choice" />
              <el-option label="简答题" value="text" />
            </el-select>
            <el-input v-model="question.score" type="number" placeholder="分值" />
            <el-input v-model="question.prompt" placeholder="题目内容" class="full-span" type="textarea" :rows="2" />
          </div>

          <!-- Options (Single Choice) -->
          <template v-if="question.question_type === 'single_choice'">
            <div class="section-block" style="padding: var(--space-4)">
              <div class="toolbar" style="justify-content: space-between">
                <strong style="font-size: var(--font-size-sm)">选项</strong>
                <button class="secondary-action" @click="addOption(index)">
                  <el-icon><Plus /></el-icon>新增选项
                </button>
              </div>
              <div class="history-grid" style="margin-top: var(--space-3)">
                <div v-for="(option, optionIndex) in question.options" :key="optionIndex" class="two-column-form" style="align-items: end">
                  <el-input v-model="option.label" placeholder="标签" style="width: 80px" />
                  <el-input v-model="option.text" placeholder="选项内容" />
                  <button class="secondary-action" style="height: fit-content" @click="removeOption(index, optionIndex)">
                    <el-icon><Delete /></el-icon>
                  </button>
                </div>
              </div>
              <el-input
                v-model="question.correct_answer"
                style="margin-top: var(--space-3)"
                placeholder="正确答案标签，例如 A"
              >
                <template #prefix>正确答案</template>
              </el-input>
            </div>
          </template>

          <!-- Text Description -->
          <template v-else>
            <div class="section-block" style="padding: var(--space-4)">
              <strong style="font-size: var(--font-size-sm)">简答题说明</strong>
              <p style="margin-top: var(--space-1-5); color: var(--color-text-secondary); font-size: var(--font-size-sm)">
                简答题不需要选项与标准答案，提交后由人事部手动批改。
              </p>
            </div>
          </template>

          <!-- Delete Question -->
          <div class="toolbar" style="justify-content: flex-end">
            <button class="secondary-action danger-action" @click="removeDraftQuestion(index)">
              <el-icon><Delete /></el-icon>删除题目
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- Available Papers -->
    <section v-if="canTakeExam" class="panel-card">
      <h4>可选试卷</h4>
      <div v-if="availablePapers.length" class="history-grid" style="margin-top: var(--space-3)">
        <article v-for="paper in availablePapers" :key="paper.id" class="history-item">
          <p><strong>{{ paper.title }}</strong></p>
          <p style="color: var(--color-text-secondary)">{{ paper.description || '暂无说明' }}</p>
          <p>{{ paper.question_count }} 题 · 及格线 {{ paper.pass_score }} 分</p>
          <div class="toolbar" style="margin-top: var(--space-2)">
            <button
              class="primary-action"
              :disabled="paper.submitted"
              @click="router.push(`/exams/take?paper_id=${paper.id}`)"
            >
              {{ paper.submitted ? '已提交，不能重复作答' : '选择并开始答题' }}
            </button>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">
        <p style="margin: 0">当前没有启用中的试卷。</p>
      </div>
    </section>

    <!-- No Access -->
    <section v-if="!canTakeExam && !canManagePaper" class="panel-card">
      <h4>试卷模块</h4>
      <div class="empty-state">当前账号没有试卷作答权限。</div>
    </section>

    <!-- Submissions Table -->
    <section class="panel-card">
      <h4>答卷列表</h4>
      <el-table :data="submissions" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="提交人" min-width="140">
          <template #default="{ row }">{{ row.user.display_name }}</template>
        </el-table-column>
        <el-table-column label="部门" min-width="140">
          <template #default="{ row }">{{ row.user.profile.department ?? '无部门' }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <span class="status-chip" :class="row.status === 'graded' ? 'status-chip--success' : row.status === 'pending_review' ? 'status-chip--warning' : ''">
              {{ row.status === 'submitted' ? '已提交' : row.status === 'pending_review' ? '待阅卷' : '已批改' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="总分" min-width="80" />
        <el-table-column label="提交时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openReview(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- Review Drawer -->
    <el-drawer v-model="reviewVisible" size="min(56%, 780px)" :with-header="false">
      <div v-if="selectedSubmission" class="drawer-stack">
        <!-- Submission Header -->
        <div class="page-header" style="margin-bottom: 0">
          <div>
            <p class="page-caption">Submission · #{{ selectedSubmission.id }}</p>
            <h3 style="margin: 0 0 var(--space-1)">{{ selectedSubmission.user.display_name }}</h3>
            <div class="chip-row">
              <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">{{ selectedSubmission.paper.title }}</span>
              <span class="status-chip" :class="selectedSubmission.status === 'graded' ? 'status-chip--success' : 'status-chip--warning'">
                {{ selectedSubmission.status === 'graded' ? '已批改' : '待阅卷' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Score Summary -->
        <div class="summary-grid">
          <div class="metric-card">
            <p class="metric-card__label">客观题</p>
            <p class="metric-card__value">{{ selectedSubmission.objective_score }}</p>
          </div>
          <div class="metric-card">
            <p class="metric-card__label">主观题</p>
            <p class="metric-card__value">{{ selectedSubmission.subjective_score }}</p>
          </div>
          <div class="metric-card">
            <p class="metric-card__label">总分</p>
            <p class="metric-card__value" :style="{ color: selectedSubmission.total_score >= selectedSubmission.paper.pass_score ? 'var(--color-success)' : 'var(--color-danger)' }">
              {{ selectedSubmission.total_score }}
            </p>
          </div>
        </div>

        <!-- Answers -->
        <section class="section-block">
          <h4>答题详情</h4>
          <div class="history-grid">
            <div v-for="answer in selectedSubmission.answers" :key="answer.id" class="history-item">
              <p><strong>第 {{ answer.question.order_no }} 题</strong>
                <span class="status-chip" style="background: var(--color-primary-light); color: var(--color-primary); margin-left: var(--space-1-5)">
                  {{ normalizedQuestionTypeLabel(answer.question.question_type) }}
                </span>
              </p>
              <p>{{ answer.question.prompt }}</p>
              <p style="margin-top: var(--space-1-5)"><strong>答案：</strong>{{ JSON.stringify(answer.answer) }}</p>
              <div class="chip-row" style="margin-top: var(--space-1)">
                <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-secondary)">客观：{{ answer.objective_score }} 分</span>
                <span class="status-chip" :class="answer.final_score >= (answer.objective_score || 1) ? 'status-chip--success' : 'status-chip--warning'">最终：{{ answer.final_score }} 分</span>
              </div>
              <p v-if="answer.attachments.length" style="margin-top: var(--space-1-5)">
                附件：
                <a
                  v-for="attachment in answer.attachments"
                  :key="attachment.id"
                  :href="previewUrl(attachment.download_path)"
                  target="_blank"
                  style="margin-right: var(--space-2)"
                >
                  {{ attachment.original_name }}
                </a>
              </p>
              <div v-if="answer.question.question_type === 'text' && canReview" class="two-column-form" style="margin-top: var(--space-2)">
                <el-input v-model="reviewScores[answer.id].manual_score" type="number" placeholder="手动分" />
                <el-input v-model="reviewScores[answer.id].grader_comment" placeholder="评分备注" />
              </div>
            </div>
          </div>
        </section>

        <!-- Overall Attachments -->
        <section class="section-block">
          <h4>整卷附件</h4>
          <div v-if="selectedSubmission.attachments.length" class="file-list">
            <a
              v-for="attachment in selectedSubmission.attachments"
              :key="attachment.id"
              class="file-link"
              :href="previewUrl(attachment.download_path)"
              target="_blank"
            >
              <span>{{ attachment.original_name }}</span>
              <span style="color: var(--color-text-muted)">{{ attachment.size }} B</span>
            </a>
          </div>
          <div v-else class="empty-state">没有整卷附件。</div>
        </section>

        <!-- Grade Submit -->
        <section v-if="canReview" class="section-block">
          <h4>阅卷提交</h4>
          <el-input v-model="overallComment" type="textarea" :rows="3" placeholder="总评备注" />
          <div class="toolbar" style="margin-top: var(--space-3)">
            <button class="primary-action" @click="saveReview">
              <el-icon><Edit /></el-icon>保存阅卷
            </button>
          </div>
        </section>
      </div>
    </el-drawer>
  </div>
</template>
