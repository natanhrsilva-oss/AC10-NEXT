from __future__ import annotations


def _profit(won: bool, odd: float | None) -> float:
    # Never invent P/L for an unpriced signal.
    if not odd or odd <= 1:
        return 0.0
    return odd - 1 if won else -1.0


def evaluate_recommendation(
    rec: dict,
    final_h: int,
    final_a: int,
    *,
    ht_goals: int | None = None,
) -> tuple[str, float, dict]:
    market = str(rec.get("market") or "")
    payload = dict(rec.get("payload") or {})
    eh = int(payload.get("entry_home_score") or 0)
    ea = int(payload.get("entry_away_score") or 0)
    won = None

    if market == "BACK CASA":
        won = final_h > final_a
    elif market == "BACK VISITANTE":
        won = final_a > final_h
    elif market in {"GOL FT", "OVER +1 GOL"}:
        won = (final_h + final_a) > (eh + ea)
    elif market == "GOL MANDANTE":
        won = final_h > eh
    elif market == "GOL VISITANTE":
        won = final_a > ea
    elif market == "OVER 2,5 GOLS":
        won = (final_h + final_a) >= 3
    elif market == "GOL HT":
        if ht_goals is None:
            return "PENDENTE_HT", 0.0, {"reason": "eventos HT indisponíveis"}
        won = ht_goals > (eh + ea)
    else:
        return "N/A", 0.0, {}

    result = "GREEN" if won else "RED"
    detail = {
        "final": f"{final_h}-{final_a}",
        "entry": f"{eh}-{ea}",
        "market_odd": rec.get("market_odd"),
        "pnl_priced": bool(rec.get("market_odd")),
    }
    if ht_goals is not None:
        detail["ht_goals"] = ht_goals
    return result, _profit(bool(won), rec.get("market_odd")), detail
