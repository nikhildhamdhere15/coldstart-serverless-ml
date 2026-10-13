"""
End-to-End Pipeline Diagnostic Test
====================================
Tests every step of the COLDSTART pipeline:

  Traffic Generator → S3 → ETL → DynamoDB → DataAggregator → ML Models → IntelligentLambdaWarmer

Run with:
    python e2e_test.py

This script does NOT modify any production data.
It reads existing data and tests each connection independently.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from config import aws
import aws_client

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅ PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}❌ FAIL{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠️  WARN{RESET}  {msg}")
def info(msg): print(f"  {BLUE}ℹ️  INFO{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{BLUE}{'='*60}{RESET}\n{BOLD}{msg}{RESET}\n{'='*60}")
def step(n, msg): print(f"\n{BOLD}[Step {n}]{RESET} {msg}")

results = {}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: Configuration
# ══════════════════════════════════════════════════════════════════════════════
header("COLDSTART End-to-End Pipeline Diagnostic")
step(0, "Configuration")

print(f"  Region:              {aws.region}")
print(f"  DynamoDB Table:      {aws.dynamodb_table}")
print(f"  S3 Bucket:           {aws.s3_bucket}")
print(f"  DataAggregator:      {aws.data_aggregator_function}")
print(f"  IntelligentWarmer:   {aws.warmer_function}")
print(f"  CloudWatch NS:       {aws.cloudwatch_namespace}")
print(f"  Credentials:         {'Explicit (.env)' if aws.access_key_id else 'Default (~/.aws/credentials)'}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: AWS Connectivity
# ══════════════════════════════════════════════════════════════════════════════
step(1, "AWS Connectivity")

try:
    sts = aws_client._session().client("sts")
    identity = sts.get_caller_identity()
    ok(f"AWS credentials valid — Account: {identity['Account']}, ARN: {identity['Arn']}")
    results["aws_auth"] = True
except Exception as e:
    fail(f"AWS credentials invalid: {e}")
    results["aws_auth"] = False
    print(f"\n{RED}FATAL: Cannot connect to AWS. Fix credentials first.{RESET}")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: S3 Bucket
# ══════════════════════════════════════════════════════════════════════════════
step(2, "S3 Bucket — Raw JSON Logs")

try:
    s3 = aws_client.s3()
    s3.head_bucket(Bucket=aws.s3_bucket)
    ok(f"Bucket '{aws.s3_bucket}' exists and is accessible")

    # Count recent files
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)
    today_prefix = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/"

    count = 0
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=aws.s3_bucket, Prefix=today_prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"] >= cutoff:
                    count += 1
    except Exception:
        pass

    if count > 0:
        ok(f"S3 has {count} files uploaded in last 1h (prefix: {today_prefix})")
    else:
        warn(f"S3 has 0 files in last 1h under '{today_prefix}' — run Traffic Generator first")

    results["s3"] = True
    results["s3_files_1h"] = count

except Exception as e:
    fail(f"S3 bucket error: {e}")
    results["s3"] = False
    results["s3_files_1h"] = 0

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: DynamoDB Table
# ══════════════════════════════════════════════════════════════════════════════
step(3, "DynamoDB — ETLFeatureData")

try:
    db    = aws_client.dynamodb()
    table = db.Table(aws.dynamodb_table)
    table.load()
    ok(f"Table '{aws.dynamodb_table}' exists — Status: {table.table_status}")

    # Count recent records
    end_ts   = int(datetime.now(timezone.utc).timestamp())
    start_ts = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())

    resp  = table.scan(
        FilterExpression="#ts BETWEEN :s AND :e",
        ExpressionAttributeNames={"#ts": "timestamp_s"},
        ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
        Select="COUNT",
    )
    count_1h = resp.get("Count", 0)

    # Last 15 min
    start_15 = int((datetime.now(timezone.utc) - timedelta(minutes=15)).timestamp())
    resp15 = table.scan(
        FilterExpression="#ts BETWEEN :s AND :e",
        ExpressionAttributeNames={"#ts": "timestamp_s"},
        ExpressionAttributeValues={":s": start_15, ":e": end_ts},
        Select="COUNT",
    )
    count_15m = resp15.get("Count", 0)

    if count_1h > 0:
        ok(f"DynamoDB has {count_1h} records in last 1h, {count_15m} in last 15 min")
    else:
        warn("DynamoDB has 0 records in last 1h — ETL Lambda may not be running")

    results["dynamodb"] = True
    results["dynamodb_records_1h"]  = count_1h
    results["dynamodb_records_15m"] = count_15m

except Exception as e:
    fail(f"DynamoDB error: {e}")
    results["dynamodb"] = False
    results["dynamodb_records_1h"]  = 0
    results["dynamodb_records_15m"] = 0

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: ML Models
# ══════════════════════════════════════════════════════════════════════════════
step(4, "Local ML Models (XGBoost + Random Forest)")

import numpy as np
import joblib

model_dir = os.path.join(os.path.dirname(__file__), "models")
xgb_path  = os.path.join(model_dir, "xgboost_model.pkl")
rf_path   = os.path.join(model_dir, "random_forest_model.pkl")

xgb_model = None
rf_model  = None

if not os.path.exists(xgb_path):
    fail(f"XGBoost model not found: {xgb_path}")
    results["models"] = False
elif not os.path.exists(rf_path):
    fail(f"Random Forest model not found: {rf_path}")
    results["models"] = False
else:
    try:
        xgb_model = joblib.load(xgb_path)
        rf_model  = joblib.load(rf_path)
        ok(f"Models loaded — XGBoost: {type(xgb_model).__name__}, RF: {type(rf_model).__name__}")

        # Test prediction
        test_features = np.array([[2.0, 6.0, 0.05, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]])
        xgb_prob = float(xgb_model.predict_proba(test_features)[0][1])
        rf_prob  = float(rf_model.predict_proba(test_features)[0][1])
        p_final  = round(0.7 * xgb_prob + 0.3 * rf_prob, 4)
        conf     = round(1.0 - abs(xgb_prob - rf_prob), 4)

        ok(f"Test prediction — XGBoost: {xgb_prob:.1%}, RF: {rf_prob:.1%}, P_final: {p_final:.1%}, C: {conf:.1%}")
        results["models"] = True
        results["test_p_final"] = p_final
        results["test_confidence"] = conf

    except Exception as e:
        fail(f"Model load/predict error: {e}")
        results["models"] = False

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: DataAggregator Lambda — check it exists and last run time
# ══════════════════════════════════════════════════════════════════════════════
step(5, "DataAggregator Lambda — existence + last EventBridge run")

lc = aws_client.lambda_client()

try:
    fn_info = lc.get_function(FunctionName=aws.data_aggregator_function)
    cfg = fn_info["Configuration"]
    ok(f"Lambda '{aws.data_aggregator_function}' exists — Runtime: {cfg['Runtime']}, "
       f"State: {cfg['State']}, Timeout: {cfg['Timeout']}s")
    results["data_aggregator_exists"] = True
except lc.exceptions.ResourceNotFoundException:
    fail(f"Lambda '{aws.data_aggregator_function}' NOT FOUND in region {aws.region}")
    info("Check DATA_AGGREGATOR_FUNCTION in .env matches exact Lambda name in AWS console")
    results["data_aggregator_exists"] = False
except Exception as e:
    fail(f"Could not check DataAggregator: {e}")
    results["data_aggregator_exists"] = False

# Check last run time from CloudWatch Logs
try:
    logs = aws_client.cloudwatch_logs()
    log_group = f"/aws/lambda/{aws.data_aggregator_function}"
    streams = logs.describe_log_streams(
        logGroupName=log_group,
        orderBy="LastEventTime",
        descending=True,
        limit=1,
    ).get("logStreams", [])

    if streams and streams[0].get("lastEventTimestamp"):
        ts_ms = streams[0]["lastEventTimestamp"]
        last_run = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        age_min  = (datetime.now(timezone.utc) - last_run).total_seconds() / 60
        if age_min < 20:
            ok(f"DataAggregator last ran {age_min:.1f} min ago (within 15-min cycle)")
        else:
            warn(f"DataAggregator last ran {age_min:.1f} min ago — may not have run recently")
        results["data_aggregator_last_run_min"] = age_min
    else:
        warn("No CloudWatch Logs found for DataAggregator — has it ever run?")
        results["data_aggregator_last_run_min"] = None

except Exception as e:
    warn(f"Could not read DataAggregator CloudWatch Logs: {e}")
    results["data_aggregator_last_run_min"] = None

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: IntelligentLambdaWarmer — existence check
# ══════════════════════════════════════════════════════════════════════════════
step(6, "IntelligentLambdaWarmer Lambda — existence + configuration")

warmer_ok = False
try:
    fn_info = lc.get_function(FunctionName=aws.warmer_function)
    cfg = fn_info["Configuration"]
    ok(f"Lambda '{aws.warmer_function}' exists — Runtime: {cfg['Runtime']}, "
       f"State: {cfg['State']}, Timeout: {cfg['Timeout']}s")
    warmer_ok = True
    results["warmer_exists"] = True

    # Check environment variables the warmer might need
    env_vars = cfg.get("Environment", {}).get("Variables", {})
    if env_vars:
        info(f"Warmer env vars: {list(env_vars.keys())}")

except lc.exceptions.ResourceNotFoundException:
    fail(f"Lambda '{aws.warmer_function}' NOT FOUND in region {aws.region}")
    info("Check WARMER_FUNCTION in .env matches exact Lambda name in AWS console")
    results["warmer_exists"] = False
except Exception as e:
    fail(f"Could not check IntelligentLambdaWarmer: {e}")
    results["warmer_exists"] = False

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: IntelligentLambdaWarmer — actual invocation test
# ══════════════════════════════════════════════════════════════════════════════
step(7, "IntelligentLambdaWarmer — LIVE invocation test")

if not warmer_ok:
    warn("Skipping invocation test — Lambda not found")
    results["warmer_invocation"] = "skipped"
else:
    # Build a realistic test payload matching what the dashboard sends
    test_payload = {
        "predictions": [
            {
                "endpoint":             "auth",
                "function_name":        "auth-function",
                "ensemble_probability": 0.92,
                "request_count":        45,
            },
            {
                "endpoint":             "profile",
                "function_name":        "profile-function",
                "ensemble_probability": 0.85,
                "request_count":        38,
            },
            {
                "endpoint":             "search",
                "function_name":        "search-function",
                "ensemble_probability": 0.78,
                "request_count":        42,
            },
        ]
    }

    info(f"Invoking '{aws.warmer_function}' with payload:")
    print(f"    {json.dumps(test_payload, indent=2)}")

    try:
        response = lc.invoke(
            FunctionName=aws.warmer_function,
            InvocationType="RequestResponse",
            Payload=json.dumps(test_payload).encode("utf-8"),
        )

        status_code = response.get("StatusCode", 0)
        fn_error    = response.get("FunctionError", "")
        raw_payload = response["Payload"].read().decode("utf-8")

        print(f"\n  Raw Lambda response:")
        print(f"    StatusCode:    {status_code}")
        print(f"    FunctionError: {fn_error or 'None'}")
        print(f"    Payload:       {raw_payload[:1000]}")

        if fn_error:
            fail(f"Lambda threw an exception: {fn_error}")
            info("Check the Lambda function code — it returned a FunctionError")
            results["warmer_invocation"] = f"function_error: {fn_error}"
        elif status_code == 200:
            try:
                outer = json.loads(raw_payload)
                body_str = outer.get("body", "{}")
                body = json.loads(body_str) if isinstance(body_str, str) else body_str
                summary = body.get("summary", {})

                ok(f"IntelligentLambdaWarmer invoked successfully!")
                ok(f"  Functions evaluated: {summary.get('functions_evaluated', '?')}")
                ok(f"  Functions warmed:    {summary.get('functions_warmed', '?')}")
                ok(f"  Success rate:        {summary.get('overall_success_rate', '?')}")

                warming_results = body.get("warming_results", [])
                if warming_results:
                    print("\n  Warming Results:")
                    for r in warming_results:
                        print(f"    {r.get('endpoint','?').upper():10} | "
                              f"Priority: {r.get('priority','?'):6} | "
                              f"Attempts: {r.get('attempts',0)} | "
                              f"Successful: {r.get('successful',0)} | "
                              f"Action: {r.get('action','?')}")

                results["warmer_invocation"] = "success"
                results["warmer_response"]   = body

            except json.JSONDecodeError as e:
                warn(f"Response is not valid JSON: {e}")
                warn(f"Raw response: {raw_payload[:500]}")
                results["warmer_invocation"] = "json_parse_error"
        else:
            fail(f"Lambda returned HTTP {status_code}")
            results["warmer_invocation"] = f"http_{status_code}"

    except lc.exceptions.ResourceNotFoundException:
        fail(f"Lambda '{aws.warmer_function}' not found during invocation")
        results["warmer_invocation"] = "not_found"
    except Exception as e:
        fail(f"Invocation exception: {type(e).__name__}: {e}")
        results["warmer_invocation"] = f"exception: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Full Pipeline Simulation
# ══════════════════════════════════════════════════════════════════════════════
step(8, "Full Pipeline Simulation — DynamoDB → ML → Warmer Payload")

if results.get("dynamodb") and results.get("models"):
    try:
        # Get features from last 15-min window
        db    = aws_client.dynamodb()
        table = db.Table(aws.dynamodb_table)

        now_utc      = datetime.now(timezone.utc)
        minutes_past = now_utc.minute % 15
        window_end   = now_utc - timedelta(minutes=minutes_past,
                                           seconds=now_utc.second,
                                           microseconds=now_utc.microsecond)
        window_start = window_end - timedelta(minutes=15)

        info(f"Querying DynamoDB window: {window_start.strftime('%H:%M')} → {window_end.strftime('%H:%M')} UTC")

        resp = table.scan(
            FilterExpression="#ts BETWEEN :s AND :e",
            ExpressionAttributeNames={"#ts": "timestamp_s"},
            ExpressionAttributeValues={
                ":s": int(window_start.timestamp()),
                ":e": int(window_end.timestamp()),
            },
        )
        items = resp.get("Items", [])

        for item in items:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = float(v)

        if not items:
            warn(f"No DynamoDB records in window {window_start.strftime('%H:%M')}→{window_end.strftime('%H:%M')}")
            warn("Trying last 15 min instead...")
            start_ts = int((datetime.now(timezone.utc) - timedelta(minutes=15)).timestamp())
            end_ts   = int(datetime.now(timezone.utc).timestamp())
            resp = table.scan(
                FilterExpression="#ts BETWEEN :s AND :e",
                ExpressionAttributeNames={"#ts": "timestamp_s"},
                ExpressionAttributeValues={":s": start_ts, ":e": end_ts},
            )
            items = resp.get("Items", [])
            for item in items:
                for k, v in item.items():
                    if isinstance(v, Decimal):
                        item[k] = float(v)

        if not items:
            warn("No DynamoDB records available — run Traffic Generator first")
            results["pipeline_sim"] = "no_data"
        else:
            ok(f"Got {len(items)} DynamoDB records for ML input")

            # Aggregate per endpoint
            predictions = []
            warmer_payload = []

            for ep_name in ["auth", "profile", "search"]:
                ep_items = [i for i in items if i.get(f"endpoint_{ep_name}", 0) == 1]
                if not ep_items:
                    ep_items = items

                n = len(ep_items)
                avg_hour    = sum(float(i.get("hour_of_day", 12)) for i in ep_items) / n
                avg_traffic = sum(float(i.get("traffic_intensity", 1.0)) for i in ep_items) / n
                avg_new     = sum(float(i.get("user_type_new", 0)) for i in ep_items) / n
                avg_mobile  = sum(float(i.get("device_mobile", 0)) for i in ep_items) / n
                day_of_week = float(ep_items[-1].get("day_of_week", 1))
                is_biz      = 1.0 if (0 <= int(day_of_week) <= 4 and 9 <= int(avg_hour) <= 17) else 0.0

                features = np.array([[
                    avg_hour, day_of_week, avg_traffic,
                    1.0 if ep_name == "auth"    else 0.0,
                    1.0 if ep_name == "profile" else 0.0,
                    1.0 if ep_name == "search"  else 0.0,
                    avg_new, avg_mobile, is_biz,
                ]])

                xgb_prob = float(xgb_model.predict_proba(features)[0][1])
                rf_prob  = float(rf_model.predict_proba(features)[0][1])
                p_final  = round(0.7 * xgb_prob + 0.3 * rf_prob, 4)
                conf     = round(1.0 - abs(xgb_prob - rf_prob), 4)
                cbw_pass = p_final >= 0.7 and conf >= 0.6

                print(f"    {ep_name.upper():10} | XGB: {xgb_prob:.1%} | RF: {rf_prob:.1%} | "
                      f"P_final: {p_final:.1%} | C: {conf:.1%} | "
                      f"CBW: {'WARM ⚡' if cbw_pass else 'SKIP'} | n={n}")

                if cbw_pass:
                    warmer_payload.append({
                        "endpoint":             ep_name,
                        "function_name":        f"{ep_name}-function",
                        "ensemble_probability": p_final,
                        "request_count":        n,
                    })

            if warmer_payload:
                ok(f"CBW gate passed for: {[p['endpoint'] for p in warmer_payload]}")
                ok(f"Warmer payload ready: {json.dumps(warmer_payload)}")
                results["pipeline_sim"] = "cbw_warm"
                results["warmer_payload"] = warmer_payload
            else:
                info("CBW gate: SKIP — all endpoints below threshold (P_final < 0.7 or C < 0.6)")
                results["pipeline_sim"] = "cbw_skip"

    except Exception as e:
        fail(f"Pipeline simulation error: {e}")
        import traceback
        traceback.print_exc()
        results["pipeline_sim"] = f"error: {e}"
else:
    warn("Skipping pipeline simulation — DynamoDB or models not available")
    results["pipeline_sim"] = "skipped"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: CloudWatch Metrics Check
# ══════════════════════════════════════════════════════════════════════════════
step(9, "CloudWatch Metrics — ColdStart/IntelligentWarming")

try:
    cw  = aws_client.cloudwatch()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=2)

    metrics_found = []
    for metric_name in ["ColdStartProbability", "WarmingSuccessRate", "FunctionsWarmed", "TotalFunctionsEvaluated"]:
        r = cw.get_metric_statistics(
            Namespace=aws.cloudwatch_namespace,
            MetricName=metric_name,
            StartTime=start, EndTime=end,
            Period=3600, Statistics=["Average", "Sum"],
        )
        pts = r.get("Datapoints", [])
        if pts:
            latest = sorted(pts, key=lambda x: x["Timestamp"])[-1]
            val = latest.get("Average") or latest.get("Sum")
            ok(f"{metric_name}: {val:.4f} (at {latest['Timestamp'].strftime('%H:%M')})")
            metrics_found.append(metric_name)
        else:
            warn(f"{metric_name}: No data in last 2h — warmer hasn't published yet")

    results["cloudwatch_metrics"] = metrics_found

except Exception as e:
    warn(f"CloudWatch metrics check failed: {e}")
    results["cloudwatch_metrics"] = []

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
header("DIAGNOSTIC SUMMARY")

checks = [
    ("AWS Auth",              results.get("aws_auth")),
    ("S3 Bucket",             results.get("s3")),
    ("DynamoDB",              results.get("dynamodb")),
    ("ML Models",             results.get("models")),
    ("DataAggregator exists", results.get("data_aggregator_exists")),
    ("Warmer exists",         results.get("warmer_exists")),
    ("Warmer invocation",     results.get("warmer_invocation") == "success"),
    ("Pipeline simulation",   results.get("pipeline_sim") in ("cbw_warm", "cbw_skip")),
]

all_pass = True
for name, passed in checks:
    if passed:
        print(f"  {GREEN}✅{RESET} {name}")
    else:
        print(f"  {RED}❌{RESET} {name}")
        all_pass = False

print()
if results.get("s3_files_1h", 0) == 0:
    print(f"  {YELLOW}⚠️{RESET}  S3 has 0 files in last 1h — run Traffic Generator")
if results.get("dynamodb_records_15m", 0) == 0:
    print(f"  {YELLOW}⚠️{RESET}  DynamoDB has 0 records in last 15 min — ETL may be delayed")
if results.get("data_aggregator_last_run_min") and results["data_aggregator_last_run_min"] > 20:
    print(f"  {YELLOW}⚠️{RESET}  DataAggregator last ran {results['data_aggregator_last_run_min']:.0f} min ago — check EventBridge rule")

print()
if results.get("warmer_invocation") not in ("success", "skipped"):
    print(f"{RED}{BOLD}WARMER ISSUE DETECTED:{RESET}")
    inv = results.get("warmer_invocation", "unknown")
    if "not_found" in str(inv):
        print(f"  Lambda '{aws.warmer_function}' does not exist.")
        print(f"  → Check WARMER_FUNCTION in .env matches exact name in AWS Lambda console")
    elif "function_error" in str(inv):
        print(f"  Lambda exists but threw an exception.")
        print(f"  → Check Lambda logs in CloudWatch: /aws/lambda/{aws.warmer_function}")
    elif "exception" in str(inv):
        print(f"  Invocation exception: {inv}")
        print(f"  → Check IAM permissions: lambda:InvokeFunction on {aws.warmer_function}")
    elif "json_parse_error" in str(inv):
        print(f"  Lambda returned non-JSON response.")
        print(f"  → Check Lambda function returns proper JSON body")

print()
if all_pass:
    print(f"{GREEN}{BOLD}All checks passed! Pipeline is healthy.{RESET}")
else:
    print(f"{YELLOW}{BOLD}Some checks failed. Fix the issues above and re-run.{RESET}")

print(f"\n{BOLD}Full results dict:{RESET}")
for k, v in results.items():
    if k != "warmer_response":
        print(f"  {k}: {v}")
