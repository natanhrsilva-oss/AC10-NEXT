from __future__ import annotations

from datetime import datetime, timezone

from ac10next.domain.models import LiveAnalysis, LiveStats, MatchRecord, PregameContext, TeamProfile


def make_match(*, minute: int = 0, home_score: int = 0, away_score: int = 0) -> MatchRecord:
    return MatchRecord(
        match_id="m1", kickoff=datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc), match_date="2026-09-16",
        country="Brazil", competition_id="71", competition="Serie A", season=2026,
        home_team_id="h1", home_team="Casa FC", away_team_id="a1", away_team="Visitante FC",
        state="Second Half" if minute > 45 else "First Half", minute=minute, home_score=home_score, away_score=away_score,
    )


def make_profile(team_id: str, name: str, *, strong: bool = False) -> TeamProfile:
    if strong:
        recent = {"form_points": 78, "gf": 2.1, "ga": .8, "over": 64, "quality": 90, "matches": 5}
        hist = {"available": True, "matches": 42, "avg_gf": 1.9, "avg_ga": .85, "attack": 78, "defense": 67,
                "historical_strength": 72, "over25_rate": 63, "quality": 82,
                "home_split": {"available": True, "attack": 81, "defense": 69, "historical_strength": 76, "avg_gf": 2.05, "avg_ga": .75, "over25_rate": 65},
                "away_split": {"available": True, "attack": 72, "defense": 62, "historical_strength": 67, "avg_gf": 1.55, "avg_ga": 1.0, "over25_rate": 59},
                "competition_profiles": {}}
    else:
        recent = {"form_points": 37, "gf": 1.0, "ga": 1.65, "over": 55, "quality": 90, "matches": 5}
        hist = {"available": True, "matches": 40, "avg_gf": 1.05, "avg_ga": 1.6, "attack": 55, "defense": 51,
                "historical_strength": 42, "over25_rate": 54, "quality": 80,
                "home_split": {"available": True, "attack": 57, "defense": 53, "historical_strength": 45, "avg_gf": 1.2, "avg_ga": 1.45, "over25_rate": 54},
                "away_split": {"available": True, "attack": 50, "defense": 46, "historical_strength": 37, "avg_gf": .9, "avg_ga": 1.8, "over25_rate": 56},
                "competition_profiles": {}}
    return TeamProfile(
        team_id=team_id, team_name=name, recent_matches=5, history_matches=40, recent_form=float(recent["form_points"]),
        attack=78 if strong else 53, defense=67 if strong else 49, weight=73 if strong else 43,
        avg_gf=float(hist["avg_gf"]), avg_ga=float(hist["avg_ga"]), over25_rate=float(hist["over25_rate"]),
        competition_history_strength=float(hist["historical_strength"]), opponent_strength=65 if strong else 45,
        data_quality=88, source="test", raw={"recent": recent, "history": hist},
    )


def make_pre() -> PregameContext:
    return PregameContext(
        match_id="m1", model_version="AC10-NEXT-PRE-0.2.0", calculated_at=datetime.now(timezone.utc), data_quality=86,
        competition_priority=90, home_attack=78, home_defense=67, home_weight=73, home_recent_form=78,
        away_attack=53, away_defense=49, away_weight=43, away_recent_form=37,
        expected_home_goals=2.05, expected_away_goals=.85, expected_total_goals=2.90, league_avg_goals=2.65, league_over25_rate=58,
        home_persona="⚔️ AGRESSIVO", away_persona="💥 FRÁGIL", home_posture="PRESSÃO ALTA", away_posture="BAIXA INTENSIDADE", game_profile="🏠 CASA DOMINANTE",
        back_home_probability=68, back_away_probability=18, goals_probability=59, back_home_index=76, back_away_index=30, goals_index=61,
        selected_market="BACK CASA", selected_probability=68, selected_index=76, market_margin=15, confidence=79, draw_risk=31,
        goals_profile=64, explosive_score=60, live_readiness_score=78, live_priority="A",
        home_odd=1.78, draw_odd=3.6, away_odd=5.2, over25_odd=1.92,
        raw={
            "home_profile": {"recent": {"gf": 2.1, "ga": .8, "form_points": 78}, "history": {"avg_gf": 1.9, "avg_ga": .85, "quality": 82}},
            "away_profile": {"recent": {"gf": 1.0, "ga": 1.65, "form_points": 37}, "history": {"avg_gf": 1.05, "avg_ga": 1.6, "quality": 80}},
        },
    )


def make_stats() -> LiveStats:
    return LiveStats(home_shots=12, away_shots=4, home_sot=5, away_sot=1, home_corners=6, away_corners=2,
                     home_dangerous=46, away_dangerous=18, home_possession=63, away_possession=37,
                     available=True, data_mode="FULL_STATS", data_quality=92)


def make_analysis(index: float = 70, status: str = "AQUECENDO") -> LiveAnalysis:
    return LiveAnalysis(
        match_id="m1", captured_at=datetime.now(timezone.utc), minute=72, home_score=1, away_score=1, state="Second Half",
        live_data_mode="FULL_STATS", data_quality=90, home_shots=12, away_shots=4, home_sot=5, away_sot=1, home_corners=6, away_corners=2,
        home_dangerous=46, away_dangerous=18, home_possession=63, away_possession=37, home_red_cards=0, away_red_cards=0,
        home_pressure=74, away_pressure=38, home_recent_pressure=70, away_recent_pressure=32, home_momentum=18, away_momentum=-3,
        home_momentum_slope=6, away_momentum_slope=-2, activity=76, gpi=73, gpi_delta=6, home_idd=82, away_idd=36, idd_delta=46,
        home_need=75, away_need=75, chance_goal_10=68, over15_more_probability=41, movement_score=72, movement_trend="SUBINDO",
        selected_market="GOL MANDANTE", selected_probability=57, market_index=index, market_quality=84, confirmation_count=4, status=status,
        fair_odd=1.75, market_odd=None, ev_percent=None, price_status="SEM PREÇO LIVE", fingerprint="abc123", raw={"movement":{"delta":12}},
    )
