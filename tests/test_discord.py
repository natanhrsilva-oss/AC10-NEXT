from copy import deepcopy

from ac10next.outputs.discord import live_summary

from conftest import make_analysis, make_match, make_pre


def test_live_discord_contract():
    m = make_match(minute=72, home_score=1, away_score=1)
    a = make_analysis(index=70, status="RECOMENDAÇÃO")
    p = make_pre()
    result = live_summary({"m1": m}, [a], {"m1": p}, min_index=55, limit=5)
    assert result is not None
    _, text = result
    assert "ativos acima de 55 de índice" in text
    assert "Entrada: **GOL MANDANTE**" in text
    assert "1 x 1" in text
    assert "(Brazil - Serie A)" in text
    assert "Odd justa **1.75**" in text
    assert "Gol 10m **68.0%**" in text
    assert "Prioridade Diário" not in text
    assert "Mercado Pré" not in text
    assert "GPI" not in text


def test_live_discord_does_not_send_below_threshold():
    assert live_summary({"m1": make_match()}, [make_analysis(index=54.9)], {"m1": make_pre()}, min_index=55, limit=5) is None


def test_live_discord_never_sends_half_time():
    m = make_match(minute=45, home_score=1, away_score=0)
    m.state = "Half Time"
    a = make_analysis(index=80, status="RECOMENDAÇÃO")
    a.minute = 45
    a.state = "Half Time"
    assert live_summary({"m1": m}, [a], {"m1": make_pre()}, min_index=55, limit=5) is None


def test_live_discord_prioritizes_recommendation_over_higher_index_observation():
    m1 = make_match(minute=60)
    a1 = make_analysis(index=62, status="RECOMENDAÇÃO")

    m2 = deepcopy(m1); m2.match_id="m2"; m2.home_team="Obs Casa"; m2.away_team="Obs Fora"
    a2 = deepcopy(a1); a2.match_id="m2"; a2.market_index=88; a2.status="AQUECENDO"

    p1 = make_pre()
    p2 = deepcopy(p1); p2.match_id="m2"
    result = live_summary({"m1":m1,"m2":m2}, [a2,a1], {"m1":p1,"m2":p2}, min_index=55, limit=5)
    assert result is not None
    _, text = result
    assert text.index("Casa FC x Visitante FC") < text.index("Obs Casa x Obs Fora")
