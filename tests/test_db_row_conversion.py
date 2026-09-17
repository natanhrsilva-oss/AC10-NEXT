from datetime import datetime, timezone
from decimal import Decimal

from ac10next.domain.mappers import pregame_from_row


def test_pregame_row_converts_postgres_decimals_to_float():
    row = {
        "match_id": "m1", "model_version": "x", "calculated_at": datetime.now(timezone.utc),
        "data_quality": Decimal("80.1"), "competition_priority": Decimal("90"),
        "home_attack": Decimal("70"), "home_defense": Decimal("60"), "home_weight": Decimal("65"), "home_recent_form": Decimal("66"),
        "away_attack": Decimal("50"), "away_defense": Decimal("49"), "away_weight": Decimal("48"), "away_recent_form": Decimal("45"),
        "expected_home_goals": Decimal("1.8"), "expected_away_goals": Decimal("0.9"), "expected_total_goals": Decimal("2.7"),
        "league_avg_goals": Decimal("2.5"), "league_over25_rate": Decimal("55"),
        "home_persona": "A", "away_persona": "B", "home_posture": "A", "away_posture": "B", "game_profile": "X",
        "back_home_probability": Decimal("60"), "back_away_probability": Decimal("20"), "goals_probability": Decimal("55"),
        "back_home_index": Decimal("70"), "back_away_index": Decimal("30"), "goals_index": Decimal("58"),
        "selected_market": "BACK CASA", "selected_probability": Decimal("60"), "selected_index": Decimal("70"),
        "market_margin": Decimal("10"), "confidence": Decimal("75"), "draw_risk": Decimal("30"), "goals_profile": Decimal("60"),
        "explosive_score": Decimal("55"), "live_readiness_score": Decimal("77"), "live_priority": "A",
        "home_odd": Decimal("1.8"), "draw_odd": None, "away_odd": None, "over25_odd": None, "raw": {},
    }
    ctx = pregame_from_row(row)
    assert isinstance(ctx.home_attack, float)
    assert isinstance(ctx.selected_probability, float)
    assert ctx.home_odd == 1.8
