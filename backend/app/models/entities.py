from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Department(str, enum.Enum):
    PUBLICITY = "宣传部门"
    HR = "人事部门"
    PLANNING = "策划部门"
    TECH = "技术部门"
    GAME_ADMIN = "游戏管理员部门"


class SystemRole(str, enum.Enum):
    MEMBER = "member"
    SUPERVISOR = "supervisor"
    SUPER_ADMIN = "super_admin"


class EmploymentStatus(str, enum.Enum):
    PENDING = "待入职"
    ACTIVE = "在职"
    INACTIVE = "离职"


class GameAdminRank(str, enum.Enum):
    REVIEW = "审查期管理员"
    ADMIN = "管理员"
    SENIOR = "高级管理员"
    CHIEF = "总管"


class EmploymentRecordType(str, enum.Enum):
    JOIN = "join"
    LEAVE = "leave"


class RankChangeType(str, enum.Enum):
    PROMOTE = "promote"
    DEMOTE = "demote"


class QuestionType(str, enum.Enum):
    SINGLE = "single_choice"
    MULTIPLE = "multiple_choice"
    BOOLEAN = "boolean"
    TEXT = "text"


class SubmissionStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    PENDING_REVIEW = "pending_review"
    GRADED = "graded"


class BugPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BugStatus(str, enum.Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"
    REOPENED = "reopened"


enum_kwargs = {"native_enum": False}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    system_role: Mapped[SystemRole] = mapped_column(Enum(SystemRole, **enum_kwargs), default=SystemRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped[StaffProfile] = relationship("StaffProfile", back_populates="user", uselist=False)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    department: Mapped[Department | None] = mapped_column(Enum(Department, **enum_kwargs), nullable=True)
    position_title: Mapped[str] = mapped_column(String(100))
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus, **enum_kwargs), default=EmploymentStatus.PENDING
    )
    game_admin_rank: Mapped[GameAdminRank | None] = mapped_column(Enum(GameAdminRank, **enum_kwargs), nullable=True)
    join_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="profile")


class EmploymentRecord(Base):
    __tablename__ = "employment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    record_type: Mapped[EmploymentRecordType] = mapped_column(Enum(EmploymentRecordType, **enum_kwargs))
    previous_status: Mapped[EmploymentStatus | None] = mapped_column(
        Enum(EmploymentStatus, **enum_kwargs), nullable=True
    )
    new_status: Mapped[EmploymentStatus] = mapped_column(Enum(EmploymentStatus, **enum_kwargs))
    reason: Mapped[str] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromotionDemotionRecord(Base):
    __tablename__ = "promotion_demotion_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    change_type: Mapped[RankChangeType] = mapped_column(Enum(RankChangeType, **enum_kwargs))
    previous_rank: Mapped[GameAdminRank | None] = mapped_column(Enum(GameAdminRank, **enum_kwargs), nullable=True)
    new_rank: Mapped[GameAdminRank] = mapped_column(Enum(GameAdminRank, **enum_kwargs))
    reason: Mapped[str] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PunishmentRecord(Base):
    __tablename__ = "punishment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    level: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pass_score: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("exam_papers.id"), index=True)
    order_no: Mapped[int] = mapped_column(Integer)
    prompt: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, **enum_kwargs))
    options_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    correct_answer_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float] = mapped_column(Float)


class ExamSubmission(Base):
    __tablename__ = "exam_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("exam_papers.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus, **enum_kwargs))
    objective_score: Mapped[float] = mapped_column(Float, default=0)
    subjective_score: Mapped[float] = mapped_column(Float, default=0)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    overall_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grader_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ExamAnswer(Base):
    __tablename__ = "exam_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("exam_submissions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("exam_questions.id"))
    answer_json: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    objective_score: Mapped[float] = mapped_column(Float, default=0)
    manual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, default=0)
    grader_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExamAttachment(Base):
    __tablename__ = "exam_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("exam_submissions.id"), index=True)
    answer_id: Mapped[int | None] = mapped_column(ForeignKey("exam_answers.id"), nullable=True)
    stored_name: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BugTicket(Base):
    __tablename__ = "bug_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(100))
    priority: Mapped[BugPriority] = mapped_column(Enum(BugPriority, **enum_kwargs), default=BugPriority.MEDIUM)
    status: Mapped[BugStatus] = mapped_column(Enum(BugStatus, **enum_kwargs), default=BugStatus.NEW)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reproduce_steps: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    actual_result: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BugComment(Base):
    __tablename__ = "bug_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("bug_tickets.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BugAttachment(Base):
    __tablename__ = "bug_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("bug_tickets.id"), index=True)
    comment_id: Mapped[int | None] = mapped_column(ForeignKey("bug_comments.id"), nullable=True)
    stored_name: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(100))
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
