from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        default_db = f"sqlite:///{(base_dir / 'app.db').as_posix()}"
        self.base_dir = base_dir
        self.environment = os.getenv("ENVIRONMENT", "development").lower()
        self.database_url = os.getenv("DATABASE_URL", default_db)
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if origin.strip()
        ]
        self.trusted_hosts = [
            host.strip()
            for host in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,::1").split(",")
            if host.strip()
        ]
        self.enable_docs = os.getenv("ENABLE_DOCS", "1" if self.environment != "production" else "0") == "1"
        self.seed_demo_data = os.getenv("SEED_DEMO_DATA", "0") == "1"
        self.bootstrap_super_admin_username = os.getenv("BOOTSTRAP_SUPER_ADMIN_USERNAME")
        self.bootstrap_super_admin_password = os.getenv("BOOTSTRAP_SUPER_ADMIN_PASSWORD")
        self.bootstrap_super_admin_display_name = os.getenv("BOOTSTRAP_SUPER_ADMIN_DISPLAY_NAME", "系统超管")
        upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        upload_path = Path(upload_dir)
        if not upload_path.is_absolute():
            upload_path = base_dir / upload_path
        self.upload_dir = upload_path
        self.default_pass_score = int(os.getenv("DEFAULT_PASS_SCORE", "60"))
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))


settings = Settings()
