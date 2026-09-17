from dataclasses import replace
from datetime import datetime, timedelta, timezone

from ac10next.domain.models import LiveInput
from ac10next.engines.live.engine import analyze
from ac10next.engines.live.pricing import apply_price
from ac10next.engines.pregame.precision import select_pre_recommendations
from ac10next.settings import Settings

from conftest import make_analysis, make_match, make_pre, make_stats


def _qualified_pre(match_id: str, score_boost: float = 0.0):
    p = replace(make_pre(), match_id=match_id)
    p.selected_index = min(95, p.selected_index + score_boost)
    p.confidence = min(95, p.confidence + score_boost)
    p.raw = dict(p.raw)
    p.raw["specialists"] = {
        "BACK CASA": {"status": "RECOMENDAÇÃO", "risks": []},
        "BACK VISITANTE": {"status": "REJEITADO", "risks": []},
        "OVER 2,5 GOLS": {"status": "OBSERVAÇÃO", "risks": []},
    }
    return p


def test_pre_precision_sends_at_most_ten_and_can_send_zero():
    settings = Settings(_env_file=None)
    contexts = [_qualified_pre(f"m{i}", score_boost=i * .1) for i in range(12)]
    selected = select_pre_recommendations(contexts, settings)
    assert len(selected) == 10
    assert all((c.raw.get("precision") or {}).get("qualifies") for c in selected)

    weak = _qualified_pre("weak")
    weak.confidence = 40
    assert select_pre_recommendations([weak], settings) == []


def _previous_row(*, home_score: int, away_score: int, stale_scans: int = 0):
    captured = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "captured_at": captured,
        "minute": 67,
        "home_score": home_score,
        "away_score": away_score,
        "home_shots": 10,
        "away_shots": 3,
        "home_sot": 4,
        "away_sot": 1,
        "home_corners": 5,
        "away_corners": 2,
        "home_dangerous": 40,
        "away_dangerous": 15,
        "home_possession": 62,
        "away_possession": 38,
        "home_red_cards": 0,
        "away_red_cards": 0,
        "home_pressure": 70,
        "away_pressure": 35,
        "home_recent_pressure": 60,
        "away_recent_pressure": 25,
        "home_momentum": 12,
        "away_momentum": -2,
        "gpi": 70,
        "raw": {"data_freshness": {"stale_scans": stale_scans}},
    }


def test_recent_goal_reduces_next_goal_probability():
    stats = make_stats()
    now = datetime.now(timezone.utc)
    current = make_match(minute=72, home_score=2, away_score=1)
    inp = LiveInput(match=current, pre=make_pre(), stats=stats, captured_at=now)

    no_new_goal = analyze(inp, _previous_row(home_score=2, away_score=1), [])
    just_scored = analyze(inp, _previous_row(home_score=1, away_score=1), [])

    assert just_scored.raw["event_state"]["post_goal_active"] is True
    assert just_scored.raw["event_state"]["goal_factor"] == .75
    assert just_scored.chance_goal_10 < no_new_goal.chance_goal_10
    if not just_scored.selected_market.startswith("BACK"):
        assert just_scored.selected_probability < no_new_goal.selected_probability
        assert just_scored.status != "SINAL"


def test_stale_stats_are_flagged_after_repeated_unchanged_scans():
    stats = make_stats()
    previous = _previous_row(home_score=1, away_score=1, stale_scans=1)
    # Make previous metrics identical to current stats.
    previous.update({
        "home_shots": stats.home_shots, "away_shots": stats.away_shots,
        "home_sot": stats.home_sot, "away_sot": stats.away_sot,
        "home_corners": stats.home_corners, "away_corners": stats.away_corners,
        "home_dangerous": stats.home_dangerous, "away_dangerous": stats.away_dangerous,
    })
    inp = LiveInput(match=make_match(minute=72, home_score=1, away_score=1), pre=make_pre(), stats=stats, captured_at=datetime.now(timezone.utc))
    out = analyze(inp, previous, [])
    assert out.raw["data_freshness"]["stale_scans"] == 2
    assert out.raw["data_freshness"]["stale_block"] is True


def test_sporting_signal_becomes_recommendation_only_after_good_price():
    a = make_analysis(index=80, status="SINAL")
    a.selected_probability = 60
    a.fair_odd = 1 / .60
    s = Settings(_env_file=None)
    apply_price(a, 1.80, s)
    assert a.status == "RECOMENDAÇÃO"
    assert a.price_status == "PREÇO OK"
