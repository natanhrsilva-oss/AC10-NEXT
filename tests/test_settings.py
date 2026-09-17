from ac10next.settings import Settings


def test_defaults_keep_live_operational_contract():
    s = Settings(_env_file=None)
    assert s.app_timezone == "America/Sao_Paulo"
    assert (s.live_minute_start, s.live_minute_end) == (10, 88)
    assert s.live_fast_lane_seconds == 300
    assert s.live_discovery_lane_seconds == 600
    assert s.live_summary_min_index == 55
    assert s.live_summary_limit == 5
