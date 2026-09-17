from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

import httpx

from ac10next.domain.models import LiveAnalysis, MatchRecord, PregameContext


async def _post(url: str, token: str, payload_type: str, rows: list[dict[str,Any]]) -> None:
    if not url or not token:
        return
    if not rows and payload_type not in {"pre_history","live_history"}:
        return
    async with httpx.AsyncClient(timeout=20,follow_redirects=True) as client:
        r=await client.post(url,json={"token":token,"type":payload_type,"rows":rows})
        r.raise_for_status()


def _n(value: Any, digits: int = 1) -> float | str:
    if value is None or value == "":
        return ""
    try:
        return round(float(value),digits)
    except (TypeError,ValueError):
        return ""


def _iso(value: Any) -> str:
    if isinstance(value,datetime):
        return value.isoformat()
    return str(value or "")


def _selected_odd(p: PregameContext) -> float | None:
    return {
        "BACK CASA":p.home_odd,
        "BACK VISITANTE":p.away_odd,
        "OVER 2,5 GOLS":p.over25_odd,
    }.get(p.selected_market)


def pre_rows(matches: dict[str,MatchRecord], contexts: list[PregameContext]) -> list[dict[str,Any]]:
    out=[]
    for p in sorted(contexts,key=lambda x:x.live_readiness_score,reverse=True):
        m=matches[p.match_id]
        precision=dict(p.raw.get("precision") or {})
        out.append({
            "Data":m.match_date,"Hora":m.kickoff.strftime("%H:%M"),"País":m.country,"Campeonato":m.competition,
            "Mandante":m.home_team,"Visitante":m.away_team,
            "Recomendação PRE":"SIM" if precision.get("qualifies") else "",
            "Precision Score":_n(precision.get("score")),
            "Prioridade Diário":p.live_priority,"Mercado Pré":p.selected_market,
            "Probabilidade Pré %":round(p.selected_probability,1),"Índice Pré":round(p.selected_index,1),
            "Confiança":round(p.confidence,1),"Qualidade Dados":round(p.data_quality,1),
            "Margem Mercado":round(p.market_margin,1),"Risco Empate":round(p.draw_risk,1),
            "Odd Pré":_n(_selected_odd(p),3),"Odd Justa":_n(precision.get("fair_odd"),3),"EV %":_n(precision.get("ev_percent"),2),
            "Perfil Gols":round(p.goals_profile,1),"Explosivo":round(p.explosive_score,1),"Readiness":round(p.live_readiness_score,1),
            "Persona Casa":p.home_persona,"Persona Visitante":p.away_persona,
            "xG Casa":round(p.expected_home_goals,2),"xG Visitante":round(p.expected_away_goals,2),"xG Total":round(p.expected_total_goals,2),
            "Atualizado":p.calculated_at.isoformat(),
        })
    return out


def live_rows(matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext]) -> list[dict[str,Any]]:
    out=[]
    for a in sorted(analyses,key=lambda x:x.market_index,reverse=True):
        m=matches[a.match_id]; p=pre.get(a.match_id)
        event=dict(a.raw.get("event_state") or {})
        fresh=dict(a.raw.get("data_freshness") or {})
        out.append({
            "País":m.country,"Campeonato":m.competition,"Mandante":m.home_team,"Visitante":m.away_team,
            "Minuto":a.minute,"Placar":f"{a.home_score} x {a.away_score}","Status":a.status,"Entrada Analisada":a.selected_market,
            "Índice":round(a.market_index,1),"Probabilidade %":round(a.selected_probability,1),"GPI":round(a.gpi,1),
            "IDD Casa":round(a.home_idd,1),"IDD Visitante":round(a.away_idd,1),
            "Momentum Casa":round(a.home_momentum,1),"Momentum Visitante":round(a.away_momentum,1),
            "Chance Gol 10 min %":round(a.chance_goal_10,1),"Over +1,5 Gols a Mais %":round(a.over15_more_probability,1),
            "Evolução":a.raw.get("movement",{}).get("evolution",""),"Delta Recente":a.raw.get("movement",{}).get("delta",""),
            "Confirmações":f"{a.confirmation_count}/5","Qualidade Mercado %":round(a.market_quality,1),
            "Gol Recente":"SIM" if event.get("post_goal_active") else "",
            "Min Desde Gol":event.get("minutes_since_goal","") if event.get("minutes_since_goal") is not None else "",
            "Fator Pós-Gol":_n(event.get("goal_factor"),2),
            "Dados Frescos":"NÃO" if fresh.get("stale_block") else "SIM",
            "Odd Live":round(a.market_odd,3) if a.market_odd else "","Odd Justa":round(a.fair_odd,3) if a.fair_odd else "",
            "EV %":round(a.ev_percent,2) if a.ev_percent is not None else "","Preço":a.price_status,
            "Prioridade Diário":p.live_priority if p else "","Mercado Pré":p.selected_market if p else "",
            "Probabilidade Pré %":round(p.selected_probability,1) if p else "","Atualizado":a.captured_at.isoformat(),
        })
    return out


def history_rows(source: str, records: list[dict[str,Any]], timezone_name: str = "America/Sao_Paulo") -> list[dict[str,Any]]:
    source=source.upper()
    local=ZoneInfo(timezone_name)
    out=[]
    for r in records:
        payload=dict(r.get("payload") or {})
        result=str(r.get("result") or "")
        common={
            "ID":str(r.get("id") or ""),
            "Data":str(r.get("match_date") or ""),
            "Hora":r.get("kickoff").astimezone(local).strftime("%H:%M") if isinstance(r.get("kickoff"),datetime) and r.get("kickoff").tzinfo else r.get("kickoff").strftime("%H:%M") if isinstance(r.get("kickoff"),datetime) else "",
            "País":str(r.get("country") or ""),"Campeonato":str(r.get("competition") or ""),
            "Mandante":str(r.get("home_team") or ""),"Visitante":str(r.get("away_team") or ""),
            "Mercado":str(r.get("market") or ""),"Probabilidade %":_n(r.get("probability")),"Índice":_n(r.get("market_index")),
            "Confiança":_n(r.get("confidence")),"Odd":_n(r.get("market_odd"),3),"Odd Justa":_n(r.get("fair_odd"),3),
            "EV %":_n(r.get("ev_percent"),2),"Resultado":result,"P/L":_n(r.get("profit_units"),2),
            "Modelo PRE":str(r.get("pre_model_version") or ""),"Modelo LIVE":str(r.get("live_model_version") or ""),
            "Criado em":_iso(r.get("created_at")),"Auditado em":_iso(r.get("evaluated_at")),
        }
        if source=="PRE":
            common.update({
                "Precision Score":_n(payload.get("precision_score")),
                "Qualidade Dados":_n(payload.get("data_quality")),
                "Margem Mercado":_n(payload.get("market_margin")),
                "Risco Empate":_n(payload.get("draw_risk")),
                "Prioridade Live":str(payload.get("live_priority") or ""),
                "Readiness":_n(payload.get("live_readiness_score")),
            })
        else:
            confirmations=payload.get("confirmation_count")
            if confirmations is None:
                confirmations=sum(bool(v) for v in dict(payload.get("confirmations") or {}).values())
            common.update({
                "Minuto":r.get("minute") if r.get("minute") is not None else "",
                "Placar Entrada":f"{int(payload.get('entry_home_score') or 0)} x {int(payload.get('entry_away_score') or 0)}",
                "Confirmações":f"{int(confirmations or 0)}/5",
                "Chance Gol 10 min %":_n(payload.get("chance_goal_10")),
                "Over +1,5 Gols a Mais %":_n(payload.get("over15_more_probability")),
                "Qualidade Mercado %":_n(payload.get("market_quality")),
                "Preço":str(payload.get("price_status") or ""),
            })
        out.append(common)
    return out


async def send_pre(url: str, token: str, matches: dict[str,MatchRecord], contexts: list[PregameContext]) -> None:
    await _post(url,token,"pre",pre_rows(matches,contexts))


async def send_live(url: str, token: str, matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext]) -> None:
    await _post(url,token,"live",live_rows(matches,analyses,pre))


async def send_history(url: str, token: str, source: str, records: list[dict[str,Any]], timezone_name: str = "America/Sao_Paulo") -> None:
    source=source.upper()
    payload_type="pre_history" if source=="PRE" else "live_history"
    await _post(url,token,payload_type,history_rows(source,records,timezone_name))
