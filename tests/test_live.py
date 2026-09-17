from datetime import datetime, timezone

from ac10next.domain.models import LiveInput
from ac10next.engines.live.engine import analyze

from conftest import make_match, make_pre, make_stats


def test_back_only_window_never_selects_goal_market():
    inp = LiveInput(match=make_match(minute=52), pre=make_pre(), stats=make_stats(), captured_at=datetime.now(timezone.utc))
    out = analyze(inp, previous=None, history=[])
    assert out.selected_market in {"BACK CASA", "BACK VISITANTE"}
    assert out.selected_market not in {"GOL HT", "GOL FT", "GOL MANDANTE", "GOL VISITANTE"}


def test_first_scan_is_marked_without_fake_delta():
    inp = LiveInput(match=make_match(minute=72, home_score=1, away_score=1), pre=make_pre(), stats=make_stats(), captured_at=datetime.now(timezone.utc))
    out = analyze(inp, previous=None, history=[])
    assert out.gpi_delta is None
    assert out.raw["comparison_ok"] is False
    assert out.price_status == "SEM PREÇO LIVE"


def test_late_goal_window_never_falls_back_to_generic_gol_ft():
    inp = LiveInput(match=make_match(minute=72, home_score=1, away_score=1), pre=make_pre(), stats=make_stats(), captured_at=datetime.now(timezone.utc))
    out = analyze(inp, previous=None, history=[])
    assert out.selected_market != "GOL FT"
    assert out.selected_market in {"OVER +1 GOL", "GOL MANDANTE", "GOL VISITANTE", "BACK CASA", "BACK VISITANTE"}
