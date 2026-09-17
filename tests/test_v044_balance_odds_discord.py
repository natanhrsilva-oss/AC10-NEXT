from __future__ import annotations

import copy
from dataclasses import replace

from ac10next.engines.pregame.precision import select_pre_recommendations, selection_diagnostics
from ac10next.outputs.discord import pre_summary
from ac10next.providers.parsers import extract_highlightly_best_main_odds
from ac10next.settings import Settings
from conftest import make_match, make_pre


def _candidate(match_id: str, market: str, precision_bias: float) -> object:
    c = copy.deepcopy(make_pre())
    c.match_id = match_id
    c.selected_market = market
    c.data_quality = 82.0
    c.confidence = 78.0 + precision_bias * 0.05
    c.market_margin = 9.0
    c.draw_risk = 38.0
    if market == "BACK CASA":
        c.selected_probability = 86.0 + precision_bias * 0.10
        c.selected_index = 89.0 + precision_bias * 0.08
    elif market == "BACK VISITANTE":
        c.selected_probability = 73.0 + precision_bias * 0.08
        c.selected_index = 76.0 + precision_bias * 0.07
    else:
        c.selected_probability = 70.0 + precision_bias * 0.08
        c.selected_index = 74.0 + precision_bias * 0.07
    c.raw = {
        "specialists": {
            market: {"status": "RECOMENDAÇÃO", "risks": [], "probability": c.selected_probability}
        }
    }
    c.home_odd = c.draw_odd = c.away_odd = c.over25_odd = None
    return c


def test_pre_balanced_selection_prevents_single_market_monopoly():
    settings = Settings(
        _env_file=None,
        pre_recommendation_limit=10,
        pre_recommendation_market_soft_cap=4,
        pre_recommendation_market_relative_weight=0.30,
    )
    contexts = []
    # BACK CASA intentionally has the highest raw numerical scale.
    contexts += [_candidate(f"h{i}", "BACK CASA", 12 - i) for i in range(12)]
    contexts += [_candidate(f"o{i}", "OVER 2,5 GOLS", 10 - i) for i in range(10)]
    contexts += [_candidate(f"a{i}", "BACK VISITANTE", 8 - i) for i in range(8)]

    selected = select_pre_recommendations(contexts, settings)
    counts = {}
    for c in selected:
        counts[c.selected_market] = counts.get(c.selected_market, 0) + 1

    assert len(selected) == 10
    assert max(counts.values()) <= 4
    assert len(counts) >= 3

    diag = selection_diagnostics(contexts, settings)
    assert diag["offered_by_market"] == counts
    assert diag["market_soft_cap"] == 4


def test_highlightly_odds_falls_back_to_available_bookmaker_without_mixing_books():
    payload = {
        "data": [{
            "matchId": 123,
            "odds": [
                {
                    "bookmakerName": "Stake.com",
                    "type": "prematch",
                    "market": "Full Time Result",
                    "values": [
                        {"value": "Home", "odd": 1.75},
                        {"value": "Draw", "odd": 3.70},
                        {"value": "Away", "odd": 4.80},
                    ],
                },
                {
                    "bookmakerName": "Stake.com",
                    "type": "prematch",
                    "market": "Total Goals 2.5",
                    "values": [
                        {"value": "Over", "odd": 1.88},
                        {"value": "Under", "odd": 1.96},
                    ],
                },
                {
                    "bookmakerName": "OtherBook",
                    "type": "prematch",
                    "market": "Full Time Result",
                    "values": [
                        {"value": "Home", "odd": 1.80},
                        {"value": "Draw", "odd": 3.60},
                        {"value": "Away", "odd": 4.60},
                    ],
                },
            ],
        }]
    }
    odds, bookmaker = extract_highlightly_best_main_odds(payload, "Bet365")
    assert bookmaker == "Stake.com"
    assert odds["home"] == 1.75
    assert odds["over25"] == 1.88


def test_pre_discord_has_country_league_and_omits_nd_price_fields():
    c = make_pre()
    c.home_odd = None
    c.raw["specialists"] = {"BACK CASA": {"status": "RECOMENDAÇÃO", "risks": []}}
    c.raw["precision"] = {"score": 91.2, "odd": None, "ev_percent": None}
    m = make_match()
    result = pre_summary({"m1": m}, [c], total_prepared=98, limit=10)
    assert result is not None
    _, text = result
    assert "(Brazil - Serie A) BACK CASA" in text
    assert "Odd ND" not in text
    assert "EV **ND**" not in text


def test_highlightly_client_uses_unfiltered_fallback_when_bet365_not_supported(monkeypatch):
    import asyncio
    from ac10next.providers.highlightly import HighlightlyClient

    settings = Settings(_env_file=None, highlightly_bookmaker="Bet365", highlightly_odds_fallback_any_bookmaker=True)
    client = HighlightlyClient(settings)
    calls = []

    async def fake_get(endpoint, *, params=None):
        calls.append((endpoint, dict(params or {})))
        if endpoint == "bookmakers":
            return {"data": []}
        if endpoint == "odds":
            return {
                "data": [{
                    "matchId": 123,
                    "odds": [{
                        "bookmakerName": "Stake.com",
                        "type": "prematch",
                        "market": "Full Time Result",
                        "values": [
                            {"value": "Home", "odd": 1.80},
                            {"value": "Draw", "odd": 3.40},
                            {"value": "Away", "odd": 4.50},
                        ],
                    }],
                }]
            }
        raise AssertionError(endpoint)

    monkeypatch.setattr(client, "_get", fake_get)

    async def run():
        try:
            payload = await client.prematch_odds("123")
            assert payload["_ac10_odds_query"]["mode"] == "any_bookmaker_fallback"
        finally:
            await client.close()

    asyncio.run(run())
    odds_calls = [params for endpoint, params in calls if endpoint == "odds"]
    assert len(odds_calls) == 1
    assert "bookmakerName" not in odds_calls[0]
