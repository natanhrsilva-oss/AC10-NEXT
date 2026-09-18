from decimal import Decimal
import json

from ac10next.engines.audit import evaluate_recommendation
from ac10next.utils import json_safe


def test_audit_accepts_postgres_decimal_odd_and_returns_float_payload():
    rec = {
        "market": "BACK CASA",
        "market_odd": Decimal("1.72"),
        "payload": {"entry_home_score": 0, "entry_away_score": 0},
    }
    result, pnl, detail = evaluate_recommendation(rec, 2, 1)
    assert result == "GREEN"
    assert pnl == 0.72
    assert isinstance(pnl, float)
    assert detail["market_odd"] == 1.72
    assert isinstance(detail["market_odd"], float)
    assert detail["pnl_priced"] is True
    json.dumps(detail)  # regression: must not raise Decimal is not JSON serializable


def test_json_safe_recursively_converts_decimal_values():
    payload = {
        "odd": Decimal("1.80"),
        "nested": {"ev": Decimal("7.25")},
        "items": [Decimal("2.10"), None],
    }
    safe = json_safe(payload)
    assert safe == {"odd": 1.8, "nested": {"ev": 7.25}, "items": [2.1, None]}
    json.dumps(safe)


def test_decimal_odd_red_is_minus_one_float():
    rec = {
        "market": "BACK CASA",
        "market_odd": Decimal("2.05"),
        "payload": {"entry_home_score": 0, "entry_away_score": 0},
    }
    result, pnl, detail = evaluate_recommendation(rec, 0, 1)
    assert result == "RED"
    assert pnl == -1.0
    assert isinstance(pnl, float)
    assert detail["market_odd"] == 2.05
