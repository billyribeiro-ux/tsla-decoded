"""FMP stable-API HTTP client with JSON caching, retry, throttling and tier degradation."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/stable"
THROTTLE_SECONDS = 0.3


class TransientAPIError(Exception):
    """429 / 5xx / network error — retried."""


class FMPClient:
    def __init__(self, api_key: str, cache_dir: Path, refresh: bool = False):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.capabilities: dict[str, str] = {}   # endpoint -> "ok" | "unavailable (4xx)"
        self.http_requests = 0
        self._last_request_at = 0.0
        self._session = requests.Session()

    # -- caching ------------------------------------------------------------
    def _cache_path(self, endpoint: str, params: dict) -> Path:
        canon = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True)
        digest = hashlib.sha1(canon.encode()).hexdigest()[:16]
        slug = endpoint.replace("/", "_")
        return self.cache_dir / f"{slug}__{digest}.json"

    # -- HTTP ---------------------------------------------------------------
    @retry(
        retry=retry_if_exception_type(TransientAPIError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        reraise=True,
    )
    def _http_get(self, endpoint: str, params: dict):
        wait = THROTTLE_SECONDS - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()
        self.http_requests += 1
        try:
            resp = self._session.get(
                f"{BASE_URL}/{endpoint}",
                params={**params, "apikey": self.api_key},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise TransientAPIError(str(exc)) from exc
        if resp.status_code in (402, 403):
            return {"__unavailable__": resp.status_code}
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientAPIError(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp.json()

    # -- public -------------------------------------------------------------
    def get(self, endpoint: str, **params):
        """Fetch endpoint with params; returns parsed JSON, or None if tier-gated.

        Responses are cached on disk keyed by endpoint+params (apikey excluded).
        """
        path = self._cache_path(endpoint, params)
        if path.exists() and not self.refresh:
            data = json.loads(path.read_text())
        else:
            data = self._http_get(endpoint, params)
            path.write_text(json.dumps(data))
        if isinstance(data, dict) and "__unavailable__" in data:
            self.capabilities[endpoint] = f"unavailable ({data['__unavailable__']})"
            log.warning("endpoint %s unavailable at this tier", endpoint)
            return None
        self.capabilities.setdefault(endpoint, "ok")
        return data
