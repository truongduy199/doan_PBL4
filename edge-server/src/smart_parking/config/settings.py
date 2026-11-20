"""Application settings loader for Smart Parking Edge Server (MySQL/InnoDB architecture)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _load_dotenv_if_present(env_path: Optional[str] = None) -> None:
    """Load key=value pairs from .env file into os.environ if not already set."""
    candidate_paths = []
    if env_path:
        candidate_paths.append(Path(env_path))
    cwd = Path.cwd()
    candidate_paths.extend([
        cwd / ".env",
        cwd / "edge-server" / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ])
    for path in candidate_paths:
        if path.is_file():
            try:
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            except OSError:
                pass
            break


_load_dotenv_if_present()


class Settings:
    """Centralized configuration for MySQL, Security, Booking, and Hardware ports."""

    def __init__(self, **overrides: object) -> None:
        self.app_env: str = str(overrides.get("app_env", os.getenv("APP_ENV", "development")))
        self.debug: bool = str(overrides.get("debug", os.getenv("DEBUG", "true"))).lower() in ("1", "true", "yes")
        self.config_dir: str = str(overrides.get("config_dir", os.getenv("CONFIG_DIR", "configs")))

        # MySQL / InnoDB Configuration
        self.mysql_host: str = str(overrides.get("mysql_host", os.getenv("MYSQL_HOST", "127.0.0.1")))
        self.mysql_port: int = int(overrides.get("mysql_port", os.getenv("MYSQL_PORT", "3306")))
        self.mysql_user: str = str(overrides.get("mysql_user", os.getenv("MYSQL_USER", "root")))
        self.mysql_password: str = str(overrides.get("mysql_password", os.getenv("MYSQL_PASSWORD", "")))
        self.mysql_database: str = str(
            overrides.get("mysql_database", os.getenv("MYSQL_DATABASE", "smart_parking_pbl4"))
        )
        self.mysql_pool_size: int = int(overrides.get("mysql_pool_size", os.getenv("MYSQL_POOL_SIZE", "10")))
        self.mysql_deadlock_retries: int = int(
            overrides.get("mysql_deadlock_retries", os.getenv("MYSQL_DEADLOCK_RETRIES", "3"))
        )

        # Business Rules & Timings
        self.booking_ttl_minutes: int = int(
            overrides.get("booking_ttl_minutes", os.getenv("BOOKING_TTL_MINUTES", "60"))
        )
        self.slot_stale_seconds: int = int(
            overrides.get("slot_stale_seconds", os.getenv("SLOT_STALE_SECONDS", "30"))
        )
        self.parking_confirm_timeout_seconds: int = int(
            overrides.get(
                "parking_confirm_timeout_seconds",
                os.getenv("PARKING_CONFIRM_TIMEOUT_SECONDS", "120"),
            )
        )
        self.session_template_retention_hours: int = int(
            overrides.get(
                "session_template_retention_hours",
                os.getenv("SESSION_TEMPLATE_RETENTION_HOURS", "24"),
            )
        )
        self.expiry_worker_interval_seconds: int = int(
            overrides.get(
                "expiry_worker_interval_seconds",
                os.getenv("EXPIRY_WORKER_INTERVAL_SECONDS", "5"),
            )
        )

        # Serial / Hardware
        self.serial_port: str = str(overrides.get("serial_port", os.getenv("SERIAL_PORT", "COM3")))
        self.serial_baudrate: int = int(overrides.get("serial_baudrate", os.getenv("SERIAL_BAUDRATE", "115200")))

        # Security & Encryption
        self.embedding_secret_key: str = str(
            overrides.get(
                "embedding_secret_key",
                os.getenv("EMBEDDING_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="),
            )
        )
        self.embedding_key_version: str = str(
            overrides.get("embedding_key_version", os.getenv("EMBEDDING_KEY_VERSION", "v1"))
        )
        self.jwt_secret_key: str = str(
            overrides.get(
                "jwt_secret_key",
                os.getenv("JWT_SECRET_KEY", "pbl4_smart_parking_jwt_secret_key_2026_change_in_prod"),
            )
        )
        self.jwt_algorithm: str = str(overrides.get("jwt_algorithm", os.getenv("JWT_ALGORITHM", "HS256")))
        self.jwt_expire_hours: int = int(overrides.get("jwt_expire_hours", os.getenv("JWT_EXPIRE_HOURS", "12")))

        # Demo Seed Defaults
        self.demo_admin_username: str = str(
            overrides.get("demo_admin_username", os.getenv("DEMO_ADMIN_USERNAME", "admin"))
        )
        self.demo_admin_password: str = str(
            overrides.get("demo_admin_password", os.getenv("DEMO_ADMIN_PASSWORD", "Admin@123"))
        )
        self.demo_user_username: str = str(
            overrides.get("demo_user_username", os.getenv("DEMO_USER_USERNAME", "viet_user"))
        )
        self.demo_user_password: str = str(
            overrides.get("demo_user_password", os.getenv("DEMO_USER_PASSWORD", "Viet@123"))
        )
        self.demo_user_display_name: str = str(
            overrides.get(
                "demo_user_display_name",
                os.getenv("DEMO_USER_DISPLAY_NAME", "Nguyễn Văn Việt (Chủ xe Demo)"),
            )
        )
        self.demo_vehicle_plate: str = str(
            overrides.get("demo_vehicle_plate", os.getenv("DEMO_VEHICLE_PLATE", "43A12345"))
        )


def get_settings() -> Settings:
    """Return a fresh Settings instance loaded from current environment."""
    return Settings()
