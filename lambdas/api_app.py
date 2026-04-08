from __future__ import annotations

import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

_agg_table_cache = None


def _aggregates_table():
    global _agg_table_cache
    if _agg_table_cache is None:
        _agg_table_cache = boto3.resource("dynamodb").Table(os.environ["AGGREGATES_TABLE"])
    return _agg_table_cache


def _jsonable(item: dict) -> dict:
    out = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    zone = params.get("zone", "S1.02")
    metric = params.get("metric", "temperature")
    limit = int(params.get("limit", "50"))

    resp = _aggregates_table().query(
        KeyConditionExpression=Key("pk").eq(f"{zone}#{metric}"),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = [_jsonable(i) for i in resp.get("Items", [])]

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"items": items}),
    }
