"""
Application bootstrap.

On startup this module:
  * creates database tables (dev convenience; production should use migrations),
  * ensures a Demo connection and a placeholder Microsoft 365 connection exist,
  * if demo seeding is enabled and the inventory is empty, runs an initial
    discovery + monitoring pass so the UI is populated immediately.

In production you would replace the SQLite auto-create with Alembic migrations
and configure a real Microsoft 365 connector via environment variables.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIAsset, Connection
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

    # Placeholder for a real tenant — clearly NOT configured until credentials
    # are supplied via environment variables.
    m365 = db.execute(
        select(Connection).where(Connection.connector_type == "microsoft365")
    ).scalars().first()
    if m365 is None:
        m365 = Connection(
            name="Microsoft 365 (configure me)",
            platform="Microsoft 365",
            connector_type="microsoft365",
            status="Not Configured",
            config={"note": "Provide MS365_* env vars and set MS365_ENABLED=true"},
        )
        db.add(m365)
        db.commit()
        db.refresh(m365)
    return demo


async def bootstrap(db: Session, seed_demo: bool) -> None:
    demo = _ensure_connections(db)

    if not seed_demo:
        return

    has_assets = db.execute(select(AIAsset.id)).first() is not None
    if has_assets:
        return

    # Run an initial discovery + monitoring pass against the demo connector.
    await run_discovery(db, demo)
    await run_monitoring(db, demo, since=None)
