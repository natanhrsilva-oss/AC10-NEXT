from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ac10next.domain.models import MatchRecord, PregameFeatures, TeamProfile
from ac10next.utils import clamp, normalize_name, number, poisson_over_25


def team_form(games: list[dict[str, Any]], team_id: str) -> dict[str, float]:
    wins = draws = scored = conceded = over = played = 0
    for game in games:
        home = game.get("homeTeam") or {}
        away = game.get("awayTeam") or {}
        state = game.get("state") or {}
        score = state.get("score") or {}
        current = score.get("current") if isinstance(score, dict) else score
        if isinstance(current, str) and "-" in current:
            left, right = current.split("-", 1)
            hs, aws = int(number(left, 0)), int(number(right, 0))
        else:
            hs = int(number(score.get("home") if isinstance(score, dict) else 0, 0))
            aws = int(number(score.get("away") if isinstance(score, dict) else 0, 0))
        if str(home.get("id")) == str(team_id):
            gf, ga = hs, aws
        elif str(away.get("id")) == str(team_id):
            gf, ga = aws, hs
        else:
            continue
        played += 1
        scored += gf
        conceded += ga
        wins += int(gf > ga)
        draws += int(gf == ga)
        over += int(gf + ga >= 3)
    if not played:
        return {"form": 50.0, "form_points": 50.0, "gf": 1.25, "ga": 1.25, "over": 50.0, "quality": 20.0, "matches": 0.0}
    return {
        "form": wins / played * 100.0,
        "form_points": (3 * wins + draws) / (3 * played) * 100.0,
        "gf": scored / played,
        "ga": conceded / played,
        "over": over / played * 100.0,
        "quality": min(100.0, played * 18.0),
        "matches": float(played),
    }


def _aggregate(rows: list[dict[str, Any]], block_name: str) -> dict[str, Any]:
    played = wins = draws = losses = gf = ga = 0.0
    for row in rows:
        block = row.get(block_name) or {}
        games = block.get("games") or {} if isinstance(block, dict) else {}
        goals = block.get("goals") or {} if isinstance(block, dict) else {}
        p = number(games.get("played"), 0)
        if p <= 0:
            continue
        played += p
        wins += number(games.get("wins"), 0)
        draws += number(games.get("draws"), 0)
        losses += number(games.get("loses"), number(games.get("losses"), 0))
        if isinstance(goals, dict):
            gf += number(goals.get("scored"), 0)
            ga += number(goals.get("received"), number(goals.get("conceded"), 0))
    if played < 3:
        return {"available": False, "matches": int(played), "quality": 0.0}
    avg_gf, avg_ga = gf / played, ga / played
    strength = (3 * wins + draws) / (3 * played) * 100.0
    return {
        "available": True,
        "matches": int(played),
        "avg_gf": avg_gf,
        "avg_ga": avg_ga,
        "attack": clamp(34 + avg_gf * 23, 20, 90),
        "defense": clamp(86 - avg_ga * 22, 15, 90),
        "historical_strength": strength,
        "over25_rate": poisson_over_25(max(0.2, avg_gf + avg_ga)) * 100.0,
        "quality": clamp(32 + min(played, 60) * 1.05, 35, 95),
    }


def history_profile(rows: list[dict[str, Any]], recent: dict[str, float]) -> dict[str, Any]:
    total = _aggregate(rows, "total")
    if not total.get("available"):
        return total
    total["form"] = number(recent.get("form_points"), total["historical_strength"]) if recent.get("matches", 0) else total["historical_strength"]
    total["weight"] = clamp(total["attack"] * .38 + total["defense"] * .32 + total["form"] * .30, 20, 90)
    total["home_split"] = _aggregate(rows, "home")
    total["away_split"] = _aggregate(rows, "away")
    profiles: dict[str, Any] = {}
    for row in rows:
        league = row.get("league") or {}
        league_id = str(row.get("leagueId") or (league.get("id") if isinstance(league, dict) else "") or "")
        league_name = str(row.get("leagueName") or (league.get("name") if isinstance(league, dict) else "") or "")
        season = str(row.get("season") or "")
        key = f"{league_id}|{normalize_name(league_name)}|{season}"
        profiles[key] = {
            "league_id": league_id,
            "league_name": league_name,
            "season": season,
            "total": _aggregate([row], "total"),
            "home": _aggregate([row], "home"),
            "away": _aggregate([row], "away"),
        }
    total["competition_profiles"] = profiles
    return total


def make_team_profile(team_id: str, team_name: str, recent_games: list[dict[str, Any]], history_rows: list[dict[str, Any]], cache_hours: int) -> TeamProfile:
    recent = team_form(recent_games, team_id)
    hist = history_profile(history_rows, recent)
    has_hist = bool(hist.get("available"))
    recent_attack = clamp(34 + number(recent.get("gf"), 1.25) * 23, 20, 90)
    recent_defense = clamp(86 - number(recent.get("ga"), 1.25) * 22, 15, 90)
    recent_form = number(recent.get("form_points"), 50)
    if has_hist:
        attack = recent_attack * .75 + number(hist.get("attack"), recent_attack) * .25
        defense = recent_defense * .75 + number(hist.get("defense"), recent_defense) * .25
        hist_strength = number(hist.get("historical_strength"), 50)
        quality = clamp(number(recent.get("quality"), 20) * .72 + number(hist.get("quality"), 0) * .28, 20, 96)
        avg_gf = number(hist.get("avg_gf"), recent.get("gf", 1.25))
        avg_ga = number(hist.get("avg_ga"), recent.get("ga", 1.25))
        over = number(hist.get("over25_rate"), recent.get("over", 50))
    else:
        attack, defense, hist_strength = recent_attack, recent_defense, recent_form
        quality = clamp(number(recent.get("quality"), 20) * .90, 20, 88)
        avg_gf, avg_ga, over = number(recent.get("gf"), 1.25), number(recent.get("ga"), 1.25), number(recent.get("over"), 50)
    weight = clamp(attack * .38 + defense * .32 + recent_form * .30, 20, 90)
    return TeamProfile(
        team_id=team_id,
        team_name=team_name,
        recent_matches=int(number(recent.get("matches"), 0)),
        history_matches=int(number(hist.get("matches"), 0)),
        recent_form=recent_form,
        attack=attack,
        defense=defense,
        weight=weight,
        avg_gf=avg_gf,
        avg_ga=avg_ga,
        over25_rate=over,
        competition_history_strength=hist_strength,
        opponent_strength=hist_strength,
        data_quality=quality,
        source="highlightly:recent5+stats2y" if has_hist else "highlightly:recent5",
        valid_until=datetime.now().astimezone() + timedelta(hours=max(1, cache_hours)),
        raw={"recent": recent, "history": hist},
    )


def _context(profile: TeamProfile, match: MatchRecord, venue: str) -> dict[str, Any]:
    hist = profile.raw.get("history") or {}
    cps = hist.get("competition_profiles") or {}
    normalized = normalize_name(match.competition)
    season = str(match.season or "")
    candidates = list(cps.values())
    def same(item: dict[str, Any]) -> bool:
        return bool((match.competition_id and str(item.get("league_id") or "") == str(match.competition_id)) or (normalized and normalize_name(str(item.get("league_name") or "")) == normalized))
    exact = [i for i in candidates if same(i) and season and str(i.get("season") or "") == season]
    previous = [i for i in candidates if same(i) and i not in exact]
    for group in (exact, previous):
        for item in group:
            selected = item.get(venue) or item.get("total") or {}
            if selected.get("available"):
                return selected
    split = hist.get(f"{venue}_split") or {}
    if split.get("available"):
        return split
    return hist if hist.get("available") else {}


def build_features(match: MatchRecord, home: TeamProfile, away: TeamProfile, recent_weight: float = .75, historical_weight: float = .25) -> PregameFeatures:
    hr = home.raw.get("recent") or {}
    ar = away.raw.get("recent") or {}
    hctx, actx = _context(home, match, "home"), _context(away, match, "away")
    hist_available = bool(hctx.get("available") and actx.get("available"))
    min_recent = min(home.recent_matches, away.recent_matches)
    if hist_available:
        if min_recent >= 5: rw, hw = .65, .35
        elif min_recent >= 3: rw, hw = .55, .45
        else: rw, hw = .45, .55
    else:
        total = max(.01, recent_weight + historical_weight)
        rw, hw = 1.0, 0.0

    hra = clamp(34 + number(hr.get("gf"), 1.25) * 23, 20, 90)
    hrd = clamp(86 - number(hr.get("ga"), 1.25) * 22, 15, 90)
    ara = clamp(34 + number(ar.get("gf"), 1.25) * 23, 20, 90)
    ard = clamp(86 - number(ar.get("ga"), 1.25) * 22, 15, 90)
    hrf, arf = number(hr.get("form_points"), home.recent_form), number(ar.get("form_points"), away.recent_form)
    hrw = clamp(hra*.38 + hrd*.32 + hrf*.30, 20, 90)
    arw = clamp(ara*.38 + ard*.32 + arf*.30, 20, 90)

    hha, hhd = number(hctx.get("attack"), hra), number(hctx.get("defense"), hrd)
    aha, ahd = number(actx.get("attack"), ara), number(actx.get("defense"), ard)
    hhf = number(hctx.get("historical_strength"), home.competition_history_strength)
    ahf = number(actx.get("historical_strength"), away.competition_history_strength)
    hhw = clamp(hha*.38 + hhd*.32 + hhf*.30, 20, 90)
    ahw = clamp(aha*.38 + ahd*.32 + ahf*.30, 20, 90)

    home_attack = clamp(hra*rw + hha*hw, 15, 92)
    home_defense = clamp(hrd*rw + hhd*hw, 15, 92)
    away_attack = clamp(ara*rw + aha*hw, 15, 92)
    away_defense = clamp(ard*rw + ahd*hw, 15, 92)
    home_weight = clamp(hrw*rw + hhw*hw, 15, 92)
    away_weight = clamp(arw*rw + ahw*hw, 15, 92)

    rxh = clamp((number(hr.get("gf"),1.25)+number(ar.get("ga"),1.25))/2, .25, 3.5)
    rxa = clamp((number(ar.get("gf"),1.25)+number(hr.get("ga"),1.25))/2, .25, 3.5)
    hxh = clamp((number(hctx.get("avg_gf"),rxh)+number(actx.get("avg_ga"),rxh))/2,.25,3.5)
    hxa = clamp((number(actx.get("avg_gf"),rxa)+number(hctx.get("avg_ga"),rxa))/2,.25,3.5)
    xh, xa = clamp(rxh*rw+hxh*hw,.25,3.5), clamp(rxa*rw+hxa*hw,.25,3.5)

    recent_over = (number(hr.get("over"),50)+number(ar.get("over"),50))/2
    hist_over = (number(hctx.get("over25_rate"),recent_over)+number(actx.get("over25_rate"),recent_over))/2
    over = clamp(recent_over*rw+hist_over*hw,10,90)
    recent_avg = (number(hr.get("gf"),1.25)+number(hr.get("ga"),1.25)+number(ar.get("gf"),1.25)+number(ar.get("ga"),1.25))/2
    hist_avg = (number(hctx.get("avg_gf"),1.25)+number(hctx.get("avg_ga"),1.25)+number(actx.get("avg_gf"),1.25)+number(actx.get("avg_ga"),1.25))/2
    avg = clamp(recent_avg*rw+hist_avg*hw,1,5)
    quality = clamp((home.data_quality+away.data_quality)/2,20,96)
    return PregameFeatures(
        match=match,
        home_attack=home_attack, home_defense=home_defense, home_weight=home_weight, home_recent_form=hrf,
        away_attack=away_attack, away_defense=away_defense, away_weight=away_weight, away_recent_form=arf,
        expected_home_goals=xh, expected_away_goals=xa, expected_total_goals=xh+xa,
        league_avg_goals=avg, league_over25_rate=over,
        home_competition_history_strength=hhf, away_competition_history_strength=ahf,
        home_opponent_strength=clamp(hhf*.70+home.competition_history_strength*.30,20,90),
        away_opponent_strength=clamp(ahf*.70+away.competition_history_strength*.30,20,90),
        data_quality=quality,
        raw={"home_profile": home.raw, "away_profile": away.raw, "recent_weight": rw, "history_weight": hw},
    )
