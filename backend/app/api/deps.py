from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.entities import SystemRole, User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_token_from_request(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    token = request.query_params.get("access_token")
    if token:
        return token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供登录凭证。")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = get_token_from_request(request)
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效。") from exc
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效。")
    user = db.scalar(select(User).where(User.username == subject))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用。")
    _ = user.profile
    return user


def require_supervisor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.system_role not in {SystemRole.SUPERVISOR, SystemRole.SUPER_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要主管权限。")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.system_role != SystemRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超管权限。")
    return current_user
