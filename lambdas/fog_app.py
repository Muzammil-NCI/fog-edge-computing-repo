from __future__ import annotations

import os

from fog_processing import process_record

_state_table = None
_agg_table = None
_iot = None
_iot_topic = None


def _tables():
    global _state_table, _agg_table, _iot, _iot_topic
    import boto3

    if _state_table is None:
        _state_table = boto3.resource("dynamodb").Table(os.environ["FOG_STATE_TABLE"])
    if _agg_table is None:
        _agg_table = boto3.resource("dynamodb").Table(os.environ["AGGREGATES_TABLE"])
    if _iot is None:
        endpoint = os.environ["IOT_DATA_ENDPOINT"].strip()
        for prefix in ("https://", "http://"):
            if endpoint.startswith(prefix):
                endpoint = endpoint[len(prefix) :]
                break
        _iot = boto3.client("iot-data", endpoint_url=f"https://{endpoint}")
    if _iot_topic is None:
        _iot_topic = os.environ.get("IOT_TOPIC", "campus/v2/fog/aggregated")
    return _state_table, _agg_table, _iot, _iot_topic


def handler(event, context):
    state_table, agg_table, iot, iot_topic = _tables()
    ok = 0
    bad = 0
    for rec in event.get("Records", []):
        body = rec.get("body", "")
        if process_record(body, state_table, agg_table, iot, iot_topic):
            ok += 1
        else:
            bad += 1
    return {"processed": ok, "invalid": bad}
