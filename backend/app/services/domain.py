from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.entities import (
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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_supervisor(user: User) -> bool:
    return user.system_role in {SystemRole.SUPERVISOR, SystemRole.SUPER_ADMIN}


def is_super_admin(user: User) -> bool:
    return user.system_role == SystemRole.SUPER_ADMIN


def is_hr_department(user: User) -> bool:
    return get_profile_or_404(user).department == Department.HR


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
    if is_supervisor(user):
        return
    profile = get_profile_or_404(user)
    if profile.department != Department.GAME_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前部门无考试权限。")


def ensure_exam_paper_management_permission(user: User) -> None:
    if is_super_admin(user) or is_supervisor(user) or is_hr_department(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅人事部、主管和超管可管理试卷。")


def ensure_exam_review_permission(viewer: User, owner: User) -> None:
    if is_super_admin(viewer) or is_supervisor(viewer) or is_hr_department(viewer):
        return
    viewer_profile = get_profile_or_404(viewer)
    owner_profile = get_profile_or_404(owner)
    if (
        viewer_profile.department == Department.GAME_ADMIN
        and viewer_profile.game_admin_rank == GameAdminRank.CHIEF
        and owner_profile.department == Department.GAME_ADMIN
    ):
        return
    if (
        viewer_profile.department == Department.GAME_ADMIN
        and viewer_profile.game_admin_rank == GameAdminRank.SENIOR
        and owner_profile.department == Department.GAME_ADMIN
        and owner_profile.game_admin_rank in {GameAdminRank.REVIEW, GameAdminRank.ADMIN}
    ):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看或批改该答卷。")


def ensure_bug_management_permission(user: User) -> None:
    if not is_supervisor(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅主管与超管可处理工单。")


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
    ensure_game_admin_rank_consistency(department, game_admin_rank)
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
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


def get_staff_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人员不存在。")
    _ = user.profile
    return user
