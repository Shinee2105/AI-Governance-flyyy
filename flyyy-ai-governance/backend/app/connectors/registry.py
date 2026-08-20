"""
Connector registry.

Maps a connector type string to its implementation and provides the ``get_connector``
helper that the orchestrator uses. When a connector reports ``is_configured() ==
False`` (e.g. Salesforce without credentials), the orchestrator transparently
falls back to the :class:`DemoConnector` so the application remains fully runnable.
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

    If the requested connector is not configured, fall back to the demo
    connector and flag it so callers can label results accordingly.
    """
    requested = build_connector(connector_type, config)
    if requested.is_configured():
        return requested, False
    return DemoConnector(config), True
