from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from server.models.entities import (
    BugPriority,
    BugStatus,
    Department,
    EmploymentRecordType,
    EmploymentStatus,
    GameAdminRank,
    RankChangeType,
    SystemRole,
)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(min_length=6)
    display_name: str
    email: str = Field(min_length=5, max_length=255)


class ProfileUpdateRequest(BaseModel):
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=6)


class UserCreateRequest(BaseModel):
    username: str
    password: str = Field(min_length=6)
    display_name: str
    email: str | None = None
    system_role: SystemRole = SystemRole.MEMBER
    department: Department | None = None
    position_title: str
    employment_status: EmploymentStatus = EmploymentStatus.PENDING
    game_admin_rank: GameAdminRank | None = None
    join_date: date | None = None
    leave_date: date | None = None
    notes: str | None = None
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=6)
    system_role: SystemRole | None = None
    department: Department | None = None
    position_title: str | None = None
    employment_status: EmploymentStatus | None = None
    game_admin_rank: GameAdminRank | None = None
    join_date: date | None = None
    leave_date: date | None = None
    notes: str | None = None
    is_active: bool | None = None


class EmploymentRecordCreateRequest(BaseModel):
    user_id: int
    record_type: EmploymentRecordType
    new_status: EmploymentStatus
    reason: str
    remark: str | None = None
    effective_at: datetime


class PromotionRecordCreateRequest(BaseModel):
    user_id: int
    change_type: RankChangeType
    new_rank: GameAdminRank
    reason: str
    remark: str | None = None
    effective_at: datetime


class PunishmentCreateRequest(BaseModel):
    user_id: int
    level: str
    reason: str
    remark: str | None = None
    effective_at: datetime


class ExamAnswerPayload(BaseModel):
    question_id: int
    answer: Any


class ExamChoiceOptionPayload(BaseModel):
    label: str
    text: str


class ExamQuestionCreatePayload(BaseModel):
    order_no: int = Field(ge=1)
    prompt: str
    question_type: str
    score: float = Field(gt=0)
    options: list[ExamChoiceOptionPayload] | None = None
    correct_answer: str | None = None


class ExamPaperCreateRequest(BaseModel):
    title: str
    description: str | None = None
    pass_score: int = Field(default=60, ge=0, le=100)
    questions: list[ExamQuestionCreatePayload]


class ExamSubmissionCreateRequest(BaseModel):
    paper_id: int
    answers: list[ExamAnswerPayload]
    overall_comment: str | None = None


class ExamGradeAnswerPayload(BaseModel):
    answer_id: int
    manual_score: float
    grader_comment: str | None = None


class ExamGradeRequest(BaseModel):
    answers: list[ExamGradeAnswerPayload]
    overall_comment: str | None = None


class BugTicketCreateRequest(BaseModel):
    title: str
    module: str
    priority: BugPriority = BugPriority.MEDIUM
    reproduce_steps: str
    expected_result: str
    actual_result: str


class BugTicketUpdateRequest(BaseModel):
    status: BugStatus | None = None
    assignee_id: int | None = None
    resolution: str | None = None
    comment: str | None = None


class BugCommentCreateRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    message: str


class MailConfigRequest(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    mail_from: str = ""
    mail_admin_reply_to: str = ""
    mail_timeout_seconds: float = 10.0


class MailConfigResponse(BaseModel):
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    mail_from: str
    mail_admin_reply_to: str
    mail_timeout_seconds: float
    updated_at: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MailTestRequest(BaseModel):
    recipient: str


class MailSendRequest(BaseModel):
    user_ids: list[int]
    subject: str
    body: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]

    model_config = ConfigDict(arbitrary_types_allowed=True)
