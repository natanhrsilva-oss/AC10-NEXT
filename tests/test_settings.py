from ac10next.settings import Settings


def test_defaults_keep_live_operational_contract():
    s = Settings(_env_file=None)
    assert s.app_timezone == "America/Sao_Paulo"
    assert (s.live_minute_start, s.live_minute_end) == (10, 88)
    assert s.live_fast_lane_seconds == 300
    assert s.live_discovery_lane_seconds == 600
    assert s.live_summary_min_index == 55
    assert s.live_summary_limit == 5


def test_discord_webhook_routing_prefers_dedicated_channels_with_legacy_fallback():
    legacy = Settings(_env_file=None, discord_webhook_url="https://legacy")
    assert legacy.pre_discord_webhook == "https://legacy"
    assert legacy.live_discord_webhook == "https://legacy"

    split = Settings(
        _env_file=None,
        discord_webhook_url="https://legacy",
        discord_webhook_pre="https://pre",
        discord_webhook_live="https://live",
    )
    assert split.pre_discord_webhook == "https://pre"
    assert split.live_discord_webhook == "https://live"
