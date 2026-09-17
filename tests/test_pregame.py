from ac10next.engines.pregame.meta import build_context
from ac10next.engines.pregame.profiles import build_features
from ac10next.engines.pregame.strategies import evaluate_all

from conftest import make_match, make_profile


def test_pregame_builds_contract_for_live():
    m = make_match()
    features = build_features(m, make_profile("h1", "Casa FC", strong=True), make_profile("a1", "Visitante FC", strong=False))
    features.competition_priority = 90
    ctx = build_context(features, evaluate_all(features), "AC10-NEXT-PRE-0.2.0")

    assert ctx.match_id == "m1"
    assert ctx.selected_market in {"BACK CASA", "BACK VISITANTE", "OVER 2,5 GOLS"}
    assert 0 <= ctx.selected_probability <= 100
    assert 0 <= ctx.live_readiness_score <= 100
    assert ctx.live_priority in {"A", "B", "C"}
    assert "home_profile" in ctx.raw
    assert "away_profile" in ctx.raw
    assert "specialists" in ctx.raw
