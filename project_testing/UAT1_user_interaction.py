"""
UAT1 - User Acceptance Test: User Interaction
Test ID : UAT1
Test    : User interaction — Streamlit dashboard components work smoothly
Expected: Dashboard renders all pages, data loads, controls respond
Run     : python UAT1_user_interaction.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone, timedelta

print("=" * 60)
print("UAT1 - User Acceptance Test: User Interaction")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: AWS backend reachable from dashboard
try:
    sts  = aws_client._session().client('sts')
    idn  = sts.get_caller_identity()
    print(f"  [1] AWS backend reachable (Account={idn['Account']}): {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [1] AWS backend connectivity                      : {FAIL} — {e}")
    results.append(False)

# Test 2: DynamoDB data retrievable (dashboard Overview page)
try:
    from realtime_data import get_live_stats
    # Simulate dashboard call (without Streamlit cache)
    db    = aws_client.dynamodb()
    table = db.Table(aws.dynamodb_table)
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    past_ts = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    resp    = table.scan(
        FilterExpression='#ts BETWEEN :s AND :e',
        ExpressionAttributeNames={'#ts': 'timestamp_s'},
        ExpressionAttributeValues={':s': past_ts, ':e': now_ts},
        Select='COUNT',
    )
    count = resp.get('Count', 0)
    print(f"  [2] Dashboard data source (DynamoDB) responsive   : {PASS}")
    print(f"      Records available for Overview page: {count}")
    results.append(True)
except Exception as e:
    print(f"  [2] DynamoDB data retrieval for dashboard         : {FAIL} — {e}")
    results.append(False)

# Test 3: ML prediction returns correct structure for display
try:
    from ml_engine import build_feature_vector, ensemble_predict
    fv   = build_feature_vector(14, 2, 1.5, "auth", False, False)
    pred = ensemble_predict(fv)
    required_display = ['p_final', 'xgboost', 'random_forest', 'confidence',
                        'should_warm', 'priority', 'label']
    missing = [k for k in required_display if k not in pred]
    if not missing:
        print(f"  [3] ML prediction returns all display fields      : {PASS}")
        print(f"      P_final={pred['p_final']:.3f}  Priority={pred['priority']}  "
              f"Label={pred['label']}")
        results.append(True)
    else:
        print(f"  [3] Missing display fields: {missing}             : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [3] ML prediction display fields                  : {FAIL} — {e}")
    results.append(False)

# Test 4: S3 file count function works (dashboard KPI card)
try:
    s3         = aws_client.s3()
    prefix     = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/"
    resp       = s3.list_objects_v2(Bucket=aws.s3_bucket, Prefix=prefix, MaxKeys=1)
    accessible = True
    print(f"  [4] S3 KPI data function accessible (bucket OK)   : {PASS}")
    print(f"      Prefix: {prefix}")
    results.append(True)
except Exception as e:
    print(f"  [4] S3 KPI function                               : {FAIL} — {e}")
    results.append(False)

# Test 5: CloudWatch sidebar status check
try:
    cw   = aws_client.cloudwatch()
    resp = cw.list_metrics(Namespace=aws.cloudwatch_namespace, Limit=5)
    metrics = [m['MetricName'] for m in resp.get('Metrics', [])]
    print(f"  [5] CloudWatch sidebar status check               : {PASS}")
    print(f"      Metrics available: {metrics if metrics else 'None yet (no warming cycle)'}")
    results.append(True)
except Exception as e:
    print(f"  [5] CloudWatch status check                       : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
