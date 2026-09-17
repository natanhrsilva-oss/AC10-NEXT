from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from typing import Any

import httpx

from ac10next.settings import Settings

LOGGER = logging.getLogger(__name__)


class HighlightlyClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.highlightly_base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(max(1, settings.highlightly_concurrency))
        self._client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=settings.http_max_connections, max_keepalive_connections=20),
        )
        self.request_counts: Counter[str] = Counter()
        self.error_counts: Counter[str] = Counter()
        self.latency_ms: Counter[str] = Counter()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @property
    def headers(self) -> dict[str, str]:
        return {"x-rapidapi-key": self.settings.highlightly_api_key}

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
        path = endpoint.lstrip("/")
        if not path.startswith("football/"):
            path = f"football/{path}"
        metric = endpoint.split("/", 1)[0]
        last_exc: Exception | None = None
        for attempt in range(max(1, self.settings.highlightly_max_retries)):
            started = time.perf_counter()
            async with self._semaphore:
                try:
                    self.request_counts[metric] += 1
                    response = await self._client.get(f"{self.base_url}/{path}", params=params, headers=self.headers)
                    self.latency_ms[metric] += int((time.perf_counter() - started) * 1000)
                    if response.status_code == 404:
                        return {}
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        self.error_counts[metric] += 1
                        retry_after = response.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after and retry_after.isdigit() else min(8.0, 0.8 * (2 ** attempt))
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    self.error_counts[metric] += 1
                    if attempt + 1 >= self.settings.highlightly_max_retries:
                        raise
                    await asyncio.sleep(min(8.0, 0.8 * (2 ** attempt)))
        if last_exc:
            raise last_exc
        return {}

    async def matches_all(self, target_date: str, timezone: str, max_records: int = 3000) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        total_count: int | None = None
        page_size = 100
        while offset < max_records:
            payload = await self._get("matches", params={"date": target_date, "timezone": timezone, "limit": page_size, "offset": offset})
            batch = list(payload.get("data") or []) if isinstance(payload, dict) else list(payload or [])
            if isinstance(payload, dict):
                pagination = payload.get("pagination") or {}
                try:
                    total_count = int(pagination.get("totalCount")) if pagination.get("totalCount") is not None else total_count
                except (TypeError, ValueError):
                    pass
            rows.extend(batch)
            offset += page_size
            if not batch or len(batch) < page_size or (total_count is not None and len(rows) >= total_count):
                break
        return rows[:max_records]

    async def match(self, match_id: str) -> dict[str, Any]:
        payload = await self._get(f"matches/{match_id}")
        if isinstance(payload, list):
            return dict(payload[0] if payload else {})
        return dict(payload or {})

    async def last_five(self, team_id: str) -> list[dict[str, Any]]:
        payload = await self._get("last-five-games", params={"teamId": team_id})
        return list(payload.get("data") or []) if isinstance(payload, dict) else list(payload or [])

    async def team_statistics(self, team_id: str, from_date: str, timezone: str) -> list[dict[str, Any]]:
        payload = await self._get(f"teams/statistics/{team_id}", params={"fromDate": from_date, "timezone": timezone})
        return list(payload.get("data") or []) if isinstance(payload, dict) else list(payload or [])

    async def statistics(self, match_id: str) -> list[dict[str, Any]]:
        payload = await self._get(f"statistics/{match_id}")
        if not payload:
            return []
        return list(payload) if isinstance(payload, list) else list(payload.get("data") or [])

    async def prematch_odds(self, match_id: str) -> dict[str, Any]:
        payload = await self._get("odds", params={
            "matchId": match_id,
            "bookmakerName": self.settings.highlightly_bookmaker,
            "oddsType": "prematch",
            "limit": 5,
        })
        return dict(payload or {}) if isinstance(payload, dict) else {"data": list(payload or [])}

    async def live_odds(self, match_id: str) -> dict[str, Any]:
        """Live odds for a shortlisted candidate only. Absence is non-fatal upstream."""
        payload = await self._get("odds", params={
            "matchId": match_id,
            "bookmakerName": self.settings.highlightly_bookmaker,
            "oddsType": "live",
            "limit": 5,
        })
        return dict(payload or {}) if isinstance(payload, dict) else {"data": list(payload or [])}

    async def events(self, match_id: str) -> list[dict[str, Any]]:
        payload = await self._get(f"events/{match_id}")
        if not payload:
            return []
        return list(payload) if isinstance(payload, list) else list(payload.get("data") or [])

    def usage(self) -> dict[str, dict[str, int]]:
        return {
            "requests": dict(self.request_counts),
            "errors": dict(self.error_counts),
            "latency_ms": dict(self.latency_ms),
        }
