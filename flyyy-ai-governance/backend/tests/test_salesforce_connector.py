"""Tests for the Salesforce connector using a mocked httpx transport."""

import asyncio
import httpx
import pytest

from app.connectors.salesforce import SalesforceConnector


_RealAsyncClient = httpx.AsyncClient


def _patch_http(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.connectors.salesforce_client.httpx.AsyncClient",
        lambda *a, **k: _RealAsyncClient(transport=transport),
    )


SCENARIO = {}


def _token_handler(request):
    url = str(request.url)
    if "oauth2/token" in url:
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if "services/data" in url:
        path = request.url.path
        q = request.url.params.get("q", "")
        if "/query" in path and q:
            if "BotDefinition" in q:
                return httpx.Response(200, json={"records": SCENARIO.get("bots", [])})
            if "FROM User" in q:
                return httpx.Response(200, json={"records": SCENARIO.get("users", [])})
            return httpx.Response(200, json={"records": []})
        if "einstein/audit/otel" in path:
            sid = path.split("/")[-1]
            return httpx.Response(200, json=SCENARIO.get("otel_sessions", {}).get(sid, {"resourceSpans": []}))
    return httpx.Response(200, json={"records": []})


def test_agent_and_user_discovery(monkeypatch):
    SCENARIO.clear()
    SCENARIO["bots"] = [
        {"Id": "bot1", "MasterLabel": "Sales Assistant", "DeveloperName": "SalesAssistant", "DeveloperVersion": "1"},
        {"Id": "bot2", "MasterLabel": "Service Bot", "DeveloperName": "ServiceBot", "DeveloperVersion": "1"},
    ]
    SCENARIO["users"] = [
        {"Id": "u1", "Username": "user1@org.com", "Email": "user1@org.com", "Name": "User One"},
        {"Id": "u2", "Username": "user2@org.com", "Email": "user2@org.com", "Name": "User Two"},
    ]
    _patch_http(monkeypatch, _token_handler)

    c = SalesforceConnector()
    res = asyncio.run(c.discover())
    assert len(res.assets) == 1
    asset = res.assets[0]
    assert asset.provider == "Salesforce"
    assert asset.enabled
    accesses = res.accesses[asset.name]
    assert len(accesses) == 2
    assert accesses[0].principal_type == "User"
    assert accesses[0].access_type == "Direct (license assigned to user)"


def test_no_agents_finds_none(monkeypatch):
    SCENARIO.clear()
    SCENARIO["bots"] = []
    _patch_http(monkeypatch, _token_handler)
    c = SalesforceConnector()
    res = asyncio.run(c.discover())
    assert len(res.assets) == 0
    assert any("No Agentforce agents" in n for n in res.notes)


def test_otel_trace_parsing(monkeypatch):
    SCENARIO.clear()
    SCENARIO["bots"] = [{"Id": "bot1", "MasterLabel": "SA", "DeveloperName": "SA", "DeveloperVersion": "1"}]
    SCENARIO["users"] = [{"Id": "u1", "Username": "u@org.com", "Email": "u@org.com", "Name": "U"}]
    otel_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "agentforce"}},
                        {"key": "user.email", "value": {"stringValue": "caller@example.com"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "sf"},
                        "spans": [
                            {
                                "traceId": "t1", "spanId": "s1",
                                "name": "LLM_REQUEST",
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000001000000000",
                                "attributes": [
                                    {"key": "llm.model", "value": {"stringValue": "gpt-4"}},
                                ],
                                "events": [
                                    {"name": "input", "attributes": [
                                        {"key": "input", "value": {"stringValue": "Hello agent"}},
                                    ]},
                                ],
                            },
                            {
                                "traceId": "t1", "spanId": "s2",
                                "name": "LLM_RESPONSE",
                                "startTimeUnixNano": "1700000001000000000",
                                "endTimeUnixNano": "1700000002000000000",
                                "attributes": [],
                                "events": [
                                    {"name": "output", "attributes": [
                                        {"key": "output", "value": {"stringValue": "Hi there"}},
                                    ]},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }
    SCENARIO["otel_sessions"] = {"sess1": otel_payload}

    c = SalesforceConnector(connection_config={
        "domain": "test-org.my.salesforce.com",
        "client_id": "client-123",
        "client_secret": "secret-123",
        "version": "62.0",
        "session_ids": "sess1",
    })
    _patch_http(monkeypatch, _token_handler)

    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 1
    inter = res.interactions[0]
    assert inter.model == "gpt-4"
    assert inter.model_available is True
    assert inter.request_info == "Hello agent"
    assert inter.request_available is True
    assert inter.response_info == "Hi there"
    assert inter.response_available is True
    assert inter.user_email == "caller@example.com"
    assert inter.external_event_id.startswith("sf:otel:sess1:")


def test_monitor_no_session_ids(monkeypatch):
    SCENARIO.clear()
    _patch_http(monkeypatch, _token_handler)
    c = SalesforceConnector()
    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 0
    assert any("No session IDs" in n for n in res.notes)


def test_monitor_session_error_handled(monkeypatch):
    SCENARIO.clear()
    SCENARIO["bots"] = [{"Id": "bot1", "MasterLabel": "SA", "DeveloperName": "SA", "DeveloperVersion": "1"}]

    def failing(request):
        url = str(request.url)
        if "oauth2/token" in url:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if "einstein/audit/otel" in url:
            return httpx.Response(500, json={"error": "server error"})
        return httpx.Response(200, json={"records": []})

    _patch_http(monkeypatch, failing)
    c = SalesforceConnector(connection_config={
        "domain": "test-org.my.salesforce.com",
        "client_id": "client-123",
        "client_secret": "secret-123",
        "version": "62.0",
        "session_ids": "sess1",
    })
    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 0
    assert any("failed" in n.lower() for n in res.notes)


def test_provider_api_failure_propagates(monkeypatch):
    SCENARIO.clear()

    def failing(request):
        url = str(request.url)
        if "oauth2/token" in url:
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if "services/data" in url:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(404)

    _patch_http(monkeypatch, failing)
    c = SalesforceConnector()
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(c.discover())


def test_capabilities_report():
    c = SalesforceConnector()
    caps = c.capabilities()
    assert caps.platform == "Salesforce"
    assert any("BotDefinition" in d for d in caps.discovery)
    assert any("OTel" in d for d in caps.monitoring)
    assert any("session" in n.lower() for n in caps.not_exposed)

