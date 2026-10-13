"""
ML Engine — Correct Architecture:

  EventBridge (every 15 min)
      ↓ triggers
  DataAggregator Lambda
      ↓ reads DynamoDB last 15 min
      ↓ calls SageMaker XGBoost + RF endpoints
      ↓ async invokes IntelligentLambdaWarmer
  IntelligentLambdaWarmer
      ↓ warms auth-function / profile-function / search-function
      ↓ publishes CloudWatch metrics

DASHBOARD ROLE (READ-ONLY for the pipeline):
  - NEVER invokes DataAggregator (EventBridge owns that)
  - NEVER invokes IntelligentLambdaWarmer (DataAggregator owns that)
  - Reads DataAggregator output from CloudWatch Logs
  - Reads DynamoDB for traffic charts and KPIs
  - Runs LOCAL ML models to show predictions in the UI
  - Can optionally invoke IntelligentLambdaWarmer ONLY from
    the "Live Prediction" manual button (not automatically)
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import numpy as np
import joblib
import streamlit as st

import aws_client
from config import aws

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

COLD_START_THRESHOLD = 0.7
HIGH_RISK_THRESHOLD  = 0.8
CONFIDENCE_THRESHOLD = 0.6


# ── 1. Load local models ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_models():
    """Load XGBoost and Random Forest models from local .pkl files."""
    xgb_path = os.path.join(MODEL_DIR, "xgboost_model.pkl")
    rf_path  = os.path.join(MODEL_DIR, "random_forest_model.pkl")
    if not os.path.exists(xgb_path) or not os.path.exists(rf_path):
        return None, None
    return joblib.load(xgb_path), joblib.load(rf_path)


def models_available() -> bool:
    xgb, rf = load_models()
    return xgb is not None and rf is not None


# ── 2. Feature vector builder ─────────────────────────────────────────────────

def build_feature_vector(hour, day, traffic, endpoint, user_new, mobile) -> np.ndarray:
    """
    9-feature vector:
    [hour_of_day, day_of_week, traffic_intensity,
     endpoint_auth, endpoint_profile, endpoint_search,
     user_type_new, device_mobile, is_business_hours]
    """
    is_biz = 1.0 if (0 <= int(day) <= 4 and 9 <= int(hour) <= 17) else 0.0
    return np.array([[
        float(hour), float(day), float(traffic),
        1.0 if endpoint == "auth"    else 0.0,
        1.0 if endpoint == "profile" else 0.0,
        1.0 if endpoint == "search"  else 0.0,
        1.0 if user_new else 0.0,
        1.0 if mobile   else 0.0,
        is_biz,
    ]])


# ── 3. Local ensemble prediction ──────────────────────────────────────────────

def ensemble_predict(features: np.ndarray) -> dict | None:
    """Run local XGBoost (70%) + Random Forest (30%) ensemble."""
    xgb_model, rf_model = load_models()
    if xgb_model is None:
        return None

    xgb_prob = float(xgb_model.predict_proba(features)[0][1])
    rf_prob  = float(rf_model.predict_proba(features)[0][1])

    p_final    = round(0.7 * xgb_prob + 0.3 * rf_prob, 4)
    confidence = round(1.0 - abs(xgb_prob - rf_prob), 4)
    cbw_pass   = p_final >= COLD_START_THRESHOLD and confidence >= CONFIDENCE_THRESHOLD

    if p_final >= HIGH_RISK_THRESHOLD:
        priority, warming_frequency = "HIGH", 2
    elif cbw_pass:
        priority, warming_frequency = "MEDIUM", 1
    else:
        priority, warming_frequency = "NONE", 0

    return {
        "xgboost":           round(xgb_prob, 4),
        "random_forest":     round(rf_prob, 4),
        "p_final":           p_final,
        "confidence":        confidence,
        "should_warm":       cbw_pass,
        "priority":          priority,
        "warming_frequency": warming_frequency,
        "label":             "cold_start" if p_final > 0.5 else "warm",
    }


# ── 4. Read DataAggregator last run time from CloudWatch Logs ─────────────────

def get_last_data_aggregator_run_time() -> datetime | None:
    """
    Check CloudWatch Logs to find when DataAggregator last ran via EventBridge.
    Does NOT invoke the Lambda.
    """
    try:
        logs_client = aws_client.cloudwatch_logs()
        log_group   = f"/aws/lambda/{aws.data_aggregator_function}"

        streams = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            descending=True,
            limit=1,
        ).get("logStreams", [])

        if streams and streams[0].get("lastEventTimestamp"):
            ts_ms = streams[0]["lastEventTimestamp"]
            return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception as e:
        logger.debug(f"Could not read DataAggregator log streams: {e}")
    return None


def get_last_data_aggregator_predictions() -> list | None:
    """
    Read the predictions that DataAggregator produced in its last EventBridge run.
    Parses CloudWatch Logs for the JSON output.
    Returns list of prediction dicts or None.
    """
    try:
        logs_client = aws_client.cloudwatch_logs()
        log_group   = f"/aws/lambda/{aws.data_aggregator_function}"

        # Look back 20 min to catch the last 15-min cycle
        end_ms   = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = int((datetime.now(timezone.utc) - timedelta(minutes=20)).timestamp() * 1000)

        streams = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            descending=True,
            limit=3,
        ).get("logStreams", [])

        if not streams:
            return None

        for stream in streams:
            events = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream["logStreamName"],
                startTime=start_ms,
                endTime=end_ms,
                limit=200,
            ).get("events", [])

            for event in reversed(events):
                msg = event.get("message", "")

                # DataAggregator logs the full response body as JSON
                if '"predictions"' in msg and '"ensemble_probability"' in msg:
                    try:
                        start = msg.find("{")
                        if start >= 0:
                            data = json.loads(msg[start:])
                            preds = data.get("predictions", [])
                            if preds:
                                return preds
                    except Exception:
                        pass

                # Also check for the body field in the response
                if '"predictions_made"' in msg or '"warming_instructions_sent"' in msg:
                    try:
                        start = msg.find("{")
                        if start >= 0:
                            data = json.loads(msg[start:])
                            preds = data.get("predictions", [])
                            if preds:
                                return preds
                    except Exception:
                        pass

    except Exception as e:
        logger.debug(f"Could not read DataAggregator predictions from logs: {e}")
    return None


# ── 5. Get features from DynamoDB last completed 15-min window ────────────────

def get_features_from_dynamodb_last_window() -> list:
    """
    Read DynamoDB for the LAST COMPLETED 15-min window.
    e.g. if now=18:23, window = 18:00 → 18:15
    Stable within a window — only changes at the next 15-min boundary.
    """
    try:
        db    = aws_client.dynamodb()
        table = db.Table(aws.dynamodb_table)

        now_utc      = datetime.now(timezone.utc)
        minutes_past = now_utc.minute % 15
        window_end   = now_utc - timedelta(minutes=minutes_past,
                                           seconds=now_utc.second,
                                           microseconds=now_utc.microsecond)
        window_start = window_end - timedelta(minutes=15)

        end_ts   = int(window_end.timestamp())
        start_ts = int(window_start.timestamp())

        resp  = table.scan(
            FilterExpression="#ts BETWEEN :s AND :e",
            ExpressionAttributeNames={"#ts": "timestamp_s"},
            ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
        )
        items = resp.get("Items", [])

        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                FilterExpression="#ts BETWEEN :s AND :e",
                ExpressionAttributeNames={"#ts": "timestamp_s"},
                ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)

        if not items:
            # Try current rolling 15 min if last window is empty
            start_ts2 = int((datetime.now(timezone.utc) - timedelta(minutes=15)).timestamp())
            end_ts2   = int(datetime.now(timezone.utc).timestamp())
            resp2 = table.scan(
                FilterExpression="#ts BETWEEN :s AND :e",
                ExpressionAttributeNames={"#ts": "timestamp_s"},
                ExpressionAttributeValues={":s": start_ts2, ":e": end_ts2},
            )
            items = resp2.get("Items", [])
            for item in items:
                for k, v in item.items():
                    if isinstance(v, Decimal):
                        item[k] = float(v)
            window_start = datetime.now(timezone.utc) - timedelta(minutes=15)
            window_end   = datetime.now(timezone.utc)

        if not items:
            return []

        result = []
        for ep_name in ["auth", "profile", "search"]:
            ep_items = [i for i in items if i.get(f"endpoint_{ep_name}", 0) == 1]
            if not ep_items:
                ep_items = items

            n = len(ep_items)
            result.append({
                "endpoint":          ep_name,
                "hour_of_day":       sum(float(i.get("hour_of_day", 12)) for i in ep_items) / n,
                "day_of_week":       float(ep_items[-1].get("day_of_week", 1)),
                "traffic_intensity": sum(float(i.get("traffic_intensity", 1.0)) for i in ep_items) / n,
                "user_type_new":     sum(float(i.get("user_type_new", 0)) for i in ep_items) / n,
                "device_mobile":     sum(float(i.get("device_mobile", 0)) for i in ep_items) / n,
                "request_count":     n,
                "window_start":      window_start.strftime("%H:%M"),
                "window_end":        window_end.strftime("%H:%M"),
            })

        return result

    except Exception as e:
        logger.debug(f"DynamoDB window query failed: {e}")
        return []


# ── 6. Full pipeline: read features → local ML → build warmer payload ─────────

def run_full_pipeline() -> dict:
    """
    Dashboard-side pipeline (READ-ONLY — never invokes DataAggregator):

    1. Try to read DataAggregator's last predictions from CloudWatch Logs
       (these are the SageMaker-based predictions from the real pipeline)
    2. Fall back to local ML on DynamoDB last-window data
       (same features DataAggregator would use, local models instead of SageMaker)

    Returns predictions + warmer_payload ready for IntelligentLambdaWarmer.
    """
    # Source 1: Read what DataAggregator produced in its last EventBridge run
    da_preds = get_last_data_aggregator_predictions()
    if da_preds:
        # DataAggregator already made SageMaker predictions — use them directly
        predictions = []
        for p in da_preds:
            ep = p.get("endpoint", "unknown")
            prob = float(p.get("ensemble_probability", 0))
            xgb  = float(p.get("xgboost_probability", prob))
            rf   = float(p.get("random_forest_probability", prob))
            conf = round(1.0 - abs(xgb - rf), 4)
            cbw  = prob >= COLD_START_THRESHOLD and conf >= CONFIDENCE_THRESHOLD

            predictions.append({
                "endpoint":          ep,
                "function_name":     f"{ep}-function",
                "xgboost":           round(xgb, 4),
                "random_forest":     round(rf, 4),
                "p_final":           round(prob, 4),
                "confidence":        conf,
                "should_warm":       cbw,
                "priority":          "HIGH" if prob >= HIGH_RISK_THRESHOLD else ("MEDIUM" if cbw else "NONE"),
                "warming_frequency": 2 if prob >= HIGH_RISK_THRESHOLD else (1 if cbw else 0),
                "request_count":     int(p.get("request_count", 0)),
                "label":             "cold_start" if prob > 0.5 else "warm",
            })

        warmer_payload = [
            {
                "endpoint":             p["endpoint"],
                "function_name":        p["function_name"],
                "ensemble_probability": p["p_final"],
                "request_count":        p["request_count"],
            }
            for p in predictions
        ]
        return {
            "source":         "data_aggregator_logs (SageMaker predictions)",
            "predictions":    predictions,
            "warmer_payload": warmer_payload,
        }

    # Source 2: Local ML on DynamoDB last-window data
    features_list = get_features_from_dynamodb_last_window()
    source = "local_ml_on_dynamodb"

    if not features_list:
        return {"source": source, "predictions": [], "warmer_payload": [], "error": "No data"}

    predictions = []
    for feat in features_list:
        endpoint = feat.get("endpoint", "unknown")
        fv = build_feature_vector(
            hour     = feat.get("hour_of_day", 12),
            day      = feat.get("day_of_week", 1),
            traffic  = feat.get("traffic_intensity", 1.0),
            endpoint = endpoint,
            user_new = feat.get("user_type_new", 0) > 0.5,
            mobile   = feat.get("device_mobile", 0) > 0.5,
        )
        result = ensemble_predict(fv)
        if result:
            result["endpoint"]      = endpoint
            result["function_name"] = f"{endpoint}-function"
            result["request_count"] = int(feat.get("request_count", 0))
            predictions.append(result)

    warmer_payload = [
        {
            "endpoint":             p["endpoint"],
            "function_name":        p["function_name"],
            "ensemble_probability": p["p_final"],
            "request_count":        p["request_count"],
        }
        for p in predictions
    ]

    return {
        "source":         source,
        "predictions":    predictions,
        "warmer_payload": warmer_payload,
    }


# ── 7. Invoke IntelligentLambdaWarmer (manual trigger from dashboard) ─────────

def invoke_intelligent_warmer(warmer_payload: list) -> tuple[dict | None, str]:
    """
    Manually invoke IntelligentLambdaWarmer from the dashboard.
    Used ONLY from the "Live Prediction → Send to Warmer" button.

    The warmer expects:
    {
      "predictions": [
        {
          "endpoint": "auth",
          "function_name": "auth-function",
          "ensemble_probability": 0.85,
          "request_count": 45
        }, ...
      ]
    }

    Returns (response_body_dict, error_string).
    error_string is "" on success.
    """
    if not warmer_payload:
        return None, "Empty payload — nothing to warm."

    try:
        lc = aws_client.lambda_client()

        # Exact payload format the warmer's lambda_handler expects
        payload = json.dumps({"predictions": warmer_payload})

        response = lc.invoke(
            FunctionName=aws.warmer_function,
            InvocationType="RequestResponse",
            Payload=payload.encode("utf-8"),
        )

        status_code = response.get("StatusCode", 0)
        fn_error    = response.get("FunctionError", "")
        raw         = response["Payload"].read().decode("utf-8")

        if fn_error:
            # Lambda threw an exception — parse the error
            try:
                err_body = json.loads(raw)
                err_msg  = err_body.get("errorMessage", raw[:300])
            except Exception:
                err_msg = raw[:300]
            return None, f"Lambda function error: {err_msg}"

        if status_code != 200:
            return None, f"Lambda returned HTTP {status_code}: {raw[:200]}"

        outer = json.loads(raw)

        # Warmer returns {"statusCode": 200, "body": "<json string>"}
        body_str = outer.get("body", "{}")
        if isinstance(body_str, str):
            body = json.loads(body_str)
        else:
            body = body_str

        # Check for warmer-level error
        if outer.get("statusCode", 200) == 500 or "error" in body:
            return None, f"Warmer returned error: {body.get('error', str(body)[:200])}"

        return body, ""

    except Exception as e:
        err_type = type(e).__name__
        err_msg  = str(e)

        # Provide specific guidance for common errors
        if "ResourceNotFoundException" in err_type or "Function not found" in err_msg:
            return None, (
                f"Lambda '{aws.warmer_function}' not found in {aws.region}. "
                "Check WARMER_FUNCTION in .env matches the exact Lambda name in AWS console."
            )
        if "AccessDeniedException" in err_type or "not authorized" in err_msg.lower():
            return None, (
                f"IAM permission denied. Add 'lambda:InvokeFunction' permission "
                f"for '{aws.warmer_function}' to your IAM user/role."
            )
        return None, f"{err_type}: {err_msg}"


# ── 8. Backward-compatible wrapper ───────────────────────────────────────────

def predict_from_aggregator() -> list | None:
    """Wrapper used by Live Prediction tab."""
    result = run_full_pipeline()
    preds  = result.get("predictions", [])
    return preds if preds else None
