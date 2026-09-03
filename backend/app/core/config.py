"""Central configuration — reads from environment / .env file."""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────
    APP_NAME: str = "FinGuard AI"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────
    # MongoDB (default) — swap DATABASE_URL for PostgreSQL to use SQLAlchemy
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "finguard"

    # ── JWT ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-a-32-char-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── ML Model ──────────────────────────────────────────────────────────
    MODEL_PATH: str = "app/services/ml/fraud_model.pkl"
    FRAUD_THRESHOLD: float = 0.65          # Probability above which a txn is flagged
    BATCH_ANALYSIS_INTERVAL_SEC: int = 30  # Background worker polling interval

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",   # Vite dev
        "http://localhost:4173",   # Vite preview
        "https://finguard.vercel.app",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
