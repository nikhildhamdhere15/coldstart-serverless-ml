"""
ST1 - System Test: End-to-End Workflow Execution
Test ID : ST1
Test    : Complete pipeline from DynamoDB → DataAggregator → ML → Warmer → CloudWatch
Expected: System runs correctly — all components connect and produce output
Run     : python ST1_end_to_end_workflow.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone, timedelta

print("=" * 60)
print("ST1 - System Test: End-to-End Workflow Execution")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
lc = aws_client.lambda_client()

# Step 1: Verify DynamoDB has data (ETL pipeline running)
try:
    db    = aws_client.dynamodb()
    table = db.Table(aws.dynamodb_table)
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    past_ts = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())
    resp    = table.scan(
        FilterExpression='#ts BETWEEN :s AND :e',
        ExpressionAttributeNames={'#ts': 'timestamp_s'},
        ExpressionAttributeValues={':s': past_ts, ':e': now_ts},
        Select='COUNT',
    )
    count = resp.get('Count', 0)
    if count > 0:
        print(f"  [1] DynamoDB has {count} records (ETL pipeline active)  : {PASS}")
        results.append(True)
    else:
        print(f"  [1] DynamoDB has 0 records in 2h — start Traffic Gen  : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [1] DynamoDB data check                           : {FAIL} — {e}")
    results.append(False)

# Step 2: DataAggregator Lambda executes successfully
body = None
preds = []
try:
    resp   = lc.invoke(FunctionName=aws.data_aggregator_function,
                       InvocationType='RequestResponse',
                       Payload=json.dumps({}).encode())
    raw    = resp['Payload'].read().decode()
    outer  = json.loads(raw)
    body   = json.loads(outer.get('body','{}')) if isinstance(outer.get('body'), str) else outer.get('body',{})
    preds  = body.get('predictions', [])
    status = resp.get('StatusCode', 0)
    fn_err = resp.get('FunctionError', '')
    assert status == 200 and not fn_err
    print(f"  [2] DataAggregator executed (HTTP 200, no error)   : {PASS}")
    print(f"      Records: {body.get('total_records',0)}  "
          f"Evaluated: {body.get('endpoints_evaluated',0)}  "
          f"To warm: {body.get('endpoints_to_warm',0)}")
    results.append(True)
except Exception as e:
    print(f"  [2] DataAggregator execution                      : {FAIL} — {e}")
    results.append(False)

# Step 3: ML predictions generated for all 3 endpoints
try:
    if preds:
        endpoints_predicted = {p.get('endpoint') for p in preds}
        expected = {'auth', 'profile', 'search'}
        if expected.issubset(endpoints_predicted):
            print(f"  [3] ML predictions for all 3 endpoints            : {PASS}")
            results.append(True)
        else:
            missing = expected - endpoints_predicted
            print(f"  [3] Missing predictions for: {missing}             : {FAIL}")
            results.append(False)
    else:
        msg = body.get('message','') if body else ''
        if 'No data' in msg or 'Insufficient' in msg:
            print(f"  [3] No data for ML prediction (expected if no traffic): {PASS}")
            results.append(True)
        else:
            print(f"  [3] No predictions returned                       : {FAIL}")
            results.append(False)
except Exception as e:
    print(f"  [3] ML prediction check                           : {FAIL} — {e}")
    results.append(False)

# Step 4: IntelligentLambdaWarmer invokable (test with direct call)
try:
    test_payload = {'predictions': [
        {'endpoint': 'auth',    'function_name': 'auth-function',    'ensemble_probability': 0.85, 'request_count': 50},
        {'endpoint': 'profile', 'function_name': 'profile-function', 'ensemble_probability': 0.80, 'request_count': 45},
        {'endpoint': 'search',  'function_name': 'search-function',  'ensemble_probability': 0.75, 'request_count': 48},
    ]}
    resp2  = lc.invoke(FunctionName=aws.warmer_function,
                       InvocationType='Event',
                       Payload=json.dumps(test_payload).encode())
    status2 = resp2.get('StatusCode', 0)
    assert status2 == 202, f"Expected 202, got {status2}"
    print(f"  [4] IntelligentLambdaWarmer invoked (HTTP 202)     : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [4] IntelligentLambdaWarmer invocation            : {FAIL} — {e}")
    results.append(False)

# Step 5: Wait and verify CloudWatch metrics published
print(f"      Waiting 20s for warming to complete and metrics to publish...")
time.sleep(20)

try:
    cw  = aws_client.cloudwatch()
    end = datetime.now(timezone.utc)
    st  = end - timedelta(hours=1)
    r   = cw.get_metric_statistics(
        Namespace=aws.cloudwatch_namespace,
        MetricName='FunctionsWarmed',
        StartTime=st, EndTime=end,
        Period=3600, Statistics=['Sum'],
    )
    pts = r.get('Datapoints', [])
    if pts:
        val = sorted(pts, key=lambda x: x['Timestamp'])[-1].get('Sum', 0)
        print(f"  [5] CloudWatch FunctionsWarmed metric={val:.0f}        : {PASS}")
        results.append(True)
    else:
        print(f"  [5] CloudWatch FunctionsWarmed has no data yet     : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [5] CloudWatch metrics                            : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
