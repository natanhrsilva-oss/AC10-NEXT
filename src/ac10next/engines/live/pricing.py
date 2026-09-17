from __future__ import annotations

import hashlib

from ac10next.domain.models import LiveAnalysis
from ac10next.settings import Settings
from ac10next.utils import ev_percent


def apply_price(analysis: LiveAnalysis, odd: float, settings: Settings) -> None:
    """Apply a live market price to a sporting recommendation candidate.

    The sporting engine is intentionally independent from bookmaker prices. This
    function is the final guard: low odds, negative EV and suspiciously large
    model/market gaps can downgrade an otherwise valid sporting signal.
    """
    if not odd or odd <= 1.0:
        analysis.price_status = "SEM PREÇO LIVE"
        if settings.live_require_price_for_recommendation and analysis.status == "RECOMENDAÇÃO":
            analysis.status = "AQUECENDO"
        analysis.raw["price"] = {
            "status": analysis.price_status,
            "required": settings.live_require_price_for_recommendation,
        }
        return

    analysis.market_odd = float(odd)
    analysis.ev_percent = ev_percent(analysis.selected_probability / 100.0, analysis.market_odd)
    implied = 100.0 / analysis.market_odd
    gap = abs(analysis.selected_probability - implied)

    if analysis.market_odd < settings.min_recommendation_odd:
        analysis.price_status = f"ODD BAIXA (<{settings.min_recommendation_odd:.2f})"
        if analysis.status == "RECOMENDAÇÃO":
            analysis.status = "SEM ENTRADA"
    elif gap > settings.max_model_market_gap_pp or analysis.ev_percent > settings.max_recommendation_ev_percent:
        analysis.price_status = "PREÇO INCONSISTENTE"
        if analysis.status == "RECOMENDAÇÃO":
            analysis.status = "AQUECENDO"
    elif analysis.ev_percent < 0:
        analysis.price_status = "SEM VALOR"
        if analysis.status == "RECOMENDAÇÃO":
            analysis.status = "SEM ENTRADA"
    else:
        analysis.price_status = "PREÇO OK"

    analysis.raw["price"] = {
        "market_odd": round(analysis.market_odd, 4),
        "fair_odd": analysis.fair_odd,
        "ev_percent": round(analysis.ev_percent, 3),
        "implied_probability": round(implied, 3),
        "model_market_gap_pp": round(gap, 3),
        "status": analysis.price_status,
    }

    # Price/status changes are material snapshot information.
    analysis.fingerprint = hashlib.sha1(
        f"{analysis.fingerprint}|{analysis.status}|{analysis.price_status}|{analysis.market_odd:.3f}".encode()
    ).hexdigest()[:20]
