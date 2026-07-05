from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.entities import BugAttachment, BugComment, BugStatus, BugTicket, SystemRole, User
from app.schemas.api import BugCommentCreateRequest, BugTicketCreateRequest, BugTicketUpdateRequest
from app.services.domain import create_audit_log, ensure_bug_management_permission, get_staff_or_404, serialize_bug, store_upload, utcnow

router = APIRouter(prefix="/api/bugs", tags=["bugs"])


def build_bug_payload(db: Session, ticket: BugTicket) -> dict:
    reporter = get_staff_or_404(db, ticket.reporter_id)
    assignee = get_staff_or_404(db, ticket.assignee_id) if ticket.assignee_id else None
    comments = list(db.scalars(select(BugComment).where(BugComment.ticket_id == ticket.id).order_by(BugComment.id)).all())
    attachments = list(db.scalars(select(BugAttachment).where(BugAttachment.ticket_id == ticket.id).order_by(BugAttachment.id)).all())
    user_ids = {comment.author_id for comment in comments}
    if ticket.reporter_id:
        user_ids.add(ticket.reporter_id)
    if ticket.assignee_id:
        user_ids.add(ticket.assignee_id)
    users_by_id = {user_id: get_staff_or_404(db, user_id) for user_id in user_ids}
    return serialize_bug(ticket, reporter, assignee, comments, attachments, users_by_id)


@router.get("/tickets")
def list_tickets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(BugTicket).order_by(BugTicket.updated_at.desc())
    if current_user.system_role == SystemRole.MEMBER:
        tickets = list(db.scalars(query.where(BugTicket.reporter_id == current_user.id)).all())
    else:
        tickets = list(db.scalars(query).all())
    return [build_bug_payload(db, ticket) for ticket in tickets]


@router.post("/tickets")
def create_ticket(
    payload: BugTicketCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = BugTicket(
        title=payload.title,
        module=payload.module,
        priority=payload.priority,
        reporter_id=current_user.id,
        assignee_id=None,
        reproduce_steps=payload.reproduce_steps,
        expected_result=payload.expected_result,
        actual_result=payload.actual_result,
        status=BugStatus.NEW,
    )
    db.add(ticket)
    db.flush()
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="bug.create",
        target_type="ticket",
        target_id=str(ticket.id),
        detail={"priority": payload.priority.value, "module": payload.module},
    )
    db.commit()
    return build_bug_payload(db, ticket)


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ticket = db.scalar(select(BugTicket).where(BugTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在。")
    if current_user.system_role == SystemRole.MEMBER and ticket.reporter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该工单。")
    return build_bug_payload(db, ticket)


@router.post("/tickets/{ticket_id}/attachments")
def upload_bug_attachments(
    ticket_id: int,
    files: list[UploadFile] = File(...),
    comment_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(select(BugTicket).where(BugTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在。")
    if current_user.system_role == SystemRole.MEMBER and ticket.reporter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权上传附件。")
    records = []
    for file in files:
        stored_name, relative_path, size, mime_type = store_upload(file, "bugs")
        attachment = BugAttachment(
            ticket_id=ticket.id,
            comment_id=comment_id,
            stored_name=stored_name,
            original_name=file.filename or stored_name,
            relative_path=relative_path,
            mime_type=mime_type,
            size=size,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.flush()
        records.append({"id": attachment.id, "name": attachment.original_name})
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="bug.attachments.upload",
        target_type="ticket",
        target_id=str(ticket.id),
        detail={"count": len(records)},
    )
    db.commit()
    return {"message": "附件上传成功。", "files": records}


@router.post("/tickets/{ticket_id}/comments")
def add_comment(
    ticket_id: int,
    payload: BugCommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.scalar(select(BugTicket).where(BugTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在。")
    if current_user.system_role == SystemRole.MEMBER and ticket.reporter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权评论该工单。")
    comment = BugComment(ticket_id=ticket.id, author_id=current_user.id, content=payload.content)
    db.add(comment)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="bug.comment",
        target_type="ticket",
        target_id=str(ticket.id),
    )
    db.commit()
    return build_bug_payload(db, ticket)


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: BugTicketUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_bug_management_permission(current_user)
    ticket = db.scalar(select(BugTicket).where(BugTicket.id == ticket_id))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在。")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        ticket.status = data["status"]
        if data["status"] == BugStatus.CLOSED:
            ticket.closed_at = utcnow()
    if "assignee_id" in data:
        ticket.assignee_id = data["assignee_id"]
    if "resolution" in data:
        ticket.resolution = data["resolution"]
    if data.get("comment"):
        db.add(BugComment(ticket_id=ticket.id, author_id=current_user.id, content=data["comment"]))
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="bug.update",
        target_type="ticket",
        target_id=str(ticket.id),
        detail={"fields": sorted(data.keys())},
    )
    db.commit()
    return build_bug_payload(db, ticket)


@router.get("/attachments/{attachment_id}")
def download_bug_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = db.scalar(select(BugAttachment).where(BugAttachment.id == attachment_id))
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在。")
    ticket = db.scalar(select(BugTicket).where(BugTicket.id == attachment.ticket_id))
    if current_user.system_role == SystemRole.MEMBER and ticket.reporter_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权下载附件。")
    file_path = settings.upload_dir / attachment.relative_path
    return FileResponse(str(file_path), media_type=attachment.mime_type, filename=attachment.original_name)
