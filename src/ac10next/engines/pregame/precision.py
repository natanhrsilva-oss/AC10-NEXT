from __future__ import annotations

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
    """High-selectivity score used only for PRE recommendations.

    This is deliberately separate from Live Readiness. Readiness answers whether a
    match deserves LIVE resources; Precision answers whether PRE is strong enough
    to be offered as a standalone recommendation.
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
        score -= max(0.0, context.draw_risk - 45.0) * 0.25

    return round(clamp(score, 0.0, 100.0), 2)


def decorate_precision(context: PregameContext, settings: Settings) -> PregameContext:
    score = precision_score(context)
    odd = selected_odd(context)
    specialist = selected_specialist(context)
    ev = ev_percent(context.selected_probability / 100.0, odd) if odd else None
    implied = 100.0 / odd if odd else None
    gap = abs(context.selected_probability - implied) if implied is not None else None
    qualifies = is_high_confidence(context, settings, score=score, odd=odd, ev=ev, gap=gap)
    context.raw["precision"] = {
        "score": score,
        "qualifies": qualifies,
        "odd": odd,
        "fair_odd": fair_odd(context.selected_probability / 100.0),
        "ev_percent": round(ev, 3) if ev is not None else None,
        "model_market_gap_pp": round(gap, 3) if gap is not None else None,
        "specialist_status": specialist.get("status"),
        "specialist_risks": list(specialist.get("risks") or []),
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
    score = precision_score(context) if score is None else score
    odd = selected_odd(context) if odd is None else odd
    specialist = selected_specialist(context)
    if ev is None and odd:
        ev = ev_percent(context.selected_probability / 100.0, odd)
    if gap is None and odd:
        gap = abs(context.selected_probability - 100.0 / odd)

    if specialist.get("status") != "RECOMENDAÇÃO":
        return False
    if context.data_quality < settings.pre_recommendation_min_data_quality:
        return False
    if context.confidence < settings.pre_recommendation_min_confidence:
        return False
    if context.selected_index < settings.pre_recommendation_min_index:
        return False
    if context.selected_probability < settings.pre_recommendation_min_probability:
        return False
    if context.selected_market.startswith("BACK") and context.draw_risk > settings.pre_recommendation_max_draw_risk:
        return False
    if context.market_margin < settings.pre_recommendation_min_margin:
        return False
    if score < settings.pre_recommendation_min_precision:
        return False
    if not odd or odd < settings.min_recommendation_odd:
        return False
    if ev is None or ev < settings.pre_recommendation_min_ev_percent:
        return False
    if gap is not None and gap > settings.max_model_market_gap_pp:
        return False
    return True


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
