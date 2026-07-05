from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db, require_super_admin
from server.models.entities import Department, GameAdminRank, SystemRole, User
from server.schemas.api import UserCreateRequest, UserUpdateRequest
from server.services.domain import (
    create_audit_log,
    department_label,
    is_supervisor,
    create_user_with_profile,
    ensure_game_admin_rank_consistency,
    ensure_staff_management_permission,
    ensure_staff_view_permission,
    get_staff_or_404,
    serialize_user,
)

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("/meta")
def get_meta():
    return {
        "departments": [item.value for item in Department],
        "game_admin_ranks": [item.value for item in GameAdminRank],
    }


@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.get("/users")
def list_users(
    department: str | None = Query(default=None),
    rank: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_global_viewer = is_supervisor(current_user)
    is_game_admin_leader = (
        current_user.profile
        and current_user.profile.department == Department.GAME_ADMIN
        and current_user.profile.game_admin_rank in {GameAdminRank.SENIOR, GameAdminRank.CHIEF}
    )
    users = list(db.scalars(select(User).order_by(User.id.desc())).all())
    filtered: list[dict] = []
    for user in users:
        _ = user.profile
        user_department = department_label(user.profile.department)
        if department and user_department != department:
            continue
        if rank and (not user.profile.game_admin_rank or user.profile.game_admin_rank.value != rank):
            continue
        if not is_global_viewer:
            if is_game_admin_leader:
                if current_user.profile.game_admin_rank == GameAdminRank.SENIOR:
                    if user.profile.department != Department.GAME_ADMIN or user.profile.game_admin_rank not in {
                        GameAdminRank.REVIEW,
                        GameAdminRank.ADMIN,
                    }:
                        continue
                elif current_user.profile.game_admin_rank == GameAdminRank.CHIEF:
                    if user.profile.department != Department.GAME_ADMIN:
                        continue
            elif user.id != current_user.id:
                continue
        filtered.append(serialize_user(user))
    return filtered


@router.get("/users/{user_id}")
def get_user_detail(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = get_staff_or_404(db, user_id)
    ensure_staff_view_permission(current_user, user)
    return serialize_user(user)


@router.post("/users", dependencies=[Depends(require_super_admin)])
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在。")
    game_admin_rank = payload.game_admin_rank if payload.department == Department.GAME_ADMIN else None
    user = create_user_with_profile(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        email=payload.email.strip() if payload.email else None,
        system_role=payload.system_role,
        department=payload.department,
        position_title=payload.position_title,
        employment_status=payload.employment_status,
        game_admin_rank=game_admin_rank,
        join_date=payload.join_date,
        leave_date=payload.leave_date,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="staff.create",
        target_type="user",
        target_id=str(user.id),
        detail={"username": payload.username, "department": department_label(payload.department)},
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_staff_or_404(db, user_id)
    if current_user.system_role != SystemRole.SUPER_ADMIN:
        ensure_staff_management_permission(current_user, user)

    data = payload.model_dump(exclude_none=True)
    profile = user.profile
    new_department = data.get("department", profile.department)
    new_rank = data.get("game_admin_rank", profile.game_admin_rank)
    if new_department != Department.GAME_ADMIN:
        new_rank = None
        data["game_admin_rank"] = None
    elif new_rank is None:
        new_rank = GameAdminRank.REVIEW
        data["game_admin_rank"] = GameAdminRank.REVIEW
    ensure_game_admin_rank_consistency(new_department, new_rank)

    if "display_name" in data:
        user.display_name = data["display_name"]
    if "email" in data:
        user.email = data["email"].strip() if data["email"] else None
    if "password" in data and data["password"]:
        from server.core.security import hash_password

        user.password_hash = hash_password(data["password"])
    if "system_role" in data and current_user.system_role == SystemRole.SUPER_ADMIN:
        user.system_role = data["system_role"]
    if "is_active" in data and current_user.system_role == SystemRole.SUPER_ADMIN:
        user.is_active = data["is_active"]

    for field_name in ("department", "position_title", "employment_status", "game_admin_rank", "join_date", "leave_date", "notes"):
        if field_name in data:
            setattr(profile, field_name, data[field_name])

    create_audit_log(
        db,
        actor_id=current_user.id,
        action="staff.update",
        target_type="user",
        target_id=str(user.id),
        detail={"changed_fields": sorted(data.keys())},
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user)
