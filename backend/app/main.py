"""
FinGuard AI — FastAPI Backend
Full-stack fraud detection system with ML inference, JWT auth, async DB, and background workers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import init_db
from app.api.routes import auth, transactions, cases, predictions, analytics, users, hardware
from app.workers.background import start_background_worker

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    worker_task = await start_background_worker()
    yield
    worker_task.cancel()


app = FastAPI(
    title="FinGuard AI API",
    description="Autonomous financial crime detection system — PMLA 2002 / FIU-IND compliant",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,         prefix="/api/v1/auth",         tags=["Auth"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["Transactions"])
app.include_router(cases.router,        prefix="/api/v1/cases",        tags=["Cases"])
app.include_router(predictions.router,  prefix="/api/v1/predictions",  tags=["Predictions"])
app.include_router(analytics.router,    prefix="/api/v1/analytics",    tags=["Analytics"])
app.include_router(users.router,        prefix="/api/v1/users",        tags=["Users"])
app.include_router(hardware.router,     prefix="/api/v1/hardware",     tags=["Hardware"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "finguard-ai", "version": "2.0.0"}
