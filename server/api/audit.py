from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.api.deps import get_db, require_super_admin
from server.models.entities import AuditLog, User
from server.services.domain import get_staff_or_404, serialize_audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs", dependencies=[Depends(require_super_admin)])
def list_audit_logs(db: Session = Depends(get_db)):
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all())
    return [serialize_audit(log, get_staff_or_404(db, log.actor_id) if log.actor_id else None) for log in logs]
