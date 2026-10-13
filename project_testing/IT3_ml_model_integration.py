"""
IT3 - Integration Test: ML Model Integration
Test ID : IT3
Test    : ML Model integration — DataAggregator Lambda returns prediction
Expected: Prediction returned with P_final, confidence, and CBW decision
Run     : python IT3_ml_model_integration.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
from config import aws
import aws_client

print("=" * 60)
print("IT3 - Integration Test: ML Model Integration")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
lc = aws_client.lambda_client()

# Test 1: DataAggregator Lambda exists
try:
    fn   = lc.get_function(FunctionName=aws.data_aggregator_function)
    state = fn['Configuration']['State']
    assert state == 'Active', f"State={state}"
    print(f"  [1] DataAggregator Lambda exists, State=Active    : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [1] DataAggregator Lambda existence               : {FAIL} — {e}")
    results.append(False)

# Test 2: Invoke DataAggregator and get response
body = None
try:
    resp    = lc.invoke(FunctionName=aws.data_aggregator_function,
                        InvocationType='RequestResponse',
                        Payload=json.dumps({}).encode())
    status  = resp.get('StatusCode', 0)
    fn_err  = resp.get('FunctionError', '')
    raw     = resp['Payload'].read().decode()
    assert status == 200, f"HTTP status={status}"
    assert not fn_err,    f"FunctionError={fn_err}"
    outer = json.loads(raw)
    body  = json.loads(outer.get('body', '{}')) if isinstance(outer.get('body'), str) else outer.get('body', {})
    print(f"  [2] DataAggregator invoked successfully            : {PASS}")
    print(f"      Message: {body.get('message','?')}")
    results.append(True)
except Exception as e:
    print(f"  [2] DataAggregator invocation                     : {FAIL} — {e}")
    results.append(False)

# Test 3: Predictions structure is correct
try:
    preds = body.get('predictions', []) if body else []
    if preds:
        for p in preds:
            assert 'endpoint'             in p, "Missing 'endpoint'"
            assert 'ensemble_probability' in p, "Missing 'ensemble_probability'"
            assert 'confidence'           in p, "Missing 'confidence'"
            assert 0.0 <= p['ensemble_probability'] <= 1.0
        print(f"  [3] Predictions structure correct ({len(preds)} endpoints): {PASS}")
        for p in preds:
            ep   = p.get('endpoint','?')
            prob = p.get('ensemble_probability', 0)
            conf = p.get('confidence', 0)
            cbw  = prob >= 0.7 and conf >= 0.6
            print(f"      {ep:10} P={prob:.3f}  C={conf:.3f}  CBW={'WARM' if cbw else 'SKIP'}")
        results.append(True)
    else:
        msg = body.get('message', '') if body else 'no body'
        if 'No data' in msg or 'Insufficient' in msg:
            print(f"  [3] No DynamoDB data available — run Traffic Generator: {PASS} (expected)")
            results.append(True)
        else:
            print(f"  [3] No predictions and unexpected message: {msg}  : {FAIL}")
            results.append(False)
except Exception as e:
    print(f"  [3] Predictions structure                         : {FAIL} — {e}")
    results.append(False)

# Test 4: Warmer invocation flag is boolean
try:
    if body:
        warmer_inv = body.get('warmer_invoked')
        assert isinstance(warmer_inv, bool), f"warmer_invoked={warmer_inv} is not bool"
        print(f"  [4] warmer_invoked is boolean: {warmer_inv}          : {PASS}")
        results.append(True)
    else:
        print(f"  [4] No body to check warmer_invoked                : {PASS} (no data)")
        results.append(True)
except Exception as e:
    print(f"  [4] warmer_invoked flag                           : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
