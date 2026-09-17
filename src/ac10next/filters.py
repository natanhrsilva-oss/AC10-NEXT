from __future__ import annotations

import re

BLOCKED_PATTERNS = [
    r"\bwomen\b", r"\bfemin", r"\bwsl\b", r"\bliga feminina\b",
    r"\bu\s?-?\d{2}\b", r"\bsub\s?-?\d{2}\b", r"\byouth\b", r"\bjunior",
    r"\breserve", r"\breservas?\b", r"\bii\b", r"\bb team\b",
    r"\bfriendly\b", r"\bamistos",
    r"\brussia\b", r"\brussian\b", r"\brússia\b",
]
LIVE_BLOCKED_PATTERNS = [p for p in BLOCKED_PATTERNS if p not in {r"\bfriendly\b", r"\bamistos"}]


def exclusion_reason(*values: str, live: bool = False) -> str | None:
    text = " ".join(str(v or "") for v in values).lower()
    patterns = LIVE_BLOCKED_PATTERNS if live else BLOCKED_PATTERNS
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return f"Excluído pelo filtro estrutural: {pattern}"
    return None
