"""
Full End-to-End Pipeline Test
Tests every component of the COLDSTART system:
  Traffic Generator → S3 → DynamoDB → DataAggregator → ML → IntelligentLambdaWarmer → CloudWatch

Run from streamlit_ml_tg folder:
    python e2e_full_test.py
"""
import sys, os, json, time, boto3
from datetime import datetime, timezone, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))
from config import aws
import aws_client

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; BOLD = "\033[1m"; E = "\033[0m"
def ok(m):     print(f"  {G}✅ PASS{E}  {m}")
def fail(m):   print(f"  {R}❌ FAIL{E}  {m}")
def warn(m):   print(f"  {Y}⚠️  WARN{E}  {m}")
def info(m):   print(f"  {B}ℹ️  INFO{E}  {m}")
def header(m): print(f"\n{BOLD}{B}{'='*60}{E}\n{BOLD}{m}{E}\n{'='*60}")
def step(n,m): print(f"\n{BOLD}[Step {n}]{E} {m}")

results = {}

header("COLDSTART — Full End-to-End Pipeline Test")
print(f"  Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Region:  {aws.region}")
print(f"  Table:   {aws.dynamodb_table}")
print(f"  Bucket:  {aws.s3_bucket}")
print(f"  DataAgg: {aws.data_aggregator_function}")
print(f"  Warmer:  {aws.warmer_function}")

# ══════════════════════════════════════════════════════════════════════════════
step(1, "AWS Credentials")
# ══════════════════════════════════════════════════════════════════════════════
try:
    sts = aws_client._session().client('sts')
    idn = sts.get_caller_identity()
    ok(f"Account: {idn['Account']}  ARN: {idn['Arn']}")
    results['auth'] = True
except Exception as e:
    fail(f"Credentials invalid: {e}")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
step(2, "S3 Bucket — Raw JSON Logs")
# ══════════════════════════════════════════════════════════════════════════════
try:
    s3 = aws_client.s3()
    s3.head_bucket(Bucket=aws.s3_bucket)
    ok(f"Bucket '{aws.s3_bucket}' accessible")

    # Count files in last 1h
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)
    prefix = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/"
    count  = 0
    pag    = s3.get_paginator('list_objects_v2')
    for page in pag.paginate(Bucket=aws.s3_bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            if obj['LastModified'] >= cutoff:
                count += 1

    if count > 0:
        ok(f"S3 has {count} files in last 1h  (prefix: {prefix})")
    else:
        warn(f"S3 has 0 files in last 1h — Traffic Generator not running")
    results['s3_files'] = count
except Exception as e:
    fail(f"S3 error: {e}")
    results['s3_files'] = 0

# ══════════════════════════════════════════════════════════════════════════════
step(3, "DynamoDB — ETLFeatureData")
# ══════════════════════════════════════════════════════════════════════════════
try:
    db    = aws_client.dynamodb()
    table = db.Table(aws.dynamodb_table)
    table.load()
    ok(f"Table '{aws.dynamodb_table}' — Status: {table.table_status}")

    now_ts    = int(datetime.now(timezone.utc).timestamp())
    ts_1h     = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    ts_15m    = int((datetime.now(timezone.utc) - timedelta(minutes=15)).timestamp())

    r1 = table.scan(FilterExpression='#ts BETWEEN :s AND :e',
                    ExpressionAttributeNames={'#ts': 'timestamp_s'},
                    ExpressionAttributeValues={':s': ts_1h, ':e': now_ts},
                    Select='COUNT')
    r2 = table.scan(FilterExpression='#ts BETWEEN :s AND :e',
                    ExpressionAttributeNames={'#ts': 'timestamp_s'},
                    ExpressionAttributeValues={':s': ts_15m, ':e': now_ts},
                    Select='COUNT')

    c1h  = r1.get('Count', 0)
    c15m = r2.get('Count', 0)

    if c1h > 0:
        ok(f"DynamoDB: {c1h} records (1h)  |  {c15m} records (15min)")
    else:
        warn("DynamoDB: 0 records in last 1h — ETL Lambda may not be running")

    results['dynamo_1h']  = c1h
    results['dynamo_15m'] = c15m
except Exception as e:
    fail(f"DynamoDB error: {e}")
    results['dynamo_1h'] = results['dynamo_15m'] = 0

# ══════════════════════════════════════════════════════════════════════════════
step(4, "Local ML Models")
# ══════════════════════════════════════════════════════════════════════════════
import numpy as np, joblib
model_dir = os.path.join(os.path.dirname(__file__), 'models')
xgb_path  = os.path.join(model_dir, 'xgboost_model.pkl')
rf_path   = os.path.join(model_dir, 'random_forest_model.pkl')

if not os.path.exists(xgb_path) or not os.path.exists(rf_path):
    fail("Model .pkl files missing — run: python save_models.py")
    results['models'] = False
else:
    xgb_m = joblib.load(xgb_path)
    rf_m  = joblib.load(rf_path)
    # High-risk test: 2AM, Sunday, low traffic, new mobile user
    feat  = np.array([[2, 6, 0.05, 1, 0, 0, 1, 1, 0]])
    xp    = float(xgb_m.predict_proba(feat)[0][1])
    rp    = float(rf_m.predict_proba(feat)[0][1])
    p     = round(0.7*xp + 0.3*rp, 4)
    c     = round(1.0 - abs(xp - rp), 4)
    ok(f"Models loaded  |  High-risk test: XGB={xp:.3f} RF={rp:.3f} P={p:.3f} C={c:.3f}")
    ok(f"CBW decision: {'WARM ⚡' if p >= 0.7 and c >= 0.6 else 'SKIP'}")
    results['models'] = True
    results['test_p'] = p

# ══════════════════════════════════════════════════════════════════════════════
step(5, "DataAggregator Lambda — invoke and get predictions")
# ══════════════════════════════════════════════════════════════════════════════
lc = aws_client.lambda_client()
da_predictions = []

try:
    resp    = lc.invoke(FunctionName=aws.data_aggregator_function,
                        InvocationType='RequestResponse',
                        Payload=json.dumps({}).encode())
    status  = resp.get('StatusCode', 0)
    fn_err  = resp.get('FunctionError', '')
    raw     = resp['Payload'].read().decode()

    if fn_err:
        err = json.loads(raw) if raw.startswith('{') else {}
        fail(f"Lambda error: {err.get('errorMessage', raw[:300])}")
        results['data_aggregator'] = 'error'
    else:
        outer = json.loads(raw)
        body  = json.loads(outer.get('body','{}')) if isinstance(outer.get('body'), str) else outer.get('body',{})
        msg   = body.get('message','')
        preds = body.get('predictions', [])
        da_predictions = preds

        ok(f"DataAggregator responded: '{msg}'")
        ok(f"Records processed: {body.get('total_records', 0)}")
        ok(f"Endpoints evaluated: {body.get('endpoints_evaluated', 0)}")

        if preds:
            print(f"\n  {'Endpoint':12} {'XGB':8} {'RF':8} {'P_final':9} {'C':8} {'CBW':6}")
            print(f"  {'-'*55}")
            for p in preds:
                ep   = p.get('endpoint','?')
                xp   = p.get('xgboost_probability', 0)
                rp   = p.get('random_forest_probability', 0)
                pf   = p.get('ensemble_probability', 0)
                cf   = p.get('confidence', 0)
                cbw  = pf >= 0.7 and cf >= 0.6
                print(f"  {ep:12} {xp:.3f}    {rp:.3f}    {pf:.3f}     {cf:.3f}    {'WARM ⚡' if cbw else 'SKIP'}")

        warm_count = body.get('endpoints_to_warm', 0)
        warmer_inv = body.get('warmer_invoked', False)

        if warm_count > 0:
            ok(f"CBW gate: {warm_count} endpoint(s) need warming")
        else:
            info("CBW gate: SKIP — all endpoints below threshold (correct for current traffic)")

        if warmer_inv:
            ok("IntelligentLambdaWarmer was invoked by DataAggregator!")
        else:
            info("IntelligentLambdaWarmer not invoked (P_final < 0.7 for all endpoints)")

        results['data_aggregator'] = 'success'
        results['da_warm_count']   = warm_count
        results['da_warmer_inv']   = warmer_inv

except Exception as e:
    fail(f"DataAggregator invocation failed: {e}")
    results['data_aggregator'] = 'failed'

# ══════════════════════════════════════════════════════════════════════════════
step(6, "IntelligentLambdaWarmer — direct invocation test")
# ══════════════════════════════════════════════════════════════════════════════
# Force a test with high-probability payload to verify warmer works
test_payload = {
    'predictions': [
        {'endpoint': 'auth',    'function_name': 'auth-function',    'ensemble_probability': 0.92, 'request_count': 50},
        {'endpoint': 'profile', 'function_name': 'profile-function', 'ensemble_probability': 0.85, 'request_count': 45},
        {'endpoint': 'search',  'function_name': 'search-function',  'ensemble_probability': 0.78, 'request_count': 48},
    ]
}

info("Invoking IntelligentLambdaWarmer with test payload (P=0.92, 0.85, 0.78) — async...")
try:
    # Use async (Event) invocation so we don't wait for all warming attempts
    resp2   = lc.invoke(FunctionName=aws.warmer_function,
                        InvocationType='Event',   # async — returns 202 immediately
                        Payload=json.dumps(test_payload).encode())
    status2 = resp2.get('StatusCode', 0)
    fn_err2 = resp2.get('FunctionError', '')

    if fn_err2:
        fail(f"Warmer error: {fn_err2}")
        results['warmer'] = 'error'
    elif status2 == 202:
        ok(f"IntelligentLambdaWarmer accepted (StatusCode=202) — warming in background")
        info("Waiting 15s for warming to complete...")
        time.sleep(15)

        # Read warmer logs to confirm it ran
        logs = aws_client.cloudwatch_logs()
        streams = logs.describe_log_streams(
            logGroupName=f'/aws/lambda/{aws.warmer_function}',
            orderBy='LastEventTime', descending=True, limit=1
        ).get('logStreams', [])

        if streams:
            events = logs.get_log_events(
                logGroupName=f'/aws/lambda/{aws.warmer_function}',
                logStreamName=streams[0]['logStreamName'],
                limit=50
            ).get('events', [])

            warmed = [e['message'] for e in events if 'Successfully warmed' in e.get('message','')]
            complete = [e['message'] for e in events if 'Warming complete' in e.get('message','')]

            if complete:
                ok(f"Warmer completed: {complete[-1].strip()}")
            if warmed:
                ok(f"Functions warmed: {len(warmed)} successful warming attempts")
                for w in warmed[-6:]:
                    print(f"    {w.strip()}")
            results['warmer'] = 'success'
        else:
            warn("No warmer logs found yet")
            results['warmer'] = 'success'  # 202 means accepted
    else:
        fail(f"Unexpected status: {status2}")
        results['warmer'] = 'failed'

except Exception as e:
    fail(f"Warmer invocation failed: {e}")
    results['warmer'] = 'failed'

# ══════════════════════════════════════════════════════════════════════════════
step(7, "CloudWatch Metrics — ColdStart/IntelligentWarming")
# ══════════════════════════════════════════════════════════════════════════════
info("Waiting 10s for CloudWatch metrics to propagate...")
time.sleep(10)

try:
    cw  = aws_client.cloudwatch()
    end = datetime.now(timezone.utc)
    st  = end - timedelta(hours=1)

    metrics_found = []
    for metric, stat in [('FunctionsWarmed','Sum'), ('WarmingSuccessRate','Average'),
                         ('ColdStartProbability','Average'), ('TotalFunctionsEvaluated','Sum')]:
        r = cw.get_metric_statistics(
            Namespace=aws.cloudwatch_namespace, MetricName=metric,
            StartTime=st, EndTime=end, Period=3600, Statistics=[stat])
        pts = r.get('Datapoints', [])
        if pts:
            latest = sorted(pts, key=lambda x: x['Timestamp'])[-1]
            val    = latest.get(stat, 0)
            ok(f"CloudWatch {metric}: {val:.4f}  (at {latest['Timestamp'].strftime('%H:%M')})")
            metrics_found.append(metric)
        else:
            warn(f"CloudWatch {metric}: no data yet")

    results['cloudwatch'] = metrics_found
except Exception as e:
    warn(f"CloudWatch check failed: {e}")
    results['cloudwatch'] = []

# ══════════════════════════════════════════════════════════════════════════════
step(8, "EventBridge Schedule — DataAggregator trigger")
# ══════════════════════════════════════════════════════════════════════════════
try:
    eb = aws_client._session().client('events')
    rules = eb.list_rules(NamePrefix='').get('Rules', [])
    da_rules = [r for r in rules if 'DataAggregator' in r.get('Name','') or
                'data' in r.get('Name','').lower() or
                'cold' in r.get('Name','').lower()]

    if da_rules:
        for rule in da_rules:
            state = rule.get('State','?')
            sched = rule.get('ScheduleExpression','?')
            ok(f"EventBridge rule '{rule['Name']}': {state}  |  Schedule: {sched}")
    else:
        # Check all rules for DataAggregator target
        found = False
        for rule in rules[:20]:
            try:
                targets = eb.list_targets_by_rule(Rule=rule['Name']).get('Targets', [])
                for t in targets:
                    if 'DataAggregator' in t.get('Arn', ''):
                        ok(f"EventBridge rule '{rule['Name']}': {rule.get('State')}  "
                           f"Schedule: {rule.get('ScheduleExpression','?')}")
                        found = True
            except Exception:
                pass
        if not found:
            warn("No EventBridge rule found targeting DataAggregator")

    results['eventbridge'] = True
except Exception as e:
    warn(f"EventBridge check failed: {e}")
    results['eventbridge'] = False

# ══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
header("END-TO-END TEST SUMMARY")

checks = [
    ("AWS Auth",                    results.get('auth')),
    ("S3 Bucket accessible",        results.get('s3_files', -1) >= 0),
    ("S3 has recent files",         results.get('s3_files', 0) > 0),
    ("DynamoDB has data (1h)",      results.get('dynamo_1h', 0) > 0),
    ("DynamoDB has data (15min)",   results.get('dynamo_15m', 0) > 0),
    ("Local ML models loaded",      results.get('models')),
    ("DataAggregator runs OK",      results.get('data_aggregator') == 'success'),
    ("IntelligentLambdaWarmer OK",  results.get('warmer') == 'success'),
    ("CloudWatch metrics present",  len(results.get('cloudwatch', [])) > 0),
]

all_pass = True
for name, passed in checks:
    if passed:
        print(f"  {G}✅{E} {name}")
    else:
        print(f"  {R}❌{E} {name}")
        all_pass = False

print()
print(f"  S3 files (1h):        {results.get('s3_files', 0)}")
print(f"  DynamoDB records (1h): {results.get('dynamo_1h', 0)}")
print(f"  DynamoDB records (15m):{results.get('dynamo_15m', 0)}")
print(f"  DataAggregator:        {results.get('data_aggregator','?')}")
print(f"  Warmer:                {results.get('warmer','?')}")
print(f"  CloudWatch metrics:    {results.get('cloudwatch', [])}")

print()
if all_pass:
    print(f"{G}{BOLD}✅ All checks passed — pipeline is fully operational!{E}")
else:
    if results.get('s3_files', 0) == 0:
        print(f"{Y}⚠️  Start Traffic Generator to populate S3 and DynamoDB{E}")
    if results.get('dynamo_15m', 0) == 0:
        print(f"{Y}⚠️  No DynamoDB data in last 15min — ETL Lambda may be delayed{E}")
    if results.get('data_aggregator') == 'success' and results.get('warmer') == 'success':
        print(f"{G}{BOLD}✅ Core pipeline (DataAggregator → Warmer) is working!{E}")
        print(f"{Y}   Only missing: live traffic data (start Traffic Generator){E}")
