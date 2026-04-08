from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from shared.telemetry import in_range, parse_event

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALPHA = Decimal("0.3")
WINDOW_SECONDS = int(os.environ.get("WINDOW_SECONDS", "30"))
MAX_SAMPLES = int(os.environ.get("WINDOW_MAX_SAMPLES", "40"))


def _update_ema(table, device_id: str, metric: str, raw_value: float) -> float:
    pk = f"D#{device_id}#{metric}"
    key = {"pk": pk, "sk": "EMA"}
    nv = Decimal(str(round(raw_value, 6)))
    got = table.get_item(Key=key)
    if "Item" in got and "ema" in got["Item"]:
        old = got["Item"]["ema"]
        if not isinstance(old, Decimal):
            old = Decimal(str(old))
        new_ema = ALPHA * nv + (Decimal("1") - ALPHA) * old
    else:
        new_ema = nv
    new_ema = new_ema.quantize(Decimal("0.000001"))
    table.put_item(Item={**key, "ema": new_ema})
    return float(new_ema)


def _window_key(zone: str, metric: str) -> tuple[str, str]:
    return f"W#{zone}#{metric}", "BUF"


def _flush_window(
    iot,
    iot_topic: str,
    agg_table,
    zone: str,
    metric: str,
    unit: str,
    samples: list[tuple[float, float]],
) -> None:
    if not samples:
        return
    values = [v for _, v in samples]
    window_end = datetime.now(timezone.utc).isoformat()
    window_start = datetime.fromtimestamp(samples[0][0], tz=timezone.utc).isoformat()
    payload = {
        "zone": zone,
        "metric": metric,
        "unit": unit,
        "window_start": window_start,
        "window_end": window_end,
        "avg": round(sum(values) / len(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "count": len(values),
        "published_at": window_end,
    }
    body = json.dumps(payload).encode("utf-8")
    print(body)
    try:
        iot.publish(topic=iot_topic, qos=1, payload=body)
        logger.info("iot_publish_ok topic=%s zone=%s metric=%s", iot_topic, zone, metric)
    except Exception:
        logger.exception("iot_publish_failed topic=%s", iot_topic)
        raise
    try:
        agg_table.put_item(
            Item={
                "pk": f"{zone}#{metric}",
                "sk": window_end,
                "zone": zone,
                "metric": metric,
                "window_start": window_start,
                "window_end": window_end,
                "avg": Decimal(str(payload["avg"])),
                "min": Decimal(str(payload["min"])),
                "max": Decimal(str(payload["max"])),
                "count": len(values),
            }
        )
        logger.info("ddb_aggregate_put pk=%s#%s sk=%s", zone, metric, window_end)
    except Exception:
        logger.exception("ddb_aggregate_put_failed pk=%s#%s", zone, metric)
        raise


def process_record(body: str, state_table, agg_table, iot, iot_topic: str) -> bool:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    ev = parse_event(data)
    if not ev:
        return False
    if not in_range(ev["metric"], ev["value"]):
        return True

    smoothed = _update_ema(state_table, ev["device_id"], ev["metric"], ev["value"])
    now = datetime.now(timezone.utc).timestamp()

    wpk, wsk = _window_key(ev["zone"], ev["metric"])
    resp = state_table.get_item(Key={"pk": wpk, "sk": wsk})
    item = resp.get("Item") or {}
    raw_samples = item.get("samples", "[]")
    try:
        samples: list[list] = json.loads(raw_samples) if isinstance(raw_samples, str) else []
    except json.JSONDecodeError:
        samples = []

    ws_raw = item.get("window_start_ts")
    if not samples:
        window_start_ts = now
    else:
        try:
            window_start_ts = float(ws_raw) if ws_raw is not None else now
        except (TypeError, ValueError):
            window_start_ts = now

    samples.append([now, smoothed])
    while len(samples) > MAX_SAMPLES:
        samples.pop(0)

    flush = len(samples) >= 1 and (now - window_start_ts) >= float(WINDOW_SECONDS)
    if flush:
        tup_samples = [(float(t), float(v)) for t, v in samples]
        _flush_window(iot, iot_topic, agg_table, ev["zone"], ev["metric"], ev["unit"], tup_samples)
        samples = []
        window_start_ts = now

    buf_item = {
        "pk": wpk,
        "sk": wsk,
        "samples": json.dumps(samples),
        "window_start_ts": Decimal(str(window_start_ts)),
    }
    state_table.put_item(Item=buf_item)
    return True
