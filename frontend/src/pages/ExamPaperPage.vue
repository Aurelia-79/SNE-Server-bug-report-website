<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Upload } from '@element-plus/icons-vue';

import { apiClient } from '../api/client';
import { useAuth } from '../stores/auth';
import type { ExamPaper, QuestionType } from '../types';

type AnswerValue = string | string[] | boolean | null;

const route = useRoute();
const router = useRouter();
const auth = useAuth();

const isPreview = computed(() => route.name === 'exam-preview');
const selectedPaperId = computed(() => Number(route.query.paper_id || 0));
const paper = ref<ExamPaper | null>(null);
const loading = ref(false);
const submitting = ref(false);
const answerForm = reactive<Record<number, AnswerValue>>({});
const answerFiles = reactive<Record<number, File[]>>({});
const overallFiles = ref<File[]>([]);
const overallComment = ref('');

function normalizedQuestionTypeLabel(type: QuestionType) {
  if (type === 'single_choice') return '选择题';
  if (type === 'text') return '简答题';
  return type;
}

function initAnswerState() {
  if (!paper.value) return;
  for (const question of paper.value.questions) {
    answerForm[question.id] = '';
  }
}

function setFileBucket(questionId: number, event: Event) {
  const input = event.target as HTMLInputElement;
  answerFiles[questionId] = Array.from(input.files ?? []);
}

function setOverallFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  overallFiles.value = Array.from(input.files ?? []);
}

async function loadPaper() {
  loading.value = true;
  try {
    if (isPreview.value) {
      if (!auth.canManageExamPaper.value) {
        ElMessage.error('当前账号没有试卷预览权限');
        router.replace('/exams');
        return;
      }
      const url = selectedPaperId.value
        ? `/api/exams/manage/papers/${selectedPaperId.value}`
        : '/api/exams/manage/paper';
      const { data } = await apiClient.get(url);
      paper.value = (data as ExamPaper | null) ?? null;
    } else {
      if (!auth.canTakeExam.value) {
        ElMessage.error('当前账号没有答题权限');
        router.replace('/exams');
        return;
      }
      if (!selectedPaperId.value) {
        ElMessage.error('请先选择要作答的试卷');
        router.replace('/exams');
        return;
      }
      const { data } = await apiClient.get(`/api/exams/papers/${selectedPaperId.value}`);
      paper.value = data as ExamPaper;
      initAnswerState();
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '读取试卷失败');
  } finally {
    loading.value = false;
  }
}

async function uploadAttachments(submissionId: number, answerIds: Record<number, number>) {
  for (const question of paper.value?.questions ?? []) {
    const files = answerFiles[question.id] ?? [];
    if (!files.length) continue;
    const formData = new FormData();
    formData.append('answer_id', String(answerIds[question.id]));
    for (const file of files) {
      formData.append('files', file);
    }
    await apiClient.post(`/api/exams/submissions/${submissionId}/attachments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  if (overallFiles.value.length) {
    const formData = new FormData();
    for (const file of overallFiles.value) {
      formData.append('files', file);
    }
    await apiClient.post(`/api/exams/submissions/${submissionId}/attachments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
}

async function submitPaper() {
  if (!paper.value || isPreview.value) return;
  submitting.value = true;
  try {
    const answers = paper.value.questions.map((question) => ({
      question_id: question.id,
      answer: answerForm[question.id] ?? '',
    }));
    const { data } = await apiClient.post('/api/exams/submissions', {
      paper_id: paper.value.id,
      answers,
      overall_comment: overallComment.value || null,
    });
    const submissionId = data.submission_id as number;
    const answerIds = Object.fromEntries(
      (data.answer_ids as Array<{ question_id: number; answer_id: number }>).map((item) => [item.question_id, item.answer_id]),
    ) as Record<number, number>;
    await uploadAttachments(submissionId, answerIds);
    ElMessage.success('试卷已提交');
    router.replace('/exams');
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail ?? '提交失败');
  } finally {
    submitting.value = false;
  }
}

onMounted(loadPaper);
</script>

<template>
  <div class="page-stack exam-paper-page" v-loading="loading">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <p class="page-caption">{{ isPreview ? 'Paper Preview' : 'Exam Session' }}</p>
        <h3>{{ isPreview ? '试卷预览' : '正式答题' }}</h3>
        <p>{{ isPreview ? '预览不会保存答案，也不会生成答卷记录。' : '请在独立答题界面完成并提交试卷。' }}</p>
      </div>
      <button class="secondary-action" @click="router.push('/exams')">
        <el-icon><ArrowLeft /></el-icon>返回
      </button>
    </div>

    <!-- Paper Content -->
    <section v-if="paper" class="panel-card">
      <div style="margin-bottom: var(--space-4)">
        <h4 style="margin: 0 0 var(--space-1-5)">{{ paper.title }}</h4>
        <p style="margin: 0; color: var(--color-text-secondary); font-size: var(--font-size-sm)">{{ paper.description }}</p>
        <div style="margin-top: var(--space-3)">
          <span class="status-chip" style="background: var(--color-primary-light); color: var(--color-primary)">
            及格线：{{ paper.pass_score }} 分
          </span>
          <span class="status-chip" style="background: var(--color-emphasis); color: var(--color-text-muted)">
            {{ paper.questions.length }} 题
          </span>
        </div>
      </div>

      <div class="history-grid">
        <article v-for="question in paper.questions" :key="question.id" class="question-card">
          <div class="question-card__meta">
            <span>第 {{ question.order_no }} 题</span>
            <span class="status-chip" style="background: var(--color-primary-light); color: var(--color-primary)">
              {{ normalizedQuestionTypeLabel(question.question_type) }}
            </span>
            <span>{{ question.score }} 分</span>
          </div>
          <h5 class="question-card__title">{{ question.prompt }}</h5>

          <!-- Single Choice -->
          <template v-if="question.question_type === 'single_choice'">
            <el-radio-group v-model="answerForm[question.id]" :disabled="isPreview">
              <div style="display: flex; flex-direction: column; gap: var(--space-2)">
                <el-radio v-for="item in question.options ?? []" :key="item.label" :label="item.label" style="margin-right: 0">
                  {{ item.label }}. {{ item.text }}
                </el-radio>
              </div>
            </el-radio-group>
          </template>

          <!-- Text Answer -->
          <template v-else>
            <el-input
              v-model="answerForm[question.id]"
              type="textarea"
              :rows="4"
              :disabled="isPreview"
              placeholder="请输入简答内容"
            />
          </template>

          <!-- Attachment Upload -->
          <div v-if="!isPreview" class="upload-box">
            <p><el-icon><Upload /></el-icon> 题目附件</p>
            <input type="file" multiple @change="setFileBucket(question.id, $event)" />
          </div>
        </article>
      </div>

      <!-- Overall Section -->
      <div v-if="!isPreview" class="section-block" style="margin-top: var(--space-4)">
        <h4>整卷补充</h4>
        <div class="upload-box" style="margin-bottom: var(--space-3)">
          <p><el-icon><Upload /></el-icon> 可上传整卷共用的图片或文件</p>
          <input type="file" multiple @change="setOverallFiles" />
        </div>
        <el-input v-model="overallComment" type="textarea" :rows="3" placeholder="补充说明" />
        <div class="toolbar" style="margin-top: var(--space-3)">
          <button class="primary-action" :disabled="submitting" @click="submitPaper">
            <el-icon><Upload /></el-icon>提交试卷
          </button>
        </div>
      </div>
    </section>

    <!-- Empty State -->
    <section v-else-if="!loading" class="panel-card">
      <div class="empty-state">当前没有可预览或可作答的试卷。</div>
    </section>
  </div>
</template>
