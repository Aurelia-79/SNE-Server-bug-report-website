from __future__ import annotations

import html
import logging
import smtplib
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.core.config import settings
from server.core.security import hash_password
from server.models.entities import (
    AuditLog,
    BugAttachment,
    BugComment,
    BugStatus,
    BugTicket,
    Department,
    EmploymentRecord,
    EmploymentRecordType,
    EmploymentStatus,
    ExamAnswer,
    ExamAttachment,
    ExamPaper,
    ExamQuestion,
    ExamSubmission,
    GameAdminRank,
    PromotionDemotionRecord,
    PunishmentRecord,
    QuestionType,
    RankChangeType,
    StaffProfile,
    SubmissionStatus,
    SystemRole,
    User,
)

RANK_LEVELS = {
    GameAdminRank.REVIEW: 1,
    GameAdminRank.ADMIN: 2,
    GameAdminRank.SENIOR: 3,
    GameAdminRank.CHIEF: 4,
}

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_supervisor(user: User) -> bool:
    return user.system_role in {SystemRole.SUPERVISOR, SystemRole.SUPER_ADMIN}


def is_super_admin(user: User) -> bool:
    return user.system_role == SystemRole.SUPER_ADMIN


def is_hr_department(user: User) -> bool:
    return get_profile_or_404(user).department == Department.HR


def is_active_employee(user: User) -> bool:
    return get_profile_or_404(user).employment_status == EmploymentStatus.ACTIVE


def department_label(department: Department | None) -> str:
    return department.value if department else "无部门"


def ensure_game_admin_rank_consistency(department: Department | None, rank: GameAdminRank | None) -> None:
    if department == Department.GAME_ADMIN and rank is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="游戏管理员部门必须设置等级。")
    if department != Department.GAME_ADMIN and rank is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非游戏管理员部门不能设置游戏管理员等级。")


def get_profile_or_404(user: User | None) -> StaffProfile:
    if not user or not user.profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员档案不存在。")
    return user.profile


def can_view_staff(viewer: User, target: User) -> bool:
    if viewer.id == target.id or is_supervisor(viewer):
        return True
    viewer_profile = get_profile_or_404(viewer)
    target_profile = get_profile_or_404(target)
    if viewer_profile.department != Department.GAME_ADMIN or target_profile.department != Department.GAME_ADMIN:
        return False
    if viewer_profile.game_admin_rank == GameAdminRank.CHIEF:
        return True
    if viewer_profile.game_admin_rank == GameAdminRank.SENIOR:
        return target_profile.game_admin_rank in {GameAdminRank.REVIEW, GameAdminRank.ADMIN}
    return False


def can_manage_game_admin(viewer: User, target: User) -> bool:
    if is_supervisor(viewer):
        return True
    viewer_profile = get_profile_or_404(viewer)
    target_profile = get_profile_or_404(target)
    return (
        viewer_profile.department == Department.GAME_ADMIN
        and viewer_profile.game_admin_rank == GameAdminRank.CHIEF
        and target_profile.department == Department.GAME_ADMIN
    )


def ensure_staff_view_permission(viewer: User, target: User) -> None:
    if not can_view_staff(viewer, target):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该人员信息。")


def ensure_staff_management_permission(viewer: User, target: User) -> None:
    if is_supervisor(viewer):
        return
    if can_manage_game_admin(viewer, target):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理该人员。")


def ensure_exam_candidate(user: User) -> None:
    _ = user
    return


def ensure_exam_paper_management_permission(user: User) -> None:
    if is_super_admin(user) or is_supervisor(user) or is_hr_department(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅人事部、主管和超管可管理试卷。")


def ensure_exam_review_permission(viewer: User, owner: User) -> None:
    if is_super_admin(viewer) or is_hr_department(viewer):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看或批改该答卷。")


def ensure_bug_management_permission(user: User) -> None:
    if not is_supervisor(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅主管与超管可处理工单。")


def ensure_server_view_permission(user: User) -> None:
    _ = user
    return


def ensure_server_operation_permission(user: User) -> None:
    if not is_active_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅已入职人员可操作服务器。")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned or "file"


def validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空。")


def store_upload(file: UploadFile, category: str) -> tuple[str, str, int, str]:
    validate_upload(file)
    extension = Path(file.filename).suffix
    stored_name = f"{uuid4().hex}{extension}"
    relative_dir = Path(category) / utcnow().strftime("%Y/%m/%d")
    absolute_dir = settings.upload_dir / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)
    absolute_path = absolute_dir / stored_name
    content = file.file.read()
    size = len(content)
    if size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="附件超过大小限制。")
    absolute_path.write_bytes(content)
    mime_type = file.content_type or "application/octet-stream"
    relative_path = (relative_dir / stored_name).as_posix()
    return stored_name, relative_path, size, mime_type


def create_audit_log(
    db: Session,
    *,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: str,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail_json=detail,
    )
    db.add(log)
    return log


def evaluate_objective_answer(question: ExamQuestion, answer: Any) -> float:
    correct = question.correct_answer_json
    if question.question_type == QuestionType.TEXT:
        return 0
    if question.question_type in {QuestionType.SINGLE, QuestionType.BOOLEAN}:
        return float(question.score if answer == correct else 0)
    if question.question_type == QuestionType.MULTIPLE:
        normalized_answer = sorted(answer or [])
        normalized_correct = sorted(correct or [])
        return float(question.score if normalized_answer == normalized_correct else 0)
    return 0


def serialize_user(user: User) -> dict[str, Any]:
    profile = user.profile
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_path": user.avatar_path,
        "avatar_url": f"/api/auth/avatar/{user.id}" if user.avatar_path else None,
        "system_role": user.system_role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "profile": {
            "department": profile.department if profile else None,
            "position_title": profile.position_title if profile else None,
            "employment_status": profile.employment_status if profile else None,
            "game_admin_rank": profile.game_admin_rank if profile else None,
            "join_date": profile.join_date if profile else None,
            "leave_date": profile.leave_date if profile else None,
            "notes": profile.notes if profile else None,
        },
    }


def serialize_attachment(attachment: ExamAttachment | BugAttachment, *, path_prefix: str) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "stored_name": attachment.stored_name,
        "original_name": attachment.original_name,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "created_at": attachment.created_at,
        "download_path": f"{path_prefix}/{attachment.id}",
    }


def serialize_staff_history(
    employment_records: list[EmploymentRecord],
    rank_records: list[PromotionDemotionRecord],
    punishments: list[PunishmentRecord],
) -> dict[str, Any]:
    return {
        "employment_records": [
            {
                "id": record.id,
                "record_type": record.record_type,
                "previous_status": record.previous_status,
                "new_status": record.new_status,
                "reason": record.reason,
                "remark": record.remark,
                "operator_id": record.operator_id,
                "effective_at": record.effective_at,
                "created_at": record.created_at,
            }
            for record in employment_records
        ],
        "promotion_records": [
            {
                "id": record.id,
                "change_type": record.change_type,
                "previous_rank": record.previous_rank,
                "new_rank": record.new_rank,
                "reason": record.reason,
                "remark": record.remark,
                "operator_id": record.operator_id,
                "effective_at": record.effective_at,
                "created_at": record.created_at,
            }
            for record in rank_records
        ],
        "punishments": [
            {
                "id": record.id,
                "level": record.level,
                "reason": record.reason,
                "remark": record.remark,
                "operator_id": record.operator_id,
                "effective_at": record.effective_at,
                "created_at": record.created_at,
            }
            for record in punishments
        ],
    }


def serialize_paper(paper: ExamPaper, questions: list[ExamQuestion], *, include_answers: bool = False) -> dict[str, Any]:
    return {
        "id": paper.id,
        "title": paper.title,
        "description": paper.description,
        "pass_score": paper.pass_score,
        "is_active": paper.is_active,
        "created_at": paper.created_at,
        "questions": [
            {
                "id": question.id,
                "order_no": question.order_no,
                "prompt": question.prompt,
                "question_type": question.question_type,
                "options": question.options_json,
                "score": question.score,
                "correct_answer": question.correct_answer_json if include_answers else None,
            }
            for question in sorted(questions, key=lambda item: item.order_no)
        ],
    }


def serialize_submission(
    submission: ExamSubmission,
    owner: User,
    paper: ExamPaper,
    questions: list[ExamQuestion],
    answers: list[ExamAnswer],
    attachments: list[ExamAttachment],
    grader: User | None,
) -> dict[str, Any]:
    question_map = {question.id: question for question in questions}
    answer_attachment_map: dict[int, list[ExamAttachment]] = {}
    submission_attachments: list[ExamAttachment] = []
    for attachment in attachments:
        if attachment.answer_id:
            answer_attachment_map.setdefault(attachment.answer_id, []).append(attachment)
        else:
            submission_attachments.append(attachment)
    serialized_answers = []
    for answer in answers:
        question = question_map[answer.question_id]
        serialized_answers.append(
            {
                "id": answer.id,
                "question": {
                    "id": question.id,
                    "order_no": question.order_no,
                    "prompt": question.prompt,
                    "question_type": question.question_type,
                    "options": question.options_json,
                    "score": question.score,
                },
                "answer": answer.answer_json,
                "objective_score": answer.objective_score,
                "manual_score": answer.manual_score,
                "final_score": answer.final_score,
                "grader_comment": answer.grader_comment,
                "attachments": [
                    serialize_attachment(attachment, path_prefix="/api/exams/attachments")
                    for attachment in answer_attachment_map.get(answer.id, [])
                ],
            }
        )
    return {
        "id": submission.id,
        "status": submission.status,
        "objective_score": submission.objective_score,
        "subjective_score": submission.subjective_score,
        "total_score": submission.total_score,
        "overall_comment": submission.overall_comment,
        "submitted_at": submission.submitted_at,
        "graded_at": submission.graded_at,
        "user": serialize_user(owner),
        "paper": serialize_paper(paper, questions, include_answers=False),
        "grader": serialize_user(grader) if grader else None,
        "attachments": [
            serialize_attachment(attachment, path_prefix="/api/exams/attachments")
            for attachment in submission_attachments
        ],
        "answers": serialized_answers,
    }


def serialize_bug(
    ticket: BugTicket,
    reporter: User,
    assignee: User | None,
    comments: list[BugComment],
    attachments: list[BugAttachment],
    users_by_id: dict[int, User],
) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "title": ticket.title,
        "module": ticket.module,
        "priority": ticket.priority,
        "status": ticket.status,
        "reporter": serialize_user(reporter),
        "assignee": serialize_user(assignee) if assignee else None,
        "reproduce_steps": ticket.reproduce_steps,
        "expected_result": ticket.expected_result,
        "actual_result": ticket.actual_result,
        "resolution": ticket.resolution,
        "closed_at": ticket.closed_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "attachments": [serialize_attachment(item, path_prefix="/api/bugs/attachments") for item in attachments],
        "comments": [
            {
                "id": comment.id,
                "author": serialize_user(users_by_id[comment.author_id]),
                "content": comment.content,
                "created_at": comment.created_at,
            }
            for comment in comments
        ],
    }


def serialize_audit(log: AuditLog, actor: User | None) -> dict[str, Any]:
    return {
        "id": log.id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": log.detail_json,
        "created_at": log.created_at,
        "actor": serialize_user(actor) if actor else None,
    }


def create_user_with_profile(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    email: str | None = None,
    system_role: SystemRole,
    department: Department | None,
    position_title: str,
    employment_status: EmploymentStatus,
    game_admin_rank: GameAdminRank | None,
    join_date: Any = None,
    leave_date: Any = None,
    notes: str | None = None,
    is_active: bool = True,
) -> User:
    if system_role == SystemRole.SUPER_ADMIN:
        department = None
        game_admin_rank = None
    if department == Department.GAME_ADMIN and game_admin_rank is None:
        game_admin_rank = GameAdminRank.REVIEW
    ensure_game_admin_rank_consistency(department, game_admin_rank)
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        email=email,
        system_role=system_role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    profile = StaffProfile(
        user_id=user.id,
        department=department,
        position_title=position_title,
        employment_status=employment_status,
        game_admin_rank=game_admin_rank,
        join_date=join_date,
        leave_date=leave_date,
        notes=notes,
    )
    db.add(profile)
    db.flush()
    db.refresh(user)
    return user


def build_email_message(*, to_addresses: list[str], subject: str, body: str, html: str | None = None) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.mail_from or settings.smtp_username or "noreply@localhost"
    message["To"] = ", ".join(to_addresses)
    if settings.mail_admin_reply_to:
        message["Reply-To"] = settings.mail_admin_reply_to
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    return message


def build_ticket_created_mail(
    *,
    ticket_id: int,
    title: str,
    module: str,
    priority: str,
    reporter_display_name: str,
    reporter_username: str,
) -> tuple[str, str, str]:
    subject_title = " ".join(title.split())
    safe_title = html.escape(title)
    safe_module = html.escape(module)
    safe_priority = html.escape(priority)
    safe_reporter = html.escape(f"{reporter_display_name} ({reporter_username})")
    subject = f"[Ticket] New #{ticket_id} {subject_title}"
    text_body = (
        "A new ticket has been submitted.\n"
        f"ID: #{ticket_id}\n"
        f"Title: {title}\n"
        f"Module: {module}\n"
        f"Priority: {priority}\n"
        f"Reporter: {reporter_display_name} ({reporter_username})\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#eef2ff;color:#3730a3;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">New Ticket</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">#{ticket_id} {safe_title}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">A new work order has been submitted and is awaiting processing.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Title</td><td style="padding:10px 0;">{safe_title}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Module</td><td style="padding:10px 0;">{safe_module}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Priority</td><td style="padding:10px 0;">{safe_priority}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Reporter</td><td style="padding:10px 0;">{safe_reporter}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def build_ticket_reply_mail(
    *,
    ticket_id: int,
    title: str,
    status_text: str,
    reply_text: str,
    resolution: str | None,
) -> tuple[str, str, str]:
    subject_title = " ".join(title.split())
    safe_title = html.escape(title)
    safe_status = html.escape(status_text)
    safe_reply = html.escape(reply_text)
    safe_resolution = html.escape(resolution or "None")
    subject = f"[Ticket Reply] #{ticket_id} {subject_title}"
    text_body = (
        "Your ticket status has changed.\n"
        f"ID: #{ticket_id}\n"
        f"Title: {title}\n"
        f"Status: {status_text}\n"
        f"Reply: {reply_text}\n"
        f"Resolution: {resolution or 'None'}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#ecfeff;color:#155e75;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">Ticket Update</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">#{ticket_id} {safe_title}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">Your ticket status has been updated and a reply has been added.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Title</td><td style="padding:10px 0;">{safe_title}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Status</td><td style="padding:10px 0;">{safe_status}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Reply</td><td style="padding:10px 0;white-space:pre-wrap;">{safe_reply}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Resolution</td><td style="padding:10px 0;white-space:pre-wrap;">{safe_resolution}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def send_email(*, to_addresses: list[str], subject: str, body: str, html: str | None = None) -> bool:
    if not settings.mail_enabled:
        return False
    recipients = [address.strip() for address in to_addresses if address and address.strip()]
    if not recipients:
        return False
    if not settings.smtp_host:
        logger.warning("Mail is enabled but SMTP_HOST is empty.")
        return False
    message = build_email_message(to_addresses=recipients, subject=subject, body=body, html=html)
    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.mail_timeout_seconds) as client:
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.mail_timeout_seconds) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send mail to %s", recipients)
        return False


def collect_admin_emails(db: Session) -> list[str]:
    users = list(
        db.scalars(
            select(User).where(User.system_role.in_([SystemRole.SUPERVISOR, SystemRole.SUPER_ADMIN]))
        ).all()
    )
    emails = []
    for user in users:
        if user.email and user.email.strip():
            emails.append(user.email.strip())
    return sorted(set(emails))


def collect_exam_reviewer_emails(db: Session) -> list[str]:
    """Collect emails of users who can review exam submissions (super admin + HR department)."""
    users = list(db.scalars(select(User)).all())
    emails = []
    for user in users:
        if not user.email or not user.email.strip():
            continue
        profile = user.profile
        if not profile:
            continue
        if user.system_role == SystemRole.SUPER_ADMIN or profile.department == Department.HR:
            emails.append(user.email.strip())
    return sorted(set(emails))


def _get_mail_config_from_db(db: Session):
    """Fetch MailConfig from DB, or return None."""
    from server.models.entities import MailConfig
    return db.scalar(select(MailConfig).where(MailConfig.id == 1))


def _send_via_db_config(config, *, to_addresses: list[str], subject: str, body: str, html: str | None = None) -> bool:
    """Send email using MailConfig row values (not .env settings)."""
    recipients = [a.strip() for a in to_addresses if a and a.strip()]
    if not recipients or not config.enabled or not config.smtp_host:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.mail_from or config.smtp_username or "noreply@localhost"
    message["To"] = ", ".join(recipients)
    if config.mail_admin_reply_to:
        message["Reply-To"] = config.mail_admin_reply_to
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")

    try:
        if config.smtp_use_ssl:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=config.mail_timeout_seconds) as client:
                if config.smtp_username:
                    client.login(config.smtp_username, config.smtp_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=config.mail_timeout_seconds) as client:
                if config.smtp_use_tls:
                    client.starttls()
                if config.smtp_username:
                    client.login(config.smtp_username, config.smtp_password)
                client.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send mail via DB config to %s", recipients)
        return False


def send_notification_email(
    db: Session,
    *,
    to_addresses: list[str],
    subject: str,
    body: str,
    html: str | None = None,
) -> bool:
    """Send a notification email.

    Tries DB MailConfig first (so the admin can configure SMTP via the UI).
    Falls back to .env settings if DB config is not available or disabled.
    """
    config = _get_mail_config_from_db(db)
    if config and config.enabled and config.smtp_host:
        return _send_via_db_config(config, to_addresses=to_addresses, subject=subject, body=body, html=html)
    return send_email(to_addresses=to_addresses, subject=subject, body=body, html=html)


# ── Notification mail builders ───────────────────────────────────────────


def build_exam_submission_mail(
    *,
    submission_id: int,
    paper_title: str,
    user_display_name: str,
    user_username: str,
    total_score: float,
) -> tuple[str, str, str]:
    safe_paper = html.escape(paper_title)
    safe_name = html.escape(f"{user_display_name} ({user_username})")
    subject = f"[Exam Submission] #{submission_id} - {paper_title}"
    text_body = (
        f"A user has submitted an exam.\n"
        f"Submission ID: #{submission_id}\n"
        f"Paper: {paper_title}\n"
        f"User: {user_display_name} ({user_username})\n"
        f"Objective Score: {total_score}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#fef3c7;color:#92400e;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">New Submission</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">#{submission_id} - {safe_paper}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">A student has submitted an exam awaiting review.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Submission</td><td style="padding:10px 0;">#{submission_id}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Paper</td><td style="padding:10px 0;">{safe_paper}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">User</td><td style="padding:10px 0;">{safe_name}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Objective Score</td><td style="padding:10px 0;">{total_score}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def build_employment_change_mail(
    *,
    user_display_name: str,
    record_type: str,
    previous_status: str,
    new_status: str,
    reason: str,
    effective_at: str,
) -> tuple[str, str, str]:
    safe_name = html.escape(user_display_name)
    safe_type = html.escape(record_type)
    safe_reason = html.escape(reason)
    safe_effective = html.escape(str(effective_at))
    subject = f"[Employment] {record_type} - {user_display_name}"
    text_body = (
        f"Your employment status has changed.\n"
        f"Name: {user_display_name}\n"
        f"Type: {record_type}\n"
        f"Previous: {previous_status}\n"
        f"New: {new_status}\n"
        f"Reason: {reason}\n"
        f"Effective: {effective_at}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#e0e7ff;color:#3730a3;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">Employment Update</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">{safe_name}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">Your employment status has been updated.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Type</td><td style="padding:10px 0;">{safe_type}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Previous Status</td><td style="padding:10px 0;">{html.escape(previous_status)}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">New Status</td><td style="padding:10px 0;">{html.escape(new_status)}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Reason</td><td style="padding:10px 0;">{safe_reason}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Effective</td><td style="padding:10px 0;">{safe_effective}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def build_rank_change_mail(
    *,
    user_display_name: str,
    change_type: str,
    previous_rank: str | None,
    new_rank: str,
    reason: str,
    effective_at: str,
) -> tuple[str, str, str]:
    safe_name = html.escape(user_display_name)
    safe_type = html.escape(change_type)
    safe_reason = html.escape(reason)
    safe_effective = html.escape(str(effective_at))
    subject = f"[Rank Change] {change_type} - {user_display_name}"
    text_body = (
        f"Your game admin rank has changed.\n"
        f"Name: {user_display_name}\n"
        f"Type: {change_type}\n"
        f"Previous: {previous_rank or 'None'}\n"
        f"New: {new_rank}\n"
        f"Reason: {reason}\n"
        f"Effective: {effective_at}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#d1fae5;color:#065f46;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">Rank Update</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">{safe_name}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">Your game admin rank has been updated.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Type</td><td style="padding:10px 0;">{safe_type}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Previous Rank</td><td style="padding:10px 0;">{html.escape(previous_rank or 'None')}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">New Rank</td><td style="padding:10px 0;">{html.escape(new_rank)}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Reason</td><td style="padding:10px 0;">{safe_reason}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Effective</td><td style="padding:10px 0;">{safe_effective}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def build_punishment_mail(
    *,
    user_display_name: str,
    level: str,
    reason: str,
    remark: str | None,
    effective_at: str,
) -> tuple[str, str, str]:
    safe_name = html.escape(user_display_name)
    safe_level = html.escape(level)
    safe_reason = html.escape(reason)
    safe_remark = html.escape(remark or "None")
    safe_effective = html.escape(str(effective_at))
    subject = f"[Punishment] {level} - {user_display_name}"
    text_body = (
        f"A punishment has been recorded.\n"
        f"Name: {user_display_name}\n"
        f"Level: {level}\n"
        f"Reason: {reason}\n"
        f"Remark: {remark or 'None'}\n"
        f"Effective: {effective_at}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#fee2e2;color:#991b1b;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">Punishment Record</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">{safe_name}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">A punishment has been recorded against your account.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Level</td><td style="padding:10px 0;">{safe_level}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Reason</td><td style="padding:10px 0;">{safe_reason}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Remark</td><td style="padding:10px 0;">{safe_remark}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Effective</td><td style="padding:10px 0;">{safe_effective}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def build_ticket_comment_mail(
    *,
    ticket_id: int,
    title: str,
    commenter_name: str,
    comment_text: str,
) -> tuple[str, str, str]:
    subject_title = " ".join(title.split())
    safe_title = html.escape(title)
    safe_commenter = html.escape(commenter_name)
    safe_comment = html.escape(comment_text)
    subject = f"[Ticket Comment] #{ticket_id} {subject_title}"
    text_body = (
        f"Someone commented on your ticket.\n"
        f"ID: #{ticket_id}\n"
        f"Title: {title}\n"
        f"Commenter: {commenter_name}\n"
        f"Comment: {comment_text}\n"
    )
    html_body = f"""
<html>
  <body style="margin:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <div style="max-width:720px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:20px;padding:28px 30px;box-shadow:0 12px 36px rgba(15,23,42,.08);">
        <div style="display:inline-block;padding:6px 12px;border-radius:999px;background:#ede9fe;color:#5b21b6;font-size:12px;letter-spacing:.04em;text-transform:uppercase;">New Comment</div>
        <h2 style="margin:16px 0 8px;font-size:24px;line-height:1.3;color:#111827;">#{ticket_id} {safe_title}</h2>
        <p style="margin:0 0 20px;color:#6b7280;">A new comment has been posted on your ticket.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <tr><td style="padding:10px 0;color:#6b7280;width:160px;">Ticket</td><td style="padding:10px 0;">#{ticket_id} - {safe_title}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Commenter</td><td style="padding:10px 0;">{safe_commenter}</td></tr>
          <tr><td style="padding:10px 0;color:#6b7280;">Comment</td><td style="padding:10px 0;white-space:pre-wrap;">{safe_comment}</td></tr>
        </table>
      </div>
    </div>
  </body>
</html>
"""
    return subject, text_body, html_body


def get_staff_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在。")
    _ = user.profile
    return user
