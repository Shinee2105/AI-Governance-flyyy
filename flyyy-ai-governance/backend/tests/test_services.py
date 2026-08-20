"""Service-layer tests: persistence, idempotent monitoring, run status."""

import asyncio
import httpx

from app.connectors.salesforce import SalesforceConnector
from app.models import AIAsset, AIInteraction, Run
from app.services.discovery_service import run_discovery
from app.services.monitoring_service import run_monitoring
from sqlalchemy import select

_RealAsyncClient = httpx.AsyncClient


def _patch_http(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.connectors.salesforce_client.httpx.AsyncClient",
        lambda *a, **k: _RealAsyncClient(transport=transport),
    )


SCENARIO = {}


def _handler(request):
    url = str(request.url)
    if "oauth2/token" in url:
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if "services/data" in url:
        path = request.url.path
        query_params = request.url.params.get("q", "")
        if "BotDefinition" in query_params:
            return httpx.Response(200, json={"records": SCENARIO.get("bots", [])})
        if "FROM User" in query_params:
            return httpx.Response(200, json={"records": SCENARIO.get("users", [])})
        if "einstein/audit/otel" in path:
            sid = path.split("/")[-1]
            return httpx.Response(200, json=SCENARIO.get("otel", {"resourceSpans": []}))
    return httpx.Response(200, json={"records": []})


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


def test_salesforce_monitoring_dedupes_same_external_id(salesforce_connection, monkeypatch, db):
    SCENARIO.clear()
    SCENARIO["bots"] = [{"Id": "bot1", "MasterLabel": "SA", "DeveloperName": "SA", "DeveloperVersion": "1"}]
    span_base = {
        "traceId": "t1", "spanId": "s1",
        "name": "LLM_REQUEST",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700000001000000000",
        "attributes": [{"key": "llm.model", "value": {"stringValue": "gpt-4"}}],
        "events": [{"name": "input", "attributes": [{"key": "input", "value": {"stringValue": "hello"}}]}],
    }
    SCENARIO["otel"] = {"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [{"spans": [span_base, span_base]}]}]}

    salesforce_connection.config = {
        "domain": "test-org.my.salesforce.com",
        "client_id": "client-123",
        "client_secret": "secret-123",
        "version": "62.0",
        "session_ids": "sess1",
    }
    db.add(salesforce_connection)
    db.commit()

    _patch_http(monkeypatch, _handler)
    asyncio.run(run_monitoring(salesforce_connection, since=None))

    # Two duplicate spans with same traceId+spanId => one unique interaction
    inters = db.execute(select(AIInteraction)).scalars().all()
    assert len(inters) == 1


def test_discovery_failure_records_failed_run(salesforce_connection, monkeypatch, db):
    def failing(request):
        url = str(request.url)
        if "oauth2/token" in url:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if "services/data" in url:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(404)

    _patch_http(monkeypatch, failing)
    run_id = asyncio.run(run_discovery(salesforce_connection))
    run = db.get(Run, run_id)
    assert run.status.value == "Failed"
    assert run.error
