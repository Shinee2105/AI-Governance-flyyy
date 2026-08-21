"""
SQLAlchemy ORM models. Every monitoring field carries a *_available boolean
so the UI can distinguish observed evidence from platform limitations.
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
    Index,
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


class CapabilityStatus(str, PyEnum):
    """Precise enablement state derived from evidence."""

    LICENSED = "Licensed"
    ENABLED = "Enabled"
    DISABLED = "Disabled"
    UNKNOWN = "Unknown"
    NOT_OBSERVABLE = "Not Observable"


class AccessType(str, PyEnum):
    """How a principal's access was established."""

    DIRECT_LICENSE = "Direct (license assigned to user)"
    GROUP_LICENSE = "Group (license assigned to group)"
    UNKNOWN = "Unknown"
    NOT_OBSERVABLE = "Not Observable"


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


class Connection(Base):
    """A configured SaaS environment."""

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus), default=ConnectorStatus.NOT_CONFIGURED
    )
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    assets: Mapped[list["AIAsset"]] = relationship(back_populates="connection")
    runs: Mapped[list["Run"]] = relationship(back_populates="connection")


class AIAsset(Base):
    """An AI capability discovered inside a SaaS environment."""

    __tablename__ = "ai_assets"
    __table_args__ = (Index("ix_ai_assets_connection", "connection_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    saas_platform: Mapped[str] = mapped_column(String(128), nullable=False)
    ai_capability: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    capability_status: Mapped[CapabilityStatus] = mapped_column(
        Enum(CapabilityStatus), default=CapabilityStatus.UNKNOWN
    )
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
    tenant_id: Mapped[str | None] = mapped_column(String(255))
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
    """A user or group with access to a discovered AI asset."""

    __tablename__ = "ai_asset_access"
    __table_args__ = (Index("ix_ai_asset_access_asset", "asset_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("ai_assets.id", ondelete="CASCADE")
    )
    principal_type: Mapped[PrincipalType] = mapped_column(Enum(PrincipalType))
    principal_id: Mapped[str | None] = mapped_column(String(255))
    principal_name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    access_type: Mapped[AccessType] = mapped_column(
        Enum(AccessType), default=AccessType.UNKNOWN
    )
    access_level: Mapped[str | None] = mapped_column(String(128))
    license_sku: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(255))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    asset: Mapped["AIAsset"] = relationship(back_populates="accesses")


class AIInteraction(Base):
    """A single observed AI interaction."""

    __tablename__ = "ai_interactions"
    __table_args__ = (
        Index("ix_ai_interactions_connection", "connection_id"),
        Index("ix_ai_interactions_asset", "asset_id"),
        Index("ix_ai_interactions_timestamp", "timestamp"),
        Index(
            "ix_ai_interactions_ext_event",
            "connection_id",
            "external_event_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_assets.id", ondelete="SET NULL")
    )
    connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("connections.id", ondelete="SET NULL")
    )
    external_event_id: Mapped[str | None] = mapped_column(String(255))
    user_email: Mapped[str | None] = mapped_column(String(255))
    user_display_name: Mapped[str | None] = mapped_column(String(255))
    principal_type: Mapped[PrincipalType | None] = mapped_column(
        Enum(PrincipalType)
    )
    saas_application: Mapped[str | None] = mapped_column(String(128))
    ai_feature: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(128))
    model_available: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    request_info: Mapped[str | None] = mapped_column(Text)
    request_available: Mapped[bool] = mapped_column(Boolean, default=False)
    response_info: Mapped[str | None] = mapped_column(Text)
    response_available: Mapped[bool] = mapped_column(Boolean, default=False)
    token_usage: Mapped[dict | None] = mapped_column(JSON)
    usage_available: Mapped[bool] = mapped_column(Boolean, default=False)
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
    run_type: Mapped[str] = mapped_column(String(32))
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


def _count(session, model) -> int:
    return int(session.query(func.count(model.id)).scalar() or 0)
