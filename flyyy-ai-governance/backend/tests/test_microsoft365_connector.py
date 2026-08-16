"""Tests for the Microsoft 365 connector using a mocked httpx transport.

These validate real behaviour (pagination, group licensing, copilot detection,
monitoring mapping, idempotent ids, no-content handling) without contacting
Microsoft. The actual Graph / Management Activity API integration is preserved;
only the HTTP layer is substituted.
"""

import asyncio
import httpx
import pytest

from app.connectors.microsoft365 import Microsoft365Connector
from app.models import AccessType, CapabilityStatus

# Capture the real AsyncClient before we patch the module attribute, otherwise
# the replacement lambda would call the patched name and recurse.
_RealAsyncClient = httpx.AsyncClient


def _patch_http(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "app.connectors.microsoft365.httpx.AsyncClient",
        lambda *a, **k: _RealAsyncClient(transport=transport),
    )


def _token_handler(request):
    if "login.microsoftonline.com" in str(request.url):
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if "manage.office.com" in str(request.url):
        if request.method == "POST":
            return httpx.Response(200, json={})
        if "subscriptions/content" in str(request.url):
            # Only the General feed carries our test data; the others are empty.
            if "Audit.General" in str(request.url):
                return httpx.Response(200, json=SCENARIO.get("content", []))
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=SCENARIO.get("blob", []))
    if "graph.microsoft.com" in str(request.url):
        path = request.url.path
        if path == "/v1.0/subscribedSkus":
            return httpx.Response(200, json={"value": SCENARIO["skus"]})
        if path == "/v1.0/users":
            return httpx.Response(200, json=SCENARIO["users_page"]())
        if path == "/v1.0/groups":
            return httpx.Response(200, json={"value": SCENARIO.get("groups", [])})
        if "transitiveMembers" in path:
            return httpx.Response(200, json={"value": SCENARIO.get("members", [])})
    return httpx.Response(200, json=SCENARIO.get("blob", []))


SCENARIO = {}


def test_copilot_sku_detection_and_direct_license(monkeypatch):
    SCENARIO.clear()
    SCENARIO["skus"] = [{"skuPartNumber": "MICROSOFT_365_COPILOT", "skuId": "SKU1"}]
    SCENARIO["users_page"] = lambda: {
        "value": [
            {"id": "u1", "displayName": "A", "userPrincipalName": "a@x",
             "mail": "a@x", "assignedLicenses": [{"skuId": "SKU1"}]},
            {"id": "u2", "displayName": "B", "userPrincipalName": "b@x",
             "mail": "b@x", "assignedLicenses": [{"skuId": "OTHER"}]},
        ]
    }
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.discover())
    assert len(res.assets) == 1
    asset = res.assets[0]
    assert asset.capability_status == CapabilityStatus.LICENSED.value
    assert len(res.accesses[asset.name]) == 1
    acc = res.accesses[asset.name][0]
    assert acc.access_type == AccessType.DIRECT_LICENSE.value


def test_pagination_multiple_pages(monkeypatch):
    SCENARIO.clear()
    SCENARIO["skus"] = [{"skuPartNumber": "MICROSOFT_365_COPILOT", "skuId": "SKU1"}]
    pages = [
        {"value": [{"id": f"u{i}", "displayName": f"U{i}", "userPrincipalName": f"u{i}@x",
                   "mail": f"u{i}@x", "assignedLicenses": [{"skuId": "SKU1"}]} for i in range(3)],
         "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?page=2"},
        {"value": [{"id": f"u{i}", "displayName": f"U{i}", "userPrincipalName": f"u{i}@x",
                   "mail": f"u{i}@x", "assignedLicenses": [{"skuId": "SKU1"}]} for i in range(3, 6)]},
    ]
    counter = {"n": 0}

    def users_page():
        p = pages[counter["n"]]
        counter["n"] += 1
        return p

    SCENARIO["users_page"] = users_page
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.discover())
    asset = res.assets[0]
    assert len(res.accesses[asset.name]) == 6


def test_pagination_empty_page_and_final_no_nextlink(monkeypatch):
    SCENARIO.clear()
    SCENARIO["skus"] = [{"skuPartNumber": "MICROSOFT_365_COPILOT", "skuId": "SKU1"}]
    SCENARIO["users_page"] = lambda: {"value": []}
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.discover())
    assert len(res.assets) == 1
    assert len(res.accesses[res.assets[0].name]) == 0


def test_pagination_malformed_page_missing_value(monkeypatch):
    SCENARIO.clear()
    SCENARIO["skus"] = [{"skuPartNumber": "MICROSOFT_365_COPILOT", "skuId": "SKU1"}]
    SCENARIO["users_page"] = lambda: {"@odata.nextLink": None}
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.discover())
    assert len(res.accesses[res.assets[0].name]) == 0


def test_group_based_licensing_resolution(monkeypatch):
    SCENARIO.clear()
    SCENARIO["skus"] = [{"skuPartNumber": "MICROSOFT_365_COPILOT", "skuId": "SKU1"}]
    SCENARIO["users_page"] = lambda: {
        "value": [{"id": "u1", "displayName": "Direct", "userPrincipalName": "d@x",
                   "mail": "d@x", "assignedLicenses": [{"skuId": "SKU1"}]}]
    }
    SCENARIO["groups"] = [{"id": "g1", "displayName": "Sales"}]
    SCENARIO["members"] = [
        {"id": "u1", "displayName": "Direct", "userPrincipalName": "d@x", "mail": "d@x"},
        {"id": "u2", "displayName": "Grouped", "userPrincipalName": "g@x", "mail": "g@x"},
    ]
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.discover())
    accesses = res.accesses[res.assets[0].name]
    types = {a.access_type for a in accesses}
    assert AccessType.DIRECT_LICENSE.value in types
    assert AccessType.GROUP_LICENSE.value in types
    # u1 via both direct + group => 3 rows (deduped by principal+access_type).
    assert len(accesses) == 3


def test_monitoring_maps_copilot_record_and_skips_others(monkeypatch):
    SCENARIO.clear()
    SCENARIO["content"] = [{"contentUri": "http://blob/1"}]
    SCENARIO["blob"] = [
        {"Id": "rec1", "Operation": "CopilotInteraction", "UserId": "u@x",
         "Workload": "Word", "CreationTime": "2024-01-01T10:00:00Z", "RecordType": 305},
        {"Id": "rec2", "Operation": "SomethingElse", "UserId": "z@x"},
    ]
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 1
    inter = res.interactions[0]
    assert inter.external_event_id == "o365:rec1"
    assert inter.model_available is False
    assert inter.request_available is False
    assert inter.visibility_note


def test_monitoring_no_content_is_not_failure(monkeypatch):
    SCENARIO.clear()
    SCENARIO["content"] = []
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 0
    assert any("no currently available" in n for n in res.notes)


def test_monitoring_malformed_record_does_not_crash(monkeypatch):
    SCENARIO.clear()
    SCENARIO["content"] = [{"contentUri": "http://blob/1"}]
    SCENARIO["blob"] = [{"Operation": "CopilotInteraction"}]
    _patch_http(monkeypatch, _token_handler)

    c = Microsoft365Connector()
    res = asyncio.run(c.monitor())
    assert len(res.interactions) == 1
    assert res.interactions[0].external_event_id.startswith("o365:fp:")


def test_provider_api_failure_propagates(monkeypatch):
    def failing(request):
        if "login.microsoftonline.com" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if "graph.microsoft.com" in str(request.url):
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(404)

    _patch_http(monkeypatch, failing)
    c = Microsoft365Connector()
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(c.discover())


def test_capabilities_report_unobservable_fields():
    c = Microsoft365Connector()
    caps = c.capabilities()
    assert "Prompt / request content" in caps.not_exposed
    assert "Underlying LLM model name" in caps.not_exposed
    assert any("group" in d.lower() for d in caps.discovery)
