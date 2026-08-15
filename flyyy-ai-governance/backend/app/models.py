"""
SQLAlchemy ORM models for the SaaS AI governance platform.

The schema is intentionally explicit about *visibility*: every monitoring
field that a SaaS platform may withhold (prompt/response content, model,
token usage) carries a companion ``*_available`` boolean so the UI can
honestly distinguish observed evidence from platform limitations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AssetStatus(str, PyEnum):
    DISCOVERED_PENDING_REVIEW = "Discovered / Pending Review"
    ENABLED = "Enabled"
    DISABLED = "Disabled"
    REVIEWED = "Reviewed"


class ReviewStatus(str, PyEnum):
    PENDING = "Pending"
    IN_REVIEW = "In Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class MonitoringStatus(str, PyEnum):
    NOT_MONITORED = "Not Monitored"
    MONITORING = "Monitoring"
    PARTIAL = "Partial Visibility"
    LIMITED = "Limited Visibility"
    NOT_AVAILABLE = "Not Available"


class PrincipalType(str, PyEnum):
    USER = "User"
    GROUP = "Group"


class ConnectorStatus(str, PyEnum):
    CONFIGURED = "Configured"
    NOT_CONFIGURED = "Not Configured"
    CONNECTED = "Connected"
    ERROR = "Error"


class RunStatus(str, PyEnum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"
    RUNNING = "Running"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Connection(Base):
    """A configured SaaS environment / connector instance."""

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus), default=ConnectorStatus.NOT_CONFIGURED
    )
    # Non-secret configuration metadata only (tenant name, org id, etc.).
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    assets: Mapped[list["AIAsset"]] = relationship(back_populates="connection")
    runs: Mapped[list["Run"]] = relationship(back_populates="connection")


class AIAsset(Base):
    """An AI capability discovered inside a SaaS environment (the inventory)."""

    __tablename__ = "ai_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    # --- Core inventory fields (spec: AI Asset Inventory) ---
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    saas_platform: Mapped[str] = mapped_column(String(128), nullable=False)
    ai_capability: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus), default=AssetStatus.DISCOVERED_PENDING_REVIEW
    )
    purpose: Mapped[str | None] = mapped_column(Text)
    accessible_resources: Mapped[list] = mapped_column(JSON, default=list)
    discovery_source: Mapped[str | None] = mapped_column(String(255))
    monitoring_status: Mapped[MonitoringStatus] = mapped_column(
        Enum(MonitoringStatus), default=MonitoringStatus.NOT_MONITORED
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.PENDING
    )
    # Tenant / workspace identifier the asset belongs to.
    tenant_id: Mapped[str | None] = mapped_column(String(255))
    # Any additional evidence / metadata gathered during discovery.
    evidence: Mapped[dict] = mapped_column("evidence", JSON, default=dict)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    connection: Mapped["Connection | None"] = relationship(back_populates="assets")
    accesses: Mapped[list["AIAssetAccess"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["AIInteraction"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class AIAssetAccess(Base):
    """A user or group that has access to a discovered AI asset (evidence)."""

    __tablename__ = "ai_asset_access"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("ai_assets.id", ondelete="CASCADE")
    )
    principal_type: Mapped[PrincipalType] = mapped_column(Enum(PrincipalType))
    principal_id: Mapped[str | None] = mapped_column(String(255))
    principal_name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    access_level: Mapped[str | None] = mapped_column(String(128))
    license_sku: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(255))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    asset: Mapped["AIAsset"] = relationship(back_populates="accesses")


class AIInteraction(Base):
    """A single observed AI interaction (monitoring component)."""

    __tablename__ = "ai_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_assets.id", ondelete="SET NULL")
    )
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    # --- Identity / context ---
    user_email: Mapped[str | None] = mapped_column(String(255))
    user_display_name: Mapped[str | None] = mapped_column(String(255))
    principal_type: Mapped[PrincipalType | None] = mapped_column(
        Enum(PrincipalType)
    )
    saas_application: Mapped[str | None] = mapped_column(String(128))
    ai_feature: Mapped[str | None] = mapped_column(String(128))
    # --- Model (often NOT exposed by SaaS platforms) ---
    model: Mapped[str | None] = mapped_column(String(128))
    model_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # --- Timing ---
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    # --- Request / response content (often NOT exposed) ---
    request_info: Mapped[str | None] = mapped_column(Text)
    request_available: Mapped[bool] = mapped_column(Boolean, default=False)
    response_info: Mapped[str | None] = mapped_column(Text)
    response_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # --- Usage / tokens (sometimes exposed) ---
    token_usage: Mapped[dict | None] = mapped_column(JSON)
    usage_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # --- Provenance & honesty ---
    source: Mapped[str | None] = mapped_column(String(255))
    visibility_note: Mapped[str | None] = mapped_column(Text)
    raw_event: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    asset: Mapped["AIAsset | None"] = relationship(back_populates="interactions")
    connection: Mapped["Connection | None"] = relationship()


class Run(Base):
    """Audit record of a discovery or monitoring execution."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    run_type: Mapped[str] = mapped_column(String(32))  # "discovery" | "monitoring"
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    assets_found: Mapped[int] = mapped_column(Integer, default=0)
    accesses_found: Mapped[int] = mapped_column(Integer, default=0)
    interactions_found: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    connection: Mapped["Connection | None"] = relationship(back_populates="runs")


# Convenience aggregate counts used by the dashboard.
def _count(session, model) -> int:
    return int(session.query(func.count(model.id)).scalar() or 0)
