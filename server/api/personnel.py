from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db
from server.models.entities import EmploymentRecord, PromotionDemotionRecord, PunishmentRecord, User
from server.schemas.api import (
    EmploymentRecordCreateRequest,
    PromotionRecordCreateRequest,
    PunishmentCreateRequest,
)
from server.services.domain import (
    build_employment_change_mail,
    build_punishment_mail,
    build_rank_change_mail,
    create_audit_log,
    ensure_staff_management_permission,
    ensure_staff_view_permission,
    get_staff_or_404,
    send_notification_email,
    serialize_staff_history,
)

router = APIRouter(prefix="/api/personnel", tags=["personnel"])


@router.get("/staff/{user_id}/history")
def get_staff_history(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = get_staff_or_404(db, user_id)
    ensure_staff_view_permission(current_user, user)
    employment_records = list(
        db.scalars(select(EmploymentRecord).where(EmploymentRecord.user_id == user_id).order_by(EmploymentRecord.id.desc())).all()
    )
    rank_records = list(
        db.scalars(
            select(PromotionDemotionRecord).where(PromotionDemotionRecord.user_id == user_id).order_by(PromotionDemotionRecord.id.desc())
        ).all()
    )
    punishments = list(
        db.scalars(select(PunishmentRecord).where(PunishmentRecord.user_id == user_id).order_by(PunishmentRecord.id.desc())).all()
    )
    return serialize_staff_history(employment_records, rank_records, punishments)


@router.post("/employment-records")
def create_employment_record(
    payload: EmploymentRecordCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_staff_or_404(db, payload.user_id)
    ensure_staff_management_permission(current_user, user)
    record = EmploymentRecord(
        user_id=payload.user_id,
        record_type=payload.record_type,
        previous_status=user.profile.employment_status,
        new_status=payload.new_status,
        reason=payload.reason,
        remark=payload.remark,
        operator_id=current_user.id,
        effective_at=payload.effective_at,
    )
    user.profile.employment_status = payload.new_status
    if payload.new_status.value == "在职" and not user.profile.join_date:
        user.profile.join_date = payload.effective_at.date()
    if payload.new_status.value == "离职":
        user.profile.leave_date = payload.effective_at.date()
    db.add(record)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="personnel.employment",
        target_type="user",
        target_id=str(payload.user_id),
        detail={"record_type": payload.record_type.value, "new_status": payload.new_status.value},
    )
    db.commit()
    if user.email:
        subject, text_body, html_body = build_employment_change_mail(
            user_display_name=user.display_name,
            record_type=payload.record_type.value,
            previous_status=record.previous_status.value if record.previous_status else "无",
            new_status=payload.new_status.value,
            reason=payload.reason,
            effective_at=str(payload.effective_at),
        )
        send_notification_email(db, to_addresses=[user.email], subject=subject, body=text_body, html=html_body)
    return {"message": "入离职记录已保存。"}


@router.post("/promotion-records")
def create_promotion_record(
    payload: PromotionRecordCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_staff_or_404(db, payload.user_id)
    ensure_staff_management_permission(current_user, user)
    record = PromotionDemotionRecord(
        user_id=payload.user_id,
        change_type=payload.change_type,
        previous_rank=user.profile.game_admin_rank,
        new_rank=payload.new_rank,
        reason=payload.reason,
        remark=payload.remark,
        operator_id=current_user.id,
        effective_at=payload.effective_at,
    )
    user.profile.game_admin_rank = payload.new_rank
    user.profile.position_title = payload.new_rank.value
    db.add(record)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="personnel.rank_change",
        target_type="user",
        target_id=str(payload.user_id),
        detail={"change_type": payload.change_type.value, "new_rank": payload.new_rank.value},
    )
    db.commit()
    if user.email:
        subject, text_body, html_body = build_rank_change_mail(
            user_display_name=user.display_name,
            change_type=payload.change_type.value,
            previous_rank=record.previous_rank.value if record.previous_rank else None,
            new_rank=payload.new_rank.value,
            reason=payload.reason,
            effective_at=str(payload.effective_at),
        )
        send_notification_email(db, to_addresses=[user.email], subject=subject, body=text_body, html=html_body)
    return {"message": "升降级记录已保存。"}


@router.post("/punishments")
def create_punishment(
    payload: PunishmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_staff_or_404(db, payload.user_id)
    ensure_staff_management_permission(current_user, user)
    record = PunishmentRecord(
        user_id=payload.user_id,
        level=payload.level,
        reason=payload.reason,
        remark=payload.remark,
        operator_id=current_user.id,
        effective_at=payload.effective_at,
    )
    db.add(record)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="personnel.punishment",
        target_type="user",
        target_id=str(payload.user_id),
        detail={"level": payload.level},
    )
    db.commit()
    if user.email:
        subject, text_body, html_body = build_punishment_mail(
            user_display_name=user.display_name,
            level=payload.level,
            reason=payload.reason,
            remark=payload.remark,
            effective_at=str(payload.effective_at),
        )
        send_notification_email(db, to_addresses=[user.email], subject=subject, body=text_body, html=html_body)
    return {"message": "处罚记录已保存。"}
