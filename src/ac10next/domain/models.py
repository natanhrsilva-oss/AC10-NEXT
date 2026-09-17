from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MatchRecord:
    match_id: str
    kickoff: datetime
    match_date: str
    country: str
    competition_id: str
    competition: str
    season: int | None
    home_team_id: str
    home_team: str
    away_team_id: str
    away_team: str
    state: str = ""
    minute: int = 0
    home_score: int = 0
    away_score: int = 0
    is_excluded: bool = False
    exclusion_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TeamProfile:
    team_id: str
    team_name: str
    recent_matches: int = 0
    history_matches: int = 0
    recent_form: float = 50.0
    attack: float = 50.0
    defense: float = 50.0
    weight: float = 50.0
    avg_gf: float = 1.25
    avg_ga: float = 1.25
    over25_rate: float = 50.0
    competition_history_strength: float = 50.0
    opponent_strength: float = 50.0
    data_quality: float = 0.0
    source: str = ""
    last_match_id: str | None = None
    valid_until: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PregameFeatures:
    match: MatchRecord
    home_attack: float = 50.0
    home_defense: float = 50.0
    home_weight: float = 50.0
    home_recent_form: float = 50.0
    away_attack: float = 50.0
    away_defense: float = 50.0
    away_weight: float = 50.0
    away_recent_form: float = 50.0
    expected_home_goals: float = 1.25
    expected_away_goals: float = 1.10
    expected_total_goals: float = 2.35
    league_avg_goals: float = 2.5
    league_over25_rate: float = 50.0
    home_competition_history_strength: float = 50.0
    away_competition_history_strength: float = 50.0
    home_opponent_strength: float = 50.0
    away_opponent_strength: float = 50.0
    data_quality: float = 45.0
    competition_priority: float = 55.0
    home_odd: float = 0.0
    draw_odd: float = 0.0
    away_odd: float = 0.0
    over25_odd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyCandidate:
    market: str
    probability: float
    market_odd: float
    index: float
    status: str
    reason: str
    risks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PregameContext:
    match_id: str
    model_version: str
    calculated_at: datetime
    data_quality: float
    competition_priority: float
    home_attack: float
    home_defense: float
    home_weight: float
    home_recent_form: float
    away_attack: float
    away_defense: float
    away_weight: float
    away_recent_form: float
    expected_home_goals: float
    expected_away_goals: float
    expected_total_goals: float
    league_avg_goals: float
    league_over25_rate: float
    home_persona: str
    away_persona: str
    home_posture: str
    away_posture: str
    game_profile: str
    back_home_probability: float
    back_away_probability: float
    goals_probability: float
    back_home_index: float
    back_away_index: float
    goals_index: float
    selected_market: str
    selected_probability: float
    selected_index: float
    market_margin: float
    confidence: float
    draw_risk: float
    goals_profile: float
    explosive_score: float
    live_readiness_score: float
    live_priority: str
    home_odd: float | None = None
    draw_odd: float | None = None
    away_odd: float | None = None
    over25_odd: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LiveStats:
    home_shots: float = 0.0
    away_shots: float = 0.0
    home_sot: float = 0.0
    away_sot: float = 0.0
    home_corners: float = 0.0
    away_corners: float = 0.0
    home_dangerous: float = 0.0
    away_dangerous: float = 0.0
    home_possession: float = 50.0
    away_possession: float = 50.0
    home_red_cards: float = 0.0
    away_red_cards: float = 0.0
    available: bool = False
    data_mode: str = "HISTORICAL_ONLY"
    data_quality: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LiveInput:
    match: MatchRecord
    pre: PregameContext
    stats: LiveStats
    captured_at: datetime


@dataclass(slots=True)
class LiveAnalysis:
    match_id: str
    captured_at: datetime
    minute: int
    home_score: int
    away_score: int
    state: str
    live_data_mode: str
    data_quality: float
    home_shots: float
    away_shots: float
    home_sot: float
    away_sot: float
    home_corners: float
    away_corners: float
    home_dangerous: float
    away_dangerous: float
    home_possession: float
    away_possession: float
    home_red_cards: float
    away_red_cards: float
    home_pressure: float
    away_pressure: float
    home_recent_pressure: float
    away_recent_pressure: float
    home_momentum: float
    away_momentum: float
    home_momentum_slope: float
    away_momentum_slope: float
    activity: float
    gpi: float
    gpi_delta: float | None
    home_idd: float
    away_idd: float
    idd_delta: float
    home_need: float
    away_need: float
    chance_goal_10: float
    over15_more_probability: float
    movement_score: float
    movement_trend: str
    selected_market: str
    selected_probability: float
    market_index: float
    market_quality: float
    confirmation_count: int
    status: str
    fair_odd: float | None
    market_odd: float | None
    ev_percent: float | None
    price_status: str
    fingerprint: str
    raw: dict[str, Any] = field(default_factory=dict)
