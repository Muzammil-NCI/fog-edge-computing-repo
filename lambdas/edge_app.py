from __future__ import annotations

import json
import os
import random
import time

import boto3

from shared.telemetry import utc_now_iso

sqs = boto3.client("sqs")

DEFAULT_CAMPUS_ZONES = [
    "S1.02",
    "S2.04",
    "S3.05",
    "S3.06",
    "Theatre-1",
    "Theatre-2",
    "Theatre-3",
    "Spencer Library 05",
    "Spencer Library 04",
]

SENSOR_TYPES = ("temperature", "humidity", "co2", "light")


def _single_metric() -> str:
    raw = os.environ.get("EDGE_SENSOR_METRIC", "").strip().lower()
    if raw not in SENSOR_TYPES:
        raise ValueError(
            "EDGE_SENSOR_METRIC must be set to one of "
            + ", ".join(SENSOR_TYPES)
            + f"; got {raw!r}"
        )
    return raw


def _zones() -> list[str]:
    raw = os.environ.get("ZONES", "")
    if raw.strip():
        return [z.strip() for z in raw.split(",") if z.strip()]
    return DEFAULT_CAMPUS_ZONES


def _sim_value(metric: str) -> float:
    if metric == "humidity":
        return max(20.0, min(90.0, random.gauss(48.0, 3.0)))
    if metric == "co2":
        return max(350.0, min(2500.0, random.gauss(750.0, 120.0)))
    if metric == "light":
        return max(0.0, min(2000.0, random.gauss(420.0, 130.0)))
    return max(10.0, min(40.0, random.gauss(22.5, 1.2)))


def _unit_for(metric: str) -> str:
    if metric == "temperature":
        return "C"
    if metric == "humidity":
        return "%"
    if metric == "co2":
        return "ppm"
    if metric == "light":
        return "lux"
    return "u"


def handler(event, context):
    queue_url = os.environ["TELEMETRY_QUEUE_URL"]
    metric = _single_metric()
    unit = _unit_for(metric)
    zones = _zones()
    per_tick = int(os.environ.get("MESSAGES_PER_INVOCATION", "120"))
    interval = float(os.environ.get("EDGE_SEND_INTERVAL_SECONDS", "0.5"))
    sent = 0

    for i in range(per_tick):
        zone = zones[i % len(zones)]
        device_id = f"{zone}-{metric}-dev-{i + 1}"
        body = {
            "device_id": device_id,
            "zone": zone,
            "metric": metric,
            "value": round(_sim_value(metric), 3),
            "unit": unit,
            "timestamp": utc_now_iso(),
        }
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
        sent += 1
        if interval > 0 and i < per_tick - 1:
            time.sleep(interval)

    return {
        "statusCode": 200,
        "body": json.dumps({"sent": sent, "metric": metric, "zones": zones}),
    }
