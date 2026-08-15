"""
Microsoft 365 connector (Microsoft 365 Copilot).

Implements *real* evidence-based discovery and monitoring using:

  Discovery
  ---------
  * Microsoft Graph ``/subscribedSkus``            -> which Copilot license
    SKUs are active in the tenant (proof a capability exists).
  * Microsoft Graph ``/users`` (+ ``assignedLicenses``) -> which users/groups
    actually hold a Copilot license (proof of *who can use it*).

  Monitoring
  ----------
  * Office 365 Management Activity API (the unified audit log) -> Copilot
    interaction records (Operation ``CopilotInteraction`` / RecordType 305 and
    related). These provide *metadata* about the interaction (user, time,
    workload, operation) but **not** the prompt/response text or the model.

IMPORTANT — honest limitation
------------------------------
Microsoft 365 (like most SaaS platforms) does **not** expose the actual prompt
or response content, nor the underlying model name, through its audit APIs.
This connector therefore reports those fields as *not available* and attaches a
``visibility_note`` so the UI can display the limitation transparently. Where a
real tenant is configured, the connector performs the calls above; otherwise it
reports ``is_configured() == False`` and the orchestrator falls back to the
demonstration connector.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.connectors.base import (
    BaseConnector,
    Capabilities,
    DiscoveryResult,
    DiscoveredAccess,
    DiscoveredAsset,
    MonitoringResult,
    ObservedInteraction,
)
from app.models import PrincipalType

GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"
MANAGEMENT_ENDPOINT = "https://manage.office.com/api/v1.0"

# SKU part-numbers that indicate a Microsoft 365 Copilot entitlement.
COPILOT_SKU_FRAGMENTS = ("COPILOT", "COPILOT_FOR_MICROSOFT_365", "MICROSOFT_365_COPILOT")

# Audit content types that carry Microsoft 365 Copilot activity.
COPILOT_CONTENT_TYPES = [
    "Audit.General",
    "Audit.Exchange",
    "Audit.SharePoint",
    "Audit.AzureActiveDirectory",
]

COPYLOT_OPERATIONS = (
    "CopilotInteraction",
    "CopilotSummary",
    "CopilotEcopilotSession",
    "CopilotForSalesInteraction",
)


class Microsoft365Connector(BaseConnector):
    platform = "Microsoft 365"
    connector_type = "microsoft365"

    def __init__(self, connection_config: dict[str, Any] | None = None) -> None:
        super().__init__(connection_config)
        self._token_cache: dict[str, Any] | None = None
        self._mgmt_token_cache: dict[str, Any] | None = None

    # ------------------------------------------------------------------ config
    def is_configured(self) -> bool:
        return bool(
            settings.MS365_ENABLED
            and settings.MS365_TENANT_ID
            and settings.MS365_CLIENT_ID
            and settings.MS365_CLIENT_SECRET
        )

    # --------------------------------------------------------------- auth utils
    async def _get_token(self) -> str:
        """Acquire an app-only (client credentials) Graph token."""
        if self._token_cache and self._token_cache["expires"] > datetime.now(
            timezone.utc
        ):
            return self._token_cache["access_token"]
        url = (
            f"https://login.microsoftonline.com/"
            f"{settings.MS365_TENANT_ID}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.MS365_CLIENT_ID,
            "client_secret": settings.MS365_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        self._token_cache = {
            "access_token": payload["access_token"],
            "expires": datetime.now(timezone.utc)
            + timedelta(seconds=payload.get("expires_in", 3600)),
        }
        return payload["access_token"]

    async def _get_management_token(self) -> str:
        """Acquire a token for the Office 365 Management Activity API."""
        client_id = settings.MS365_MANAGEMENT_API_CLIENT_ID or settings.MS365_CLIENT_ID
        client_secret = (
            settings.MS365_MANAGEMENT_API_CLIENT_SECRET
            or settings.MS365_CLIENT_SECRET
        )
        if self._mgmt_token_cache and self._mgmt_token_cache["expires"] > (
            datetime.now(timezone.utc)
        ):
            return self._mgmt_token_cache["access_token"]
        url = (
            f"https://login.microsoftonline.com/"
            f"{settings.MS365_TENANT_ID}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://manage.office.com/.default",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        self._mgmt_token_cache = {
            "access_token": payload["access_token"],
            "expires": datetime.now(timezone.utc)
            + timedelta(seconds=payload.get("expires_in", 3600)),
        }
        return payload["access_token"]

    async def _graph_get(self, path: str, params: dict | None = None) -> dict:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GRAPH_ENDPOINT}{path}", headers=headers, params=params or {}
            )
            resp.raise_for_status()
            return resp.json()

    # --------------------------------------------------------------- discovery
    async def discover(self) -> DiscoveryResult:
        result = DiscoveryResult()
        notes: list[str] = []

        # 1) Find active Copilot license SKUs in the tenant.
        skus = await self._graph_get("/subscribedSkus")
        copilot_skus = [
            s
            for s in skus.get("value", [])
            if any(
                frag in (s.get("skuPartNumber") or "").upper()
                for frag in COPILOT_SKU_FRAGMENTS
            )
        ]
        if not copilot_skus:
            notes.append(
                "No Microsoft 365 Copilot license SKU found in subscribedSkus; "
                "Copilot capability appears not provisioned/licensed."
            )
            result.notes = notes
            return result

        copilot_sku_ids = {s["skuId"] for s in copilot_skus}
        license_label = ", ".join(
            s.get("skuPartNumber") for s in copilot_skus if s.get("skuPartNumber")
        )

        # 2) Enumerate users and find those holding a Copilot license.
        accesses: list[DiscoveredAccess] = []
        users = await self._graph_get(
            "/users",
            params={
                "$select": "id,displayName,mail,userPrincipalName,assignedLicenses"
            },
        )
        for u in users.get("value", []):
            assigned = {
                lic.get("skuId")
                for lic in u.get("assignedLicenses", [])
                if lic.get("skuId")
            }
            held = assigned & copilot_sku_ids
            if held:
                accesses.append(
                    DiscoveredAccess(
                        principal_type=PrincipalType.USER.value,
                        principal_id=u.get("id"),
                        principal_name=u.get("userPrincipalName"),
                        display_name=u.get("displayName"),
                        email=u.get("mail") or u.get("userPrincipalName"),
                        access_level="Licensed",
                        license_sku=license_label,
                        source="Microsoft Graph — user.assignedLicenses",
                    )
                )

        # 3) Build the AI asset for Microsoft 365 Copilot.
        asset = DiscoveredAsset(
            name="Microsoft 365 Copilot",
            asset_type="SaaS AI Feature",
            provider="Microsoft",
            saas_platform="Microsoft 365",
            ai_capability="Copilot for Microsoft 365",
            enabled=True,
            purpose=(
                "Generative AI assistant embedded across Microsoft 365 "
                "(Word, Excel, PowerPoint, Outlook, Teams, SharePoint) that can "
                "summarise, draft, search organisational knowledge and reason "
                "over business data."
            ),
            accessible_resources=[
                "SharePoint",
                "OneDrive",
                "Outlook",
                "Teams",
                "Word",
                "Excel",
                "PowerPoint",
            ],
            discovery_source=(
                "Microsoft Graph — subscribedSkus & user.assignedLicenses"
            ),
            monitoring_status="Partial Visibility",
            metadata={
                "license_skus": [s.get("skuPartNumber") for s in copilot_skus],
                "capability_evidence": "License assignment present in tenant",
            },
            tenant_id=settings.MS365_TENANT_ID,
        )
        result.assets.append(asset)
        result.accesses[asset.name] = accesses
        notes.append(
            f"Discovered {len(accesses)} user(s) licensed for Microsoft 365 "
            f"Copilot via SKU(s): {license_label}."
        )
        result.notes = notes
        return result

    # --------------------------------------------------------------- monitoring
    async def monitor(self, since: datetime | None = None) -> MonitoringResult:
        result = MonitoringResult()
        notes: list[str] = []
        token = await self._get_management_token()
        tenant = settings.MS365_TENANT_ID
        headers = {"Authorization": f"Bearer {token}"}

        start = (since or datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        async with httpx.AsyncClient(timeout=60) as client:
            # Start/ensure subscriptions for the relevant content types.
            for ctype in COPILOT_CONTENT_TYPES:
                try:
                    await client.post(
                        f"{MANAGEMENT_ENDPOINT}/{tenant}/activity/feed/"
                        f"subscriptions/start?contentType={ctype}",
                        headers=headers,
                    )
                except httpx.HTTPError:
                    # Subscription may already be active; non-fatal.
                    pass

            # Pull content URIs and fetch each blob.
            for ctype in COPILOT_CONTENT_TYPES:
                content = await client.get(
                    f"{MANAGEMENT_ENDPOINT}/{tenant}/activity/feed/subscriptions/"
                    f"content?contentType={ctype}&startTime={start}&endTime={end}",
                    headers=headers,
                )
                if content.status_code != 200:
                    continue
                for item in content.json():
                    blob_url = item.get("contentUri")
                    if not blob_url:
                        continue
                    blob = await client.get(blob_url, headers=headers)
                    if blob.status_code != 200:
                        continue
                    for record in blob.json():
                        if not self._is_copilot_record(record):
                            continue
                        result.interactions.append(
                            self._map_record(record)
                        )

        notes.append(
            "Microsoft 365 audit logs expose Copilot *activity metadata* "
            "(user, workload, operation, time) but NOT the prompt, response, "
            "model name, or token usage. These fields are reported as not "
            "available by design."
        )
        result.notes = notes
        return result

    @staticmethod
    def _is_copilot_record(record: dict) -> bool:
        operation = (record.get("Operation") or "").lower()
        record_type = record.get("RecordType")
        return operation in [o.lower() for o in COPYLOT_OPERATIONS] or (
            record_type in (305, 309)
        )

    @staticmethod
    def _map_record(record: dict) -> ObservedInteraction:
        raw_time = record.get("CreationTime")
        try:
            ts = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            ts = datetime.now(timezone.utc)
        return ObservedInteraction(
            user_email=record.get("UserId"),
            user_display_name=record.get("UserId"),
            principal_type=PrincipalType.USER.value,
            saas_application=record.get("Workload") or record.get("AppName"),
            ai_feature="Copilot",
            model=None,
            model_available=False,
            timestamp=ts,
            request_info=None,
            request_available=False,
            response_info=None,
            response_available=False,
            token_usage=None,
            usage_available=False,
            source="Office 365 Management Activity API (unified audit log)",
            visibility_note=(
                "Prompt/response content and model are not exposed by the "
                "Microsoft 365 audit log; only interaction metadata is available."
            ),
            raw_event=record,
            asset_keys={
                "saas_platform": "Microsoft 365",
                "ai_capability": "Copilot for Microsoft 365",
            },
        )

    # --------------------------------------------------------------- capabilities
    def capabilities(self) -> Capabilities:
        return Capabilities(
            platform="Microsoft 365",
            discovery=[
                "AI capability presence (via Copilot license SKUs)",
                "Enabled status (license assigned in tenant)",
                "Users/groups with access (assignedLicenses reconciliation)",
                "Relevant license / entitlement (skuPartNumber)",
                "Associated Microsoft 365 workloads (SharePoint, Teams, ...)",
            ],
            monitoring=[
                "Identity generating the interaction (UserId)",
                "SaaS application / workload (Workload)",
                "Time of interaction (CreationTime)",
                "AI feature / operation (Operation / RecordType 305)",
            ],
            not_exposed=[
                "Prompt / request content",
                "Response content",
                "Underlying LLM model name",
                "Token or usage counts",
            ],
        )
