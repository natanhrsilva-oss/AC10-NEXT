from ac10next.outputs.sheets import live_rows
from conftest import make_analysis, make_match, make_pre


def test_live_sheet_column_order_status_and_momentum_game():
    m=make_match(minute=45, home_score=1, away_score=1)
    a=make_analysis(index=70, status="RECOMENDAÇÃO")
    a.minute=45
    a.state="Half Time"
    a.home_momentum=18
    a.away_momentum=-3
    row=live_rows({"m1":m}, [a], {"m1":make_pre()})[0]
    keys=list(row)
    assert keys[:13] == [
        "País","Campeonato","Mandante","Visitante","Minuto","Placar","Status",
        "Odd Justa","Entrada Analisada","Confirmações","Índice","Probabilidade %","Momentum Jogo",
    ]
    assert row["Status"] == "INTERVALO"
    assert row["Momentum Jogo"] == 65.0
    assert keys.index("GPI") > keys.index("Qualidade Mercado %")
    assert keys.index("IDD Casa") > keys.index("Qualidade Mercado %")
    assert keys.index("IDD Visitante") > keys.index("Qualidade Mercado %")


def test_live_sheet_visual_status_mapping():
    m=make_match(minute=70)
    p=make_pre()
    for internal, expected in [("SEM ENTRADA","X"),("AQUECENDO","OBSERVAR"),("SINAL","OBSERVAR"),("RECOMENDAÇÃO","ENTRAR")]:
        a=make_analysis(index=70,status=internal)
        row=live_rows({"m1":m},[a],{"m1":p})[0]
        assert row["Status"] == expected
