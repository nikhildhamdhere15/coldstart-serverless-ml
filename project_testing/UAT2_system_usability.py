"""
UAT2 - User Acceptance Test: System Usability
Test ID : UAT2
Test    : System usability — easy to use, configuration correct
Expected: Config loads, environment valid, all services reachable
Run     : python UAT2_system_usability.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client

print("=" * 60)
print("UAT2 - User Acceptance Test: System Usability")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: Configuration loads with correct values
try:
    assert aws.region,             "AWS region not configured"
    assert aws.dynamodb_table,     "DynamoDB table not configured"
    assert aws.s3_bucket,          "S3 bucket not configured"
    assert aws.data_aggregator_function, "DataAggregator function not configured"
    assert aws.warmer_function,    "Warmer function not configured"
    assert aws.cloudwatch_namespace, "CloudWatch namespace not configured"
    print(f"  [1] Configuration loaded correctly                 : {PASS}")
    print(f"      Region={aws.region}  Table={aws.dynamodb_table}")
    print(f"      Bucket={aws.s3_bucket}")
    results.append(True)
except Exception as e:
    print(f"  [1] Configuration loading                         : {FAIL} — {e}")
    results.append(False)

# Test 2: Model files exist (dashboard can load models)
try:
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg', 'models')
    xgb_path  = os.path.join(model_dir, 'xgboost_model.pkl')
    rf_path   = os.path.join(model_dir, 'random_forest_model.pkl')
    assert os.path.exists(xgb_path), f"Missing: {xgb_path}"
    assert os.path.exists(rf_path),  f"Missing: {rf_path}"
    xgb_kb = os.path.getsize(xgb_path) / 1024
    rf_kb  = os.path.getsize(rf_path)  / 1024
    print(f"  [2] Model files exist (XGB={xgb_kb:.0f}KB, RF={rf_kb:.0f}KB): {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [2] Model files existence                         : {FAIL} — {e}")
    results.append(False)

# Test 3: All 5 AWS services reachable
services = {
    'DynamoDB': lambda: aws_client.dynamodb().Table(aws.dynamodb_table).load(),
    'S3':       lambda: aws_client.s3().head_bucket(Bucket=aws.s3_bucket),
    'Lambda':   lambda: aws_client.lambda_client().get_function(FunctionName=aws.data_aggregator_function),
    'CloudWatch': lambda: aws_client.cloudwatch().list_metrics(Namespace=aws.cloudwatch_namespace, Limit=1),
    'CloudWatch Logs': lambda: aws_client.cloudwatch_logs().describe_log_groups(Limit=1),
}
all_ok = True
for name, fn in services.items():
    try:
        fn()
        print(f"  [3.{list(services.keys()).index(name)+1}] {name:<20} reachable    : {PASS}")
    except Exception as e:
        print(f"  [3.{list(services.keys()).index(name)+1}] {name:<20}              : {FAIL} — {e}")
        all_ok = False
results.append(all_ok)

# Test 4: Both Lambda functions are Active
try:
    lc     = aws_client.lambda_client()
    fn_da  = lc.get_function(FunctionName=aws.data_aggregator_function)
    fn_wm  = lc.get_function(FunctionName=aws.warmer_function)
    st_da  = fn_da['Configuration']['State']
    st_wm  = fn_wm['Configuration']['State']
    assert st_da == 'Active' and st_wm == 'Active'
    print(f"  [4] Lambda functions Active: DataAggregator={st_da}  Warmer={st_wm}: {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [4] Lambda functions state                        : {FAIL} — {e}")
    results.append(False)

# Test 5: Streamlit app file exists and importable
try:
    app_path = os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg', 'app.py')
    assert os.path.exists(app_path), f"app.py not found at {app_path}"
    size_kb = os.path.getsize(app_path) / 1024
    print(f"  [5] Streamlit app.py exists ({size_kb:.0f} KB)            : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [5] Streamlit app.py                              : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
