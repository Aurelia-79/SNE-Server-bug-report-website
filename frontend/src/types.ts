export type SystemRole = 'member' | 'supervisor' | 'super_admin';
export type Department =
  | '宣传部门'
  | '人事部门'
  | '策划部门'
  | '技术部门'
  | '游戏管理员部门';
export type GameAdminRank = '审查期管理员' | '管理员' | '高级管理员' | '总管';
export type EmploymentStatus = '待入职' | '在职' | '离职';
export type QuestionType = 'single_choice' | 'multiple_choice' | 'boolean' | 'text';
export type SubmissionStatus = 'submitted' | 'pending_review' | 'graded';
export type BugPriority = 'low' | 'medium' | 'high' | 'critical';
export type BugStatus = 'new' | 'assigned' | 'processing' | 'resolved' | 'closed' | 'rejected' | 'reopened';

export interface MailConfig {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password?: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  mail_from: string;
  mail_admin_reply_to: string;
  mail_timeout_seconds: number;
  updated_at: string | null;
}

export interface MailTestPayload {
  recipient: string;
}

export interface MailSendPayload {
  user_ids: number[];
  subject: string;
  body: string;
}

export interface Profile {
  department: Department | null;
  position_title: string;
  employment_status: EmploymentStatus;
  game_admin_rank: GameAdminRank | null;
  join_date: string | null;
  leave_date: string | null;
  notes: string | null;
}

export interface User {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  avatar_path: string | null;
  avatar_url: string | null;
  system_role: SystemRole;
  is_active: boolean;
  created_at: string;
  profile: Profile;
}

export interface StaffHistoryRecord {
  id: number;
  record_type?: string;
  change_type?: string;
  previous_status?: EmploymentStatus | null;
  new_status?: EmploymentStatus | null;
  previous_rank?: GameAdminRank | null;
  new_rank?: GameAdminRank | null;
  level?: string;
  reason: string;
  remark: string | null;
  operator_id: number;
  effective_at: string;
  created_at: string;
}

export interface StaffHistory {
  employment_records: StaffHistoryRecord[];
  promotion_records: StaffHistoryRecord[];
  punishments: StaffHistoryRecord[];
}

export interface ExamQuestion {
  id: number;
  order_no: number;
  prompt: string;
  question_type: QuestionType;
  options: Array<{ label: string; text: string }> | null;
  score: number;
  correct_answer?: unknown;
}

export interface ExamPaper {
  id: number;
  title: string;
  description: string | null;
  pass_score: number;
  is_active?: boolean;
  created_at?: string;
  questions: ExamQuestion[];
}

export interface AvailableExamPaper extends Omit<ExamPaper, 'questions'> {
  question_count: number;
  submitted: boolean;
  can_submit: boolean;
}

export interface ManagedExamPaper extends Omit<ExamPaper, 'questions'> {
  question_count: number;
  submission_count: number;
  can_delete: boolean;
}

export interface ExamPaperDraftQuestion {
  order_no: number;
  prompt: string;
  question_type: 'single_choice' | 'text';
  score: number;
  options: Array<{ label: string; text: string }>;
  correct_answer: string;
}

export interface ExamPaperDraft {
  title: string;
  description: string;
  pass_score: number;
  questions: ExamPaperDraftQuestion[];
}

export interface AttachmentItem {
  id: number;
  stored_name: string;
  original_name: string;
  mime_type: string;
  size: number;
  created_at: string;
  download_path: string;
}

export interface ExamAnswer {
  id: number;
  question: ExamQuestion;
  answer: unknown;
  objective_score: number;
  manual_score: number | null;
  final_score: number;
  grader_comment: string | null;
  attachments: AttachmentItem[];
}

export interface ExamSubmission {
  id: number;
  status: SubmissionStatus;
  objective_score: number;
  subjective_score: number;
  total_score: number;
  overall_comment: string | null;
  submitted_at: string;
  graded_at: string | null;
  user: User;
  paper: ExamPaper;
  grader: User | null;
  attachments: AttachmentItem[];
  answers: ExamAnswer[];
}

export interface BugComment {
  id: number;
  content: string;
  created_at: string;
  author: User;
}

export interface BugTicket {
  id: number;
  title: string;
  module: string;
  priority: BugPriority;
  status: BugStatus;
  reporter: User;
  assignee: User | null;
  reproduce_steps: string;
  expected_result: string;
  actual_result: string;
  resolution: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  attachments: AttachmentItem[];
  comments: BugComment[];
}

export interface DashboardSummary {
  staff_total: number;
  pending_review_count: number;
  open_bug_count: number;
  department_breakdown: Array<{ department: string; count: number }>;
}

export interface ScoreOverview {
  chart_items: Array<{
    user_id: number;
    name: string;
    rank: GameAdminRank | null;
    score: number;
    status: SubmissionStatus;
  }>;
  summary: {
    submission_count: number;
    average_score: number;
    pass_rate: number;
  };
}

export interface GameServerStatus {
  available: boolean;
  server_name: string;
  online_count: number;
  max_players: number;
  round_in_progress: boolean;
  round_time_seconds: number;
  round_time_text: string;
  memory_working_set_mb: number;
  memory_private_mb: number;
  memory_gc_mb?: number;
  started_at: string;
  updated_at: string;
}

export interface GameServerPlayer {
  nickname: string;
  player_id: number;
  user_id: string;
  steam64: string;
  role: string;
  team: string;
  is_admin: boolean;
  admin_group: string | null;
}

export interface GameServerEmergency {
  available: boolean;
  plugin_loaded: boolean;
  has_started_this_round: boolean;
  is_active: boolean;
  started_at_round_seconds: number;
  started_at_round_time_text: string;
  message: string;
}

export interface GameServerChatMessage {
  time_sent: string;
  type: string;
  sender_nickname: string;
  sender_role: string;
  text: string;
}

export interface GameServerLogResponse {
  available: boolean;
  path: string | null;
  lines: string[];
  message: string;
}

export interface GameServerActionResult {
  success: boolean;
  message: string;
  command_id: string;
  executed_at: string;
  output?: string;
}
