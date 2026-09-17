from ac10next.filters import exclusion_reason
from ac10next.providers.parsers import extract_highlightly_main_odds


def test_structural_filters():
    assert exclusion_reason("Russia", "Premier League", "A", "B")
    assert exclusion_reason("Brazil", "U20 League", "A U20", "B U20")
    assert exclusion_reason("Brazil", "Serie A", "A", "B") is None


def test_odds_parser_reads_main_markets():
    payload = {"data": [{"odds": [
        {"bookmakerName":"Bet365","type":"prematch","market":"Full Time Result","values":[
            {"value":"Home","odd":1.80},{"value":"Draw","odd":3.50},{"value":"Away","odd":4.80}]},
        {"bookmakerName":"Bet365","type":"prematch","market":"Total Goals","line":2.5,"values":[
            {"value":"Over","odd":1.92},{"value":"Under","odd":1.88}]}
    ]}]}
    out = extract_highlightly_main_odds(payload)
    assert out["home"] == 1.80
    assert out["away"] == 4.80
    assert out["over25"] == 1.92

from ac10next.providers.parsers import extract_highlightly_live_market_odd, first_half_goal_count


def test_live_odds_parser_maps_back_and_next_goal_total():
    payload = {"data": [{"odds": [
        {"bookmakerName":"Bet365","type":"live","market":"Full Time Result","values":[
            {"value":"Home","odd":2.10},{"value":"Draw","odd":3.00},{"value":"Away","odd":3.70}]},
        {"bookmakerName":"Bet365","type":"live","market":"Total Goals 2.5","values":[
            {"value":"Over","odd":1.82},{"value":"Under","odd":1.95}]}
    ]}]}
    assert extract_highlightly_live_market_odd(payload, "BACK CASA", 1, 1) == 2.10
    assert extract_highlightly_live_market_odd(payload, "OVER +1 GOL", 1, 1) == 1.82
    assert extract_highlightly_live_market_odd(payload, "GOL MANDANTE", 1, 1) == 0.0


def test_first_half_goal_count_handles_added_time_and_var_cancel():
    events = [
        {"time":"12", "type":"Goal"},
        {"time":"44", "type":"Goal"},
        {"time":"45+1", "type":"VAR Goal Cancelled - Offside"},
        {"time":"45+3", "type":"Penalty"},
        {"time":"52", "type":"Goal"},
    ]
    assert first_half_goal_count(events) == 2
