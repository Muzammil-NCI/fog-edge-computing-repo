from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

REQUIRED = ("device_id", "zone", "metric", "value", "unit")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_event(data: dict[str, Any]) -> dict[str, Any] | None:
    for k in REQUIRED:
        if k not in data:
            return None
    try:
        value = float(data["value"])
    except (TypeError, ValueError):
        return None
    if not all(isinstance(data[k], str) and data[k] for k in ("device_id", "zone", "metric", "unit")):
        return None
    ts = data.get("timestamp")
    if not isinstance(ts, str):
        ts = utc_now_iso()
    return {
        "device_id": data["device_id"],
        "zone": data["zone"],
        "metric": data["metric"],
        "value": value,
        "unit": data["unit"],
        "timestamp": ts,
    }


RANGES = {
    "temperature": (10.0, 40.0),
    "humidity": (20.0, 90.0),
    "co2": (350.0, 2500.0),
    "light": (0.0, 2000.0),
}


def in_range(metric: str, value: float) -> bool:
    low, high = RANGES.get(metric, (-math.inf, math.inf))
    return low <= value <= high
