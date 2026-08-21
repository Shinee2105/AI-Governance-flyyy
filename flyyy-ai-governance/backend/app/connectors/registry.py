"""
Connector registry. Maps a connector type string to its implementation and
provides ``effective_connector()``, which falls back to the demo connector
when the requested connector is not configured.
"""

from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.demo import DemoConnector
from app.connectors.salesforce import SalesforceConnector

_REGISTRY: dict[str, type[BaseConnector]] = {
    "salesforce": SalesforceConnector,
    "demo": DemoConnector,
}


def available_connector_types() -> list[str]:
    return list(_REGISTRY.keys())


def build_connector(connector_type: str, config: dict | None = None) -> BaseConnector:
    cls = _REGISTRY.get(connector_type, DemoConnector)
    return cls(config)


def effective_connector(
    connector_type: str, config: dict | None = None
) -> tuple[BaseConnector, bool]:
    """Return (connector, using_fallback).

    Falls back to the demo connector if the requested connector is not
    configured, and flags it so callers can label results accordingly.
    """
    requested = build_connector(connector_type, config)
    if requested.is_configured():
        return requested, False
    return DemoConnector(config), True
