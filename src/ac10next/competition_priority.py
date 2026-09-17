from __future__ import annotations

from .utils import normalize_name


def competition_priority_score(country: str, competition: str) -> float:
    c = normalize_name(country)
    l = normalize_name(competition)
    joined = f"{c} {l}"
    if any(x in l for x in ("champions league", "copa libertadores", "world cup", "copa america")):
        return 100.0
    if any(x in l for x in ("europa league", "copa sudamericana")):
        return 92.0
    if "conference league" in l:
        return 88.0
    elite = {
        "england": ("premier league",), "spain": ("la liga", "primera division"),
        "italy": ("serie a",), "germany": ("bundesliga",), "france": ("ligue 1",),
        "brazil": ("serie a", "brasileirao", "campeonato brasileiro"),
        "brasil": ("serie a", "brasileirao", "campeonato brasileiro"),
    }
    for nation, names in elite.items():
        if nation in c and any(name in l for name in names):
            return 100.0
    strong = {
        "portugal": ("primeira liga", "liga portugal"), "netherlands": ("eredivisie",),
        "argentina": ("liga profesional", "primera division"), "belgium": ("pro league",),
        "turkey": ("super lig",), "turkiye": ("super lig",), "scotland": ("premiership",),
        "japan": ("j1 league",), "japao": ("j1 league",), "south korea": ("k league 1",),
    }
    for nation, names in strong.items():
        if nation in c and any(name in l for name in names):
            return 90.0
    if ("united states" in c or "usa" in c) and ("major league soccer" in l or l == "mls"):
        return 85.0
    if "mexico" in c and "liga mx" in l:
        return 85.0
    if "saudi" in c and "pro league" in l:
        return 82.0
    if any(x in l for x in ("fa cup", "copa del rey", "coppa italia", "dfb pokal", "copa do brasil")):
        return 82.0
    if any(x in l for x in ("championship", "serie b", "segunda division", "la liga 2", "2 bundesliga", "ligue 2")):
        return 72.0
    if any(x in l for x in ("premier division", "premier league", "first division", "super league", "liga 1", "primera division", "allsvenskan", "eliteserien", "superliga", "ekstraklasa")):
        return 68.0
    if any(x in joined for x in ("third division", "league one", "league two", "serie c", "serie d", "regional", "estadual", "national league")):
        return 45.0
    return 55.0


def live_priority(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    return "C"
