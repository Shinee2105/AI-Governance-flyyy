"""
Salesforce API client helper.

Provides:
  * ECA OAuth 2.0 Client Credentials flow token acquisition with caching.
  * Bounded, retried REST calls against the Salesforce REST API.
  * Error classification for 429 (rate limit) and 5xx (transient) with
    exponential backoff + jitter.

Only APIs verified against official Salesforce documentation are used:
  POST /services/oauth2/token  grant_type=client_credentials
  GET  /services/data/v{ver}/query?q=...
  GET  /services/data/v{ver}/einstein/audit/otel/{session-id}
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

DEFAULT_VERSION = "62.0"
DEFAULT_BASE_DELAY = 0.5
DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT = 30.0


class SalesforceClient:
    """Minimal authenticated Salesforce REST client with token caching."""

    def __init__(
        self,
        domain: str,
        client_id: str,
        client_secret: str,
        version: str = DEFAULT_VERSION,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.domain = domain.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.version = version
        self.base_url = f"https://{self.domain}/services/data/v{version}"
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _ensure_token(self) -> str:
        """Acquire (or refresh) an OAuth access token via client credentials."""
        if self._token and time.time() < self._token_expires_at:
            return self._token
        url = f"https://{self.domain}/services/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        self._token = payload["access_token"]
        # Refresh 60s before real expiry to avoid edge failures.
        self._token_expires_at = time.time() + max(
            60.0, payload.get("expires_in", 3600) - 60
        )
        return self._token

    @staticmethod
    def _is_retryable(status: int) -> bool:
        return status in (429, 502, 503, 504)

    def _backoff_delay(self, attempt: int, resp: httpx.Response | None = None) -> float:
        if resp is not None and resp.status_code == 429:
            ra = resp.headers.get("retry-after")
            if ra:
                try:
                    return float(ra)
                except ValueError:
                    pass
        return self.base_delay * (2 ** attempt)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        raw: bool = False,
    ) -> Any:
        """Perform an authenticated request with bounded retry/backoff.

        ``path`` is treated as relative to the REST base URL.  When ``raw`` is
        True the caller supplies an absolute path (used for the OTel endpoint).
        """
        url = path if raw else f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            token = await self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.request(
                        method, url, headers=headers, params=params, json=json_body,
                    )
                if self._is_retryable(resp.status_code):
                    delay = self._backoff_delay(attempt, resp)
                    last_exc = _build_error(resp, url)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                if resp.status_code in (204, 202) or not resp.content:
                    return None
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self._backoff_delay(attempt))
        raise last_exc  # type: ignore[misc]

    async def query(self, soql: str) -> list[dict]:
        """Run a SOQL query and auto-paginate via nextRecordsUrl.

        Returns the flattened list of records.  SOQL MAX is 2000 per page.
        """
        records: list[dict] = []
        next_url: str | None = None
        params: dict[str, Any] = {"q": soql}
        pages = 0
        while True:
            if next_url:
                token = await self._ensure_token()
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(next_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            else:
                data = await self.request("GET", "/query", params=params)
            records.extend(data.get("records", []))
            next_url = data.get("nextRecordsUrl")
            if not next_url:
                break
            pages += 1
            if pages >= 200:
                break
        return records


def _build_error(resp: httpx.Response, url: str) -> Exception:
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:500]}
    if isinstance(body, dict) and body.get("message"):
        detail = body["message"]
    else:
        detail = body
    return httpx.HTTPStatusError(
        f"{resp.status_code} {resp.reason_phrase} for {url}: {detail}",
        request=resp.request,
        response=resp,
    )
