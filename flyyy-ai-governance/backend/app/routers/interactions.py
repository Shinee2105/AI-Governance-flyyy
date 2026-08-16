"""AI interactions (monitoring) API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIInteraction
from app.schemas import AIInteractionOut

router = APIRouter(prefix="/interactions", tags=["interactions"])


def _serialize(i: AIInteraction) -> dict:
    data = AIInteractionOut.model_validate(i).model_dump()
    data["simulated"] = "simulated" in (i.source or "").lower()
    return data


@router.get("", response_model=list[AIInteractionOut])
def list_interactions(
    db: Session = Depends(get_db),
    asset_id: str | None = Query(None),
    user_email: str | None = Query(None),
    saas_application: str | None = Query(None),
    ai_feature: str | None = Query(None),
    only_limited: bool = Query(False, description="Only interactions missing content"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    stmt = select(AIInteraction)
    if asset_id:
        stmt = stmt.where(AIInteraction.asset_id == asset_id)
    if user_email:
        stmt = stmt.where(AIInteraction.user_email == user_email)
    if saas_application:
        stmt = stmt.where(AIInteraction.saas_application == saas_application)
    if ai_feature:
        stmt = stmt.where(AIInteraction.ai_feature == ai_feature)
    if only_limited:
        stmt = stmt.where(AIInteraction.request_available == False)  # noqa: E712
    interactions = db.execute(
        stmt.order_by(AIInteraction.timestamp.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [_serialize(i) for i in interactions]


@router.get("/filters", response_model=dict)
def interaction_filters(db: Session = Depends(get_db)):
    apps = db.execute(
        select(AIInteraction.saas_application)
        .where(AIInteraction.saas_application.is_not(None))
        .distinct()
    ).scalars().all()
    features = db.execute(
        select(AIInteraction.ai_feature)
        .where(AIInteraction.ai_feature.is_not(None))
        .distinct()
    ).scalars().all()
    users = db.execute(
        select(AIInteraction.user_email)
        .where(AIInteraction.user_email.is_not(None))
        .distinct()
    ).scalars().all()
    return {"applications": apps, "features": features, "users": users}
