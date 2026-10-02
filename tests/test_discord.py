from copy import deepcopy

from ac10next.outputs.discord import live_alerts, live_summary, weekly_audit_summary

from conftest import make_analysis, make_match, make_pre


def test_live_discord_contract():
    m = make_match(minute=72, home_score=1, away_score=1)
    a = make_analysis(index=70, status="RECOMENDAÇÃO")
    p = make_pre()
    result = live_summary({"m1": m}, [a], {"m1": p}, min_index=55, limit=5, local_time="14:30")
    assert result is not None
    state_hash, text = result
    assert len(state_hash) == 20
    assert "55" in text
    assert "jogos com dados" in text
    assert "Índice ≥55" in text
    assert "Back Casa ≥55" in text
    assert "Prob. ≥60%" in text
    assert "Momentum dominante Δ≥15" in text
    assert "MELHORES OPORTUNIDADES" in text
    assert "Entrada: **GOL MANDANTE**" in text
    assert "1 x 1" in text
    assert "(Brazil - Serie A)" in text
    assert "Odd justa **1.75**" in text
    assert "Gol 10m **68.0%**" in text


def test_live_discord_can_show_panorama_without_actionable_game():
    a = make_analysis(index=54.9, status="SEM ENTRADA")
    result = live_summary({"m1": make_match()}, [a], {"m1": make_pre()}, min_index=55, limit=5)
    assert result is not None
    _, text = result
    assert "Índice ≥55: **0**" in text
    assert "Nenhum jogo acionável" in text


def test_live_discord_never_lists_half_time():
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


def test_live_state_hash_ignores_small_metric_noise_but_changes_on_bucket_crossing():
    m=make_match(minute=72)
    p=make_pre()
    a1=make_analysis(index=61.0,status="SINAL")
    a2=deepcopy(a1); a2.market_index=62.0; a2.selected_probability=58.0
    a3=deepcopy(a1); a3.market_index=66.0
    h1,_=live_summary({"m1":m},[a1],{"m1":p},min_index=55)
    h2,_=live_summary({"m1":m},[a2],{"m1":p},min_index=55)
    h3,_=live_summary({"m1":m},[a3],{"m1":p},min_index=55)
    assert h1 == h2
    assert h1 != h3


def test_live_alerts_uses_distinct_icons_for_recommendation_and_high_index():
    m1=make_match(minute=72,home_score=1,away_score=1)
    a1=make_analysis(index=58,status="RECOMENDAÇÃO")
    m2=deepcopy(m1); m2.match_id="m2"; m2.home_team="Indice Casa"; m2.away_team="Indice Fora"
    a2=deepcopy(a1); a2.match_id="m2"; a2.market_index=63; a2.status="SINAL"
    state,text=live_alerts({"m1":m1,"m2":m2},[a1,a2],min_index=60,local_time="17:30")
    assert len(state)==20
    assert text is not None
    assert "✅ **RECOMENDAÇÃO" in text
    assert "🔥 **ÍNDICE ALTO" in text
    assert "Recomendação AC10" in text
    assert "Índice ≥60" in text


def test_live_alerts_excludes_below_60_when_not_recommendation_and_half_time():
    m=make_match(minute=72)
    a=make_analysis(index=59.9,status="SINAL")
    _,text=live_alerts({"m1":m},[a],min_index=60)
    assert text is None
    a.market_index=80; a.state="Half Time"; m.state="Half Time"
    _,text=live_alerts({"m1":m},[a],min_index=60)
    assert text is None


def test_live_alerts_hash_changes_when_high_index_becomes_recommendation():
    m=make_match(minute=72)
    a1=make_analysis(index=64,status="SINAL")
    a2=deepcopy(a1); a2.status="RECOMENDAÇÃO"; a2.minute=73
    h1,_=live_alerts({"m1":m},[a1],min_index=60)
    h2,_=live_alerts({"m1":m},[a2],min_index=60)
    assert h1 != h2


def test_weekly_audit_summary_contract():
    stats={
        "start_date":"2026-09-23","end_date":"2026-09-29",
        "totals":{
            "PRE":{"recommendations":10,"games":10,"reviewed":9,"greens":6,"reds":3,"priced":4,"profit_units":1.5},
            "LIVE":{"recommendations":20,"games":14,"reviewed":18,"greens":13,"reds":5,"priced":0,"profit_units":0},
        },
        "markets":{
            "PRE":[{"market":"BACK CASA","greens":4,"reds":1}],
            "LIVE":[{"market":"OVER +1 GOL","greens":8,"reds":2}],
        },
    }
    text=weekly_audit_summary(stats,{"successful_slots":500,"watchdog_recoveries":2,"errors":1},expected_live_slots=504)
    assert "AUDITORIA SEMANAL" in text
    assert "PRÉ" in text and "LIVE" in text
    assert "Acertos: **6**" in text
    assert "Ciclos LIVE concluídos: **500/504**" in text
