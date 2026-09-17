from __future__ import annotations

from typing import Any

import httpx

from ac10next.domain.models import LiveAnalysis, MatchRecord, PregameContext


async def _post(url: str, token: str, payload_type: str, rows: list[dict[str,Any]]) -> None:
    if not url or not token or not rows:return
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
        r=await client.post(url,json={"token":token,"type":payload_type,"rows":rows})
        r.raise_for_status()


def pre_rows(matches: dict[str,MatchRecord], contexts: list[PregameContext]) -> list[dict[str,Any]]:
    out=[]
    for p in sorted(contexts,key=lambda x:x.live_readiness_score,reverse=True):
        m=matches[p.match_id]
        out.append({"Data":m.match_date,"Hora":m.kickoff.strftime("%H:%M"),"País":m.country,"Campeonato":m.competition,"Mandante":m.home_team,"Visitante":m.away_team,"Prioridade Diário":p.live_priority,"Mercado Pré":p.selected_market,"Probabilidade Pré %":round(p.selected_probability,1),"Índice Pré":round(p.selected_index,1),"Confiança":round(p.confidence,1),"Qualidade Dados":round(p.data_quality,1),"Perfil Gols":round(p.goals_profile,1),"Explosivo":round(p.explosive_score,1),"Readiness":round(p.live_readiness_score,1),"Persona Casa":p.home_persona,"Persona Visitante":p.away_persona,"xG Casa":round(p.expected_home_goals,2),"xG Visitante":round(p.expected_away_goals,2),"xG Total":round(p.expected_total_goals,2),"Atualizado":p.calculated_at.isoformat()})
    return out


def live_rows(matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext]) -> list[dict[str,Any]]:
    out=[]
    for a in sorted(analyses,key=lambda x:x.market_index,reverse=True):
        m=matches[a.match_id]; p=pre.get(a.match_id)
        out.append({"País":m.country,"Campeonato":m.competition,"Mandante":m.home_team,"Visitante":m.away_team,"Minuto":a.minute,"Placar":f"{a.home_score} x {a.away_score}","Status":a.status,"Entrada Analisada":a.selected_market,"Índice":round(a.market_index,1),"Probabilidade %":round(a.selected_probability,1),"GPI":round(a.gpi,1),"IDD Casa":round(a.home_idd,1),"IDD Visitante":round(a.away_idd,1),"Momentum Casa":round(a.home_momentum,1),"Momentum Visitante":round(a.away_momentum,1),"Chance Gol 10 min %":round(a.chance_goal_10,1),"Over +1,5 Gols a Mais %":round(a.over15_more_probability,1),"Evolução":a.raw.get("movement",{}).get("evolution",""),"Delta Recente":a.raw.get("movement",{}).get("delta",""),"Confirmações":f"{a.confirmation_count}/5","Qualidade Mercado %":round(a.market_quality,1),"Odd Live":round(a.market_odd,3) if a.market_odd else "","Odd Justa":round(a.fair_odd,3) if a.fair_odd else "","EV %":round(a.ev_percent,2) if a.ev_percent is not None else "","Preço":a.price_status,"Prioridade Diário":p.live_priority if p else "","Mercado Pré":p.selected_market if p else "","Probabilidade Pré %":round(p.selected_probability,1) if p else "","Atualizado":a.captured_at.isoformat()})
    return out


async def send_pre(url: str, token: str, matches: dict[str,MatchRecord], contexts: list[PregameContext]) -> None:
    await _post(url,token,"pre",pre_rows(matches,contexts))


async def send_live(url: str, token: str, matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext]) -> None:
    await _post(url,token,"live",live_rows(matches,analyses,pre))
