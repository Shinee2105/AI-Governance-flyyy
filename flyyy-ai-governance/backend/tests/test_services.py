"""Service-layer tests: persistence, idempotent monitoring, run status."""

import asyncio
import httpx

from app.connectors.microsoft365 import Microsoft365Connector
from app.models import AIAsset, AIInteraction, Run
from app.services.discovery_service import run_discovery
from app.services.monitoring_service import run_monitoring
from sqlalchemy import select

_RealAsyncClient = httpx.AsyncClient


def _patch_http(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.connectors.microsoft365.httpx.AsyncClient",
        lambda *a, **k: _RealAsyncClient(transport=transport),
    )


SCENARIO = {}


def _handler(request):
    if "login.microsoftonline.com" in str(request.url):
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if "manage.office.com" in str(request.url):
        if request.method == "POST":
            return httpx.Response(200, json={})
        if "subscriptions/content" in str(request.url):
            if "Audit.General" in str(request.url):
                return httpx.Response(200, json=SCENARIO.get("content", []))
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=SCENARIO.get("blob", []))
    return httpx.Response(200, json=SCENARIO.get("blob", []))


def test_demo_discovery_and_monitoring_idempotent(demo_connection, db):
    asyncio.run(run_discovery(demo_connection))
    asyncio.run(run_monitoring(demo_connection, since=None))
    first = db.execute(select(AIInteraction)).scalars().all()

    asyncio.run(run_monitoring(demo_connection, since=None))
    second = db.execute(select(AIInteraction)).scalars().all()

    assert len(first) == len(second)
    assets = db.execute(select(AIAsset)).scalars().all()
    assert len(assets) == 3
    assert all(a.capability_status for a in assets)


def test_m365_monitoring_dedupes_same_external_id(m365_connection, monkeypatch, db):
    SCENARIO.clear()
    SCENARIO["content"] = [{"contentUri": "http://blob/1"}]
    SCENARIO["blob"] = [
        {"Id": "SAME", "Operation": "CopilotInteraction", "UserId": "u@x",
         "Workload": "Word", "CreationTime": "2024-01-01T10:00:00Z", "RecordType": 305},
        {"Id": "SAME", "Operation": "CopilotInteraction", "UserId": "u@x",
         "Workload": "Word", "CreationTime": "2024-01-01T10:00:00Z", "RecordType": 305},
    ]
    _patch_http(monkeypatch, _handler)

    asyncio.run(run_monitoring(m365_connection, since=None))
    inters = db.execute(select(AIInteraction)).scalars().all()
    assert len(inters) == 1


def test_discovery_failure_records_failed_run(m365_connection, monkeypatch, db):
    def failing(request):
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if "graph.microsoft.com" in str(request.url):
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(404)

    _patch_http(monkeypatch, failing)
    run_id = asyncio.run(run_discovery(m365_connection))
    run = db.get(Run, run_id)
    assert run.status.value == "Failed"
    assert run.error
