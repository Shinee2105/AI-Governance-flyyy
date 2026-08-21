"""
Monitoring service. Runs connector.monitor() and persists AI interactions
linked to discovered assets. Uses asyncio.to_thread for DB writes. Provider
failures are recorded as FAILED runs.
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
    AIInteraction,
    Connection,
    PrincipalType,
    Run,
    RunStatus,
)


async def run_monitoring(connection: Connection, since=None) -> str:
    """Monitor and persist. Returns the created Run id."""
    connector, using_fallback = effective_connector(
        connection.connector_type, connection.config
    )
    try:
        result = await connector.monitor(since)
    except Exception as exc:
        return await asyncio.to_thread(
            _persist_failed, connection.id, "monitoring", _safe_err(exc)
        )
    try:
        out = await asyncio.to_thread(
            _persist_monitoring, connection.id, result, using_fallback
        )
        return out["run_id"]
    except Exception as exc:
        return await asyncio.to_thread(
            _persist_failed, connection.id, "monitoring", _safe_err(exc)
        )


def _persist_monitoring(connection_id: str, result, using_fallback: bool) -> dict:
    db: Session = SessionLocal()
    run = Run(connection_id=connection_id, run_type="monitoring")
    try:
        db.add(run)
        db.commit()
        db.refresh(run)

        assets = db.execute(select(AIAsset)).scalars().all()
        asset_index = {(a.saas_platform, a.ai_capability): a.id for a in assets}

        seen_ext_ids = set()

        for inter in result.interactions:
            asset_id = None
            keys = inter.asset_keys or {}
            plat = keys.get("saas_platform")
            cap = keys.get("ai_capability")
            if plat and cap:
                asset_id = asset_index.get((plat, cap))

            ext_id = inter.external_event_id
            if ext_id and (ext_id in seen_ext_ids or _exists(db, connection_id, ext_id, inter)):
                continue
            if ext_id:
                seen_ext_ids.add(ext_id)

            db.add(
                AIInteraction(
                    asset_id=asset_id,
                    connection_id=connection_id,
                    external_event_id=ext_id,
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

        conn = db.get(Connection, connection_id)
        if conn:
            conn.last_run_at = datetime.now(timezone.utc)

        diag = (result.metadata or {}).get("diagnostics")
        had_errors = bool(diag and diag.get("errors"))
        if run.interactions_found == 0 and had_errors:
            run.status = RunStatus.PARTIAL
        else:
            run.status = RunStatus.SUCCESS
        run.summary = {
            "using_fallback": using_fallback,
            "notes": result.notes,
            "interactions_normalized": run.interactions_found,
            "diagnostics": diag,
        }
        db.commit()
    except Exception as exc:
        db.rollback()
        run.status = RunStatus.FAILED
        run.error = _safe_err(exc)
        db.add(run)
        db.commit()
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        db.close()
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


def _exists(
    db: Session, connection_id: str, external_event_id: str | None, inter
) -> bool:
    """Return True if this event is already stored for the connection."""
    if external_event_id:
        stmt = select(AIInteraction).where(
            AIInteraction.connection_id == connection_id,
            AIInteraction.external_event_id == external_event_id,
        )
        return db.execute(stmt).first() is not None
    stmt = select(AIInteraction).where(
        AIInteraction.connection_id == connection_id,
        AIInteraction.user_email == inter.user_email,
        AIInteraction.saas_application == inter.saas_application,
        AIInteraction.timestamp == (inter.timestamp or None),
        AIInteraction.source == inter.source,
    )
    return db.execute(stmt).first() is not None


def _safe_err(exc: Exception) -> str:
    text = str(exc)
    import re

    text = re.sub(r"(client_secret=)[^&\s]+", r"\1<redacted>", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer <redacted>", text)
    return text[:500]
