
"""
Salesforce Agentforce connector.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

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

MAX_USERS = 500
MAX_CONCURRENT_SESSIONS = 5

class SalesforceConnector(BaseConnector):
    platform = "Salesforce"
    connector_type = "salesforce"

    def __init__(self, connection_config=None):
        super().__init__(connection_config)
        self._client = None

    def is_configured(self):
        from app.config import settings
        return bool(
            settings.SFDC_ENABLED
            and settings.SFDC_DOMAIN
            and settings.SFDC_CLIENT_ID
            and settings.SFDC_CLIENT_SECRET
        )

    def _get_config(self):
        from app.config import settings
        env_cfg = {
            "domain": settings.SFDC_DOMAIN,
            "client_id": settings.SFDC_CLIENT_ID,
            "client_secret": settings.SFDC_CLIENT_SECRET,
            "version": settings.SFDC_API_VERSION,
        }
        return {**env_cfg, **(self.config or {})}

    def _get_client(self):
        if self._client is None:
            from app.connectors.salesforce_client import SalesforceClient
            cfg = self._get_config()
            self._client = SalesforceClient(
                domain=cfg["domain"],
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                version=cfg.get("version", "62.0"),
            )
        return self._client

    async def discover(self):
        result = DiscoveryResult()
        notes = []
        client = self._get_client()
        cfg = self._get_config()

        bot_soql = (
            "SELECT Id, MasterLabel, DeveloperName, BotUserId, Type, AgentType FROM BotDefinition"
        )
        # Let unexpected errors propagate so the service layer can record a
        # FAILED run; only genuine "not found" results are handled gracefully.
        bots = await client.query(bot_soql)

        if not bots:
            notes.append(
                "No Agentforce agents found in this org. Agentforce may not be "
                "enabled."
            )
            result.notes = notes
            return result

        user_soql = (
            f"SELECT Id, Username, Email, Name FROM User "
            f"WHERE IsActive = true LIMIT {MAX_USERS}"
        )
        user_list = []
        try:
            user_list = await client.query(user_soql)
        except Exception as exc:
            notes.append(
                f"User enumeration failed: {exc}. Agent discovery still reported."
            )

        agent_names = [
            b.get("MasterLabel") or b.get("DeveloperName") or b.get("Id")
            for b in bots
        ]
        asset = DiscoveredAsset(
            name="Salesforce Agentforce",
            asset_type="SaaS AI Feature",
            provider="Salesforce",
            saas_platform="Salesforce",
            ai_capability="Agentforce",
            enabled=True,
            capability_status=CapabilityStatus.ENABLED.value,
            purpose=(
                "Salesforce Agentforce is Salesforce native generative AI "
                "platform for building and managing autonomous AI agents "
                "powered by Einstein GPT."
            ),
            accessible_resources=agent_names,
            discovery_source=(
                "Salesforce REST API -- SOQL on BotDefinition and User"
            ),
            monitoring_status="Limited Visibility",
            metadata={
                "agent_count": len(bots),
                "agents": [
                    {
                        "id": b.get("Id"),
                        "name": b.get("MasterLabel"),
                        "developer_name": b.get("DeveloperName"),
                        "version": b.get("AgentType", b.get("Type")),
                    }
                    for b in bots
                ],
                "organization_domain": cfg["domain"],
                "api_version": cfg.get("version", "62.0"),
            },
            tenant_id=cfg["domain"],
        )
        result.assets.append(asset)

        accesses = []
        for u in user_list:
            accesses.append(
                DiscoveredAccess(
                    principal_type=PrincipalType.USER.value,
                    principal_id=u.get("Id"),
                    principal_name=u.get("Username"),
                    display_name=u.get("Name"),
                    email=u.get("Email"),
                    access_type=AccessType.DIRECT_LICENSE.value,
                    access_level="Licensed (org-level Agentforce feature)",
                    license_sku="Agentforce (Einstein GPT)",
                    source="Salesforce REST API -- SOQL on User",
                )
            )
        result.accesses[asset.name] = accesses

        sessions = self._get_session_ids()
        if sessions:
            notes.append(
                "Agentforce session traces queryable via OTel API for "
                f"{len(sessions)} configured session ID(s)."
            )
        else:
            notes.append(
                "No session IDs configured (SFDC_OTEL_SESSION_IDS). "
                "Session-trace monitoring requires session IDs from the "
                "Session Trace UI."
            )

        notes.append(
            f"Discovered {len(bots)} Agentforce agent(s) and "
            f"{len(accesses)} active user(s) in {cfg['domain']}."
        )
        result.notes = notes
        return result

    def _get_session_ids(self):
        cfg = self._get_config()
        ids = cfg.get("session_ids") or os.getenv("SFDC_OTEL_SESSION_IDS")
        if not ids:
            return []
        if isinstance(ids, str):
            return [s.strip() for s in ids.split(",") if s.strip()]
        return list(ids)

    async def monitor(self, since=None):
        result = MonitoringResult()
        notes = []
        diag = {
            "sessions_requested": 0,
            "sessions_succeeded": 0,
            "sessions_failed": 0,
            "interactions_normalized": 0,
            "errors": [],
        }

        sessions = self._get_session_ids()
        cfg = self._get_config()

        if not sessions:
            notes.append(
                "No session IDs configured. Agentforce session-trace "
                "monitoring requires session IDs from the Session Trace UI."
            )
            result.metadata = {"diagnostics": diag}
            result.notes = notes
            return result

        diag["sessions_requested"] = len(sessions)
        client = self._get_client()
        version = cfg.get("version", "62.0")
        sem = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)

        async def _fetch_one(sid):
            async with sem:
                try:
                    url = (
                        f"https://{cfg["domain"]}/services/data/v{version}/einstein/audit/otel/{sid}"
                    )
                    try:
                        otel_data = await client.request("GET", url, raw=True)
                    except Exception as exc:
                        exc_msg = str(exc)
                        if "404" in exc_msg or "Not Found" in exc_msg:
                            diag["sessions_failed"] += 1
                            diag["errors"].append(
                                f"session {sid}: OTel API not available in this org "
                                f"(Session Trace / Einstein Audit not enabled). "
                                f"This requires a production or Sandbox org with "
                                f"Session Tracing enabled."
                            )
                            return []
                        raise
                    if otel_data is None:
                        diag["sessions_failed"] += 1
                        diag["errors"].append(f"session {sid}: no data")
                        return []
                    interactions = _parse_otel_sessions(otel_data, sid, notes)
                    diag["sessions_succeeded"] += 1
                    return interactions
                except Exception as exc:
                    diag["sessions_failed"] += 1
                    diag["errors"].append(f"session {sid}: {exc}")
                    return []

        tasks = [_fetch_one(sid) for sid in sessions]
        batch = await asyncio.gather(*tasks, return_exceptions=False)
        for interactions in batch:
            for inter in interactions:
                result.interactions.append(inter)
                diag["interactions_normalized"] += 1

        if diag["sessions_succeeded"] == 0:
            notes.append("All session-trace fetches failed. See diagnostics.")
        else:
            notes.append(
                f"Retrieved traces for {diag['sessions_succeeded']} session(s). "
                "OTel traces expose model, request/response, and token "
                "usage where the platform provides them."
            )
        result.notes = notes
        result.metadata = {"diagnostics": diag}
        return result

    def capabilities(self):
        return Capabilities(
            platform="Salesforce",
            discovery=[
                "Agentforce agents (BotDefinition SOQL)",
                "Active users (User SOQL)",
                "Agent metadata: name, developer name, version",
            ],
            monitoring=[
                "Session Trace OTel API (one session per request, 72h window)",
                "Model name (LLM span attributes)",
                "Request / prompt content (LLM request events)",
                "Response / output content (LLM response events)",
                "Token usage (prompt / completion / total)",
                "User identity (resource attributes)",
                "Session and turn timestamps",
            ],
            not_exposed=[
                "Session-listing API (session IDs must be supplied from UI)",
                "Sessions older than 72 hours",
                "Sessions when Session Tracing is not enabled",
            ],
        )


# ---------------------------------------------------------------------------
# OTLP JSON parsing helpers
# ---------------------------------------------------------------------------


def _parse_otel_sessions(otel_data, session_id, notes):
    """Parse an OTLP JSON payload into ObservedInteraction records.

    Spans sharing the same traceId are merged into a single interaction.
    """
    interactions = []
    if not isinstance(otel_data, dict):
        return interactions
    resource_spans = otel_data.get("resourceSpans") or otel_data.get("resource_spans") or []
    if not resource_spans:
        notes.append(f"Session {session_id}: OTel payload had no resourceSpans.")
        return interactions

    for rs in resource_spans:
        resource_attrs = _attrs_to_dict(rs.get("resource", {}).get("attributes", []))
        scope_spans = rs.get("scopeSpans") or rs.get("scope_spans") or []
        all_spans = []
        for ss in scope_spans:
            all_spans.extend(ss.get("spans") or [])

        by_trace = {}
        for span in all_spans:
            inter = _parse_span(span, resource_attrs, session_id)
            if inter is not None:
                tid = span.get("traceId", "")
                by_trace.setdefault(tid, []).append(inter)

        for tid, group in by_trace.items():
            if len(group) == 1:
                interactions.append(group[0])
            else:
                merged = group[0]
                for extra in group[1:]:
                    if not merged.model and extra.model:
                        merged.model = extra.model
                        merged.model_available = extra.model_available
                    if not merged.request_info and extra.request_info:
                        merged.request_info = extra.request_info
                        merged.request_available = extra.request_available
                    if not merged.response_info and extra.response_info:
                        merged.response_info = extra.response_info
                        merged.response_available = extra.response_available
                    if not merged.token_usage and extra.token_usage:
                        merged.token_usage = extra.token_usage
                        merged.usage_available = extra.usage_available
                interactions.append(merged)
    return interactions

def _parse_span(span, resource_attrs, session_id):
    """Parse a single OTLP span into an ObservedInteraction if LLM-related."""
    name = span.get("name", "")
    if not name.upper().startswith("LLM"):
        return None

    span_attrs = _attrs_to_dict(span.get("attributes", []))
    events = span.get("events", [])

    model = _pick(span_attrs, ["llm.model", "gen_ai.model", "model", "gen_ai.model.name"])
    model_available = bool(model)

    request_info = None
    request_available = False
    response_info = None
    response_available = False
    token_usage = None
    usage_available = False

    for evt in events:
        ev_name = (evt.get("name") or "").lower()
        ev_attrs = _attrs_to_dict(evt.get("attributes", []))
        if "request" in ev_name or "input" in ev_name or "prompt" in ev_name:
            request_info = _pick(
                ev_attrs, ["input", "prompt", "request", "message", "content"]
            ) or _pick(span_attrs, ["input", "prompt", "request", "message", "content"])
            if request_info:
                request_available = True
        if "response" in ev_name or "output" in ev_name or "completion" in ev_name:
            response_info = _pick(
                ev_attrs, ["output", "response", "completion", "message", "content"]
            ) or _pick(span_attrs, ["output", "response", "completion", "message", "content"])
            if response_info:
                response_available = True
        tokens = {}
        for key in ("usage.token_prompt", "usage.token_completion",
                    "usage.token_total", "input_tokens", "output_tokens",
                    "total_tokens"):
            val = _pick(ev_attrs, [key])
            if val is not None:
                tokens[key] = _to_int(val)
        if tokens:
            token_usage = tokens
            usage_available = True

    if not usage_available:
        tokens = {}
        for key in ("usage.token_prompt", "usage.token_completion",
                    "usage.token_total", "input_tokens", "output_tokens",
                    "total_tokens"):
            val = _pick(span_attrs, [key])
            if val is not None:
                tokens[key] = _to_int(val)
        if tokens:
            token_usage = tokens
            usage_available = True

    timestamp = _parse_nano_timestamp(span.get("startTimeUnixNano"))
    user_email = _pick(resource_attrs, [
        "user.email", "user.id", "user_id", "username",
    ])
    user_display_name = _pick(resource_attrs, [
        "user.name", "user.display_name", "user.displayName",
    ])

    raw_event = {
        "session_id": session_id,
        "span_id": span.get("spanId"),
        "trace_id": span.get("traceId"),
        "span_name": name,
        "attributes": span_attrs,
        "events": events,
    }
    external_id = f"sf:otel:{session_id}:{span.get('traceId','')}:{span.get('spanId','')}"

    return ObservedInteraction(
        user_email=user_email,
        user_display_name=user_display_name,
        principal_type=PrincipalType.USER.value,
        saas_application="Salesforce Agentforce",
        ai_feature="Agentforce Session Trace",
        model=model,
        model_available=model_available,
        timestamp=timestamp or datetime.now(timezone.utc),
        request_info=request_info,
        request_available=request_available,
        response_info=response_info,
        response_available=response_available,
        token_usage=token_usage,
        usage_available=usage_available,
        source="Salesforce Session Trace OTel API",
        visibility_note=(
            "Retrieved from Salesforce Agentforce OTel API. "
            "Where the platform exposes model, prompt, response, or "
            "token usage, they are captured; otherwise *_available is false."
        ),
        raw_event=raw_event,
        external_event_id=external_id,
        asset_keys={
            "saas_platform": "Salesforce",
            "ai_capability": "Agentforce",
        },
    )

def _attrs_to_dict(attrs):
    """Convert OTLP key-value attribute list to a plain dict."""
    out = {}
    if not attrs:
        return out
    for item in attrs:
        key = item.get("key")
        if not key:
            continue
        val = item.get("value", {})
        if isinstance(val, dict):
            for vk in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if val.get(vk) is not None:
                    out[key] = val[vk]
                    break
        else:
            out[key] = val
    return out


def _pick(d, keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _parse_nano_timestamp(nano):
    """Parse OTLP Unix-nanosecond timestamp into a timezone-aware datetime."""
    if not nano:
        return None
    try:
        return datetime.fromtimestamp(int(nano) / 1e9, tz=timezone.utc)
    except (TypeError, ValueError):
        return None