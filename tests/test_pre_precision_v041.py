from ac10next.engines.pregame.precision import decorate_precision, is_high_confidence
from ac10next.settings import Settings

from conftest import make_pre


def test_pre_observation_can_qualify_when_precision_and_price_are_good():
    c = make_pre()
    c.raw["specialists"] = {
        "BACK CASA": {"status": "OBSERVAÇÃO", "risks": []}
    }
    c.selected_probability = 64
    c.selected_index = 68
    c.confidence = 66
    c.data_quality = 76
    c.market_margin = 6
    c.draw_risk = 40
    c.home_odd = 1.72
    s = Settings(_env_file=None)
    decorate_precision(c, s)
    assert is_high_confidence(c, s) is True
    assert c.raw["precision"]["qualifies"] is True


def test_pre_rejected_specialist_still_does_not_qualify():
    c = make_pre()
    c.raw["specialists"] = {
        "BACK CASA": {"status": "REJEITADO", "risks": []}
    }
    c.home_odd = 1.90
    s = Settings(_env_file=None)
    decorate_precision(c, s)
    assert is_high_confidence(c, s) is False
    assert "especialista_rejeitado" in c.raw["precision"]["rejection_reasons"]
