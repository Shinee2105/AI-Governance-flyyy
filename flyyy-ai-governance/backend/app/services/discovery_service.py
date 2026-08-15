"""
Discovery orchestration service.

Runs a connector's ``discover()`` against a :class:`Connection`, persists the
resulting AI assets and their access evidence, and records a :class:`Run` audit
entry. Uses *upsert* semantics keyed on the asset identity so repeated
discoveries keep a stable inventory while refreshing evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import effective_connector
from app.models import (
    AIAsset,
    AIAssetAccess,
    AssetStatus,
    Connection,
    MonitoringStatus,
    ReviewStatus,
    Run,
    RunStatus,
)


async def run_discovery(db: Session, connection: Connection) -> Run:
    run = Run(connection_id=connection.id, run_type="discovery")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        connector, using_fallback = effective_connector(
            connection.connector_type, connection.config
        )
        result = await connector.discover()

        for asset in result.assets:
            db_asset = _upsert_asset(db, connection, asset)
            accesses = result.accesses.get(asset.name, [])
            # Refresh access evidence for this asset each discovery run.
            db.query(AIAssetAccess).filter(
                AIAssetAccess.asset_id == db_asset.id
            ).delete()
            for acc in accesses:
                db.add(
                    AIAssetAccess(
                        asset_id=db_asset.id,
                        principal_type=acc.principal_type,
                        principal_id=acc.principal_id,
                        principal_name=acc.principal_name,
                        display_name=acc.display_name,
                        email=acc.email,
                        access_level=acc.access_level,
                        license_sku=acc.license_sku,
                        source=acc.source,
                    )
                )
            run.assets_found += 1
            run.accesses_found += len(accesses)

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
    except Exception as exc:  # noqa: BLE001 - record failure, never crash caller
        db.rollback()
        run.status = RunStatus.FAILED
        run.error = str(exc)
        connection.status = "Error"
        db.commit()
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return run


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
