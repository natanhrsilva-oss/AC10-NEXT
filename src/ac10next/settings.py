from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    supabase_database_url: str = ""

    highlightly_api_key: str = ""
    highlightly_base_url: str = "https://sports.highlightly.net"
    highlightly_bookmaker: str = "Bet365"

    discord_webhook_url: str = ""
    google_sheets_webapp_url: str = ""
    google_sheets_token: str = ""

    app_timezone: str = "America/Sao_Paulo"
    app_hour_start: int = 6
    app_hour_end: int = 23

    pre_model_version: str = "AC10-NEXT-PRE-0.4.0"
    live_model_version: str = "AC10-NEXT-LIVE-0.4.0"
    calibration_version: str = "AC10-NEXT-CAL-0.4.0"

    history_lookback_days: int = 730
    team_profile_cache_hours: int = 24
    recent_weight: float = 0.75
    historical_weight: float = 0.25

    http_timeout_seconds: float = 12.0
    http_max_connections: int = 30
    highlightly_concurrency: int = 12
    highlightly_max_retries: int = 4

    pre_max_teams_refresh: int = 220
    pre_max_odds_requests: int = 20
    pre_odds_min_index: float = 55.0
    pre_recommendation_limit: int = 10
    pre_recommendation_min_data_quality: float = 65.0
    pre_recommendation_min_confidence: float = 68.0
    pre_recommendation_min_index: float = 65.0
    pre_recommendation_min_probability: float = 60.0
    pre_recommendation_min_margin: float = 6.0
    pre_recommendation_min_precision: float = 70.0
    pre_recommendation_min_ev_percent: float = 0.0
    pre_recommendation_max_draw_risk: float = 55.0

    live_minute_start: int = 10
    live_minute_end: int = 88
    live_fast_lane_seconds: int = 300
    live_discovery_lane_seconds: int = 600
    live_max_stats_requests_per_run: int = 80
    live_max_odds_requests_per_run: int = 15
    live_require_price_for_recommendation: bool = True
    live_summary_min_index: float = 55.0
    live_summary_limit: int = 5
    sheet_history_limit: int = 1000

    min_back_odd: float = 1.60
    min_recommendation_odd: float = 1.60
    max_model_market_gap_pp: float = 20.0
    max_recommendation_ev_percent: float = 100.0

    pre_discord_enabled: bool = True
    live_discord_enabled: bool = True
    sheets_enabled: bool = True

    @property
    def database_enabled(self) -> bool:
        return bool(self.supabase_database_url.strip())

    @property
    def highlightly_enabled(self) -> bool:
        return bool(self.highlightly_api_key.strip())
