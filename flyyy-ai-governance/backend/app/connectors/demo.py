"""
Demonstration connector.

Generates *realistic simulated* data so the full discovery → inventory →
monitoring → review workflow is demonstrable end-to-end **without** any real
SaaS credentials. Every record produced here is clearly tagged as simulated in
its ``source`` / ``visibility_note`` so it is never mistaken for observed
evidence.

The simulated data intentionally mirrors the honest limitations described in the
challenge: for Microsoft 365 Copilot the prompt/response/model are *not
available* (matching the real connector), whereas other platforms in the demo
expose different slices of visibility. This lets the UI show the full range of
the ``*_available`` states.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

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

_DEMO_USERS = [
    ("Ava Sharma", "ava.sharma", "sales"),
    ("Liam Patel", "liam.patel", "sales"),
    ("Noah Kim", "noah.kim", "sales"),
    ("Mia Chen", "mia.chen", "sales"),
    ("Ethan Rogers", "ethan.rogers", "marketing"),
    ("Sofia Rossi", "sofia.rossi", "marketing"),
    ("Lucas Nguyen", "lucas.nguyen", "engineering"),
    ("Olivia Brown", "olivia.brown", "engineering"),
    ("Priya Singh", "priya.singh", "support"),
    ("Daniel Lee", "daniel.lee", "support"),
]

_DEMO_APPS = ["Word", "Excel", "PowerPoint", "Outlook", "Teams", "SharePoint"]


class DemoConnector(BaseConnector):
    platform = "Demo / Simulated"
    connector_type = "demo"

    def __init__(self, connection_config: dict | None = None) -> None:
        super().__init__(connection_config)
        random.seed(42)

    def is_configured(self) -> bool:
        # The demo connector is always "available" so the app runs out-of-box.
        return True

    # --------------------------------------------------------------- discovery
    async def discover(self) -> DiscoveryResult:
        result = DiscoveryResult()

        # --- Microsoft 365 Copilot (matches the challenge's end-to-end example) ---
        m365_asset = DiscoveredAsset(
            name="Microsoft 365 Copilot",
            asset_type="SaaS AI Feature",
            provider="Microsoft",
            saas_platform="Microsoft 365",
            ai_capability="Copilot for Microsoft 365",
            enabled=True,
            purpose=(
                "Generative AI assistant embedded across Microsoft 365 that "
                "summarises, drafts, and reasons over business data."
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
            discovery_source="Simulated — Microsoft Graph (subscribedSkus)",
            monitoring_status="Partial Visibility",
            metadata={"simulated": True, "license_skus": ["MICROSOFT_365_COPILOT"]},
            tenant_id="demo-contoso",
        )
        m365_access = [
            DiscoveredAccess(
                principal_type=PrincipalType.USER.value,
                principal_id=f"u-{i}",
                principal_name=f"{un}@contoso.com",
                display_name=nm,
                email=f"{un}@contoso.com",
                access_level="Licensed",
                license_sku="MICROSOFT_365_COPILOT",
                source="Simulated — user.assignedLicenses",
            )
            for i, (nm, un, _grp) in enumerate(_DEMO_USERS)
        ]
        result.assets.append(m365_asset)
        result.accesses[m365_asset.name] = m365_access

        # --- Slack AI (different slice of visibility) ---
        slack_asset = DiscoveredAsset(
            name="Slack AI",
            asset_type="SaaS AI Feature",
            provider="Salesforce (Slack)",
            saas_platform="Slack",
            ai_capability="Slack AI (thread summaries, search, recaps)",
            enabled=True,
            purpose="In-channel AI: conversation summaries, search answers, recaps.",
            accessible_resources=["Slack Workspace #general", "#sales", "#eng"],
            discovery_source="Simulated — Slack admin API (aiSettings)",
            monitoring_status="Limited Visibility",
            metadata={"simulated": True},
            tenant_id="demo-contoso",
        )
        slack_access = [
            DiscoveredAccess(
                principal_type=PrincipalType.GROUP.value,
                principal_id="g-sales",
                principal_name="Sales",
                display_name="Sales",
                access_level="Workspace Enabled",
                source="Simulated — Slack workspace settings",
            )
        ]
        result.assets.append(slack_asset)
        result.accesses[slack_asset.name] = slack_access

        # --- Notion AI (exposes model in some plans) ---
        notion_asset = DiscoveredAsset(
            name="Notion AI",
            asset_type="SaaS AI Feature",
            provider="Notion",
            saas_platform="Notion",
            ai_capability="Notion AI (write, summarise, Q&A)",
            enabled=True,
            purpose="AI writing assistant and workspace Q&A inside Notion.",
            accessible_resources=["Notion Workspace"],
            discovery_source="Simulated — Notion workspace API",
            monitoring_status="Partial Visibility",
            metadata={"simulated": True},
            tenant_id="demo-contoso",
        )
        notion_access = [
            DiscoveredAccess(
                principal_type=PrincipalType.GROUP.value,
                principal_id="g-eng",
                principal_name="Engineering",
                display_name="Engineering",
                access_level="Add-on Enabled",
                source="Simulated — Notion billing/settings",
            )
        ]
        result.assets.append(notion_asset)
        result.accesses[notion_asset.name] = notion_access

        result.notes = [
            "SIMULATED DATA — no real SaaS tenant was contacted. "
            "Replace the demo connection with a configured Microsoft 365 "
            "connector to discover real evidence."
        ]
        return result

    # --------------------------------------------------------------- monitoring
    async def monitor(self, since: datetime | None = None) -> MonitoringResult:
        result = MonitoringResult()
        now = datetime.now(timezone.utc)

        # Microsoft 365 Copilot: honest limitation — content NOT available.
        for i in range(18):
            u = random.choice(_DEMO_USERS)
            result.interactions.append(
                ObservedInteraction(
                    user_email=f"{u[1]}@contoso.com",
                    user_display_name=u[0],
                    principal_type=PrincipalType.USER.value,
                    saas_application=random.choice(_DEMO_APPS),
                    ai_feature="Copilot",
                    model=None,
                    model_available=False,
                    timestamp=now - timedelta(hours=random.randint(1, 72)),
                    request_info=None,
                    request_available=False,
                    response_info=None,
                    response_available=False,
                    token_usage=None,
                    usage_available=False,
                    source="Simulated — Office 365 Management Activity API",
                    visibility_note=(
                        "SIMULATED. In a real tenant, Microsoft 365 audit logs "
                        "expose only interaction metadata, not prompt/response."
                    ),
                    asset_keys={
                        "saas_platform": "Microsoft 365",
                        "ai_capability": "Copilot for Microsoft 365",
                    },
                )
            )

        # Slack AI: partial — we can see a request summary, not the response.
        for i in range(8):
            u = random.choice(_DEMO_USERS)
            result.interactions.append(
                ObservedInteraction(
                    user_email=f"{u[1]}@contoso.com",
                    user_display_name=u[0],
                    principal_type=PrincipalType.USER.value,
                    saas_application="Slack",
                    ai_feature="Slack AI",
                    model=None,
                    model_available=False,
                    timestamp=now - timedelta(hours=random.randint(1, 48)),
                    request_info="Requested a summary of #sales channel thread.",
                    request_available=True,
                    response_info=None,
                    response_available=False,
                    token_usage=None,
                    usage_available=False,
                    source="Simulated — Slack audit logs",
                    visibility_note=(
                        "SIMULATED. Slack exposes the action type but not the "
                        "generated summary text."
                    ),
                    asset_keys={
                        "saas_platform": "Slack",
                        "ai_capability": "Slack AI (thread summaries, search, recaps)",
                    },
                )
            )

        # Notion AI: simulates model being exposed for some plans.
        for i in range(6):
            u = random.choice(_DEMO_USERS)
            result.interactions.append(
                ObservedInteraction(
                    user_email=f"{u[1]}@contoso.com",
                    user_display_name=u[0],
                    principal_type=PrincipalType.USER.value,
                    saas_application="Notion",
                    ai_feature="Notion AI",
                    model="gpt-4" if random.random() > 0.5 else "claude-3-sonnet",
                    model_available=True,
                    timestamp=now - timedelta(hours=random.randint(1, 36)),
                    request_info="Asked Notion AI to draft a sprint retro summary.",
                    request_available=True,
                    response_info="(simulated) Generated a structured retro draft.",
                    response_available=True,
                    token_usage={
                        "prompt_tokens": random.randint(120, 800),
                        "completion_tokens": random.randint(80, 600),
                        "total_tokens": random.randint(200, 1400),
                    },
                    usage_available=True,
                    source="Simulated — Notion AI usage API",
                    visibility_note=(
                        "SIMULATED. Notion's usage API can expose model + token "
                        "counts for some plans."
                    ),
                    asset_keys={
                        "saas_platform": "Notion",
                        "ai_capability": "Notion AI (write, summarise, Q&A)",
                    },
                )
            )

        result.notes = [
            "SIMULATED monitoring data. Replace with a configured connector "
            "to capture real interactions."
        ]
        return result

    # --------------------------------------------------------------- capabilities
    def capabilities(self) -> Capabilities:
        return Capabilities(
            platform="Demo / Simulated",
            discovery=[
                "Simulated AI capability presence",
                "Simulated enabled status",
                "Simulated user/group access",
                "Simulated license / entitlement",
                "Simulated associated resources",
            ],
            monitoring=[
                "Simulated interaction identity",
                "Simulated application / feature",
                "Simulated timestamp",
                "Simulated request/response/model/usage (mixed availability)",
            ],
            not_exposed=[
                "Real prompts/responses (demo only illustrates the limitation)",
            ],
        )
