from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db
from server.models.entities import (
    BugStatus,
    BugTicket,
    Department,
    ExamSubmission,
    GameAdminRank,
    SubmissionStatus,
    SystemRole,
    User,
)
from server.services.domain import can_view_staff, department_label, get_staff_or_404

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.system_role == SystemRole.MEMBER and current_user.profile.game_admin_rank not in {
        GameAdminRank.SENIOR,
        GameAdminRank.CHIEF,
    }:
        own_submissions = list(db.scalars(select(ExamSubmission).where(ExamSubmission.user_id == current_user.id)).all())
        own_bugs = list(
            db.scalars(select(BugTicket).where(BugTicket.reporter_id == current_user.id, BugTicket.status != BugStatus.CLOSED)).all()
        )
        return {
            "staff_total": 1,
            "pending_review_count": sum(1 for item in own_submissions if item.status == SubmissionStatus.PENDING_REVIEW),
            "open_bug_count": len(own_bugs),
            "department_breakdown": [{"department": department_label(current_user.profile.department), "count": 1}],
        }

    users = list(db.scalars(select(User)).all())
    department_breakdown = defaultdict(int)
    for user in users:
        _ = user.profile
        if current_user.system_role == SystemRole.MEMBER and current_user.profile.game_admin_rank in {GameAdminRank.SENIOR, GameAdminRank.CHIEF}:
            if user.profile.department != Department.GAME_ADMIN:
                continue
            if not can_view_staff(current_user, user):
                continue
        department_breakdown[department_label(user.profile.department)] += 1

    pending_review_count = len(
        list(db.scalars(select(ExamSubmission).where(ExamSubmission.status == SubmissionStatus.PENDING_REVIEW)).all())
    )
    open_bug_count = len(list(db.scalars(select(BugTicket).where(BugTicket.status != BugStatus.CLOSED)).all()))
    return {
        "staff_total": sum(department_breakdown.values()),
        "pending_review_count": pending_review_count,
        "open_bug_count": open_bug_count,
        "department_breakdown": [
            {"department": department, "count": count}
            for department, count in department_breakdown.items()
        ],
    }


@router.get("/exams/score-overview")
def get_exam_score_overview(
    rank: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.system_role == SystemRole.MEMBER and current_user.profile.game_admin_rank not in {
        GameAdminRank.SENIOR,
        GameAdminRank.CHIEF,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看统计图表。")

    submissions = list(db.scalars(select(ExamSubmission).order_by(ExamSubmission.submitted_at.desc())).all())
    latest_by_user: dict[int, ExamSubmission] = {}
    chart_items = []
    for submission in submissions:
        if submission.user_id in latest_by_user:
            continue
        owner = get_staff_or_404(db, submission.user_id)
        if owner.profile.department != Department.GAME_ADMIN:
            continue
        try:
            if not can_view_staff(current_user, owner):
                continue
        except HTTPException:
            continue
        if rank and (not owner.profile.game_admin_rank or owner.profile.game_admin_rank.value != rank):
            continue
        latest_by_user[submission.user_id] = submission
        chart_items.append(
            {
                "user_id": owner.id,
                "name": owner.display_name,
                "rank": owner.profile.game_admin_rank,
                "score": submission.total_score,
                "status": submission.status,
            }
        )
    scores = [item["score"] for item in chart_items]
    pass_score = 60
    return {
        "chart_items": chart_items,
        "summary": {
            "submission_count": len(chart_items),
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "pass_rate": round((sum(1 for score in scores if score >= pass_score) / len(scores)) * 100, 2) if scores else 0,
        },
    }
