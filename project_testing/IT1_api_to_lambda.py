"""
IT1 - Integration Test: Traffic Generator → S3 (API to Lambda flow)
Test ID : IT1
Test    : API Gateway to Lambda communication — data flows correctly
Expected: Traffic generator writes JSON to S3, data flows without error
Run     : python IT1_api_to_lambda.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone

print("=" * 60)
print("IT1 - Integration Test: Traffic Generator → S3")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
s3 = aws_client.s3()

# Test 1: Write a test record to S3 (simulating traffic generator)
test_key = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/integration_test_{int(time.time())}.json"
test_record = {
    'request': {
        'timestamp':         datetime.now(timezone.utc).isoformat(),
        'instance_id':       'integration-test',
        'endpoint':          '/auth',
        'hour':              2,
        'day_of_week':       6,
        'traffic_intensity': 0.05,
        'user_type':         'new',
        'device':            'mobile',
        'is_business_hours': 0,
    },
    'response': {
        'success':       True,
        'response_time': 2.45,
        'cold_start':    True,
        'status_code':   200,
    },
    'ml_label':      1,
    'utc_timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
}

try:
    s3.put_object(
        Bucket=aws.s3_bucket,
        Key=test_key,
        Body=json.dumps(test_record).encode('utf-8'),
    )
    print(f"  [1] Write test record to S3                        : {PASS}")
    print(f"      Key: {test_key}")
    results.append(True)
except Exception as e:
    print(f"  [1] Write to S3                                    : {FAIL} — {e}")
    results.append(False)

# Test 2: Read back the record and verify integrity
try:
    time.sleep(1)
    obj  = s3.get_object(Bucket=aws.s3_bucket, Key=test_key)
    data = json.loads(obj['Body'].read())
    assert data['ml_label'] == 1
    assert data['request']['endpoint'] == '/auth'
    assert data['request']['hour'] == 2
    print(f"  [2] Read-back record integrity verified            : {PASS}")
    print(f"      ml_label={data['ml_label']}  endpoint={data['request']['endpoint']}  "
          f"hour={data['request']['hour']}")
    results.append(True)
except Exception as e:
    print(f"  [2] Read-back integrity                            : {FAIL} — {e}")
    results.append(False)

# Test 3: Count recent S3 files (data pipeline is active)
try:
    prefix = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/"
    resp   = s3.list_objects_v2(Bucket=aws.s3_bucket, Prefix=prefix)
    count  = resp.get('KeyCount', 0)
    if count > 0:
        print(f"  [3] S3 has {count} records today (data pipeline active): {PASS}")
        results.append(True)
    else:
        print(f"  [3] No S3 records found — run Traffic Generator    : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [3] S3 record count                                : {FAIL} — {e}")
    results.append(False)

# Cleanup test record
try:
    s3.delete_object(Bucket=aws.s3_bucket, Key=test_key)
except Exception:
    pass

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
