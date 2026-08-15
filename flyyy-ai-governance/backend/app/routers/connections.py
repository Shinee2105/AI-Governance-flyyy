"""Connections (SaaS connectors) API — configuration, discovery & monitoring."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.registry import (
    available_connector_types,
    build_connector,
)
from app.database import get_db
from app.models import Connection, Run, RunStatus
from app.schemas import ConnectionCreate, ConnectionOut, RunOut
from app.security import get_current_user
from app.services.discovery_service import run_discovery
from app.services.monitoring_service import run_monitoring

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/types", response_model=list[str])
def list_connector_types():
    return available_connector_types()


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Connection).order_by(Connection.created_at.desc())
    ).scalars().all()
    return [ConnectionOut.model_validate(c).model_dump() for c in rows]


@router.post("", response_model=ConnectionOut)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    # Validate the connector type is known.
    build_connector(payload.connector_type, payload.config)
    conn = Connection(
        name=payload.name,
        platform=payload.platform,
        connector_type=payload.connector_type,
        config=payload.config,
        status="Not Configured",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return ConnectionOut.model_validate(conn).model_dump()


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ConnectionOut.model_validate(conn).model_dump()


@router.get("/{connection_id}/capabilities", response_model=dict)
def connection_capabilities(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    connector = build_connector(conn.connector_type, conn.config)
    caps = connector.capabilities()
    return {
        "platform": caps.platform,
        "configured": connector.is_configured(),
        "discovery": caps.discovery,
        "monitoring": caps.monitoring,
        "not_exposed": caps.not_exposed,
    }


@router.get("/{connection_id}/runs", response_model=list[RunOut])
def connection_runs(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    runs = db.execute(
        select(Run)
        .where(Run.connection_id == connection_id)
        .order_by(Run.started_at.desc())
    ).scalars().all()
    return [RunOut.model_validate(r).model_dump() for r in runs]


@router.post("/{connection_id}/discover", response_model=RunOut)
async def trigger_discovery(
    connection_id: str,
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    run = await run_discovery(db, conn)
    return RunOut.model_validate(run).model_dump()


@router.post("/{connection_id}/monitor", response_model=RunOut)
async def trigger_monitoring(
    connection_id: str,
    db: Session = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    conn = db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    run = await run_monitoring(db, conn, since=None)
    return RunOut.model_validate(run).model_dump()
