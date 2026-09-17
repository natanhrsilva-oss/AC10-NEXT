from __future__ import annotations

from ac10next.domain.models import PregameContext, TeamProfile


def team_profile_from_row(row: dict) -> TeamProfile:
    return TeamProfile(
        team_id=str(row["team_id"]),
        team_name=str(row.get("team_name") or ""),
        recent_matches=int(row.get("recent_matches") or 0),
        history_matches=int(row.get("history_matches") or 0),
        recent_form=float(row.get("recent_form") or 50),
        attack=float(row.get("attack") or 50),
        defense=float(row.get("defense") or 50),
        weight=float(row.get("weight") or 50),
        avg_gf=float(row.get("avg_gf") or 1.25),
        avg_ga=float(row.get("avg_ga") or 1.25),
        over25_rate=float(row.get("over25_rate") or 50),
        competition_history_strength=float(row.get("competition_history_strength") or 50),
        opponent_strength=float(row.get("opponent_strength") or 50),
        data_quality=float(row.get("data_quality") or 0),
        source=str(row.get("source") or ""),
        last_match_id=row.get("last_match_id"),
        valid_until=row.get("valid_until"),
        raw=dict(row.get("raw") or {}),
    )


def pregame_from_row(row: dict) -> PregameContext:
    """Map PostgreSQL rows to the pure-domain PRE contract.

    psycopg returns NUMERIC as Decimal. The LIVE engine intentionally uses float
    arithmetic, so every numeric field is normalized here once at the boundary.
    """
    keys = PregameContext.__dataclass_fields__.keys()
    values = {k: row.get(k) for k in keys}
    float_fields = {
        "data_quality", "competition_priority", "home_attack", "home_defense", "home_weight", "home_recent_form",
        "away_attack", "away_defense", "away_weight", "away_recent_form", "expected_home_goals", "expected_away_goals",
        "expected_total_goals", "league_avg_goals", "league_over25_rate", "back_home_probability", "back_away_probability",
        "goals_probability", "back_home_index", "back_away_index", "goals_index", "selected_probability", "selected_index",
        "market_margin", "confidence", "draw_risk", "goals_profile", "explosive_score", "live_readiness_score",
        "home_odd", "draw_odd", "away_odd", "over25_odd",
    }
    for field in float_fields:
        value = values.get(field)
        values[field] = float(value) if value is not None else None
    values["raw"] = dict(row.get("raw") or {})
    return PregameContext(**values)
