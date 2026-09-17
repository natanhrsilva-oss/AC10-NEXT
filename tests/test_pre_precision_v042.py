from ac10next.engines.pregame.precision import decorate_precision, is_high_confidence
from ac10next.settings import Settings
from conftest import make_pre


def strong_pre():
    c=make_pre()
    c.raw["specialists"]={"BACK CASA":{"status":"RECOMENDAÇÃO","risks":[]}}
    c.selected_market="BACK CASA"
    c.selected_probability=72
    c.selected_index=78
    c.confidence=76
    c.data_quality=80
    c.market_margin=9
    c.draw_risk=38
    return c

def test_pre_can_recommend_without_odd():
    c=strong_pre(); c.home_odd=None
    s=Settings(_env_file=None); decorate_precision(c,s)
    assert is_high_confidence(c,s) is True
    assert c.raw["precision"]["qualifies"] is True
    assert "sem_odd" not in c.raw["precision"]["rejection_reasons"]

def test_pre_bad_price_is_informational_not_blocking():
    c=strong_pre(); c.home_odd=1.20
    s=Settings(_env_file=None); decorate_precision(c,s)
    assert is_high_confidence(c,s) is True
    assert c.raw["precision"]["odd"] == 1.20
