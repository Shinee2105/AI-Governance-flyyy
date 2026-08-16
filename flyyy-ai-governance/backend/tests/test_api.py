"""API-layer tests: authentication, authorization, validation, 404s."""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _auth_header():
    with TestClient(app) as c:
        tok = c.post(
            "/api/v1/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_public_read_endpoints_do_not_require_auth():
    with TestClient(app) as client:
        assert client.get("/api/v1/assets").status_code == 200
        assert client.get("/api/v1/stats/dashboard").status_code == 200


def test_missing_resource_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/v1/connections/does-not-exist").status_code == 404


def test_create_connection_requires_auth():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/connections",
            json={"name": "X", "platform": "Y", "connector_type": "demo"},
        )
        assert r.status_code == 401


def test_create_connection_with_auth_succeeds():
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/connections",
            json={"name": "X", "platform": "Y", "connector_type": "demo"},
            headers=_auth_header(),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["connector_type"] == "demo"


def test_invalid_payload_returns_422():
    with TestClient(app) as client:
        # connector_type must reference a known connector; an unknown type still
        # validates the schema, but a missing field should be rejected.
        r = client.post(
            "/api/v1/connections",
            json={"name": "X"},
            headers=_auth_header(),
        )
        assert r.status_code == 422
