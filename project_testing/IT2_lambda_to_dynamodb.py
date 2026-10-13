"""
IT2 - Integration Test: Lambda to DynamoDB Storage
Test ID : IT2
Test    : Lambda to DynamoDB storage — data stored successfully
Expected: ETL Lambda writes processed records to ETLFeatureData DynamoDB table
Run     : python IT2_lambda_to_dynamodb.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone, timedelta
from decimal import Decimal

print("=" * 60)
print("IT2 - Integration Test: Lambda to DynamoDB Storage")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
db    = aws_client.dynamodb()
table = db.Table(aws.dynamodb_table)

# Test 1: DynamoDB table exists and is ACTIVE
try:
    table.load()
    status = table.table_status
    assert status == 'ACTIVE', f"Table status is {status}"
    print(f"  [1] DynamoDB table '{aws.dynamodb_table}' status=ACTIVE: {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [1] DynamoDB table status                          : {FAIL} — {e}")
    results.append(False)

# Test 2: Records exist in DynamoDB (ETL is running)
try:
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
        print(f"  [2] DynamoDB has {count} records in last 2h           : {PASS}")
        results.append(True)
    else:
        print(f"  [2] No records in last 2h — ETL may not have run   : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [2] DynamoDB record count                          : {FAIL} — {e}")
    results.append(False)

# Test 3: Records have required feature fields
try:
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    past_ts = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())
    resp    = table.scan(
        FilterExpression='#ts BETWEEN :s AND :e',
        ExpressionAttributeNames={'#ts': 'timestamp_s'},
        ExpressionAttributeValues={':s': past_ts, ':e': now_ts},
        Limit=3,
    )
    items = resp.get('Items', [])
    if items:
        item     = items[0]
        required = ['timestamp_s', 'hour_of_day', 'day_of_week',
                    'traffic_intensity', 'user_type_new', 'device_mobile',
                    'is_business_hours']
        missing  = [k for k in required if k not in item]
        if not missing:
            print(f"  [3] DynamoDB record has all required feature fields: {PASS}")
            print(f"      hour={item.get('hour_of_day')}  day={item.get('day_of_week')}  "
                  f"traffic={float(item.get('traffic_intensity', 0)):.3f}")
            results.append(True)
        else:
            print(f"  [3] Missing fields: {missing}                     : {FAIL}")
            results.append(False)
    else:
        print(f"  [3] No items returned for field check              : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [3] DynamoDB field validation                      : {FAIL} — {e}")
    results.append(False)

# Test 4: Endpoint one-hot flags are present
try:
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    past_ts = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    resp    = table.scan(
        FilterExpression='#ts BETWEEN :s AND :e',
        ExpressionAttributeNames={'#ts': 'timestamp_s'},
        ExpressionAttributeValues={':s': past_ts, ':e': now_ts},
        Limit=10,
    )
    items = resp.get('Items', [])
    if items:
        endpoints_found = set()
        for item in items:
            if item.get('endpoint_auth', 0)    == 1: endpoints_found.add('auth')
            if item.get('endpoint_profile', 0) == 1: endpoints_found.add('profile')
            if item.get('endpoint_search', 0)  == 1: endpoints_found.add('search')
        if len(endpoints_found) >= 2:
            print(f"  [4] Endpoint one-hot flags found: {endpoints_found}   : {PASS}")
            results.append(True)
        else:
            print(f"  [4] Only endpoints found: {endpoints_found}           : {FAIL}")
            results.append(False)
    else:
        print(f"  [4] No items for endpoint check                    : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [4] Endpoint flag validation                       : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
