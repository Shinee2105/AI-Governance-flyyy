"""Dashboard statistics API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIAsset, AIAssetAccess, AIInteraction, Connection, Run
from app.schemas import DashboardStats, RunOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    total_assets = db.execute(select(func.count(AIAsset.id))).scalar() or 0
    enabled_assets = (
        db.execute(select(func.count(AIAsset.id)).where(AIAsset.enabled == True))  # noqa: E712
        .scalar()
        or 0
    )
    total_accesses = db.execute(select(func.count(AIAssetAccess.id))).scalar() or 0
    unique_users = (
        db.execute(
            select(func.count(func.distinct(AIAssetAccess.email))).where(
                AIAssetAccess.email.is_not(None)
            )
        ).scalar()
        or 0
    )
    total_interactions = (
        db.execute(select(func.count(AIInteraction.id))).scalar() or 0
    )
    monitoring_limited = (
        db.execute(
            select(func.count(AIAsset.id)).where(
                AIAsset.monitoring_status.in_(["Limited Visibility", "Not Available"])
            )
        ).scalar()
        or 0
    )
    connections = db.execute(select(func.count(Connection.id))).scalar() or 0

    # Whether any inventory is demonstration/simulated data.
    assets = db.execute(select(AIAsset)).scalars().all()
    simulated_evidence = any((a.evidence or {}).get("simulated") for a in assets)

    # Visibility summary: how many interactions expose each signal.
    visibility_summary = {
        "request_available": db.execute(
            select(func.count(AIInteraction.id)).where(
                AIInteraction.request_available == True  # noqa: E712
            )
        ).scalar()
        or 0,
        "response_available": db.execute(
            select(func.count(AIInteraction.id)).where(
                AIInteraction.response_available == True  # noqa: E712
            )
        ).scalar()
        or 0,
        "model_available": db.execute(
            select(func.count(AIInteraction.id)).where(
                AIInteraction.model_available == True  # noqa: E712
            )
        ).scalar()
        or 0,
        "usage_available": db.execute(
            select(func.count(AIInteraction.id)).where(
                AIInteraction.usage_available == True  # noqa: E712
            )
        ).scalar()
        or 0,
        "no_content": db.execute(
            select(func.count(AIInteraction.id)).where(
                AIInteraction.request_available == False,  # noqa: E712
                AIInteraction.response_available == False,  # noqa: E712
            )
        ).scalar()
        or 0,
    }

    recent_runs = db.execute(
        select(Run).order_by(Run.started_at.desc()).limit(8)
    ).scalars().all()

    return DashboardStats(
        total_assets=total_assets,
        enabled_assets=enabled_assets,
        total_accesses=total_accesses,
        unique_users_exposed=unique_users,
        total_interactions=total_interactions,
        monitoring_limited=monitoring_limited,
        connections=connections,
        simulated_evidence=simulated_evidence,
        recent_runs=[RunOut.model_validate(r).model_dump() for r in recent_runs],
        visibility_summary=visibility_summary,
    )
