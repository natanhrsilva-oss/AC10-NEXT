from __future__ import annotations

from datetime import datetime, timezone

from ac10next.competition_priority import live_priority
from ac10next.domain.models import PregameContext, PregameFeatures, StrategyCandidate
from ac10next.utils import clamp, ev_percent


def _persona(m: PregameFeatures, home: bool) -> tuple[str,str,float]:
    attack=m.home_attack if home else m.away_attack
    defense=m.home_defense if home else m.away_defense
    form=m.home_recent_form if home else m.away_recent_form
    weight=m.home_weight if home else m.away_weight
    expected=m.expected_home_goals if home else m.expected_away_goals
    exposure=100-defense
    openness=clamp(attack*.34+exposure*.24+m.league_over25_rate*.22+clamp(expected/2.2*100,0,100)*.20,0,100)
    if attack>=64 and exposure>=56 and openness>=62: name="🔥 EUFÓRICO"
    elif attack>=64 and defense>=48: name="⚔️ AGRESSIVO"
    elif attack<=44 and defense<=44: name="💥 FRÁGIL"
    elif attack<=49 and defense>=60 and openness<=50: name="🛡️ CAUTELOSO"
    elif defense>=58 and attack<64: name="🦂 REATIVO"
    else: name="⚖️ EQUILIBRADO"
    pressure=attack*.31+form*.25+weight*.20+defense*.10+openness*.14
    posture="PRESSÃO ALTA" if pressure>=67 else "PROPOSITIVO" if pressure>=58 else "EQUILIBRADO" if pressure>=48 else "REATIVO" if defense>=57 else "BAIXA INTENSIDADE"
    return name,posture,openness


def _contexts(m: PregameFeatures, hop: float, aop: float) -> dict[str,float]:
    weight=m.home_weight-m.away_weight; form=m.home_recent_form-m.away_recent_form; xg=(m.expected_home_goals-m.expected_away_goals)*22
    h=clamp(52+weight*.24+form*.20+(m.home_attack-m.away_defense)*.20+xg*.30,0,100)
    a=clamp(48-weight*.24-form*.20+(m.away_attack-m.home_defense)*.20-xg*.30,0,100)
    gp=clamp((m.expected_total_goals-1.65)/1.75*100,0,100)
    over=clamp(gp*.38+m.league_over25_rate*.27+((m.home_attack+m.away_attack)/2)*.19+((hop+aop)/2)*.16,0,100)
    return {"BACK CASA":h,"BACK VISITANTE":a,"OVER 2,5 GOLS":over}


def _draw_risk(m: PregameFeatures) -> float:
    """Estimate draw risk on a calibrated 0-100 scale.

    v0.4.2 accidentally added 145% of the market draw component plus 55% of
    parity, which systematically inflated the result and vetoed strong BACKs.
    v0.4.3 uses a true weighted average. Without usable 1X2 odds we use a
    neutral 28% draw prior; odds are informative, never required.
    """
    market_draw = 28.0
    if all(x > 1 for x in (m.home_odd, m.draw_odd, m.away_odd)):
        implied = [1 / m.home_odd, 1 / m.draw_odd, 1 / m.away_odd]
        total = sum(implied)
        market_draw = implied[1] / total * 100 if total else 28.0
    parity = clamp(
        100
        - abs(m.home_weight - m.away_weight) * 2.2
        - abs(m.expected_home_goals - m.expected_away_goals) * 35
        - abs(m.home_recent_form - m.away_recent_form) * .8,
        0, 100,
    )
    return clamp(market_draw * .55 + parity * .45, 0, 100)


def build_context(m: PregameFeatures, candidates: list[StrategyCandidate], model_version: str) -> PregameContext:
    by={c.market:c for c in candidates}
    hn,hp,ho=_persona(m,True); an,ap,ao=_persona(m,False); ctx=_contexts(m,ho,ao)
    indexes={market:clamp(by[market].probability*100*.68+ctx[market]*.32,0,100) for market in by}
    ordered=sorted(indexes,key=indexes.get,reverse=True); market,second=ordered[:2]
    idx=indexes[market]; margin=idx-indexes[second]; source=by[market]
    delta=clamp((ctx[market]-source.probability*100)*.10,-4,4); prob=clamp(source.probability+delta/100,.04,.94)
    odd=source.market_odd; gap=(prob-1/odd)*100 if odd>1 else None; ev=ev_percent(prob,odd) if odd>1 else 0
    draw=_draw_risk(m)
    confidence=clamp(m.data_quality*.55+idx*.30+min(margin,20)*.75,0,100)
    goals_profile=clamp(m.expected_total_goals/3.5*38+m.league_over25_rate*.32+(ho+ao)/2*.30,0,100)
    # Explosive score deliberately asks a different question than Over 2.5: ceiling, not just crossing 2.5.
    explosive=clamp((m.expected_total_goals-2.0)/2.0*40 + ((m.home_attack+m.away_attack)/2)*.25 + ((100-m.home_defense+100-m.away_defense)/2)*.15 + m.league_over25_rate*.20,0,100)
    readiness=clamp(idx*.34+confidence*.22+m.data_quality*.16+m.competition_priority*.12+goals_profile*.08+explosive*.08,0,100)
    profile=("🔥 CONFRONTO OFENSIVO" if ctx["OVER 2,5 GOLS"]>=69 and ho>=60 and ao>=60 else "🏠 CASA DOMINANTE" if ctx["BACK CASA"]-ctx["BACK VISITANTE"]>=20 else "✈️ VISITANTE DOMINANTE" if ctx["BACK CASA"]-ctx["BACK VISITANTE"]<=-20 else "⚡ EQUILIBRADO E ABERTO" if abs(ctx["BACK CASA"]-ctx["BACK VISITANTE"])<=7 and ctx["OVER 2,5 GOLS"]>=61 else "🛡️ EQUILIBRADO E FECHADO" if abs(ctx["BACK CASA"]-ctx["BACK VISITANTE"])<=8 and ctx["OVER 2,5 GOLS"]<=47 else "⚖️ CONFRONTO EQUILIBRADO")
    return PregameContext(
        match_id=m.match.match_id, model_version=model_version, calculated_at=datetime.now(timezone.utc), data_quality=m.data_quality,
        competition_priority=m.competition_priority, home_attack=m.home_attack,home_defense=m.home_defense,home_weight=m.home_weight,home_recent_form=m.home_recent_form,
        away_attack=m.away_attack,away_defense=m.away_defense,away_weight=m.away_weight,away_recent_form=m.away_recent_form,
        expected_home_goals=m.expected_home_goals,expected_away_goals=m.expected_away_goals,expected_total_goals=m.expected_total_goals,
        league_avg_goals=m.league_avg_goals,league_over25_rate=m.league_over25_rate,home_persona=hn,away_persona=an,home_posture=hp,away_posture=ap,game_profile=profile,
        back_home_probability=by["BACK CASA"].probability*100,back_away_probability=by["BACK VISITANTE"].probability*100,goals_probability=by["OVER 2,5 GOLS"].probability*100,
        back_home_index=indexes["BACK CASA"],back_away_index=indexes["BACK VISITANTE"],goals_index=indexes["OVER 2,5 GOLS"],
        selected_market=market,selected_probability=prob*100,selected_index=idx,market_margin=margin,confidence=confidence,draw_risk=draw,
        goals_profile=goals_profile,explosive_score=explosive,live_readiness_score=readiness,live_priority=live_priority(readiness),
        home_odd=m.home_odd or None,draw_odd=m.draw_odd or None,away_odd=m.away_odd or None,over25_odd=m.over25_odd or None,
        raw={**m.raw,"second_market":second,"specialists":{c.market:{"probability":round(c.probability*100,2),"status":c.status,"reason":c.reason,"risks":c.risks} for c in candidates},"model_market_gap_pp":gap,"ev_percent":ev},
    )
