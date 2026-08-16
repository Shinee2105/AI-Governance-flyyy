"""
Microsoft 365 connector (Microsoft 365 Copilot).

Implements *real* evidence-based discovery and monitoring using:

  Discovery
  ---------
  * Microsoft Graph ``/subscribedSkus``            -> which Copilot license
    SKUs are active in the tenant (proof a capability exists).
  * Microsoft Graph ``/users`` (+ ``assignedLicenses``) -> users with a Copilot
    license assigned *directly* (proof of *who can use it* — DIRECT access).
  * Microsoft Graph ``/groups`` (filtered by assigned Copilot SKU) +
    ``transitiveMembers`` -> users who can use Copilot because a *group* they
    belong to is licensed (GROUP access, including nested groups).

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

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

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
from app.models import AccessType, CapabilityStatus, PrincipalType

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

# Hard upper bound on pagination iterations to avoid any runaway loop.
MAX_PAGES = 100


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

    async def _graph_paged(
        self, path: str, params: dict | None = None
    ) -> AsyncIterator[dict]:
        """Yield every item across all ``@odata.nextLink`` pages.

        Handles empty pages, missing/``null`` nextLink, and caps iteration count
        to guarantee termination. Raises on HTTP errors so callers can decide
        whether a failure is fatal or partial.
        """
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{GRAPH_ENDPOINT}{path}"
        page = 0
        async with httpx.AsyncClient(timeout=60) as client:
            while url and page < MAX_PAGES:
                page += 1
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                # First iteration used `params`; subsequent use the full nextLink.
                params = None
                for item in data.get("value", []):
                    yield item
                url = data.get("@odata.nextLink")
            if page >= MAX_PAGES:
                # Defensive: stop paginating but do not silently drop data.
                raise RuntimeError(
                    "Pagination exceeded MAX_PAGES; aborting to avoid runaway loop."
                )

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

        accesses: list[DiscoveredAccess] = []
        seen: set[tuple[str | None, str]] = set()  # (principal_id, access_type)

        # 2a) Direct license assignment (users with the SKU assigned to them).
        try:
            async for u in self._graph_paged(
                "/users",
                params={
                    "$select": "id,displayName,mail,userPrincipalName,assignedLicenses"
                },
            ):
                assigned = {
                    lic.get("skuId")
                    for lic in u.get("assignedLicenses", [])
                    if lic.get("skuId")
                }
                if assigned & copilot_sku_ids:
                    key = (u.get("id"), AccessType.DIRECT_LICENSE.value)
                    if key in seen:
                        continue
                    seen.add(key)
                    accesses.append(
                        DiscoveredAccess(
                            principal_type=PrincipalType.USER.value,
                            principal_id=u.get("id"),
                            principal_name=u.get("userPrincipalName"),
                            display_name=u.get("displayName"),
                            email=u.get("mail") or u.get("userPrincipalName"),
                            access_type=AccessType.DIRECT_LICENSE.value,
                            access_level="Licensed (direct)",
                            license_sku=license_label,
                            source="Microsoft Graph — user.assignedLicenses",
                        )
                    )
        except httpx.HTTPError as exc:
            notes.append(
                f"Direct license enumeration failed: {_safe_err(exc)}. "
                "Discovery is partial."
            )

        # 2b) Group-based licensing: groups assigned the SKU, expanded to their
        # (transitive) member users. Handles nested groups via transitiveMembers.
        group_count = 0
        try:
            sku_filter = " or ".join(
                f"assignedLicenses/any(s:s/skuId eq '{sid}')"
                for sid in copilot_sku_ids
            )
            async for grp in self._graph_paged(
                "/groups",
                params={"$filter": sku_filter, "$select": "id,displayName,mail"},
            ):
                group_count += 1
                gsrc = (
                    f"Microsoft Graph — group '{grp.get('displayName')}' "
                    "license (transitiveMembers)"
                )
                try:
                    async for member in self._graph_paged(
                        f"/groups/{grp['id']}/transitiveMembers/microsoft.graph.user",
                        params={
                            "$select": "id,displayName,mail,userPrincipalName"
                        },
                    ):
                        key = (member.get("id"), AccessType.GROUP_LICENSE.value)
                        if key in seen:
                            continue
                        seen.add(key)
                        accesses.append(
                            DiscoveredAccess(
                                principal_type=PrincipalType.USER.value,
                                principal_id=member.get("id"),
                                principal_name=member.get("userPrincipalName"),
                                display_name=member.get("displayName"),
                                email=member.get("mail")
                                or member.get("userPrincipalName"),
                                access_type=AccessType.GROUP_LICENSE.value,
                                access_level="Licensed (via group)",
                                license_sku=license_label,
                                source=gsrc,
                            )
                        )
                except httpx.HTTPError as exc:
                    notes.append(
                        f"Group member expansion failed for "
                        f"'{grp.get('displayName')}': {_safe_err(exc)}."
                    )
        except httpx.HTTPError as exc:
            notes.append(
                f"Group-based license discovery failed: {_safe_err(exc)}. "
                "Direct-license access is still reported where available."
            )

        # 3) Build the AI asset for Microsoft 365 Copilot.
        # We can prove the capability is *provisioned/licensed* (LICENSED), not
        # that an independent "enabled" toggle is on — so we record LICENSED
        # rather than over-claiming ENABLED.
        asset = DiscoveredAsset(
            name="Microsoft 365 Copilot",
            asset_type="SaaS AI Feature",
            provider="Microsoft",
            saas_platform="Microsoft 365",
            ai_capability="Copilot for Microsoft 365",
            enabled=True,
            capability_status=CapabilityStatus.LICENSED.value,
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
                "Microsoft Graph — subscribedSkus, user.assignedLicenses, "
                "group license (transitiveMembers)"
            ),
            monitoring_status="Partial Visibility",
            metadata={
                "license_skus": [s.get("skuPartNumber") for s in copilot_skus],
                "capability_evidence": "License assignment present in tenant",
                "groups_with_license": group_count,
            },
            tenant_id=settings.MS365_TENANT_ID,
        )
        result.assets.append(asset)
        result.accesses[asset.name] = accesses
        notes.append(
            f"Discovered {len(accesses)} user(s) with Microsoft 365 Copilot "
            f"access via SKU(s): {license_label} "
            f"({group_count} licensed group(s) resolved)."
        )
        notes.append(
            "Capability recorded as LICENSED (license evidence), not an "
            "unverified ENABLED state."
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

        diag = {
            "window_start": start,
            "window_end": end,
            "subscriptions": {},
            "content_types_requested": 0,
            "content_retrieved": 0,
            "content_failed": 0,
            "relevant_records": 0,
            "normalized_interactions": 0,
            "skipped_records": 0,
            "errors": [],
        }

        async with httpx.AsyncClient(timeout=60) as client:
            # Start/ensure subscriptions for the relevant content types.
            for ctype in COPILOT_CONTENT_TYPES:
                try:
                    resp = await client.post(
                        f"{MANAGEMENT_ENDPOINT}/{tenant}/activity/feed/"
                        f"subscriptions/start?contentType={ctype}",
                        headers=headers,
                    )
                    diag["subscriptions"][ctype] = (
                        "enabled" if resp.status_code in (200, 201) else f"http_{resp.status_code}"
                    )
                except httpx.HTTPError as exc:
                    diag["subscriptions"][ctype] = f"error: {_safe_err(exc)}"
                    diag["errors"].append(f"subscription {ctype}: {_safe_err(exc)}")

            # Pull content URIs and fetch each blob.
            for ctype in COPILOT_CONTENT_TYPES:
                diag["content_types_requested"] += 1
                try:
                    content = await client.get(
                        f"{MANAGEMENT_ENDPOINT}/{tenant}/activity/feed/subscriptions/"
                        f"content?contentType={ctype}&startTime={start}&endTime={end}",
                        headers=headers,
                    )
                except httpx.HTTPError as exc:
                    diag["content_failed"] += 1
                    diag["errors"].append(f"content {ctype}: {_safe_err(exc)}")
                    continue

                if content.status_code != 200:
                    # No content available yet is NORMAL (ingestion delay); not an error.
                    if content.status_code == 404:
                        diag["content_retrieved"] += 0
                    else:
                        diag["content_failed"] += 1
                        diag["errors"].append(
                            f"content {ctype}: http_{content.status_code}"
                        )
                    continue

                items = content.json()
                if not items:
                    # Expected when the audit feed has not ingested events yet.
                    continue
                diag["content_retrieved"] += 1

                for item in items:
                    blob_url = item.get("contentUri")
                    if not blob_url:
                        continue
                    try:
                        blob = await client.get(blob_url, headers=headers)
                        blob.raise_for_status()
                    except httpx.HTTPError as exc:
                        diag["errors"].append(f"blob: {_safe_err(exc)}")
                        continue
                    for record in blob.json():
                        if not self._is_copilot_record(record):
                            diag["skipped_records"] += 1
                            continue
                        diag["relevant_records"] += 1
                        inter = self._map_record(record)
                        if inter is not None:
                            result.interactions.append(inter)
                            diag["normalized_interactions"] += 1

        if diag["normalized_interactions"] == 0:
            notes.append(
                "Completed — no currently available matching Copilot events in "
                "the requested window. This does NOT mean no Copilot usage "
                "exists; the Office 365 audit feed has an ingestion delay and "
                "may not yet expose the most recent activity."
            )
        else:
            notes.append(
                "Microsoft 365 audit logs expose Copilot *activity metadata* "
                "(user, workload, operation, time) but NOT the prompt, response, "
                "model name, or token usage. These fields are reported as not "
                "available by design."
            )
        result.notes = notes
        # Stash diagnostics on the result so the service can record them on the Run.
        result.metadata = {"diagnostics": diag}
        return result

    @staticmethod
    def _is_copilot_record(record: dict) -> bool:
        operation = (record.get("Operation") or "").lower()
        record_type = record.get("RecordType")
        return operation in [o.lower() for o in COPYLOT_OPERATIONS] or (
            record_type in (305, 309)
        )

    def _map_record(self, record: dict) -> ObservedInteraction | None:
        raw_time = record.get("CreationTime")
        ts = datetime.now(timezone.utc)
        if raw_time:
            try:
                ts = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                ts = datetime.now(timezone.utc)
        external_id = _stable_event_id(record)
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
            external_event_id=external_id,
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
                "AI capability presence (via Copilot license SKUs in subscribedSkus)",
                "Enabled/provisioned status (LICENSED via license assignment)",
                "Direct user access (user.assignedLicenses reconciliation)",
                "Group-based access (group license + transitiveMembers, nested groups)",
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


def _safe_err(exc: Exception) -> str:
    """Return an error string with any embedded secrets/headers redacted."""
    text = str(exc)
    # Remove anything that looks like a token/secret.
    import re

    text = re.sub(r"(client_secret=)[^&\s]+", r"\1<redacted>", text)
    text = re.sub(r"(access_token)[=:\s]+[A-Za-z0-9._-]+", r"\1=<redacted>", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer <redacted>", text)
    return text[:300]


def _stable_event_id(record: dict) -> str:
    """Build a deterministic external event id.

    Prefers the provider's own ``Id`` GUID when present; otherwise derives a
    stable fingerprint from the record's identifying fields so duplicate
    monitoring runs do not create duplicate interaction rows.
    """
    provider_id = record.get("Id")
    if provider_id:
        return f"o365:{provider_id}"
    fp = "|".join(
        str(record.get(k))
        for k in ("UserId", "RecordType", "CreationTime", "Operation", "Workload", "Id")
    )
    return "o365:fp:" + hashlib.sha256(fp.encode("utf-8")).hexdigest()
