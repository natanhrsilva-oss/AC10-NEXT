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


def live_summary(matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext], *, min_index: float = 55.0, limit: int = 5) -> tuple[str,str] | None:
    # Discord only shows matches that are actively running and actionable enough
    # to watch. Half-time and SEM ENTRADA are never surfaced.
    running = [
        a for a in analyses
        if a.market_index >= min_index
        and normalize_state(a.state) != "half time"
        and a.status in {"AQUECENDO", "SINAL", "RECOMENDAÇÃO"}
    ]
    if not running:
        return None

    # Recommendations always take priority. If there are none (or fewer than the
    # limit), the strongest observation candidates follow by index/confirmations.
    status_priority = {"RECOMENDAÇÃO": 3, "SINAL": 2, "AQUECENDO": 1}
    eligible = sorted(
        running,
        key=lambda a:(status_priority.get(a.status,0),a.market_index,a.confirmation_count,a.selected_probability),
        reverse=True,
    )
    top=eligible[:limit]
    recs=sum(a.status=="RECOMENDAÇÃO" for a in eligible)
    lines=[f"⚡ **AC10 LIVE** — {len(eligible)} jogo(s) ativos acima de {min_index:.0f} de índice | ✅ {recs} entrada(s)",""]
    for i,a in enumerate(top,1):
        m=matches[a.match_id]
        emoji="✅" if a.status=="RECOMENDAÇÃO" else "👀" if a.status=="SINAL" else "🌡️"
        lines.append(f"{emoji} **{i}. {m.home_team} x {m.away_team}** {a.minute}' | **{a.home_score} x {a.away_score}** | **({_location(m)})**")
        lines.append(f"Entrada: **{a.selected_market}** | Índice **{a.market_index:.1f}** | Prob. **{a.selected_probability:.1f}%** | Conf. **{a.confirmation_count}/5** |")
        fair = f"{a.fair_odd:.2f}" if a.fair_odd else "ND"
        lines.append(f"Odd justa **{fair}** | Gol 10m **{a.chance_goal_10:.1f}%** | +1,5 gols **{a.over15_more_probability:.1f}%**")
        lines.append("")
    text="\n".join(lines).strip()
    key_obj=[(a.match_id,a.selected_market,a.status,int(a.market_index//5),a.home_score,a.away_score) for a in top]
    key="live-summary:"+hashlib.sha1(json.dumps(key_obj,sort_keys=True).encode()).hexdigest()[:20]
    return key,text


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
