"""
Monitoring orchestration service.

Runs a connector's ``monitor()`` to capture AI interactions, links each
interaction to the discovered asset it belongs to (by platform + capability),
and records a :class:`Run` audit entry. Duplicate interactions (same identity,
timestamp and source) are skipped so re-runs are idempotent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import effective_connector
from app.models import (
    AIAsset,
    AIInteraction,
    Connection,
    Run,
    RunStatus,
)
from app.models import PrincipalType


async def run_monitoring(
    db: Session, connection: Connection, since: datetime | None = None
) -> Run:
    run = Run(connection_id=connection.id, run_type="monitoring")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        connector, using_fallback = effective_connector(
            connection.connector_type, connection.config
        )
        result = await connector.monitor(since)

        # Index existing assets for fast linking.
        assets = db.execute(select(AIAsset)).scalars().all()
        asset_index = {
            (a.saas_platform, a.ai_capability): a.id for a in assets
        }

        for inter in result.interactions:
            asset_id = None
            keys = inter.asset_keys or {}
            plat = keys.get("saas_platform")
            cap = keys.get("ai_capability")
            if plat and cap:
                asset_id = asset_index.get((plat, cap))

            if _exists(db, connection.id, inter):
                continue

            db.add(
                AIInteraction(
                    asset_id=asset_id,
                    connection_id=connection.id,
                    user_email=inter.user_email,
                    user_display_name=inter.user_display_name,
                    principal_type=(
                        PrincipalType(inter.principal_type)
                        if inter.principal_type
                        else None
                    ),
                    saas_application=inter.saas_application,
                    ai_feature=inter.ai_feature,
                    model=inter.model,
                    model_available=inter.model_available,
                    timestamp=inter.timestamp or datetime.now(timezone.utc),
                    request_info=inter.request_info,
                    request_available=inter.request_available,
                    response_info=inter.response_info,
                    response_available=inter.response_available,
                    token_usage=inter.token_usage,
                    usage_available=inter.usage_available,
                    source=inter.source,
                    visibility_note=inter.visibility_note,
                    raw_event=inter.raw_event,
                )
            )
            run.interactions_found += 1

        connection.last_run_at = datetime.now(timezone.utc)
        run.status = RunStatus.SUCCESS
        run.summary = {
            "using_fallback": using_fallback,
            "notes": result.notes,
        }
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run.status = RunStatus.FAILED
        run.error = str(exc)
        db.commit()
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
    return run


def _exists(db: Session, connection_id: str, inter) -> bool:
    stmt = select(AIInteraction).where(
        AIInteraction.connection_id == connection_id,
        AIInteraction.user_email == inter.user_email,
        AIInteraction.saas_application == inter.saas_application,
        AIInteraction.timestamp == (inter.timestamp or None),
        AIInteraction.source == inter.source,
    )
    return db.execute(stmt).first() is not None
