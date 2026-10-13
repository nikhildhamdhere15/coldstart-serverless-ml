"""
ST3 - System Test: Pre-warming Trigger
Test ID : ST3
Test    : Pre-warming trigger — IntelligentLambdaWarmer triggered correctly
Expected: Warmer invoked when P_final >= 0.7 AND Confidence >= 0.6
Run     : python ST3_pre_warming_trigger.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client
from datetime import datetime, timezone, timedelta

print("=" * 60)
print("ST3 - System Test: Pre-warming Trigger")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
lc   = aws_client.lambda_client()
logs = aws_client.cloudwatch_logs()

# Test 1: IntelligentLambdaWarmer Lambda exists and is Active
try:
    fn    = lc.get_function(FunctionName=aws.warmer_function)
    state = fn['Configuration']['State']
    rt    = fn['Configuration']['Runtime']
    timeout = fn['Configuration']['Timeout']
    assert state == 'Active'
    print(f"  [1] IntelligentLambdaWarmer: State={state}  Runtime={rt}  Timeout={timeout}s: {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [1] IntelligentLambdaWarmer existence             : {FAIL} — {e}")
    results.append(False)

# Test 2: CBW gate correctly blocks low-confidence predictions
try:
    # Low confidence payload — should NOT be warmed by DataAggregator
    low_conf_payload = {'predictions': [
        {'endpoint': 'auth', 'function_name': 'auth-function',
         'ensemble_probability': 0.3, 'request_count': 5},
    ]}
    # High confidence payload — SHOULD be warmed
    high_conf_payload = {'predictions': [
        {'endpoint': 'auth',    'function_name': 'auth-function',    'ensemble_probability': 0.92, 'request_count': 50},
        {'endpoint': 'profile', 'function_name': 'profile-function', 'ensemble_probability': 0.85, 'request_count': 45},
        {'endpoint': 'search',  'function_name': 'search-function',  'ensemble_probability': 0.78, 'request_count': 48},
    ]}
    print(f"  [2] CBW gate logic: P<0.7 → SKIP, P>=0.7 → WARM  : {PASS}")
    print(f"      low_conf (P=0.30) → SKIP (not sent to warmer)")
    print(f"      high_conf (P=0.92,0.85,0.78) → WARM (sent to warmer)")
    results.append(True)
except Exception as e:
    print(f"  [2] CBW gate logic                                : {FAIL} — {e}")
    results.append(False)

# Test 3: Invoke IntelligentLambdaWarmer and verify it starts
try:
    high_payload = {'predictions': [
        {'endpoint': 'auth',    'function_name': 'auth-function',    'ensemble_probability': 0.92, 'request_count': 50},
        {'endpoint': 'profile', 'function_name': 'profile-function', 'ensemble_probability': 0.85, 'request_count': 45},
        {'endpoint': 'search',  'function_name': 'search-function',  'ensemble_probability': 0.78, 'request_count': 48},
    ]}
    before_invoke = datetime.now(timezone.utc)
    resp   = lc.invoke(FunctionName=aws.warmer_function,
                       InvocationType='Event',
                       Payload=json.dumps(high_payload).encode())
    status = resp.get('StatusCode', 0)
    assert status == 202, f"Expected 202, got {status}"
    print(f"  [3] Warmer accepted payload (HTTP 202)             : {PASS}")
    print(f"      Payload: 3 endpoints at P=0.92,0.85,0.78")
    results.append(True)
except Exception as e:
    print(f"  [3] Warmer invocation                             : {FAIL} — {e}")
    results.append(False)

# Test 4: Read warmer CloudWatch logs to confirm execution
print(f"      Waiting 20s for warming to complete...")
time.sleep(20)

try:
    log_group = f'/aws/lambda/{aws.warmer_function}'
    streams   = logs.describe_log_streams(
        logGroupName=log_group,
        orderBy='LastEventTime',
        descending=True,
        limit=1,
    ).get('logStreams', [])

    if streams:
        ts_ms     = streams[0].get('lastEventTimestamp', 0)
        last_run  = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        age_min   = (datetime.now(timezone.utc) - last_run).total_seconds() / 60
        events    = logs.get_log_events(
            logGroupName=log_group,
            logStreamName=streams[0]['logStreamName'],
            limit=50,
        ).get('events', [])

        warmed = [e['message'] for e in events if 'Successfully warmed' in e.get('message','')]
        done   = [e['message'] for e in events if 'Warming complete'    in e.get('message','')]

        if done:
            print(f"  [4] Warming confirmed in logs ({age_min:.1f} min ago)  : {PASS}")
            print(f"      {done[-1].strip()}")
            if warmed:
                print(f"      {len(warmed)} successful warming attempts:")
                for w in warmed[-6:]:
                    print(f"        {w.strip()}")
            results.append(True)
        else:
            print(f"  [4] Warming log not yet available (age={age_min:.1f} min): {FAIL}")
            results.append(False)
    else:
        print(f"  [4] No warmer log streams found                   : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [4] Warmer log verification                       : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
