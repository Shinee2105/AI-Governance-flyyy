"""Assets (AI inventory) API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIAsset, AIAssetAccess, AIInteraction
from app.schemas import (
    AIAssetDetailOut,
    AIAssetOut,
    AIAssetReviewUpdate,
)

router = APIRouter(prefix="/assets", tags=["assets"])


def _serialize(asset: AIAsset, counts: bool = True) -> dict:
    data = AIAssetOut.model_validate(asset).model_dump()
    if counts:
        data["access_count"] = len(asset.accesses)
        data["interaction_count"] = len(asset.interactions)
    return data


@router.get("", response_model=list[AIAssetOut])
def list_assets(
    db: Session = Depends(get_db),
    saas_platform: str | None = Query(None),
    provider: str | None = Query(None),
    monitoring_status: str | None = Query(None),
    search: str | None = Query(None),
):
    stmt = select(AIAsset)
    if saas_platform:
        stmt = stmt.where(AIAsset.saas_platform == saas_platform)
    if provider:
        stmt = stmt.where(AIAsset.provider == provider)
    if monitoring_status:
        stmt = stmt.where(AIAsset.monitoring_status == monitoring_status)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (AIAsset.name.ilike(like))
            | (AIAsset.ai_capability.ilike(like))
            | (AIAsset.provider.ilike(like))
        )
    assets = db.execute(stmt.order_by(AIAsset.discovered_at.desc())).scalars().all()
    return [_serialize(a) for a in assets]


@router.get("/{asset_id}", response_model=AIAssetDetailOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(AIAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    data = AIAssetDetailOut.model_validate(asset).model_dump()
    data["access_count"] = len(asset.accesses)
    data["interaction_count"] = len(asset.interactions)
    data["accesses"] = [AIAssetAccessOut.model_validate(a).model_dump()
                        for a in asset.accesses]
    return data


@router.patch("/{asset_id}", response_model=AIAssetDetailOut)
def update_asset(
    asset_id: str,
    payload: AIAssetReviewUpdate,
    db: Session = Depends(get_db),
):
    asset = db.get(AIAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if payload.review_status is not None:
        asset.review_status = payload.review_status
    if payload.status is not None:
        asset.status = payload.status
    if payload.monitoring_status is not None:
        asset.monitoring_status = payload.monitoring_status
    if payload.purpose is not None:
        asset.purpose = payload.purpose
    db.commit()
    db.refresh(asset)
    data = AIAssetDetailOut.model_validate(asset).model_dump()
    data["access_count"] = len(asset.accesses)
    data["interaction_count"] = len(asset.interactions)
    data["accesses"] = [AIAssetAccessOut.model_validate(a).model_dump()
                        for a in asset.accesses]
    return data
