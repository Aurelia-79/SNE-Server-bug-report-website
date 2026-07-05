from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

from app.api import analytics, audit, auth, bugs, exams, personnel, staff
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bootstrap import bootstrap_super_admin, init_database, normalize_super_admin_profiles, seed_defaults

FRONTEND_DIST = settings.base_dir.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    db = SessionLocal()
    try:
        normalize_super_admin_profiles(db)
        bootstrap_super_admin(db)
        if settings.seed_demo_data:
            seed_defaults(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="非礼勿视服务器管理系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(staff.router)
app.include_router(personnel.router)
app.include_router(exams.router)
app.include_router(analytics.router)
app.include_router(bugs.router)
app.include_router(audit.router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


def _frontend_file(path: str) -> Path | None:
    if not FRONTEND_DIST.exists():
        return None
    if path:
      candidate = FRONTEND_DIST / path
      if candidate.is_file():
          return candidate
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return index_file
    return None


@app.get("/")
def serve_frontend_root():
    file_path = _frontend_file("")
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend build not found.")
    return FileResponse(str(file_path))


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    file_path = _frontend_file(full_path)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return FileResponse(str(file_path))
