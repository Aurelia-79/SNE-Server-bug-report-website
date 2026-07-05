from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.api import LoginRequest, RegisterRequest, TokenResponse
from app.services.domain import create_audit_log, create_user_with_profile, serialize_user
from app.models.entities import EmploymentStatus, SystemRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在。")
    user = create_user_with_profile(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        system_role=SystemRole.MEMBER,
        department=None,
        position_title="普通玩家",
        employment_status=EmploymentStatus.PENDING,
        game_admin_rank=None,
        join_date=None,
        leave_date=None,
        notes="注册用户",
    )
    token = create_access_token(user.username, extra_claims={"role": user.system_role.value})
    create_audit_log(db, actor_id=user.id, action="auth.register", target_type="user", target_id=str(user.id))
    db.commit()
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误。")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用。")
    token = create_access_token(user.username, extra_claims={"role": user.system_role.value})
    create_audit_log(db, actor_id=user.id, action="auth.login", target_type="user", target_id=str(user.id))
    db.commit()
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)
