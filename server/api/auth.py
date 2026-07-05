from __future__ import annotations

from pathlib import Path

import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db
from server.core.config import settings
from server.core.security import create_access_token, hash_password, verify_password
from server.models.entities import User
from server.schemas.api import LoginRequest, ProfileUpdateRequest, RegisterRequest, TokenResponse
from server.services.domain import create_audit_log, create_user_with_profile, serialize_user
from server.models.entities import EmploymentStatus, SystemRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在。")
    email = payload.email.strip()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写有效的电子邮箱。")
    user = create_user_with_profile(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        email=email,
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


@router.patch("/me", response_model=TokenResponse)
def update_me(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    username = payload.username.strip() if payload.username else current_user.username
    display_name = payload.display_name.strip() if payload.display_name else current_user.display_name
    email = payload.email.strip() if payload.email else current_user.email
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空。")
    if not display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="显示名不能为空。")
    if username != current_user.username:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在。")
        current_user.username = username
    current_user.display_name = display_name
    current_user.email = email

    if payload.new_password:
        if not payload.current_password or not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误。")
        current_user.password_hash = hash_password(payload.new_password)

    create_audit_log(db, actor_id=current_user.id, action="auth.profile.update", target_type="user", target_id=str(current_user.id))
    db.commit()
    db.refresh(current_user)
    token = create_access_token(current_user.username, extra_claims={"role": current_user.system_role.value})
    return TokenResponse(access_token=token, user=serialize_user(current_user))


@router.post("/me/avatar")
def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择头像文件。")
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像必须是图片文件。")
    content = file.file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像不能超过 2MB。")
    suffix = Path(file.filename).suffix.lower() or ".png"
    avatar_dir = settings.upload_dir / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    avatar_path = avatar_dir / f"user_{current_user.id}{suffix}"
    avatar_path.write_bytes(content)
    current_user.avatar_path = avatar_path.relative_to(settings.upload_dir).as_posix()
    create_audit_log(db, actor_id=current_user.id, action="auth.avatar.upload", target_type="user", target_id=str(current_user.id))
    db.commit()
    db.refresh(current_user)
    return serialize_user(current_user)


@router.get("/avatar/{user_id}")
def get_avatar(user_id: int, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id))
    if not user or not user.avatar_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="头像不存在。")
    file_path = settings.upload_dir / user.avatar_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="头像不存在。")
    return FileResponse(str(file_path))
