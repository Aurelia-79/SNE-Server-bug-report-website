from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db
from server.models.entities import Department, SystemRole, User
from server.services.domain import create_audit_log, ensure_server_operation_permission
from server.services.server_bridge import bridge_client

router = APIRouter(prefix="/api/server", tags=["server"])

ALLOWED_RA_COMMANDS = {
    "cleanup corpses",
    "cleanup items",
    "warhead start",
    "warhead stop",
    "emergency_escape start",
}


class RaCommandRequest(BaseModel):
    command: str


class ServerActionRequest(BaseModel):
    reason: str | None = None


def require_server_viewer(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_danger_operator(current_user: User = Depends(get_current_user)) -> User:
    ensure_server_operation_permission(current_user)
    return current_user


def ensure_ra_allowed(command: str, current_user: User) -> None:
    if current_user.system_role == SystemRole.SUPER_ADMIN:
        return
    normalized = " ".join(command.strip().lower().split())
    if normalized not in ALLOWED_RA_COMMANDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该 RA 指令不在白名单内。")


def audit_server_action(
    db: Session,
    actor: User,
    action: str,
    target_id: str,
    payload: dict[str, Any],
) -> None:
    create_audit_log(
        db,
        actor_id=actor.id,
        action=action,
        target_type="game_server",
        target_id=target_id,
        detail=payload,
    )
    db.commit()


@router.get("/overview")
def overview(_: User = Depends(require_server_viewer)):
    return {
        "status": bridge_client.get("/status"),
        "players": bridge_client.get("/players"),
        "emergency": bridge_client.get("/emergency"),
    }


@router.get("/status")
def status(_: User = Depends(require_server_viewer)):
    return bridge_client.get("/status")


@router.get("/players")
def players(_: User = Depends(require_server_viewer)):
    return bridge_client.get("/players")


@router.get("/logs")
def logs(lines: int = Query(200, ge=1, le=1000), _: User = Depends(require_server_viewer)):
    return bridge_client.get("/logs", {"lines": lines})


@router.get("/chat")
def chat(limit: int = Query(100, ge=1, le=500), _: User = Depends(require_server_viewer)):
    return bridge_client.get("/chat", {"limit": limit})


@router.get("/emergency")
def emergency(_: User = Depends(require_server_viewer)):
    return bridge_client.get("/emergency")


@router.post("/ra")
def run_ra(
    payload: RaCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_danger_operator),
):
    command = payload.command.strip()
    if not command:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RA 指令不能为空。")
    ensure_ra_allowed(command, current_user)
    result = bridge_client.post("/ra", {"command": command})
    audit_server_action(db, current_user, "server.ra", command[:100], {"command": command, "result": result})
    return result


@router.post("/actions/{action_name}")
def run_action(
    action_name: str,
    payload: ServerActionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_danger_operator),
):
    if action_name not in {"restart", "rnr", "shutdown"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未知服务器操作。")
    result = bridge_client.post(f"/actions/{action_name}", {"reason": payload.reason if payload else None})
    audit_server_action(
        db,
        current_user,
        f"server.{action_name}",
        action_name,
        {"reason": payload.reason if payload else None, "result": result},
    )
    return result

