from ac10next.engines.pregame.meta import _draw_risk
from ac10next.engines.pregame.precision import decorate_precision, is_high_confidence
from ac10next.settings import Settings
from conftest import make_pre


def test_draw_risk_without_odds_is_not_artificially_inflated():
    c=make_pre()
    # make_pre returns PregameContext, so validate recommendation behavior directly
    c.selected_market='BACK CASA'; c.selected_probability=82; c.selected_index=88
    c.confidence=84; c.data_quality=82; c.market_margin=10; c.draw_risk=68
    c.home_odd=None
    c.raw['specialists']={'BACK CASA':{'status':'RECOMENDAÇÃO','risks':[]}}
    s=Settings(_env_file=None)
    decorate_precision(c,s)
    assert 'risco_empate_alto' not in c.raw['precision']['rejection_reasons']
    assert is_high_confidence(c,s)


def test_draw_risk_attention_is_soft_flag_only():
    c=make_pre(); c.selected_market='BACK CASA'; c.selected_probability=75; c.selected_index=80
    c.confidence=78; c.data_quality=80; c.market_margin=8; c.draw_risk=60
    c.raw['specialists']={'BACK CASA':{'status':'RECOMENDAÇÃO','risks':[]}}
    s=Settings(_env_file=None); decorate_precision(c,s)
    assert 'risco_empate_atencao' in c.raw['precision']['soft_flags']
    assert 'risco_empate_alto' not in c.raw['precision']['rejection_reasons']
