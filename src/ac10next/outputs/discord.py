from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from ac10next.domain.models import LiveAnalysis, MatchRecord, PregameContext


def live_summary(matches: dict[str,MatchRecord], analyses: list[LiveAnalysis], pre: dict[str,PregameContext], *, min_index: float = 55.0, limit: int = 5) -> tuple[str,str] | None:
    eligible=sorted([a for a in analyses if a.market_index>=min_index], key=lambda a:(a.market_index,a.confirmation_count,a.selected_probability), reverse=True)
    if not eligible:return None
    top=eligible[:limit]
    lines=[f"⚡ **AC10 LIVE** — {len(eligible)} jogo(s) acima de {min_index:.0f} de índice",""]
    for i,a in enumerate(top,1):
        m=matches[a.match_id]; p=pre.get(a.match_id)
        emoji="✅" if a.status=="RECOMENDAÇÃO" else "🎯" if a.status=="SINAL" else "🌡️" if a.status=="AQUECENDO" else "👀"
        lines.append(f"{emoji} **{i}. {m.home_team} x {m.away_team}**")
        lines.append(f"{a.minute}' | **{a.home_score} x {a.away_score}** | Entrada analisada: **{a.selected_market}**")
        lines.append(f"Índice **{a.market_index:.1f}** | Prob. **{a.selected_probability:.1f}%** | GPI {a.gpi:.1f} | Conf. {a.confirmation_count}/5")
        if a.market_odd:
            ev_txt=f"{a.ev_percent:+.1f}%" if a.ev_percent is not None else "ND"
            lines.append(f"Odd **{a.market_odd:.2f}** | Fair {a.fair_odd:.2f} | EV **{ev_txt}** | {a.price_status}")
        lines.append(f"Gol 10m {a.chance_goal_10:.1f}% | +1,5 gols {a.over15_more_probability:.1f}% | Evolução {a.movement_trend}")
        if p:
            lines.append(f"Prioridade Diário **{p.live_priority}** | Mercado Pré **{p.selected_market}** | Prob. Pré {p.selected_probability:.1f}%")
        lines.append("")
    text="\n".join(lines).strip()
    key_obj=[(a.match_id,a.selected_market,a.status,int(a.market_index//5),a.home_score,a.away_score) for a in top]
    key="live-summary:"+hashlib.sha1(json.dumps(key_obj,sort_keys=True).encode()).hexdigest()[:20]
    return key,text


def pre_summary(matches: dict[str,MatchRecord], contexts: list[PregameContext], *, total_prepared: int | None = None, limit: int = 10) -> tuple[str,str] | None:
    # contexts must already be filtered by the PRE Precision layer. If there is
    # no high-confidence candidate, PRE stays silent instead of filling slots.
    # The PRE selector already returns a diversity-aware quality ranking. Keep
    # that order here instead of re-sorting by raw Precision and reintroducing
    # the market-scale bias we just removed.
    top=list(contexts[:limit])
    if not top:return None
    prepared=total_prepared if total_prepared is not None else len(contexts)
    lines=[f"🎯 **AC10 PRE — ALTA CONFIANÇA** — {len(top)} recomendação(ões) de {prepared} jogos preparados","" ]
    for i,p in enumerate(top,1):
        m=matches[p.match_id]; precision=dict(p.raw.get("precision") or {})
        odd=precision.get("odd"); ev=precision.get("ev_percent"); score=precision.get("score")
        lines.append(f"✅ **{i}. {m.home_team} x {m.away_team}** | {m.kickoff.strftime('%H:%M')}")
        location = " - ".join(x for x in (str(m.country or "").strip(), str(m.competition or "").strip()) if x) or "Liga ND"
        detail=f"**({location}) {p.selected_market}** | Prob. **{p.selected_probability:.1f}%** | Índice **{p.selected_index:.1f}** | Precision **{float(score or 0):.1f}**"
        # Price is informative only. When Highlightly has no usable price, omit
        # Odd/EV entirely instead of printing ND noise in the Discord message.
        if odd:
            detail += f" | Odd **{float(odd):.2f}**"
            if ev is not None:
                detail += f" | EV **{float(ev):+.1f}%**"
        lines.append(detail)
        lines.append("")
    text="\n".join(lines).strip()
    key_obj=[(p.match_id,p.selected_market) for p in top]
    key="pre-summary:"+hashlib.sha1(json.dumps(key_obj,sort_keys=True).encode()).hexdigest()[:20]
    return key,text


async def send(webhook_url: str, content: str) -> None:
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        response=await client.post(webhook_url,json={"content":content[:1950]})
        response.raise_for_status()
