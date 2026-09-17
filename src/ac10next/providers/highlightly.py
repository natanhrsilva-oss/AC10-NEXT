from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from typing import Any

import httpx

from ac10next.settings import Settings
from ac10next.utils import normalize_name

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
        self._bookmaker_supported: bool | None = None
        self._bookmaker_check_done = False
        self._bookmaker_check_lock = asyncio.Lock()

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

    @staticmethod
    def _payload_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            rows = payload.get("data") or []
            return [dict(x) for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []
        if isinstance(payload, list):
            return [dict(x) for x in payload if isinstance(x, dict)]
        return []

    @staticmethod
    def _has_core_odds(payload: Any) -> bool:
        for row in HighlightlyClient._payload_rows(payload):
            for market in row.get("odds") or []:
                if not isinstance(market, dict):
                    continue
                name = normalize_name(str(market.get("market") or market.get("name") or ""))
                if name in {"full time result", "match result", "1x2", "1 x 2", "3-way moneyline", "3 way moneyline"}:
                    return True
                if name.startswith("total goals") or name in {"totals", "match totals", "over under", "over/under", "goals over/under"}:
                    return True
        return False

    async def _configured_bookmaker_is_supported(self) -> bool | None:
        """Check bookmaker catalogue once per run, even under concurrent odds calls."""
        if self._bookmaker_check_done:
            return self._bookmaker_supported
        async with self._bookmaker_check_lock:
            if self._bookmaker_check_done:
                return self._bookmaker_supported
            wanted = self.settings.highlightly_bookmaker.strip()
            if not wanted:
                self._bookmaker_supported = False
                self._bookmaker_check_done = True
                return False
            try:
                payload = await self._get("bookmakers", params={"name": wanted, "limit": 100, "offset": 0})
                rows = self._payload_rows(payload)
                target = normalize_name(wanted)
                self._bookmaker_supported = any(
                    normalize_name(str(row.get("name") or row.get("bookmakerName") or "")) == target
                    for row in rows
                )
                LOGGER.info("Highlightly bookmaker '%s' supported=%s", wanted, self._bookmaker_supported)
            except Exception as exc:
                self._bookmaker_supported = None
                LOGGER.info("Highlightly bookmaker catalogue unavailable (%s): %s", wanted, exc)
            self._bookmaker_check_done = True
            return self._bookmaker_supported

    async def _odds_with_fallback(self, match_id: str, odds_type: str) -> dict[str, Any]:
        base = {"matchId": match_id, "oddsType": odds_type, "limit": 5}
        wanted = self.settings.highlightly_bookmaker.strip()
        supported = await self._configured_bookmaker_is_supported() if wanted else False

        # Prefer the configured bookmaker when Highlightly advertises it, or when
        # the catalogue check was inconclusive. A 200 response with zero rows is
        # treated as "no coverage for this match", not as an API failure.
        if wanted and supported is not False:
            filtered = await self._get("odds", params={**base, "bookmakerName": wanted})
            if self._payload_rows(filtered) and self._has_core_odds(filtered):
                result = dict(filtered or {}) if isinstance(filtered, dict) else {"data": list(filtered or [])}
                result["_ac10_odds_query"] = {"mode": "preferred_bookmaker", "bookmaker": wanted}
                return result

        if self.settings.highlightly_odds_fallback_any_bookmaker:
            unfiltered = await self._get("odds", params=base)
            result = dict(unfiltered or {}) if isinstance(unfiltered, dict) else {"data": list(unfiltered or [])}
            result["_ac10_odds_query"] = {
                "mode": "any_bookmaker_fallback",
                "bookmaker": wanted or None,
                "preferred_supported": supported,
            }
            return result

        # Fallback disabled: preserve the old strict behaviour.
        strict = await self._get("odds", params={**base, **({"bookmakerName": wanted} if wanted else {})})
        result = dict(strict or {}) if isinstance(strict, dict) else {"data": list(strict or [])}
        result["_ac10_odds_query"] = {"mode": "strict", "bookmaker": wanted or None}
        return result

    async def prematch_odds(self, match_id: str) -> dict[str, Any]:
        return await self._odds_with_fallback(match_id, "prematch")

    async def live_odds(self, match_id: str) -> dict[str, Any]:
        """Live odds for a shortlisted candidate only. Absence is non-fatal upstream."""
        return await self._odds_with_fallback(match_id, "live")

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
