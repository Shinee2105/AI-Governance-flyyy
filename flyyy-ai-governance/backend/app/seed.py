"""
Application bootstrap. Creates database tables in development, ensures the
Demo connection exists, and optionally runs an initial discovery + monitoring
pass so the UI is populated immediately.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIAsset, AIAssetAccess, AIInteraction, Run, Connection
from app.services.discovery_service import run_discovery
from app.services.monitoring_service import run_monitoring


def _ensure_connections(db: Session) -> Connection:
    """Create the Demo connection if missing; return it."""
    demo = db.execute(
        select(Connection).where(Connection.connector_type == "demo")
    ).scalars().first()
    if demo is None:
        demo = Connection(
            name="Demo SaaS Environment (Contoso)",
            platform="Demo / Simulated",
            connector_type="demo",
            status="Configured",
            config={"simulated": True},
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

    sf = db.execute(
        select(Connection).where(Connection.connector_type == "salesforce")
    ).scalars().first()
    if sf is None:
        sf = Connection(
            name="Salesforce (configure me)",
            platform="Salesforce",
            connector_type="salesforce",
            status="Not Configured",
            config={"note": "Provide SFDC_* env vars and set SFDC_ENABLED=true"},
        )
        db.add(sf)
        db.commit()
        db.refresh(sf)
    return demo


async def bootstrap(db: Session, seed_demo: bool) -> None:
    demo = _ensure_connections(db)

    if not seed_demo:
        return

    has_assets = db.execute(select(AIAsset.id)).first() is not None
    if has_assets:
        return

    await run_discovery(demo)
    await run_monitoring(demo, since=None)
