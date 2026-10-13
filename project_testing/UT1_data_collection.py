"""
UT1 - Unit Test: Data Collection
Test ID : UT1
Module  : Data Collection (Traffic Generator → S3)
Test    : Validate data retrieval from API logs
Expected: Correct data fetched and stored in S3 with proper structure
Run     : python UT1_data_collection.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone, timedelta

print("=" * 60)
print("UT1 - Unit Test: Data Collection")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: S3 bucket accessible
try:
    s3 = aws_client.s3()
    s3.head_bucket(Bucket=aws.s3_bucket)
    print(f"  [1] S3 bucket '{aws.s3_bucket}' accessible             : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [1] S3 bucket accessible                               : {FAIL} — {e}")
    results.append(False)

# Test 2: S3 has training data files today
try:
    prefix = f"training-data/{datetime.now().strftime('%Y/%m/%d')}/"
    resp   = s3.list_objects_v2(Bucket=aws.s3_bucket, Prefix=prefix, MaxKeys=5)
    files  = resp.get('Contents', [])
    if files:
        print(f"  [2] Training data files found (prefix={prefix}) : {PASS}")
        print(f"      Sample file: {files[0]['Key']}")
        results.append(True)
    else:
        print(f"  [2] No files under {prefix}                        : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [2] S3 file listing                                    : {FAIL} — {e}")
    results.append(False)

# Test 3: JSON record has correct structure
try:
    if files:
        obj  = s3.get_object(Bucket=aws.s3_bucket, Key=files[0]['Key'])
        data = json.loads(obj['Body'].read())
        required = ['request', 'response', 'ml_label', 'utc_timestamp']
        missing  = [k for k in required if k not in data]
        if not missing:
            req = data['request']
            req_fields = ['timestamp', 'endpoint', 'hour', 'day_of_week',
                          'traffic_intensity', 'user_type', 'device']
            missing_req = [k for k in req_fields if k not in req]
            if not missing_req:
                print(f"  [3] JSON record has correct structure              : {PASS}")
                print(f"      endpoint={req['endpoint']}  hour={req['hour']}  "
                      f"traffic={req['traffic_intensity']:.3f}  ml_label={data['ml_label']}")
                results.append(True)
            else:
                print(f"  [3] Missing request fields: {missing_req}          : {FAIL}")
                results.append(False)
        else:
            print(f"  [3] Missing top-level keys: {missing}                 : {FAIL}")
            results.append(False)
    else:
        print(f"  [3] No file to validate structure                      : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [3] JSON structure validation                          : {FAIL} — {e}")
    results.append(False)

# Test 4: ml_label is 0 or 1
try:
    if files:
        obj   = s3.get_object(Bucket=aws.s3_bucket, Key=files[0]['Key'])
        data  = json.loads(obj['Body'].read())
        label = data.get('ml_label')
        if label in [0, 1]:
            print(f"  [4] ml_label is binary (0 or 1), got={label}      : {PASS}")
            results.append(True)
        else:
            print(f"  [4] ml_label={label} not in [0,1]                 : {FAIL}")
            results.append(False)
    else:
        print(f"  [4] No file available                                  : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [4] ml_label validation                                : {FAIL} — {e}")
    results.append(False)

# Summary
total = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
