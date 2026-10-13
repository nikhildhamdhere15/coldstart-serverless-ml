"""
Real-time data fetcher for the dashboard.
Pulls live data from DynamoDB, CloudWatch, and S3.
"""
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

import aws_client
from config import aws


# ── DynamoDB: recent traffic records ─────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def get_recent_traffic(minutes: int = 60) -> pd.DataFrame:
    """Get recent traffic records from DynamoDB for live charts."""
    try:
        db    = aws_client.dynamodb()
        table = db.Table(aws.dynamodb_table)
        end_ts   = int(datetime.now(timezone.utc).timestamp())
        start_ts = int((datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp())

        resp  = table.scan(
            FilterExpression="#ts BETWEEN :s AND :e",
            ExpressionAttributeNames={"#ts": "timestamp_s"},
            ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
        )
        items = resp.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                FilterExpression="#ts BETWEEN :s AND :e",
                ExpressionAttributeNames={"#ts": "timestamp_s"},
                ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

        if not items:
            return pd.DataFrame()

        # Convert Decimal
        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)

        df = pd.DataFrame(items)

        # Add derived columns
        if "timestamp_s" in df.columns:
            df["datetime"] = pd.to_datetime(df["timestamp_s"], unit="s", utc=True)
            df["datetime_local"] = df["datetime"].dt.tz_convert("Asia/Kolkata")
            df["minute"] = df["datetime_local"].dt.floor("min")

        # Endpoint label
        def ep_label(row):
            if row.get("endpoint_auth", 0) == 1: return "auth"
            if row.get("endpoint_profile", 0) == 1: return "profile"
            if row.get("endpoint_search", 0) == 1: return "search"
            return "unknown"
        df["endpoint"] = df.apply(ep_label, axis=1)

        # Cold start label
        df["is_cold"] = df.get("cold_start_label", df.get("ml_label", 0)).astype(int)

        return df.sort_values("timestamp_s")

    except Exception as e:
        return pd.DataFrame()


# ── DynamoDB: summary stats ───────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def get_live_stats() -> dict:
    """Compute live stats from DynamoDB."""
    df = get_recent_traffic(minutes=60)
    if df.empty:
        return {}

    total = len(df)
    cold  = int(df["is_cold"].sum()) if "is_cold" in df.columns else 0
    warm  = total - cold

    # requests_per_min: average over the last 60 minutes
    rpm = round(total / 60, 1)

    stats = {
        "total_requests_1h":   total,
        "cold_starts_1h":      cold,
        "warm_starts_1h":      warm,
        # cold_start_rate is real — traffic generator sends 85% high-risk intentionally
        "cold_start_rate":     cold / total if total > 0 else 0.0,
        "requests_per_min":    rpm,
    }

    # Per endpoint — we have exactly 3 endpoints
    if "endpoint" in df.columns:
        for ep in ["auth", "profile", "search"]:
            ep_df = df[df["endpoint"] == ep]
            ep_cold = int(ep_df["is_cold"].sum()) if "is_cold" in ep_df.columns else 0
            stats[f"{ep}_count"]     = len(ep_df)
            stats[f"{ep}_cold_rate"] = ep_cold / len(ep_df) if len(ep_df) > 0 else 0.0

    # Last 15 min window (matches DataAggregator cycle)
    df15 = get_recent_traffic(minutes=15)
    stats["requests_15min"] = len(df15)

    return stats


# ── CloudWatch: metric history ────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_cw_metric_history(metric_name: str, hours: int = 6) -> pd.DataFrame:
    """Get CloudWatch metric history for charting."""
    try:
        cw    = aws_client.cloudwatch()
        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)

        r = cw.get_metric_statistics(
            Namespace=aws.cloudwatch_namespace,
            MetricName=metric_name,
            StartTime=start,
            EndTime=end,
            Period=900,   # 15-min periods
            Statistics=["Average", "Sum"],
        )
        pts = r.get("Datapoints", [])
        if not pts:
            return pd.DataFrame()

        df = pd.DataFrame(pts)
        df["datetime"] = pd.to_datetime(df["Timestamp"]).dt.tz_convert("Asia/Kolkata")
        return df.sort_values("datetime")

    except Exception:
        return pd.DataFrame()


# ── S3: recent file count ─────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_s3_recent_files(hours: int = 1) -> int:
    """Count S3 files uploaded in the last N hours.
    Traffic generator writes to: training-data/YYYY/MM/DD/<key>.json
    """
    try:
        s3     = aws_client.s3()
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)

        # Use today's date prefix to avoid scanning the entire bucket
        from datetime import datetime as _dt
        today_prefix = f"training-data/{_dt.now().strftime('%Y/%m/%d')}/"

        count = 0
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=aws.s3_bucket, Prefix=today_prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"] >= cutoff:
                    count += 1
        return count
    except Exception:
        return 0


# ── CloudWatch: all metrics summary ──────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def get_cw_latest_values() -> dict:
    """Get latest value for each CloudWatch metric."""
    try:
        cw    = aws_client.cloudwatch()
        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=1)
        result = {}

        for metric, stat in [
            ("ColdStartProbability",    "Average"),
            ("WarmingSuccessRate",      "Average"),
            ("FunctionsWarmed",         "Sum"),       # total warmed in last cycle
            ("TotalFunctionsEvaluated", "Sum"),
        ]:
            r = cw.get_metric_statistics(
                Namespace=aws.cloudwatch_namespace,
                MetricName=metric,
                StartTime=start, EndTime=end,
                Period=3600, Statistics=[stat],
            )
            pts = r.get("Datapoints", [])
            result[metric] = pts[-1][stat] if pts else None

        # FunctionsWarmed from CloudWatch is a cumulative sum over 1h.
        # Cap it at 3 (we only have 3 endpoints: auth, profile, search).
        if result.get("FunctionsWarmed") is not None:
            result["FunctionsWarmed"] = min(int(result["FunctionsWarmed"]), 3)

        return result
    except Exception:
        return {}
