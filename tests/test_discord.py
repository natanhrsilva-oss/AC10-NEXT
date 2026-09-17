from ac10next.outputs.discord import live_summary

from conftest import make_analysis, make_match, make_pre


def test_live_discord_contract():
    m = make_match(minute=72, home_score=1, away_score=1)
    a = make_analysis(index=70)
    p = make_pre()
    result = live_summary({"m1": m}, [a], {"m1": p}, min_index=55, limit=5)
    assert result is not None
    _, text = result
    assert "acima de 55 de índice" in text
    assert "Entrada analisada" in text
    assert "1 x 1" in text
    assert "Prioridade Diário" in text
    assert "Mercado Pré" in text
    assert "bons jogos" not in text.lower()


def test_live_discord_does_not_send_below_threshold():
    assert live_summary({"m1": make_match()}, [make_analysis(index=54.9)], {"m1": make_pre()}, min_index=55, limit=5) is None
