from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ac10next.domain.models import LiveInput
from ac10next.utils import clamp, number, parse_iso


@dataclass(frozen=True, slots=True)
class TeamPersona:
    name: str
    attack: float
    exposure: float
    openness: float
    quality: float
    avg_gf: float
    avg_ga: float
    over25_rate: float


def ratio(value: float, expected: float, low: float = .30, high: float = 1.90) -> float:
    if expected <= 0: return 0.0
    return clamp((value/expected-low)/max(.01,high-low),0,1)


def pressure_from_metrics(shots: float, sot: float, corners: float, dangerous: float, possession: float, minutes: float) -> float:
    minutes=max(float(minutes),1)
    possession_signal=clamp((possession-38)/24,0,1)
    return clamp(
        ratio(shots,minutes*.11)*.27 + ratio(sot,minutes*.0375,.20,2.10)*.36 + ratio(corners,minutes*.045)*.09
        + ratio(dangerous,minutes*.41)*.23 + possession_signal*.05,0,1
    )


def team_pressure(inp: LiveInput, home: bool) -> float:
    s=inp.stats
    if not s.available:return 0.0
    return pressure_from_metrics(
        s.home_shots if home else s.away_shots,
        s.home_sot if home else s.away_sot,
        s.home_corners if home else s.away_corners,
        s.home_dangerous if home else s.away_dangerous,
        s.home_possession if home else s.away_possession,
        max(inp.match.minute,10),
    )


def activity_score(inp: LiveInput) -> float:
    s=inp.stats
    if not s.available:return 0.0
    minute=max(inp.match.minute,10)
    shots=s.home_shots+s.away_shots; sot=s.home_sot+s.away_sot; corners=s.home_corners+s.away_corners; dangerous=s.home_dangerous+s.away_dangerous
    imbalance=abs(s.home_possession-s.away_possession)/50
    return clamp(ratio(shots,minute*.22)*.28+ratio(sot,minute*.075,.25,2)*.34+ratio(corners,minute*.09)*.10+ratio(dangerous,minute*.82)*.23+clamp(imbalance,0,1)*.05,0,1)


def necessity_score(inp: LiveInput, home: bool) -> float:
    m=inp.match; p=inp.pre
    own=m.home_score if home else m.away_score; opp=m.away_score if home else m.home_score
    own_w=p.home_weight if home else p.away_weight; opp_w=p.away_weight if home else p.home_weight
    diff=own-opp; urgency=clamp((m.minute-15)/75,0,1)
    if diff<0: need=48+urgency*42+min(10,abs(diff-1)*6)
    elif diff==0: need=26+urgency*48
    else: need=12+urgency*13-min(7,(diff-1)*4)
    if diff<=0 and own_w-opp_w>=10: need+=8
    if diff<=0 and own_w-opp_w>=20: need+=4
    return clamp(need,0,100)


def persona(inp: LiveInput, home: bool) -> TeamPersona:
    p=inp.pre
    raw=p.raw or {}
    profiles=(raw.get("home_profile") if home else raw.get("away_profile")) or {}
    recent=profiles.get("recent") or {}
    hist=profiles.get("history") or {}
    recent_gf=number(recent.get("gf"),1.25); recent_ga=number(recent.get("ga"),1.25); recent_over=number(recent.get("over"),50)
    hist_matches=int(number(hist.get("matches"),0)); hist_gf=number(hist.get("avg_gf"),recent_gf); hist_ga=number(hist.get("avg_ga"),recent_ga); hist_over=number(hist.get("over25_rate"),recent_over)
    if hist_matches>=3:
        avg_gf=hist_gf*.35+recent_gf*.65; avg_ga=hist_ga*.35+recent_ga*.65; over=hist_over*.35+recent_over*.65; quality=number(hist.get("quality"),p.data_quality)
    else:
        avg_gf,avg_ga,over,quality=recent_gf,recent_ga,recent_over,p.data_quality
    attack=clamp((avg_gf-.55)/1.65*100,0,100); exposure=clamp((avg_ga-.55)/1.65*100,0,100)
    total=clamp(((avg_gf+avg_ga)-1.45)/1.95*100,0,100); openness=clamp(total*.62+over*.38,0,100)
    if attack>=64 and exposure>=58 and openness>=62:name="🔥 EUFÓRICO"
    elif attack>=64 and exposure<58:name="⚔️ AGRESSIVO"
    elif attack<=43 and exposure>=62:name="💥 FRÁGIL"
    elif attack<=48 and exposure<=48 and openness<=48:name="🛡️ CAUTELOSO"
    elif exposure<=48 and attack<64:name="🦂 REATIVO"
    else:name="⚖️ EQUILIBRADO"
    return TeamPersona(name,attack,exposure,openness,quality,avg_gf,avg_ga,over)


def interval_pressure(inp: LiveInput, previous: dict[str,Any] | None, home: bool, current_pressure: float, history: list[dict[str,Any]]) -> tuple[float,float,float,float,dict[str,float],bool]:
    if not previous:return 0,0,0,0,{"shots":0,"sot":0,"corners":0,"dangerous":0},False
    prev_min=int(number(previous.get("minute"),0)); game_delta=inp.match.minute-prev_min if prev_min else 0
    now=inp.captured_at; old=previous.get("captured_at"); old_dt=old if hasattr(old,"tzinfo") else parse_iso(old)
    elapsed=max(0,(now-old_dt).total_seconds()/60) if old_dt else 0
    effective=float(game_delta if game_delta>0 else elapsed)
    if effective<.75 or effective>30:return 0,0,0,0,{"shots":0,"sot":0,"corners":0,"dangerous":0},False
    s=inp.stats; prefix="home" if home else "away"
    current={"shots":getattr(s,f"{prefix}_shots"),"sot":getattr(s,f"{prefix}_sot"),"corners":getattr(s,f"{prefix}_corners"),"dangerous":getattr(s,f"{prefix}_dangerous")}
    prev_keys={"shots":f"{prefix}_shots","sot":f"{prefix}_sot","corners":f"{prefix}_corners","dangerous":f"{prefix}_dangerous"}
    deltas={k:max(0,current[k]-number(previous.get(prev_keys[k]),0)) for k in current}
    recent=pressure_from_metrics(deltas["shots"],deltas["sot"],deltas["corners"],deltas["dangerous"],getattr(s,f"{prefix}_possession"),effective)*100
    baseline=number(previous.get(f"{prefix}_recent_pressure"),number(previous.get(f"{prefix}_pressure"),current_pressure*100))
    instant=clamp(recent-baseline,-50,50)
    movements=[]
    for row in history[-4:][1:]:
        raw=row.get(f"{prefix}_momentum")
        if raw not in (None,""): movements.append(clamp(number(raw,0),-50,50))
    movements.append(instant); movements=movements[-4:]
    weights=list(range(1,len(movements)+1)); momentum=sum(v*w for v,w in zip(movements,weights))/max(1,sum(weights))
    slope=instant-(movements[-2] if len(movements)>=2 else 0)
    return recent,clamp(momentum,-50,50),instant,slope,deltas,True


def movement(history: list[dict[str,Any]], inp: LiveInput) -> dict[str,Any]:
    current={"minute":inp.match.minute,"home_shots":inp.stats.home_shots,"away_shots":inp.stats.away_shots,"home_sot":inp.stats.home_sot,"away_sot":inp.stats.away_sot,"home_dangerous":inp.stats.home_dangerous,"away_dangerous":inp.stats.away_dangerous,"home_corners":inp.stats.home_corners,"away_corners":inp.stats.away_corners}
    snapshots=[]
    for h in history[-6:]:
        snapshots.append({"minute":h.get("minute"),"home_shots":h.get("home_shots"),"away_shots":h.get("away_shots"),"home_sot":h.get("home_sot"),"away_sot":h.get("away_sot"),"home_dangerous":h.get("home_dangerous"),"away_dangerous":h.get("away_dangerous"),"home_corners":h.get("home_corners"),"away_corners":h.get("away_corners")})
    snapshots.append(current); intervals=[]
    for left,right in zip(snapshots,snapshots[1:]):
        dm=int(number(right.get("minute"),0))-int(number(left.get("minute"),0))
        if dm<=0 or dm>30:continue
        d=lambda k:max(0,number(right.get(k),0)-number(left.get(k),0))
        hs,aws=d("home_shots"),d("away_shots"); hst,ast=d("home_sot"),d("away_sot"); hd,ad=d("home_dangerous"),d("away_dangerous"); hc,ac=d("home_corners"),d("away_corners")
        score=clamp(((hs+aws)/dm)*30+((hst+ast)/dm)*70+((hd+ad)/dm)*12+((hc+ac)/dm)*25,0,100)
        ht=hs*1.3+hst*3+hd*.35+hc*.8; at=aws*1.3+ast*3+ad*.35+ac*.8; total=max(.01,ht+at)
        intervals.append({"score":score,"home_share":ht/total,"shots":hs+aws,"sot":hst+ast,"dangerous":hd+ad,"corners":hc+ac,"minutes":dm})
    if not intervals:return {"score":0.0,"trend":"BASE","evolution":"Base inicial","delta":"Aguardando próximo scan","samples":1,"home_share":.5,"away_share":.5}
    recent=intervals[-5:]; weights=list(range(1,len(recent)+1)); scores=[x["score"] for x in recent]
    weighted=sum(x["score"]*w for x,w in zip(recent,weights))/sum(weights); diffs=[b-a for a,b in zip(scores,scores[1:])]; slope=sum(diffs)/len(diffs) if diffs else 0
    moment=clamp(weighted+(sum(d>3 for d in diffs)/len(diffs) if diffs else 0)*8-(sum(d<-3 for d in diffs)/len(diffs) if diffs else 0)*8+clamp(slope*.30,-10,10),0,100)
    trend="↑ FORTE" if slope>=10 else "↑" if slope>=3 else "↓ FORTE" if slope<=-10 else "↓" if slope<=-3 else "→ ESTÁVEL"
    last=recent[-1]; home_share=sum(x["home_share"]*w for x,w in zip(recent,weights))/sum(weights)
    return {"score":round(moment,1),"trend":trend,"evolution":" → ".join(str(int(round(x))) for x in scores),"delta":f"+{last['shots']:.0f} chutes | +{last['sot']:.0f} no alvo | +{last['dangerous']:.0f} perigosos | +{last['corners']:.0f} escanteios em {last['minutes']:.0f} min","samples":len(intervals)+1,"home_share":home_share,"away_share":1-home_share}


def history_goal_signal(inp: LiveInput, hp: TeamPersona, ap: TeamPersona) -> float:
    p=inp.pre
    persona_open=(hp.openness+ap.openness)/200
    recent_over=clamp((hp.over25_rate+ap.over25_rate)/200,.05,.95)
    league=clamp(p.league_over25_rate/100,.05,.95)
    expected=clamp((p.expected_total_goals-1.35)/2.85,0,1)
    return clamp(persona_open*.45+recent_over*.20+league*.10+expected*.25,.05,.95)


def goal_probability(inp: LiveInput, gpi: float, market: str) -> float:
    remaining=max(1,47-inp.match.minute) if market=="GOL HT" else max(3,96-inp.match.minute)
    base=clamp(inp.pre.expected_total_goals,1.45,4.2)/95; pace=.62+(gpi/100)*.92; lam=base*remaining*pace
    return clamp(1-math.exp(-lam),.05,.92)
