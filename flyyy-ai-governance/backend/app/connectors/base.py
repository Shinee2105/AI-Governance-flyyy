"""
Connector framework.

A *connector* is the pluggable adapter that talks to a specific SaaS platform.
Every connector must be able to:

  1. ``discover()``  — find AI capabilities, whether enabled, and who can use
     them (the *discovery* objective of the challenge).
  2. ``monitor()``   — observe AI interactions (requests/responses sent to the
     underlying LLM) where the platform exposes them (the *monitoring*
     objective).
  3. ``capabilities()`` — honestly declare what evidence the platform actually
     exposes, so the UI can distinguish observed data from platform limits.

The framework deliberately models *visibility* as first-class: connectors
report ``model_available``, ``request_available``, ``response_available`` and
``usage_available`` flags rather than silently returning empty strings.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DiscoveredAsset:
    """Normalised representation of a discovered AI capability."""

    name: str
    asset_type: str
    provider: str
    saas_platform: str
    ai_capability: str
    enabled: bool
    # Precise enablement evidence (LICENSED / ENABLED / UNKNOWN / ...).
    capability_status: str = "Unknown"
    purpose: str | None = None
    accessible_resources: list[str] = field(default_factory=list)
    discovery_source: str | None = None
    monitoring_status: str = "Not Monitored"
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None


@dataclass
class DiscoveredAccess:
    """A user or group that can use a discovered AI capability."""

    principal_type: str  # "User" | "Group"
    principal_id: str | None = None
    principal_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    # How access was established (Direct license / Group license / Unknown).
    access_type: str | None = None
    access_level: str | None = None
    license_sku: str | None = None
    source: str | None = None


@dataclass
class ObservedInteraction:
    """A single observed AI interaction (monitoring evidence)."""

    # Identity / context
    user_email: str | None = None
    user_display_name: str | None = None
    principal_type: str | None = None
    saas_application: str | None = None
    ai_feature: str | None = None
    # Model — frequently NOT exposed by the platform.
    model: str | None = None
    model_available: bool = False
    # Timing
    timestamp: datetime | None = None
    # Request / response content — frequently NOT exposed.
    request_info: str | None = None
    request_available: bool = False
    response_info: str | None = None
    response_available: bool = False
    # Token / usage — sometimes exposed.
    token_usage: dict[str, Any] | None = None
    usage_available: bool = False
    # Provenance
    source: str | None = None
    visibility_note: str | None = None
    raw_event: dict[str, Any] | None = None
    # Stable external event id (for idempotent monitoring) or None.
    external_event_id: str | None = None
    # Keys used to link the interaction back to a discovered asset.
    asset_keys: dict[str, str] = field(default_factory=dict)


@dataclass
class Capabilities:
    """Honest description of what the connector can observe."""

    platform: str
    discovery: list[str]
    monitoring: list[str]
    not_exposed: list[str]


@dataclass
class DiscoveryResult:
    assets: list[DiscoveredAsset] = field(default_factory=list)
    accesses: dict[str, list[DiscoveredAccess]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringResult:
    interactions: list[ObservedInteraction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseConnector(abc.ABC):
    """Abstract base for all SaaS connectors."""

    #: Human readable platform name, e.g. "Microsoft 365".
    platform: str = "unknown"
    #: Short connector type key used in the DB, e.g. "microsoft365".
    connector_type: str = "unknown"

    def __init__(self, connection_config: dict[str, Any] | None = None) -> None:
        self.config = connection_config or {}

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Return True if the connector has the credentials it needs."""

    @abc.abstractmethod
    async def discover(self) -> DiscoveryResult:
        """Discover AI capabilities and their access."""

    @abc.abstractmethod
    async def monitor(self, since: datetime | None = None) -> MonitoringResult:
        """Observe AI interactions since ``since`` (if the platform allows)."""

    @abc.abstractmethod
    def capabilities(self) -> Capabilities:
        """Declare what the platform exposes vs. withholds."""
