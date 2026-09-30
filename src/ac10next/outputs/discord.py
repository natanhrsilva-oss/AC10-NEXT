from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

import httpx

from ac10next.domain.models import LiveAnalysis, MatchRecord, PregameContext
from ac10next.providers.parsers import normalize_state


def _location(match: MatchRecord) -> str:
    return " - ".join(x for x in (str(match.country or "").strip(), str(match.competition or "").strip()) if x) or "Liga ND"


def _pre_icon(market: str) -> str:
    market = str(market or "").upper()
    if market == "BACK CASA":
        return "🏠"
    if market == "BACK VISITANTE":
        return "✈️"
    return "⚽"


def _score_10(context: PregameContext) -> float:
    precision = dict(context.raw.get("precision") or {})
    try:
        value = float(precision.get("score") or 0.0) / 10.0
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(10.0, value))


def _score_text(value: float) -> str:
    rounded = round(float(value), 1)
    return f"{int(rounded)}/10" if rounded.is_integer() else f"{rounded:.1f}/10"


def _ellipsize(value: str, limit: int) -> str:
    text=str(value or "")
    return text if len(text)<=limit else text[:max(1,limit-1)].rstrip()+"…"


def _live_state_hash(analyses: list[LiveAnalysis], *, min_index: float) -> str:
    """Hash only meaningful LIVE changes so small metric noise does not spam Discord."""
    running=[a for a in analyses if normalize_state(a.state)!="half time"]
    above=[a for a in running if a.market_index>=min_index]
    status_priority={"RECOMENDAÇÃO":3,"SINAL":2,"AQUECENDO":1,"SEM ENTRADA":0}
    top=sorted(
        [a for a in above if a.status in {"AQUECENDO","SINAL","RECOMENDAÇÃO"}],
        key=lambda a:(status_priority.get(a.status,0),a.market_index,a.confirmation_count,a.selected_probability),
        reverse=True,
    )[:5]
    state={
        "with_data":len(running),
        "above":len(above),
        "recs":sum(a.status=="RECOMENDAÇÃO" for a in above),
        "signal":sum(a.status=="SINAL" for a in above),
        "back_home":sum(a.selected_market=="BACK CASA" for a in above),
        "back_away":sum(a.selected_market=="BACK VISITANTE" for a in above),
        "prob60":sum(a.selected_probability>=60 for a in running),
        "mom15":sum(abs(float(a.home_momentum)-float(a.away_momentum))>=15 for a in running),
        "goal60":sum(a.chance_goal_10>=60 for a in running),
        "top":[
            (
                a.match_id,a.selected_market,a.status,a.home_score,a.away_score,
                int(a.market_index//5),int(a.selected_probability//5),
                int(abs(float(a.home_momentum)-float(a.away_momentum))//5),
            )
            for a in top
        ],
    }
    return hashlib.sha1(json.dumps(state,sort_keys=True).encode()).hexdigest()[:20]


def live_summary(
    matches: dict[str,MatchRecord],
    analyses: list[LiveAnalysis],
    pre: dict[str,PregameContext],
    *,
    min_index: float = 55.0,
    limit: int = 5,
    total_with_data: int | None = None,
    local_time: str | None = None,
) -> tuple[str,str] | None:
    """Build the operational LIVE panorama plus the best current opportunities.

    The first tuple item is a stable state hash. The pipeline compares it with the
    last sent state so :15/:30/:45 messages are only emitted when something
    meaningful changed. Hourly :00 summaries are always allowed by the pipeline.
    """
    del pre  # kept in the signature for compatibility and future context use
    running=[a for a in analyses if normalize_state(a.state)!="half time"]
    if not running:
        return None

    above=[a for a in running if a.market_index>=min_index]
    actionable=[a for a in above if a.status in {"AQUECENDO","SINAL","RECOMENDAÇÃO"}]
    status_priority={"RECOMENDAÇÃO":3,"SINAL":2,"AQUECENDO":1}
    top=sorted(
        actionable,
        key=lambda a:(status_priority.get(a.status,0),a.market_index,a.confirmation_count,a.selected_probability),
        reverse=True,
    )[:limit]

    with_data=int(total_with_data if total_with_data is not None else len(running))
    recs=sum(a.status=="RECOMENDAÇÃO" for a in above)
    observing=sum(a.status in {"SINAL","AQUECENDO"} for a in above)
    back_home=sum(a.selected_market=="BACK CASA" for a in above)
    back_away=sum(a.selected_market=="BACK VISITANTE" for a in above)
    goals=max(0,len(above)-back_home-back_away)
    prob60=sum(a.selected_probability>=60 for a in running)
    momentum15=sum(abs(float(a.home_momentum)-float(a.away_momentum))>=15 for a in running)
    goal10_60=sum(a.chance_goal_10>=60 for a in running)

    stamp=f" — {local_time}" if local_time else ""
    lines=[
        f"⚡ **AC10 LIVE{stamp}**",
        f"📡 **{with_data} jogos com dados**",
        f"🎯 Índice ≥{min_index:.0f}: **{len(above)}** | ✅ Entradas: **{recs}** | 👀 Observar: **{observing}**",
        f"🏠 Back Casa ≥{min_index:.0f}: **{back_home}** | ✈️ Back Visitante ≥{min_index:.0f}: **{back_away}** | ⚽ Gols ≥{min_index:.0f}: **{goals}**",
        f"📈 Prob. ≥60%: **{prob60}** | 🚀 Momentum dominante Δ≥15: **{momentum15}** | ⚡ Gol 10m ≥60%: **{goal10_60}**",
        "",
        "🏆 **MELHORES OPORTUNIDADES**",
    ]
    if not top:
        lines.append(f"Nenhum jogo acionável acima de **{min_index:.0f}** neste momento.")
    else:
        for i,a in enumerate(top,1):
            m=matches.get(a.match_id)
            if not m:
                continue
            emoji="✅" if a.status=="RECOMENDAÇÃO" else "👀" if a.status=="SINAL" else "🌡️"
            mom_delta=abs(float(a.home_momentum)-float(a.away_momentum))
            lines.append(f"{emoji} **{i}. {m.home_team} x {m.away_team}** {a.minute}' | **{a.home_score} x {a.away_score}** | **({_location(m)})**")
            lines.append(f"Entrada: **{a.selected_market}** | Índice **{a.market_index:.1f}** | Prob. **{a.selected_probability:.1f}%** | Conf. **{a.confirmation_count}/5**")
            fair=f"{a.fair_odd:.2f}" if a.fair_odd else "ND"
            lines.append(f"Odd justa **{fair}** | Gol 10m **{a.chance_goal_10:.1f}%** | +1,5 gols **{a.over15_more_probability:.1f}%** | Mom. Δ **{mom_delta:.1f}**")
            lines.append("")
    text="\n".join(lines).strip()
    if len(text)>1900:
        # Keep the panorama intact and compact only fixture metadata.
        compact=lines[:6]+["","🏆 **MELHORES OPORTUNIDADES**"]
        for i,a in enumerate(top,1):
            m=matches.get(a.match_id)
            if not m:
                continue
            emoji="✅" if a.status=="RECOMENDAÇÃO" else "👀" if a.status=="SINAL" else "🌡️"
            compact.append(f"{emoji} **{i}. {_ellipsize(m.home_team,18)} x {_ellipsize(m.away_team,18)}** {a.minute}' | **{a.home_score} x {a.away_score}**")
            compact.append(f"**{a.selected_market}** | Índ. **{a.market_index:.1f}** | Prob. **{a.selected_probability:.1f}%** | Gol10 **{a.chance_goal_10:.1f}%**")
        text="\n".join(compact).strip()
    return _live_state_hash(running,min_index=min_index),text


def weekly_audit_summary(stats: dict[str,Any], reliability: dict[str,int], *, expected_live_slots: int) -> str:
    start=str(stats.get("start_date") or "")
    end=str(stats.get("end_date") or "")
    totals=dict(stats.get("totals") or {})
    markets=dict(stats.get("markets") or {})
    lines=[f"📊 **AC10 — AUDITORIA SEMANAL** | {start} → {end}",""]

    for source,title,icon in (("PRE","PRÉ","🎯"),("LIVE","LIVE","⚡")):
        row=dict(totals.get(source) or {})
        recs=int(row.get("recommendations") or 0)
        games=int(row.get("games") or 0)
        reviewed=int(row.get("reviewed") or 0)
        greens=int(row.get("greens") or 0)
        reds=int(row.get("reds") or 0)
        pending=max(0,recs-greens-reds)
        decided=greens+reds
        hit=(greens/decided*100) if decided else 0.0
        priced=int(row.get("priced") or 0)
        units=float(row.get("profit_units") or 0.0)
        lines.extend([
            f"{icon} **{title}**",
            f"Jogos: **{games}** | Entradas: **{recs}** | Verificadas: **{reviewed}** | Pendentes: **{pending}**",
            f"🟢 Acertos: **{greens}** | 🔴 Erros: **{reds}** | Assertividade: **{hit:.1f}%**",
        ])
        if priced:
            lines.append(f"💰 Entradas com odd: **{priced}** | Resultado auditado: **{units:+.2f}u**")
        market_rows=list(markets.get(source) or [])[:4]
        if market_rows:
            parts=[]
            for mr in market_rows:
                mg=int(mr.get("greens") or 0); mrds=int(mr.get("reds") or 0); md=mg+mrds
                rate=(mg/md*100) if md else 0.0
                parts.append(f"{mr.get('market')}: {mg}-{mrds} ({rate:.0f}%)")
            lines.append("Mercados: " + " • ".join(parts))
        lines.append("")

    ok=int(reliability.get("successful_slots") or 0)
    recovered=int(reliability.get("watchdog_recoveries") or 0)
    errors=int(reliability.get("errors") or 0)
    lines.extend([
        "🤖 **OPERAÇÃO LIVE**",
        f"Slots concluídos: **{ok}/{expected_live_slots}** | Recuperados pelo watchdog: **{recovered}** | Execuções com erro: **{errors}**",
    ])
    return "\n".join(lines).strip()


def pre_summaries(matches: dict[str,MatchRecord], contexts: list[PregameContext], *, total_prepared: int | None = None, limit: int = 10) -> list[tuple[str,str]]:
    # Selection is already quality-ranked by the PRE engine. Preserve the best
    # N first, then reorder only those selected fixtures chronologically.
    selected=list(contexts[:limit])
    if not selected:
        return []
    prepared=total_prepared if total_prepared is not None else len(contexts)
    top=sorted(selected,key=lambda p:(matches[p.match_id].kickoff,p.match_id))

    counts=Counter(p.selected_market for p in selected)
    hour_rows: dict[str,list[float]] = defaultdict(list)
    for p in selected:
        hour=matches[p.match_id].kickoff.strftime("%Hh")
        hour_rows[hour].append(_score_10(p))
    best_hours=sorted(
        hour_rows,
        key=lambda h:(len(hour_rows[h]),sum(hour_rows[h])/len(hour_rows[h])),
        reverse=True,
    )[:3]
    hours_text=" • ".join(best_hours) if best_hours else "—"
    goals=sum(v for k,v in counts.items() if not k.startswith("BACK"))
    summary_lines=[
        "📊 **AC10 PRE — RESUMO DO DIA**",
        f"Jogos analisados: **{prepared}** | Selecionados: **{len(selected)}**",
        f"🏠 BACK CASA: **{counts.get('BACK CASA',0)}** | ✈️ BACK VISITANTE: **{counts.get('BACK VISITANTE',0)}** | ⚽ GOLS: **{goals}**",
        f"⏰ Horários de atenção: **{hours_text}**",
    ]
    summary_text="\n".join(summary_lines)
    summary_key_obj={"prepared":prepared,"selected":[(p.match_id,p.selected_market) for p in selected],"hours":best_hours}
    summary_key="pre-daily-summary:"+hashlib.sha1(json.dumps(summary_key_obj,sort_keys=True).encode()).hexdigest()[:20]

    recommendation_lines=["🎯 **AC10 PRE — MELHORES DO DIA**",""]
    for i,p in enumerate(top,1):
        m=matches[p.match_id]
        precision=dict(p.raw.get("precision") or {})
        odd=precision.get("odd")
        ev=precision.get("ev_percent")
        detail=f"**{p.selected_market}** | **{_score_text(_score_10(p))}**"
        if odd:
            detail += f" | Odd **{float(odd):.2f}**"
            if ev is not None:
                detail += f" | EV **{float(ev):+.1f}%**"
        recommendation_lines.append(f"{_pre_icon(p.selected_market)} **{i}. {m.home_team} x {m.away_team}** | {m.kickoff.strftime('%H:%M')} **({_location(m)})**")
        recommendation_lines.append(detail)
        recommendation_lines.append("")
    recommendation_lines.append("──────────")
    recommendations_text="\n".join(recommendation_lines).strip()
    if len(recommendations_text) > 1900:
        # Preserve all selected games and never let Discord cut a fixture in half.
        compact=["🎯 **AC10 PRE — MELHORES DO DIA**",""]
        for i,p in enumerate(top,1):
            m=matches[p.match_id]; precision=dict(p.raw.get("precision") or {})
            odd=precision.get("odd"); ev=precision.get("ev_percent")
            detail=f"**{p.selected_market}** | **{_score_text(_score_10(p))}**"
            if odd:
                detail += f" | Odd **{float(odd):.2f}**"
                if ev is not None: detail += f" | EV **{float(ev):+.1f}%**"
            home=_ellipsize(m.home_team,22); away=_ellipsize(m.away_team,22); location=_ellipsize(_location(m),30)
            compact.append(f"{_pre_icon(p.selected_market)} **{i}. {home} x {away}** | {m.kickoff.strftime('%H:%M')} **({location})**")
            compact.append(detail)
        compact.append("──────────")
        recommendations_text="\n".join(compact).strip()
    rec_key_obj=[(p.match_id,p.selected_market) for p in top]
    rec_key="pre-top10:"+hashlib.sha1(json.dumps(rec_key_obj,sort_keys=True).encode()).hexdigest()[:20]
    return [(summary_key,summary_text),(rec_key,recommendations_text)]


def pre_summary(matches: dict[str,MatchRecord], contexts: list[PregameContext], *, total_prepared: int | None = None, limit: int = 10) -> tuple[str,str] | None:
    """Backward-compatible helper returning the detailed PRE list only."""
    messages=pre_summaries(matches,contexts,total_prepared=total_prepared,limit=limit)
    return messages[-1] if messages else None


async def send(webhook_url: str, content: str) -> None:
    if len(content) > 1950:
        raise ValueError(f"Mensagem Discord excede limite seguro: {len(content)} caracteres")
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        response=await client.post(webhook_url,json={"content":content})
        response.raise_for_status()
