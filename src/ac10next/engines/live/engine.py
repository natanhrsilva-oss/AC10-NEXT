from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from ac10next.domain.models import LiveAnalysis, LiveInput
from ac10next.engines.live.metrics import (
    TeamPersona, activity_score, goal_probability, history_goal_signal, interval_pressure,
    movement, necessity_score, persona, team_pressure,
)
from ac10next.utils import clamp, fair_odd, number


GOAL_BUCKETS = {
    "HT": {"gpi":62.0,"prob":32.0,"pressure":58.0,"activity":50.0},
    "66-70": {"gpi":62.0,"prob":28.0,"pressure":60.0,"activity":52.0},
    "71-75": {"gpi":64.0,"prob":24.0,"pressure":62.0,"activity":54.0},
    "76-80": {"gpi":67.0,"prob":20.0,"pressure":64.0,"activity":56.0},
    "81-85": {"gpi":70.0,"prob":16.0,"pressure":67.0,"activity":58.0},
    "86-88": {"gpi":74.0,"prob":12.0,"pressure":70.0,"activity":60.0},
}


def _team_back_index(inp: LiveInput, home: bool, own_persona: TeamPersona, opponent_persona: TeamPersona,
                     own_pressure: float, opponent_pressure: float, own_momentum: float, opponent_momentum: float,
                     own_need: float, comparison_ok: bool) -> float:
    m,p,s=inp.match,inp.pre,inp.stats
    own_score=m.home_score if home else m.away_score; opp_score=m.away_score if home else m.home_score
    own_weight=p.home_weight if home else p.away_weight; opp_weight=p.away_weight if home else p.home_weight
    own_form=p.home_recent_form if home else p.away_recent_form; opp_form=p.away_recent_form if home else p.home_recent_form
    own_red=s.home_red_cards if home else s.away_red_cards; opp_red=s.away_red_cards if home else s.home_red_cards
    own_pct=own_pressure*100; opp_pct=opponent_pressure*100
    live_edge=clamp(own_pct*.78+clamp(own_pct-opp_pct,-30,30)*.55+10,0,100)
    hist=clamp(own_persona.attack*.54+opponent_persona.exposure*.34+own_persona.quality*.12,0,100)
    structural=clamp(50+(own_weight-opp_weight)*.90+(own_form-opp_form)*.25,0,100)
    momentum=clamp(50+(own_momentum-opponent_momentum)*1.10,0,100) if comparison_ok else 50
    diff=own_score-opp_score; late=max(0,m.minute-68)*.85
    score_time=0 if diff>0 else clamp(82-late,32,82) if diff==0 else clamp(58-late*1.35,8,58) if diff==-1 else 4
    card=clamp(50+(opp_red-own_red)*28,0,100)
    value=live_edge*.30+hist*.18+structural*.15+momentum*.12+own_need*.10+score_time*.10+card*.05
    if diff>0:value=min(value,35)
    elif diff<=-2:value=min(value,42)
    if m.minute<18 or m.minute>80:value=min(value,58)
    if own_red>opp_red:value-=min(18,(own_red-opp_red)*12)
    return clamp(value,0,100)


def _poisson_pmf(lam: float, goals: int) -> float:
    return math.exp(-lam)*(lam**goals)/math.factorial(goals)


def _back_probabilities(inp: LiveInput, gpi: float, hi: float, ai: float) -> tuple[float,float]:
    m,p=inp.match,inp.pre; remaining=max(2,96-m.minute); base=clamp(p.expected_total_goals,1.45,4.2)/95; pace=.62+(gpi/100)*.95; total_lam=clamp(base*remaining*pace,.08,4.8)
    total=max(.20,p.expected_home_goals+p.expected_away_goals); pre_share=clamp(p.expected_home_goals/total,.25,.75); shift=clamp((hi-ai)/280,-.20,.20); hs=clamp(pre_share+shift,.18,.82)
    hl,al=total_lam*hs,total_lam*(1-hs); hw=aw=0.0
    for hg in range(9):
        ph=_poisson_pmf(hl,hg)
        for ag in range(9):
            prob=ph*_poisson_pmf(al,ag); fh=m.home_score+hg; fa=m.away_score+ag
            if fh>fa:hw+=prob
            elif fa>fh:aw+=prob
    return clamp(hw,.01,.94),clamp(aw,.01,.94)


def _back_allowed(inp: LiveInput, home: bool, index: float, opponent_index: float, prob: float, pressure: float, momentum: float, opponent_momentum: float, comparison_ok: bool) -> bool:
    m=inp.match; own=m.home_score if home else m.away_score; opp=m.away_score if home else m.home_score
    if m.minute<18 or m.minute>80 or own>opp or own<opp-1:return False
    threshold=76 if m.minute<=42 else 72
    if m.minute>=76:threshold+=5
    if own<opp:threshold+=7
    if index<threshold or index-opponent_index<9 or pressure*100<52 or prob<.20:return False
    if comparison_ok and momentum<opponent_momentum-8 and momentum<4:return False
    return True


def _goal_bucket(minute: int, market: str) -> str:
    if market=="GOL HT":return "HT"
    if minute<=70:return "66-70"
    if minute<=75:return "71-75"
    if minute<=80:return "76-80"
    if minute<=85:return "81-85"
    return "86-88"


def _market_quality(inp: LiveInput, market: str) -> float:
    s=inp.stats; base=clamp(inp.pre.data_quality*.45+s.data_quality*.55,0,100)
    if not s.available:return min(base,35)
    completeness=(35 if s.home_shots+s.away_shots>0 else 0)+(30 if s.home_sot+s.away_sot>0 else 0)+(20 if s.home_dangerous+s.away_dangerous>0 else 0)+(15 if s.home_possession+s.away_possession>0 else 0)
    if market.startswith("BACK"):completeness=min(100,completeness+5)
    return clamp(base*.72+completeness*.28,0,100)


def _goal_watch(inp: LiveInput, gpi: float, quality: float, mov: dict[str,Any], hp: TeamPersona, ap: TeamPersona, hpress: float, apress: float, hidd: float, aidd: float) -> dict[str,Any]:
    profile=(hp.openness+ap.openness)/2; has_delta=int(number(mov.get("samples"),1))>=2
    chance=clamp(gpi*.42+number(mov.get("score"),0)*.43+profile*.15,8,92) if has_delta else clamp(gpi*.62+profile*.38,8,78)
    lh=hpress*100*.35+hidd*.25+hp.attack*.20+number(mov.get("home_share"),.5)*100*.20
    la=apress*100*.35+aidd*.25+ap.attack*.20+number(mov.get("away_share"),.5)*100*.20; total=max(1,lh+la)
    home_goal=chance*lh/total; away_goal=chance-home_goal; confidence=clamp(quality*.55+min(100,number(mov.get("samples"),1)*14)*.25+abs(home_goal-away_goal)*1.2*.20,20,95)
    side_share=max(home_goal,away_goal)/max(1,chance); side_prob=max(home_goal,away_goal)
    if side_share>=.64 and side_prob>=30:candidate="GOL MANDANTE" if home_goal>=away_goal else "GOL VISITANTE"; candidate_prob=side_prob
    else:candidate="GOL HT" if inp.match.minute<=37 else "GOL FT"; candidate_prob=chance
    status="BASE INICIAL" if not has_delta else "RECOMENDADO" if ((chance>=65 and number(mov.get("score"),0)>=60 and confidence>=58) or (chance>=56 and number(mov.get("score"),0)>=56 and confidence>=55 and side_share>=.66 and side_prob>=36)) else "AQUECENDO" if chance>=52 or number(mov.get("score"),0)>=55 else "SEM ENTRADA"
    return {"chance":chance,"candidate":candidate,"candidate_prob":candidate_prob,"status":status,"confidence":confidence}


def _over15_more(inp: LiveInput, gpi: float, hpress: float, apress: float, hneed: float, aneed: float, mov: dict[str,Any], hp: TeamPersona, ap: TeamPersona) -> float:
    remaining=max(0,96-inp.match.minute)
    if remaining<=1:return 0.0
    hist=clamp(((hp.avg_gf+hp.avg_ga)+(ap.avg_gf+ap.avg_ga))/2,1.25,4.8); expected=clamp(inp.pre.expected_total_goals,1.25,4.8); structural=expected*.56+hist*.44
    g=clamp(gpi/100,0,1); press=clamp(max(hpress,apress),0,1); moment=clamp(number(mov.get("score"),0)/100,0,1)
    if int(number(mov.get("samples"),1))<2:moment=.45
    profile=clamp((hp.openness+ap.openness)/200,0,1); need=clamp(max(hneed,aneed)/100,0,1); intensity=g*.40+press*.32+moment*.28
    pace=clamp(.68+intensity*.72+(profile-.50)*.24,.55,1.50); lam=structural*(remaining/95)*pace*(.94+need*.12); prob=1-math.exp(-lam)*(1+lam)
    return clamp(prob*100,0,96)


def analyze(inp: LiveInput, previous: dict[str,Any] | None, history: list[dict[str,Any]]) -> LiveAnalysis:
    hp,ap=persona(inp,True),persona(inp,False); hpress,apress=team_pressure(inp,True),team_pressure(inp,False); activity=activity_score(inp); hneed,aneed=necessity_score(inp,True),necessity_score(inp,False)
    hrp,hm,hmi,hms,hdeltas,hcomp=interval_pressure(inp,previous,True,hpress,history); arp,am,ami,ams,adeltas,acomp=interval_pressure(inp,previous,False,apress,history); comparison=hcomp and acomp
    live=clamp(activity*.55+max(hpress,apress)*.30+min(hpress,apress)*.15,0,1)
    recent=clamp(max(hrp,arp)/100*.70+min(hrp,arp)/100*.15+clamp(max(hm,am)/50,-1,1)*.15,0,1) if comparison else .50
    hist=history_goal_signal(inp,hp,ap); exec_need=max((hneed/100)*hpress,(aneed/100)*apress); gpi=clamp((live*.55+recent*.20+hist*.20+exec_need*.05)*100,0,100)
    diff=abs(inp.match.home_score-inp.match.away_score)
    if diff>=2 and max(hpress,apress)<.72:gpi-=6 if diff==2 else 11
    gpi=clamp(gpi,0,100); prev_gpi=number((previous or {}).get("gpi"),-1); gdelta=gpi-prev_gpi if comparison and prev_gpi>=0 else None
    hi=_team_back_index(inp,True,hp,ap,hpress,apress,hm,am,hneed,comparison); ai=_team_back_index(inp,False,ap,hp,apress,hpress,am,hm,aneed,comparison); hprob,aprob=_back_probabilities(inp,gpi,hi,ai)
    hallowed=_back_allowed(inp,True,hi,ai,hprob,hpress,hm,am,comparison); aallowed=_back_allowed(inp,False,ai,hi,aprob,apress,am,hm,comparison)
    minute=inp.match.minute; back_only=38<=minute<=65; baseline="GOL HT" if minute<=37 else "OVER +1 GOL"; goalprob=goal_probability(inp,gpi,"GOL HT" if minute<=37 else "OVER +1 GOL")
    market=baseline; idx=gpi; prob=goalprob*100; selected_pressure=max(hpress,apress)*100; selected_recent=max(hrp,arp) if comparison else 0; selected_mom=max(hm,am) if comparison else 0; back_allowed=False
    choose_home=hi>=ai
    if back_only:
        if hallowed or aallowed:choose_home=hallowed and (not aallowed or hi>=ai); back_allowed=True
        market="BACK CASA" if choose_home else "BACK VISITANTE"; idx=hi if choose_home else ai; prob=(hprob if choose_home else aprob)*100; selected_pressure=(hpress if choose_home else apress)*100; selected_recent=(hrp if choose_home else arp) if comparison else 0; selected_mom=(hm if choose_home else am) if comparison else 0
    elif hallowed or aallowed:
        choose_home=hallowed and (not aallowed or hi>=ai); best=hi if choose_home else ai; opp=ai if choose_home else hi; bp=hprob if choose_home else aprob; bp_press=hpress if choose_home else apress; bp_recent=hrp if choose_home else arp; bp_mom=hm if choose_home else am
        back_conv=best+min(8,max(0,best-opp)*.22)+bp*5; goal_conv=gpi+(3 if min(hpress,apress)>=.55 else 0)
        if back_conv>=goal_conv+2 or (best>=85 and abs(hi-ai)>=15): market="BACK CASA" if choose_home else "BACK VISITANTE"; idx=best; prob=bp*100; selected_pressure=bp_press*100; selected_recent=bp_recent if comparison else 0; selected_mom=bp_mom if comparison else 0; back_allowed=True
    quality=_market_quality(inp,market); mov=movement(history,inp); watch=_goal_watch(inp,gpi,quality,mov,hp,ap,hpress,apress,hi,ai)
    if not market.startswith("BACK") and not back_only:
        # Até 37': o watcher pode escolher gol HT ou gol direcional.
        # De 66' em diante, o mercado-base oficial é OVER +1 GOL. Gol direcional
        # só substitui o mercado quando há dominância clara; nunca voltamos a "GOL FT".
        if minute <= 37 and watch["candidate"] in {"GOL HT","GOL MANDANTE","GOL VISITANTE"}:
            market=watch["candidate"]; prob=max(prob,watch["candidate_prob"])
        elif minute >= 66 and watch["candidate"] in {"GOL MANDANTE","GOL VISITANTE"}:
            market=watch["candidate"]; prob=max(prob,watch["candidate_prob"])
        elif minute >= 66:
            market="OVER +1 GOL"
    confirmations={}
    if market.startswith("BACK"):
        sel=hi if market=="BACK CASA" else ai; opp=ai if market=="BACK CASA" else hi
        confirmations={"indice":back_allowed and sel>=72,"direcao":sel-opp>=9,"pressao":selected_pressure>=52,"probabilidade":prob>=20,"evolucao":comparison and selected_mom>=-4}
        count=sum(confirmations.values()); exceptional=(not comparison and back_allowed and sel>=86 and sel-opp>=18 and selected_pressure>=70 and prob>=25 and quality>=70)
        status="SEM ENTRADA" if not inp.stats.available or quality<58 or (back_only and not back_allowed) else "RECOMENDAÇÃO" if ((comparison and back_allowed and count>=4) or exceptional) else "AQUECENDO" if back_allowed or count>=3 else "SEM ENTRADA"
    else:
        bucket=_goal_bucket(minute,"GOL HT" if minute<=37 else "OVER +1 GOL"); th=GOAL_BUCKETS[bucket]
        confirmations={"gpi":gpi>=th["gpi"],"tempo_prob":prob>=th["prob"],"execucao_live":selected_pressure>=th["pressure"] and activity*100>=th["activity"],"evolucao_recente":comparison and selected_recent>=54 and selected_mom>=-4,"qualidade_contexto":quality>=58 and hist>=.45}
        count=sum(confirmations.values()); exceptional=(not comparison and gpi>=th["gpi"]+8 and prob>=th["prob"]+5 and selected_pressure>=72 and activity*100>=68 and quality>=72 and hist>=.55)
        status="SEM ENTRADA" if not inp.stats.available or quality<58 or back_only else "RECOMENDAÇÃO" if ((comparison and count>=4 and watch["status"] in {"RECOMENDADO","AQUECENDO"}) or exceptional) else "AQUECENDO" if count>=3 or gpi>=th["gpi"]-5 or watch["status"]=="AQUECENDO" else "SEM ENTRADA"
    # No primeiro scan, recommendation remains exceptional-only by construction.
    market_odd=None; ev=None; fodd=fair_odd(prob/100) if prob>0 else None; price_status="SEM PREÇO LIVE"
    over15=_over15_more(inp,gpi,hpress,apress,hneed,aneed,mov,hp,ap)
    raw={
        "pregame":{"priority":inp.pre.live_priority,"market":inp.pre.selected_market,"probability":inp.pre.selected_probability,"index":inp.pre.selected_index},
        "personas":{"home":hp.name,"away":ap.name},"confirmations":confirmations,"comparison_ok":comparison,
        "movement":{"evolution":mov.get("evolution"),"delta":mov.get("delta"),"samples":mov.get("samples")},
        "goal_watch":watch,"entry_analyzed":market,"live_score":f"{inp.match.home_score} x {inp.match.away_score}",
        "recent_deltas":{"home":hdeltas,"away":adeltas},
    }
    fp_obj={"minute_bucket":minute//3,"score":[inp.match.home_score,inp.match.away_score],"stats":[round(inp.stats.home_shots),round(inp.stats.away_shots),round(inp.stats.home_sot),round(inp.stats.away_sot),round(inp.stats.home_corners),round(inp.stats.away_corners),round(inp.stats.home_dangerous/3),round(inp.stats.away_dangerous/3)],"market":market,"status":status,"index_bucket":int(idx//3)}
    fingerprint=hashlib.sha1(json.dumps(fp_obj,sort_keys=True).encode()).hexdigest()[:20]
    return LiveAnalysis(
        match_id=inp.match.match_id,captured_at=inp.captured_at,minute=minute,home_score=inp.match.home_score,away_score=inp.match.away_score,state=inp.match.state,live_data_mode=inp.stats.data_mode,data_quality=clamp(inp.pre.data_quality*.45+inp.stats.data_quality*.55,0,100),
        home_shots=inp.stats.home_shots,away_shots=inp.stats.away_shots,home_sot=inp.stats.home_sot,away_sot=inp.stats.away_sot,home_corners=inp.stats.home_corners,away_corners=inp.stats.away_corners,home_dangerous=inp.stats.home_dangerous,away_dangerous=inp.stats.away_dangerous,home_possession=inp.stats.home_possession,away_possession=inp.stats.away_possession,home_red_cards=inp.stats.home_red_cards,away_red_cards=inp.stats.away_red_cards,
        home_pressure=hpress*100,away_pressure=apress*100,home_recent_pressure=hrp,away_recent_pressure=arp,home_momentum=hm,away_momentum=am,home_momentum_slope=hms,away_momentum_slope=ams,activity=activity*100,gpi=gpi,gpi_delta=gdelta,home_idd=hi,away_idd=ai,idd_delta=hi-ai,home_need=hneed,away_need=aneed,chance_goal_10=watch["chance"],over15_more_probability=over15,movement_score=number(mov.get("score"),0),movement_trend=str(mov.get("trend") or "BASE"),selected_market=market,selected_probability=prob,market_index=idx,market_quality=quality,confirmation_count=count,status=status,fair_odd=fodd,market_odd=market_odd,ev_percent=ev,price_status=price_status,fingerprint=fingerprint,raw=raw,
    )
