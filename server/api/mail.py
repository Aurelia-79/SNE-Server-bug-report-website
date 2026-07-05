from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db, require_super_admin
from server.models.entities import MailConfig, User
from server.schemas.api import (
    MailConfigRequest,
    MailConfigResponse,
    MailSendRequest,
    MailTestRequest,
    MessageResponse,
)
from server.services.domain import _send_via_db_config, utcnow

router = APIRouter(prefix="/api/mail", tags=["mail"])


def _get_mail_config(db: Session) -> MailConfig:
    """Fetch or seed the singleton mail config row."""
    config = db.scalar(select(MailConfig).where(MailConfig.id == 1))
    if not config:
        config = MailConfig(id=1)
        db.add(config)
        db.flush()
    return config


def _serialize_config(config: MailConfig) -> dict:
    return {
        "enabled": config.enabled,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_username": config.smtp_username,
        "smtp_use_tls": config.smtp_use_tls,
        "smtp_use_ssl": config.smtp_use_ssl,
        "mail_from": config.mail_from,
        "mail_admin_reply_to": config.mail_admin_reply_to,
        "mail_timeout_seconds": config.mail_timeout_seconds,
        "updated_at": config.updated_at,
    }


@router.get("/config", response_model=MailConfigResponse, dependencies=[Depends(require_super_admin)])
def get_mail_config(db: Session = Depends(get_db)):
    config = _get_mail_config(db)
    return _serialize_config(config)


@router.put("/config", response_model=MailConfigResponse, dependencies=[Depends(require_super_admin)])
def update_mail_config(payload: MailConfigRequest, db: Session = Depends(get_db)):
    config = _get_mail_config(db)
    config.enabled = payload.enabled
    config.smtp_host = payload.smtp_host.strip()
    config.smtp_port = payload.smtp_port
    config.smtp_username = payload.smtp_username.strip()
    config.smtp_use_tls = payload.smtp_use_tls
    config.smtp_use_ssl = payload.smtp_use_ssl
    config.mail_from = payload.mail_from.strip()
    config.mail_admin_reply_to = payload.mail_admin_reply_to.strip()
    config.mail_timeout_seconds = payload.mail_timeout_seconds
    if payload.smtp_password:
        config.smtp_password = payload.smtp_password
    db.commit()
    db.refresh(config)
    # Return config without exposing the password
    result = _serialize_config(config)
    return result


@router.post("/test", response_model=MessageResponse, dependencies=[Depends(require_super_admin)])
def test_mail(payload: MailTestRequest, db: Session = Depends(get_db)):
    config = _get_mail_config(db)
    if not config.enabled or not config.smtp_host:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮件服务未启用或 SMTP 主机未配置。")
    recipient = payload.recipient.strip()
    if not recipient:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写收件人邮箱。")

    success = _send_via_db_config(
        config=config,
        to_addresses=[recipient],
        subject="[非礼勿视] 邮件配置测试",
        body="这是一封来自非礼勿视管理系统的测试邮件。\n\n如果你收到这封邮件，说明 SMTP 配置正确。",
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败，请检查 SMTP 配置。")
    return MessageResponse(message=f"测试邮件已发送至 {recipient}，请查收。")


@router.post("/send", response_model=MessageResponse, dependencies=[Depends(require_super_admin)])
def send_mail_to_users(
    payload: MailSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = _get_mail_config(db)
    if not config.enabled or not config.smtp_host:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮件服务未启用或 SMTP 主机未配置。")

    users = list(db.scalars(select(User).where(User.id.in_(payload.user_ids))).all())
    recipients = [u.email for u in users if u.email and u.email.strip()]
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选用户均未填写邮箱。")

    success = _send_via_db_config(
        config=config,
        to_addresses=recipients,
        subject=payload.subject,
        body=payload.body,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败，请检查 SMTP 配置。")

    return MessageResponse(message=f"邮件已发送至 {len(recipients)} 位用户。")
