"""
Discovery orchestration service.

Runs a connector's ``discover()`` against a :class:`Connection`, persists the
resulting AI assets and their access evidence, and records a :class:`Run` audit
entry. Uses *upsert* semantics keyed on the asset identity so repeated
discoveries keep a stable inventory while refreshing evidence.

The network/IO part (``connector.discover()``) runs in the async event loop; the
blocking database persistence runs in a worker thread via
``asyncio.to_thread`` so a long discovery does not block the event loop. The
persistence function opens its own SQLAlchemy session (sessions are not
thread-safe) and returns the resulting ``Run`` id. If the provider call fails, a
FAILED run is recorded rather than crashing the request.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import effective_connector
from app.database import SessionLocal
from app.models import (
    AIAsset,
    AIAssetAccess,
    AccessType,
    AssetStatus,
    CapabilityStatus,
    Connection,
    MonitoringStatus,
    ReviewStatus,
    Run,
    RunStatus,
)


async def run_discovery(connection: Connection) -> str:
    """Discover and persist. Returns the created Run id."""
    connector, using_fallback = effective_connector(
        connection.connector_type, connection.config
    )
    try:
        result = await connector.discover()
    except Exception as exc:  # noqa: BLE001 - provider failure -> FAILED run
        return await asyncio.to_thread(
            _persist_failed, connection.id, "discovery", _safe_err(exc)
        )
    out = await asyncio.to_thread(
        _persist_discovery, connection.id, result, using_fallback
    )
    return out["run_id"]


def _persist_discovery(connection_id: str, result, using_fallback: bool) -> dict:
    db: Session = SessionLocal()
    run = Run(connection_id=connection_id, run_type="discovery")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        connection = db.get(Connection, connection_id)
        for asset in result.assets:
            db_asset = _upsert_asset(db, connection, asset)
            db.query(AIAssetAccess).filter(
                AIAssetAccess.asset_id == db_asset.id
            ).delete()
            for acc in result.accesses.get(asset.name, []):
                db.add(
                    AIAssetAccess(
                        asset_id=db_asset.id,
                        principal_type=acc.principal_type,
                        principal_id=acc.principal_id,
                        principal_name=acc.principal_name,
                        display_name=acc.display_name,
                        email=acc.email,
                        access_type=AccessType(acc.access_type or "Unknown"),
                        access_level=acc.access_level,
                        license_sku=acc.license_sku,
                        source=acc.source,
                    )
                )
            run.assets_found += 1
            run.accesses_found += len(result.accesses.get(asset.name, []))

        connection.last_run_at = datetime.now(timezone.utc)
        connection.status = (
            "Configured" if not using_fallback else "Not Configured"
        )
        run.status = RunStatus.SUCCESS if result.assets else RunStatus.PARTIAL
        run.summary = {
            "assets": [a.name for a in result.assets],
            "using_fallback": using_fallback,
            "notes": result.notes,
        }
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run.status = RunStatus.FAILED
        run.error = _safe_err(exc)
        conn = db.get(Connection, connection_id)
        if conn:
            conn.status = "Error"
        db.commit()
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return {"run_id": run.id, "status": run.status.value, "summary": run.summary}


def _persist_failed(connection_id: str, run_type: str, error: str) -> str:
    db: Session = SessionLocal()
    run = Run(connection_id=connection_id, run_type=run_type)
    run.status = RunStatus.FAILED
    run.error = error
    db.add(run)
    db.commit()
    db.refresh(run)
    conn = db.get(Connection, connection_id)
    if conn:
        conn.status = "Error"
        db.commit()
    run_id = run.id
    db.close()
    return run_id


def _upsert_asset(db: Session, connection: Connection, asset) -> AIAsset:
    existing = db.execute(
        select(AIAsset).where(
            AIAsset.connection_id == connection.id,
            AIAsset.saas_platform == asset.saas_platform,
            AIAsset.ai_capability == asset.ai_capability,
        )
    ).scalars().first()

    if existing:
        existing.name = asset.name
        existing.asset_type = asset.asset_type
        existing.provider = asset.provider
        existing.enabled = asset.enabled
        existing.capability_status = CapabilityStatus(asset.capability_status)
        existing.purpose = asset.purpose
        existing.accessible_resources = asset.accessible_resources
        existing.discovery_source = asset.discovery_source
        existing.monitoring_status = MonitoringStatus(asset.monitoring_status)
        existing.tenant_id = asset.tenant_id
        existing.evidence = asset.metadata
        existing.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    new = AIAsset(
        connection_id=connection.id,
        name=asset.name,
        asset_type=asset.asset_type,
        provider=asset.provider,
        saas_platform=asset.saas_platform,
        ai_capability=asset.ai_capability,
        enabled=asset.enabled,
        capability_status=CapabilityStatus(asset.capability_status),
        status=AssetStatus.DISCOVERED_PENDING_REVIEW,
        purpose=asset.purpose,
        accessible_resources=asset.accessible_resources,
        discovery_source=asset.discovery_source,
        monitoring_status=MonitoringStatus(asset.monitoring_status),
        review_status=ReviewStatus.PENDING,
        tenant_id=asset.tenant_id,
        evidence=asset.metadata,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


def _safe_err(exc: Exception) -> str:
    text = str(exc)
    import re

    text = re.sub(r"(client_secret=)[^&\s]+", r"\1<redacted>", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer <redacted>", text)
    return text[:500]
