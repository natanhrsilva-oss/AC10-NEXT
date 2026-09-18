from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def probability(value: Any, default: float = 0.5) -> float:
    parsed = number(value, default)
    if parsed > 1.0:
        parsed /= 100.0
    return clamp(parsed, 0.0, 1.0)


def fair_odd(prob: float) -> float:
    return round(1.0 / max(0.01, float(prob)), 4)


def ev_percent(prob: float, odd: float) -> float:
    if odd <= 1.0:
        return 0.0
    return (float(prob) * float(odd) - 1.0) * 100.0


def poisson_over_25(lam: float) -> float:
    lam = max(0.01, float(lam))
    p0 = math.exp(-lam)
    p1 = p0 * lam
    p2 = p1 * lam / 2.0
    return clamp(1.0 - (p0 + p1 + p2), 0.0, 1.0)


def parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

def json_safe(value: Any) -> Any:
    """Recursively convert common DB/Python values to JSON-serializable primitives.

    PostgreSQL NUMERIC columns are returned by psycopg as Decimal.  JSON payloads
    stored through psycopg Jsonb must not receive Decimal directly.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return value

