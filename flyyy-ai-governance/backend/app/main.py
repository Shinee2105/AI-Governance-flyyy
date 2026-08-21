"""
Flyyy.ai FastAPI entrypoint. Serves the REST API under /api/v1.
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
        "them."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

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
