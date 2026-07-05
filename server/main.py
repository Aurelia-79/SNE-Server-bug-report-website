from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.api import analytics, audit, auth, bugs, exams, mail, personnel, server_control, staff
from server.core.config import settings
from server.db.session import SessionLocal
from server.services.bootstrap import bootstrap_super_admin, init_database, normalize_super_admin_profiles, seed_defaults

TEMPLATES_DIR = settings.base_dir / "templates"
STATIC_DIR = settings.base_dir / "static"

# 确保静态文件和模板目录存在（前端构建前可能为空）
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "assets").mkdir(parents=True, exist_ok=True)


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
    title="非礼勿视管理系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")
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
app.include_router(server_control.router)
app.include_router(mail.router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


def _index_file():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend template not found.")
    return FileResponse(str(index_file))


@app.get("/")
def serve_frontend_root():
    return _index_file()


@app.get("/favicon.svg")
def serve_favicon():
    return FileResponse(str(STATIC_DIR / "favicon.svg"))


@app.get("/icons.svg")
def serve_icons():
    return FileResponse(str(STATIC_DIR / "icons.svg"))


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return _index_file()
