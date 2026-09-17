from ac10next.engines.audit import evaluate_recommendation
from ac10next.engines.live.pricing import apply_no_price_requirement, apply_price
from ac10next.settings import Settings

from conftest import make_analysis


def test_price_guard_blocks_low_odd_recommendation():
    a = make_analysis(index=80, status="RECOMENDAÇÃO")
    a.selected_probability = 70
    s = Settings(_env_file=None)
    apply_price(a, 1.40, s)
    assert a.status == "SEM ENTRADA"
    assert a.price_status.startswith("ODD BAIXA")


def test_price_guard_accepts_positive_value():
    a = make_analysis(index=80, status="RECOMENDAÇÃO")
    a.selected_probability = 60
    a.fair_odd = 1 / .60
    s = Settings(_env_file=None)
    apply_price(a, 1.80, s)
    assert a.status == "RECOMENDAÇÃO"
    assert a.price_status == "PREÇO OK"
    assert a.ev_percent > 0


def test_ht_audit_uses_first_half_goals_after_entry_score():
    rec = {"market":"GOL HT", "market_odd":1.80, "payload":{"entry_home_score":0,"entry_away_score":0}}
    result, pnl, detail = evaluate_recommendation(rec, 2, 1, ht_goals=1)
    assert result == "GREEN"
    assert round(pnl, 2) == .80
    assert detail["ht_goals"] == 1


def test_unpriced_signal_does_not_invent_profit():
    rec = {"market":"BACK CASA", "market_odd":None, "payload":{"entry_home_score":0,"entry_away_score":0}}
    result, pnl, detail = evaluate_recommendation(rec, 2, 1)
    assert result == "GREEN"
    assert pnl == 0.0
    assert detail["pnl_priced"] is False


def test_live_default_does_not_require_odd():
    s = Settings(_env_file=None)
    assert s.live_require_price_for_recommendation is False


def test_live_signal_promotes_without_odd():
    a = make_analysis(index=72, status="SINAL")
    apply_no_price_requirement(a)
    assert a.status == "RECOMENDAÇÃO"
    assert a.market_odd is None
    assert a.ev_percent is None
    assert a.price_status == "ODD NÃO EXIGIDA"
    assert a.raw["price"]["required"] is False
