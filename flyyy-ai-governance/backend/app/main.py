"""
Flyyy.ai - SaaS AI Discovery & Monitoring Platform.

FastAPI entrypoint. Serves the REST API under ``/api/v1`` and (in production
builds) can serve the bundled React frontend.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import assets, auth, connections, interactions, stats
from app.seed import bootstrap


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In development we auto-create tables for convenience. In production the
    # authoritative schema is managed by Alembic migrations (see README), so we
    # deliberately do NOT mutate the schema on startup there.
    if settings.CREATE_TABLES_ON_STARTUP:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        await bootstrap(db, settings.SEED_DEMO_DATA)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Discover AI capabilities embedded in SaaS applications, identify who "
        "can use them, and monitor the AI interactions taking place through "
        "them. See README for architecture and research notes."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS is environment-driven. We never use a wildcard together with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(assets.router, prefix=API_PREFIX)
app.include_router(interactions.router, prefix=API_PREFIX)
app.include_router(connections.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.APP_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
