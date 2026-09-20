from __future__ import annotations

import re

from ac10next.utils import normalize_name

BLOCKED_PATTERNS = [
    r"\bwomen\b", r"\bfemin", r"\bwsl\b", r"\bliga feminina\b",
    r"\bu\s?-?\d{2}\b", r"\bsub\s?-?\d{2}\b", r"\byouth\b", r"\bjunior",
    r"\breserve", r"\breservas?\b", r"\bii\b", r"\bb team\b",
    r"\bfriendly\b", r"\bamistos",
]
LIVE_BLOCKED_PATTERNS = [p for p in BLOCKED_PATTERNS if p not in {r"\bfriendly\b", r"\bamistos"}]

# Competições domésticas destes países não aparecem de forma confiável na Bet365
# para a operação do AC10. Clubes desses países em competições internacionais
# continuam elegíveis (Champions, Europa, Conference etc.).
BLOCKED_DOMESTIC_COUNTRIES = {"russia", "ukraine", "belarus"}
INTERNATIONAL_COMPETITION_PATTERNS = [
    r"\buefa\b", r"\bchampions league\b", r"\beuropa league\b", r"\bconference league\b",
    r"\bfifa\b", r"\bclub world cup\b", r"\bintercontinental\b",
    r"\bafc champions\b", r"\bafc cup\b", r"\bcaf champions\b", r"\bcaf confederation\b",
    r"\bconcacaf\b", r"\bconmebol\b", r"\blibertadores\b", r"\bsudamericana\b",
]


def _is_international_competition(competition: str) -> bool:
    name = normalize_name(competition)
    return any(re.search(pattern, name, flags=re.IGNORECASE) for pattern in INTERNATIONAL_COMPETITION_PATTERNS)


def exclusion_reason(country: str, competition: str, home_team: str, away_team: str, *, live: bool = False) -> str | None:
    # Structural filters (women/youth/reserves/etc.) still inspect the full fixture.
    text = " ".join(str(v or "") for v in (country, competition, home_team, away_team)).lower()
    patterns = LIVE_BLOCKED_PATTERNS if live else BLOCKED_PATTERNS
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return f"Excluído pelo filtro estrutural: {pattern}"

    # Russia/Ukraine/Belarus are blocked only when the fixture belongs to their
    # domestic competition. International competitions remain available.
    country_key = normalize_name(country)
    if country_key in BLOCKED_DOMESTIC_COUNTRIES and not _is_international_competition(competition):
        return f"Excluído por país doméstico sem mercado Bet365: {country_key}"
    return None
