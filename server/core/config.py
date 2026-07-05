from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        default_db = f"sqlite:///{(base_dir / 'data' / 'app.db').as_posix()}"
        self.base_dir = base_dir
        self.environment = os.getenv("ENVIRONMENT", "production").lower()
        self.database_url = os.getenv("DATABASE_URL", default_db)
        self.secret_key = os.getenv("SECRET_KEY", "change-this-before-public-deploy")
        if self.environment == "production" and self.secret_key == "change-this-before-public-deploy":
            raise RuntimeError("Production SECRET_KEY must be set in .env before deployment.")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:17250,http://localhost:17250").split(",")
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
        self.mail_enabled = os.getenv("MAIL_ENABLED", "0") == "1"
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "1") == "1"
        self.smtp_use_ssl = os.getenv("SMTP_USE_SSL", "0") == "1"
        self.mail_from = os.getenv("MAIL_FROM", self.smtp_username)
        self.mail_admin_reply_to = os.getenv("MAIL_ADMIN_REPLY_TO", self.mail_from)
        self.mail_timeout_seconds = float(os.getenv("MAIL_TIMEOUT_SECONDS", "10"))
        upload_dir = os.getenv("UPLOAD_DIR", "data/uploads")
        upload_path = Path(upload_dir)
        if not upload_path.is_absolute():
            upload_path = base_dir / upload_path
        self.upload_dir = upload_path
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            db_path = Path(self.database_url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_pass_score = int(os.getenv("DEFAULT_PASS_SCORE", "60"))
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        self.game_bridge_base_url = os.getenv("GAME_BRIDGE_BASE_URL", "http://127.0.0.1:17251").rstrip("/")
        self.game_bridge_token = os.getenv("GAME_BRIDGE_TOKEN", "change-this-bridge-token")
        self.game_bridge_timeout_seconds = float(os.getenv("GAME_BRIDGE_TIMEOUT_SECONDS", "5"))


settings = Settings()
