from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ac10next.domain.models import MatchRecord, LiveStats
from ac10next.utils import clamp, normalize_name, number

LIVE_STATES = {
    "first half", "second half", "in progress", "half time", "first-half", "second-half",
    "1st half", "2nd half", "live",
}
FINISHED_STATES = {"finished", "full time", "ended", "after penalties", "after extra time"}


def parse_score(match: dict[str, Any]) -> tuple[int, int]:
    state = match.get("state") or {}
    score = state.get("score") or {}
    current = score.get("current") if isinstance(score, dict) else score
    if isinstance(current, str) and "-" in current:
        left, right = current.split("-", 1)
        return int(number(left, 0)), int(number(right, 0))
    if isinstance(score, dict):
        return int(number(score.get("home"), 0)), int(number(score.get("away"), 0))
    return 0, 0


def normalize_state(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def parse_live_minute(raw: dict[str, Any], now: datetime | None = None) -> int:
    state = raw.get("state") or {}
    description = normalize_state(state.get("description"))
    for key in ("clock", "minute", "elapsed", "time"):
        value = state.get(key)
        if isinstance(value, dict):
            value = next((value.get(k) for k in ("minute", "elapsed", "current", "value", "clock") if value.get(k) not in (None, "")), None)
        if value not in (None, ""):
            if isinstance(value, (int, float)) and float(value) > 0:
                return int(float(value))
            text = str(value).strip()
            added = re.fullmatch(r"\s*(\d{1,3})\s*\+\s*(\d{1,2})\s*'?\s*", text)
            if added:
                return int(added.group(1)) + int(added.group(2))
            clock = re.match(r"\s*(\d{1,3})(?::\d{1,2})?\s*'?", text)
            if clock and int(clock.group(1)) > 0:
                return int(clock.group(1))
    if description == "half time":
        return 45
    if description not in LIVE_STATES:
        return 0
    kickoff = parse_kickoff(raw, "UTC")
    if not kickoff:
        return 0
    current = now or datetime.now(kickoff.tzinfo or ZoneInfo("UTC"))
    wall = int(max(0, (current - kickoff).total_seconds()) // 60)
    if description in {"first half", "first-half", "1st half"}:
        return min(wall, 45)
    if description in {"second half", "second-half", "2nd half"}:
        return min(90, max(46, wall - 15))
    if wall > 60:
        wall -= 15
    return min(120, wall)


def parse_kickoff(raw: dict[str, Any], timezone: str) -> datetime | None:
    value = next((raw.get(k) for k in ("date", "startTime", "start_time", "kickoff", "kickoffTime", "fixtureDate", "eventDate", "gameDate") if raw.get(k) not in (None, "")), None)
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone))
        return dt.astimezone(ZoneInfo(timezone))
    except (TypeError, ValueError):
        return None


def match_record(raw: dict[str, Any], timezone: str) -> MatchRecord | None:
    home = raw.get("homeTeam") or raw.get("home") or {}
    away = raw.get("awayTeam") or raw.get("away") or {}
    league = raw.get("league") or raw.get("competition") or {}
    country = raw.get("country") or {}
    kickoff = parse_kickoff(raw, timezone)
    if not kickoff:
        return None
    state = raw.get("state") or {}
    home_score, away_score = parse_score(raw)
    season_raw = raw.get("season") or (league.get("season") if isinstance(league, dict) else None)
    season = int(number(season_raw, 0)) or None
    return MatchRecord(
        match_id=str(raw.get("id") or raw.get("matchId") or ""),
        kickoff=kickoff,
        match_date=kickoff.date().isoformat(),
        country=str(country.get("name") if isinstance(country, dict) else country or ""),
        competition_id=str(league.get("id") if isinstance(league, dict) else raw.get("leagueId") or ""),
        competition=str(league.get("name") if isinstance(league, dict) else league or ""),
        season=season,
        home_team_id=str(home.get("id") if isinstance(home, dict) else ""),
        home_team=str(home.get("name") if isinstance(home, dict) else home or ""),
        away_team_id=str(away.get("id") if isinstance(away, dict) else ""),
        away_team=str(away.get("name") if isinstance(away, dict) else away or ""),
        state=str(state.get("description") if isinstance(state, dict) else state or ""),
        minute=parse_live_minute(raw),
        home_score=home_score,
        away_score=away_score,
        raw=raw,
    )


def statistics_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for team_row in rows:
        team = team_row.get("team") or {}
        team_id = str(team.get("id") or team.get("name") or len(result))
        values: dict[str, float] = {}
        for stat in team_row.get("statistics") or []:
            name = normalize_name(str(stat.get("displayName") or stat.get("name") or ""))
            values[name] = number(stat.get("value"), 0)
        result[team_id] = values
    return result


def _first_stat(stats: dict[str, float], *names: str) -> float | None:
    for name in names:
        key = normalize_name(name)
        if key in stats:
            return number(stats[key], 0.0)
    return None


def _shot_metrics(stats: dict[str, float]) -> tuple[float, float]:
    total = _first_stat(stats, "Total shots", "Shots", "Shot attempts", "Total shot attempts", "Goal attempts", "Total attempts")
    sot = _first_stat(stats, "Shots on target", "Shots on goal", "On target", "Goal attempts on target")
    off = _first_stat(stats, "Shots off target", "Off target", "Shots wide", "Missed shots")
    blocked = _first_stat(stats, "Blocked shots", "Shots blocked", "Blocked attempts")
    if total is None and sum(x is not None for x in (sot, off, blocked)) >= 2:
        total = sum(number(x, 0) for x in (sot, off, blocked))
    return max(number(total, 0), number(sot, 0)), max(0.0, number(sot, 0))


def live_stats(rows: list[dict[str, Any]], home_team_id: str, away_team_id: str) -> LiveStats:
    maps = statistics_map(rows)
    h = maps.get(str(home_team_id), {})
    a = maps.get(str(away_team_id), {})
    hs, hsot = _shot_metrics(h)
    aws, asot = _shot_metrics(a)
    hc = number(_first_stat(h, "Corner kicks", "Corners", "Corner"), 0)
    ac = number(_first_stat(a, "Corner kicks", "Corners", "Corner"), 0)
    hd = number(_first_stat(h, "Dangerous attacks", "Dangerous attack"), 0)
    ad = number(_first_stat(a, "Dangerous attacks", "Dangerous attack"), 0)
    hp = number(_first_stat(h, "Ball possession", "Possession", "Possession percentage"), 50)
    ap = number(_first_stat(a, "Ball possession", "Possession", "Possession percentage"), 50)
    if 0 < hp <= 1:
        hp *= 100
    if 0 < ap <= 1:
        ap *= 100
    hr = number(_first_stat(h, "Red cards", "Red card"), 0)
    ar = number(_first_stat(a, "Red cards", "Red card"), 0)
    available = any(v > 0 for v in (hs, hsot, aws, asot, hc, ac, hd, ad)) or abs(hp - 50) > 0.5 or abs(ap - 50) > 0.5
    completeness = 0.0
    completeness += 30 if hs + aws > 0 else 0
    completeness += 30 if hsot + asot > 0 else 0
    completeness += 20 if hd + ad > 0 else 0
    completeness += 10 if hc + ac > 0 else 0
    completeness += 10 if hp + ap > 0 else 0
    return LiveStats(
        home_shots=hs, away_shots=aws, home_sot=hsot, away_sot=asot,
        home_corners=hc, away_corners=ac, home_dangerous=hd, away_dangerous=ad,
        home_possession=clamp(hp, 0, 100), away_possession=clamp(ap, 0, 100),
        home_red_cards=hr, away_red_cards=ar, available=available,
        data_mode="FULL_STATS" if available else "HISTORICAL_ONLY",
        data_quality=clamp(35 + completeness * 0.65, 0, 100) if available else 20.0,
        raw={"statistics": rows},
    )


def _market_name(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().replace("_", " ").split())


def _valid_odd(value: Any) -> float:
    odd = number(value, 0)
    return odd if 1.001 <= odd <= 100.0 else 0.0


def _iter_odds_markets(payload: dict[str, Any], bookmaker: str, allowed_types: set[str]) -> list[dict[str, Any]]:
    rows = payload.get("data") or [] if isinstance(payload, dict) else []
    target_bookmaker = normalize_name(bookmaker)
    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        for market in row.get("odds") or []:
            if not isinstance(market, dict):
                continue
            market_bookmaker = normalize_name(str(market.get("bookmakerName") or market.get("bookmaker") or ""))
            if market_bookmaker and market_bookmaker != target_bookmaker:
                continue
            odds_type = normalize_name(str(market.get("type") or "prematch"))
            if odds_type and odds_type not in allowed_types:
                continue
            out.append(market)
    return out


def _market_line(market: dict[str, Any]) -> float | None:
    for key in ("line", "total", "handicap", "variant"):
        if market.get(key) not in (None, ""):
            m = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", str(market.get(key)))
            if m:
                return number(m.group(1), -999)
    # Highlightly often embeds the variant in the market name: "Total Goals 2.5".
    name = str(market.get("market") or market.get("name") or "")
    m = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", name)
    return number(m.group(1), -999) if m else None


def _full_time_result(markets: list[dict[str, Any]]) -> dict[str, float]:
    result = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for market in markets:
        name = _market_name(market.get("market") or market.get("name"))
        if name not in {"FULL TIME RESULT", "1X2", "ML", "MONEYLINE", "3-WAY MONEYLINE", "3 WAY MONEYLINE"}:
            continue
        parsed: dict[str, float] = {}
        for item in market.get("values") or []:
            label = _market_name(item.get("value") or item.get("name"))
            odd = _valid_odd(item.get("odd"))
            if label == "HOME" and odd:
                parsed["home"] = odd
            elif label == "DRAW" and odd:
                parsed["draw"] = odd
            elif label == "AWAY" and odd:
                parsed["away"] = odd
        home, draw, away = parsed.get("home", 0.0), parsed.get("draw", 0.0), parsed.get("away", 0.0)
        if home and away:
            implied = 1 / home + 1 / away + (1 / draw if draw else 0)
            if 0.75 <= implied <= 1.65:
                result.update({"home": home, "draw": draw, "away": away})
                break
    return result


def _total_over(markets: list[dict[str, Any]], target_line: float) -> float:
    best = 0.0
    for market in markets:
        name = _market_name(market.get("market") or market.get("name"))
        if not (name.startswith("TOTAL GOALS") or name in {"TOTALS", "MATCH TOTALS", "GOALS OVER/UNDER"}):
            continue
        base_line = _market_line(market)
        over = under = 0.0
        for item in market.get("values") or []:
            label_text = str(item.get("value") or item.get("name") or "")
            item_line = base_line
            if item_line is None or item_line < 0:
                lm = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", label_text)
                item_line = number(lm.group(1), -999) if lm else -999
            if abs(float(item_line) - float(target_line)) > 0.001:
                continue
            odd = _valid_odd(item.get("odd"))
            label = _market_name(label_text)
            if label.startswith("OVER") and odd:
                over = odd
            elif label.startswith("UNDER") and odd:
                under = odd
        if over:
            # Under may be absent in some live feeds; when present use it as sanity check.
            if not under or 0.70 <= (1 / over + 1 / under) <= 1.65:
                best = over
                break
    return best


def extract_highlightly_main_odds(payload: dict[str, Any], bookmaker: str = "Bet365") -> dict[str, float]:
    result = {"home": 0.0, "draw": 0.0, "away": 0.0, "over25": 0.0, "under25": 0.0}
    markets = _iter_odds_markets(payload, bookmaker, {"prematch", "pre match"})
    result.update(_full_time_result(markets))
    result["over25"] = _total_over(markets, 2.5)
    # capture under 2.5 for diagnostics without changing the PRE logic
    for market in markets:
        name = _market_name(market.get("market") or market.get("name"))
        if not (name.startswith("TOTAL GOALS") or name in {"TOTALS", "MATCH TOTALS", "GOALS OVER/UNDER"}):
            continue
        line = _market_line(market)
        if line is None or abs(line - 2.5) > 0.001:
            continue
        for item in market.get("values") or []:
            if _market_name(item.get("value") or item.get("name")).startswith("UNDER"):
                result["under25"] = _valid_odd(item.get("odd"))
    return result


def extract_highlightly_live_market_odd(
    payload: dict[str, Any],
    market: str,
    home_score: int,
    away_score: int,
    bookmaker: str = "Bet365",
) -> float:
    """Return an odd only when Highlightly exposes an equivalent supported market.

    Highlightly officially exposes Full Time Result and Total Goals among its
    football odds markets. Therefore BACK Casa/Visitante can be priced directly;
    OVER +1 GOL (and legacy GOL FT) is mapped to Full Time Total Goals at the
    current score + 0.5. Directional goal and GOL HT are deliberately left
    unpriced instead of guessing an unrelated market.
    """
    markets = _iter_odds_markets(payload, bookmaker, {"live"})
    target = _market_name(market)
    if target == "BACK CASA":
        return _full_time_result(markets)["home"]
    if target == "BACK VISITANTE":
        return _full_time_result(markets)["away"]
    if target in {"OVER +1 GOL", "GOL FT"}:
        return _total_over(markets, float(home_score + away_score) + 0.5)
    return 0.0


def event_minute(value: Any) -> tuple[int, int]:
    """Parse Highlightly event time such as 45+1 into (base_minute, added)."""
    text = str(value or "").strip().replace("'", "")
    m = re.match(r"^(\d{1,3})(?:\+(\d{1,2}))?", text)
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2) or 0)


def first_half_goal_count(events: list[dict[str, Any]]) -> int:
    """Estimate official first-half goals from Highlightly live events.

    A VAR confirmation does not add a second goal. A VAR cancellation removes the
    most recent still-counted goal in the same short time neighbourhood.
    """
    counted: list[tuple[int, int]] = []
    for event in events or []:
        base, added = event_minute(event.get("time"))
        if base <= 0 or base > 45:
            continue
        kind = normalize_name(str(event.get("type") or ""))
        if kind in {"goal", "own goal", "penalty"}:
            counted.append((base, added))
        elif kind in {"var goal cancelled", "var goal cancelled offside"} and counted:
            current = base + added / 100.0
            # VAR cancellation normally follows the just-recorded goal.
            for i in range(len(counted) - 1, -1, -1):
                gbase, gadded = counted[i]
                gtime = gbase + gadded / 100.0
                if 0 <= current - gtime <= 4.5:
                    counted.pop(i)
                    break
    return len(counted)
