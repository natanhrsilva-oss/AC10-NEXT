from __future__ import annotations

from collections import Counter

from ac10next.domain.models import PregameContext
from ac10next.settings import Settings
from ac10next.utils import clamp, ev_percent, fair_odd


def selected_odd(context: PregameContext) -> float | None:
    mapping = {
        "BACK CASA": context.home_odd,
        "BACK VISITANTE": context.away_odd,
        "OVER 2,5 GOLS": context.over25_odd,
    }
    value = mapping.get(context.selected_market)
    return float(value) if value and float(value) > 1.0 else None


def selected_specialist(context: PregameContext) -> dict:
    specialists = dict(context.raw.get("specialists") or {})
    return dict(specialists.get(context.selected_market) or {})


def precision_score(context: PregameContext) -> float:
    """Score exclusivo das recomendações PRE.

    Readiness responde se o jogo merece ser acompanhado no LIVE.
    Precision responde se o PRE é forte o suficiente para ser ofertado sozinho.

    A v0.4.1 evita transformar cada subindicador em trava absoluta: confiança,
    probabilidade e margem já entram no score. As travas duras ficam apenas nos
    pontos realmente esportivos (qualidade mínima, índice mínimo e consistência do sinal).
    """
    margin_component = clamp(context.market_margin / 15.0 * 100.0, 0.0, 100.0)
    score = (
        context.confidence * 0.30
        + context.selected_index * 0.25
        + context.data_quality * 0.20
        + context.selected_probability * 0.15
        + margin_component * 0.10
    )

    specialist = selected_specialist(context)
    risks = list(specialist.get("risks") or [])
    score -= min(8.0, len(risks) * 2.0)

    if context.selected_market.startswith("BACK"):
        score -= max(0.0, context.draw_risk - 55.0) * 0.10

    # OBSERVAÇÃO não elimina um jogo forte; apenas perde alguns pontos.
    if specialist.get("status") == "OBSERVAÇÃO":
        score -= 2.0
    elif specialist.get("status") == "REJEITADO":
        score -= 10.0

    return round(clamp(score, 0.0, 100.0), 2)


def _values(context: PregameContext, settings: Settings, *, score: float | None = None, odd: float | None = None, ev: float | None = None, gap: float | None = None) -> tuple[float, float | None, float | None, float | None, dict]:
    score = precision_score(context) if score is None else float(score)
    odd = selected_odd(context) if odd is None else odd
    specialist = selected_specialist(context)
    if ev is None and odd:
        ev = ev_percent(context.selected_probability / 100.0, odd)
    if gap is None and odd:
        gap = abs(context.selected_probability - 100.0 / odd)
    return score, odd, ev, gap, specialist


def qualification_reasons(
    context: PregameContext,
    settings: Settings,
    *,
    score: float | None = None,
    odd: float | None = None,
    ev: float | None = None,
    gap: float | None = None,
) -> list[str]:
    """Retorna somente as travas duras que impedem uma recomendação PRE."""
    score, odd, ev, gap, specialist = _values(context, settings, score=score, odd=odd, ev=ev, gap=gap)
    reasons: list[str] = []

    if specialist.get("status") == "REJEITADO":
        reasons.append("especialista_rejeitado")
    # Pisos de segurança: evitam que um score alto mas muito desequilibrado
    # aprove uma leitura com confiança/probabilidade realmente fracas.
    if context.confidence < max(50.0, settings.pre_recommendation_min_confidence - 10.0):
        reasons.append("confianca_muito_baixa")
    if context.selected_probability < max(50.0, settings.pre_recommendation_min_probability - 3.0):
        reasons.append("probabilidade_muito_baixa")
    if context.data_quality < settings.pre_recommendation_min_data_quality:
        reasons.append("qualidade_baixa")
    if context.selected_index < settings.pre_recommendation_min_index:
        reasons.append("indice_baixo")
    if score < settings.pre_recommendation_min_precision:
        reasons.append("precision_baixo")
    # v0.4.3: draw risk is no longer a hard veto. It is already reflected as a
    # small progressive penalty in Precision Score, preventing an artificial
    # bias that previously removed most BACK candidates.
    # v0.4.2: preço é apenas informativo no PRE.
    # Se houver odd, ela é registrada e o EV pode ser exibido, mas preço ausente,
    # odd baixa, EV negativo ou divergência modelo/mercado NÃO bloqueiam o sinal.
    # A recomendação PRE é decidida pela leitura esportiva/Precision Score.
    return reasons


def soft_flags(context: PregameContext, settings: Settings) -> list[str]:
    """Sinais de atenção que reduzem o score, mas não matam sozinhos o jogo."""
    flags=[]
    if context.confidence < settings.pre_recommendation_min_confidence:
        flags.append("confianca_moderada")
    if context.selected_probability < settings.pre_recommendation_min_probability:
        flags.append("probabilidade_moderada")
    if context.market_margin < settings.pre_recommendation_min_margin:
        flags.append("margem_curta")
    if context.selected_market.startswith("BACK") and context.draw_risk >= settings.pre_recommendation_draw_risk_attention:
        flags.append("risco_empate_atencao")
    return flags


def decorate_precision(context: PregameContext, settings: Settings) -> PregameContext:
    score = precision_score(context)
    odd = selected_odd(context)
    specialist = selected_specialist(context)
    ev = ev_percent(context.selected_probability / 100.0, odd) if odd else None
    implied = 100.0 / odd if odd else None
    gap = abs(context.selected_probability - implied) if implied is not None else None
    reasons = qualification_reasons(context, settings, score=score, odd=odd, ev=ev, gap=gap)
    context.raw["precision"] = {
        "score": score,
        "qualifies": not reasons,
        "odd": odd,
        "fair_odd": fair_odd(context.selected_probability / 100.0),
        "ev_percent": round(ev, 3) if ev is not None else None,
        "model_market_gap_pp": round(gap, 3) if gap is not None else None,
        "specialist_status": specialist.get("status"),
        "specialist_risks": list(specialist.get("risks") or []),
        "rejection_reasons": reasons,
        "soft_flags": soft_flags(context, settings),
    }
    return context


def is_high_confidence(
    context: PregameContext,
    settings: Settings,
    *,
    score: float | None = None,
    odd: float | None = None,
    ev: float | None = None,
    gap: float | None = None,
) -> bool:
    return not qualification_reasons(context, settings, score=score, odd=odd, ev=ev, gap=gap)


def select_pre_recommendations(contexts: list[PregameContext], settings: Settings) -> list[PregameContext]:
    decorated = [decorate_precision(c, settings) for c in contexts]
    qualified = [c for c in decorated if bool((c.raw.get("precision") or {}).get("qualifies"))]
    qualified.sort(
        key=lambda c: (
            float((c.raw.get("precision") or {}).get("score") or 0),
            c.confidence,
            c.selected_index,
            c.selected_probability,
        ),
        reverse=True,
    )
    return qualified[: settings.pre_recommendation_limit]


def selection_diagnostics(contexts: list[PregameContext], settings: Settings) -> dict:
    """Funil legível no log para calibrar o PRE sem adivinhação."""
    decorated=[decorate_precision(c,settings) for c in contexts]
    reasons=Counter()
    near=[]
    qualified=0
    for c in decorated:
        p=dict(c.raw.get("precision") or {})
        rs=list(p.get("rejection_reasons") or [])
        if not rs:
            qualified+=1
        else:
            reasons.update(rs)
            near.append({
                "match_id":c.match_id,
                "market":c.selected_market,
                "precision":p.get("score"),
                "index":round(c.selected_index,1),
                "probability":round(c.selected_probability,1),
                "confidence":round(c.confidence,1),
                "odd":p.get("odd"),
                "ev":p.get("ev_percent"),
                "reasons":rs,
            })
    near.sort(key=lambda x:(float(x.get("precision") or 0),float(x.get("index") or 0)),reverse=True)
    return {
        "evaluated":len(decorated),
        "qualified_before_limit":qualified,
        "offered":min(qualified,settings.pre_recommendation_limit),
        "rejections":dict(reasons.most_common()),
        "near_misses":near[:5],
    }
