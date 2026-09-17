from __future__ import annotations

import hashlib

from ac10next.domain.models import LiveAnalysis
from ac10next.settings import Settings
from ac10next.utils import ev_percent


def apply_no_price_requirement(analysis: LiveAnalysis) -> None:
    """Promove um sinal esportivo LIVE sem consultar/usar odds.

    Na v0.4.1 a decisão LIVE é exclusivamente esportiva por padrão. O preço pode
    continuar existindo como recurso opcional, mas não é necessário para liberar
    a recomendação.
    """
    if analysis.status == "SINAL":
        analysis.status = "RECOMENDAÇÃO"
    analysis.market_odd = None
    analysis.ev_percent = None
    analysis.price_status = "ODD NÃO EXIGIDA"
    analysis.raw["price"] = {"required": False, "status": analysis.price_status}
    analysis.fingerprint = hashlib.sha1(
        f"{analysis.fingerprint}|{analysis.status}|NO_PRICE_REQUIRED".encode()
    ).hexdigest()[:20]


def apply_price(analysis: LiveAnalysis, odd: float, settings: Settings) -> None:
    """Guarda final opcional de mercado quando preço é exigido por configuração."""
    if not odd or odd <= 1.0:
        analysis.price_status = "SEM PREÇO LIVE"
        if analysis.status == "RECOMENDAÇÃO":
            analysis.status = "SINAL"
        analysis.raw["price"] = {"status": analysis.price_status, "required": True}
        return

    analysis.market_odd = float(odd)
    analysis.ev_percent = ev_percent(analysis.selected_probability / 100.0, analysis.market_odd)
    implied = 100.0 / analysis.market_odd
    gap = abs(analysis.selected_probability - implied)

    if analysis.market_odd < settings.min_recommendation_odd:
        analysis.price_status = f"ODD BAIXA (<{settings.min_recommendation_odd:.2f})"
        if analysis.status in {"SINAL", "RECOMENDAÇÃO"}:
            analysis.status = "SEM ENTRADA"
    elif gap > settings.max_model_market_gap_pp or analysis.ev_percent > settings.max_recommendation_ev_percent:
        analysis.price_status = "PREÇO INCONSISTENTE"
        if analysis.status in {"SINAL", "RECOMENDAÇÃO"}:
            analysis.status = "AQUECENDO"
    elif analysis.ev_percent < 0:
        analysis.price_status = "SEM VALOR"
        if analysis.status in {"SINAL", "RECOMENDAÇÃO"}:
            analysis.status = "SEM ENTRADA"
    else:
        analysis.price_status = "PREÇO OK"
        if analysis.status == "SINAL":
            analysis.status = "RECOMENDAÇÃO"

    analysis.raw["price"] = {
        "market_odd": round(analysis.market_odd, 4),
        "fair_odd": analysis.fair_odd,
        "ev_percent": round(analysis.ev_percent, 3),
        "implied_probability": round(implied, 3),
        "model_market_gap_pp": round(gap, 3),
        "status": analysis.price_status,
    }

    analysis.fingerprint = hashlib.sha1(
        f"{analysis.fingerprint}|{analysis.status}|{analysis.price_status}|{analysis.market_odd:.3f}".encode()
    ).hexdigest()[:20]
