from __future__ import annotations

import math

from ac10next.domain.models import PregameFeatures, StrategyCandidate
from ac10next.utils import clamp, ev_percent, poisson_over_25


def _sigmoid(v: float) -> float:
    return 1/(1+math.exp(-v))


def _status(prob: float, odd: float, data_quality: float, market: str, ev_min: float) -> str:
    thresholds = {"BACK CASA": .58, "BACK VISITANTE": .57, "OVER 2,5 GOLS": .60}
    pmin = thresholds[market]
    if odd > 1:
        ev = ev_percent(prob, odd)
        if prob >= pmin and ev >= ev_min and data_quality >= 55:
            return "RECOMENDAÇÃO"
        if prob >= pmin-.06 and ev >= 0 and data_quality >= 35:
            return "OBSERVAÇÃO"
    else:
        if prob >= pmin+.03 and data_quality >= 55:
            return "RECOMENDAÇÃO"
        if prob >= pmin-.06 and data_quality >= 35:
            return "OBSERVAÇÃO"
    return "REJEITADO"


def back_home(m: PregameFeatures) -> StrategyCandidate:
    draw_pressure = 0.0
    if m.draw_odd > 1 and m.home_odd > 1:
        draw_pressure = clamp((1/m.draw_odd)/max(1/m.home_odd,.01),0,1.25)
    statistical = _sigmoid(
        -.05 + .42*((m.home_weight-m.away_weight)/20) + .28*(((m.home_attack-m.away_defense)+(m.away_defense-m.away_attack)*.25)/45)
        + .20*((m.home_recent_form-m.away_recent_form)/35) + .22*((m.home_competition_history_strength-m.away_competition_history_strength)/35)
        + .12*((m.home_opponent_strength-m.away_opponent_strength)/45) + .30*((m.expected_home_goals-m.expected_away_goals)/1.2)
        + .10*(0 if draw_pressure<=0 else (.72-draw_pressure)/.35)
    )
    p = statistical
    risks=[]
    if m.home_recent_form < 48: risks.append("forma recente da casa moderada")
    if m.expected_home_goals <= m.expected_away_goals: risks.append("xG sem vantagem da casa")
    if draw_pressure >= .78: p -= .025; risks.append("risco de empate")
    consensus = sum((m.home_weight>=m.away_weight+2,m.home_recent_form>=m.away_recent_form+2,m.expected_home_goals>=m.expected_away_goals+.12,m.home_attack>=m.away_defense,m.home_defense>=m.away_attack-5,m.home_competition_history_strength+5>=m.away_competition_history_strength))
    p=clamp(p,.04,.94)
    status=_status(p,m.home_odd,m.data_quality,"BACK CASA",5)
    if consensus < 4 and status=="RECOMENDAÇÃO": status="OBSERVAÇÃO"
    return StrategyCandidate("BACK CASA",p,m.home_odd,p*100,status,f"Back Casa: peso {m.home_weight:.1f}x{m.away_weight:.1f}; xG {m.expected_home_goals:.2f}x{m.expected_away_goals:.2f}; consenso {consensus}/6.",risks)


def back_away(m: PregameFeatures) -> StrategyCandidate:
    draw_pressure=0.0
    if m.draw_odd>1 and m.away_odd>1:
        draw_pressure=clamp((1/m.draw_odd)/max(1/m.away_odd,.01),0,1.25)
    statistical=_sigmoid(
        -.30 + .32*((m.away_weight-m.home_weight)/20)+.22*((m.away_attack-m.home_defense)/35)+.30*((m.away_defense-m.home_attack)/35)
        +.22*((m.away_recent_form-m.home_recent_form)/30)+.18*((m.away_competition_history_strength-m.home_competition_history_strength)/30)
        +.10*((m.away_opponent_strength-m.home_opponent_strength)/40)+.36*((m.expected_away_goals-m.expected_home_goals)/1.0)
        +.10*(0 if draw_pressure<=0 else (.72-draw_pressure)/.35)
    )
    p=statistical
    risks=[]
    if m.away_recent_form < 52 or m.away_recent_form <= m.home_recent_form: risks.append("forma visitante sem vantagem")
    if m.expected_away_goals < m.expected_home_goals+.15: risks.append("xG visitante sem vantagem clara")
    if m.home_attack >= m.away_defense+10: risks.append("ataque mandante perigoso")
    if draw_pressure>=.78: p-=.03; risks.append("risco de empate")
    consensus=sum((m.away_weight>=m.home_weight+3,m.away_recent_form>=m.home_recent_form+4,m.expected_away_goals>=m.expected_home_goals+.15,m.away_attack>=m.home_defense,m.away_defense>=m.home_attack-5,m.away_competition_history_strength+5>=m.home_competition_history_strength))
    p=clamp(p,.04,.94)
    status=_status(p,m.away_odd,m.data_quality,"BACK VISITANTE",5)
    if (consensus<4 or m.away_odd>2.60) and status=="RECOMENDAÇÃO": status="OBSERVAÇÃO"
    return StrategyCandidate("BACK VISITANTE",p,m.away_odd,p*100,status,f"Back Visitante: peso {m.away_weight:.1f}x{m.home_weight:.1f}; xG {m.expected_away_goals:.2f}x{m.expected_home_goals:.2f}; consenso {consensus}/6.",risks)


def over25(m: PregameFeatures) -> StrategyCandidate:
    poisson=poisson_over_25(m.expected_total_goals)
    league=clamp(m.league_over25_rate/100,.20,.80)
    attack_signal=clamp((m.home_attack+m.away_attack+(100-m.home_defense)+(100-m.away_defense))/400,.20,.80)
    league_goals=clamp((m.league_avg_goals-1.40)/2.20,.20,.80)
    p=poisson*.65+league*.20+attack_signal*.10+league_goals*.05
    if m.league_avg_goals>=2.8: p+=.015
    if m.league_avg_goals<2.15: p-=.035
    risks=[]
    if m.expected_total_goals<2.35: risks.append("xG total moderado")
    if m.league_over25_rate<48: risks.append("taxa de over baixa")
    p=clamp(p,.05,.95)
    status=_status(p,m.over25_odd,m.data_quality,"OVER 2,5 GOLS",6)
    blockers = m.expected_total_goals<2.10 or (m.league_over25_rate<42 and m.expected_total_goals<2.65)
    if blockers and status=="RECOMENDAÇÃO": status="OBSERVAÇÃO"
    return StrategyCandidate("OVER 2,5 GOLS",p,m.over25_odd,p*100,status,f"Over por xG {m.expected_total_goals:.2f}, liga {m.league_over25_rate:.1f}% e ataques {m.home_attack:.1f}+{m.away_attack:.1f}.",risks)


def evaluate_all(m: PregameFeatures) -> list[StrategyCandidate]:
    return [back_home(m), back_away(m), over25(m)]
