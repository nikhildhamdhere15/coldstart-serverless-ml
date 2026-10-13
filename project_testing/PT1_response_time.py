"""
PT1 - Performance Test: Response Time Check
Test ID : PT1
Test    : Response time check — local ML inference latency
Expected: < 50 ms latency for ensemble prediction
Run     : python PT1_response_time.py
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import numpy as np
from ml_engine import build_feature_vector, ensemble_predict

print("=" * 60)
print("PT1 - Performance Test: Response Time Check")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []
THRESHOLD_MS = 50.0   # 50 ms SLO

# Test 1: Single prediction latency < 50 ms
try:
    fv    = build_feature_vector(2, 6, 0.05, "auth", True, True)
    start = time.perf_counter()
    pred  = ensemble_predict(fv)
    end   = time.perf_counter()
    ms    = (end - start) * 1000
    if ms < THRESHOLD_MS:
        print(f"  [1] Single prediction latency: {ms:.2f} ms < {THRESHOLD_MS} ms: {PASS}")
        results.append(True)
    else:
        print(f"  [1] Single prediction latency: {ms:.2f} ms >= {THRESHOLD_MS} ms : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [1] Single prediction latency                     : {FAIL} — {e}")
    results.append(False)

# Test 2: 100 predictions — average latency < 50 ms
try:
    scenarios = [
        (2,  6, 0.05, "auth",    True,  True),
        (14, 2, 1.80, "profile", False, False),
        (23, 5, 0.07, "search",  True,  True),
    ]
    latencies = []
    for i in range(100):
        h, d, t, ep, un, mob = scenarios[i % 3]
        fv    = build_feature_vector(h, d, t, ep, un, mob)
        start = time.perf_counter()
        pred  = ensemble_predict(fv)
        end   = time.perf_counter()
        latencies.append((end - start) * 1000)

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    min_ms = min(latencies)
    p95_ms = sorted(latencies)[94]   # 95th percentile

    if avg_ms < THRESHOLD_MS:
        print(f"  [2] 100 predictions avg={avg_ms:.2f} ms < {THRESHOLD_MS} ms  : {PASS}")
        results.append(True)
    else:
        print(f"  [2] 100 predictions avg={avg_ms:.2f} ms >= {THRESHOLD_MS} ms : {FAIL}")
        results.append(False)
    print(f"      Min={min_ms:.2f}ms  Max={max_ms:.2f}ms  P95={p95_ms:.2f}ms")
except Exception as e:
    print(f"  [2] 100-prediction benchmark                      : {FAIL} — {e}")
    results.append(False)

# Test 3: Feature vector construction latency < 1 ms
try:
    times = []
    for _ in range(1000):
        s = time.perf_counter()
        build_feature_vector(12, 3, 1.0, "auth", False, False)
        times.append((time.perf_counter() - s) * 1000)
    avg_fv = sum(times) / len(times)
    if avg_fv < 1.0:
        print(f"  [3] Feature vector build avg={avg_fv:.4f} ms < 1 ms : {PASS}")
        results.append(True)
    else:
        print(f"  [3] Feature vector build avg={avg_fv:.4f} ms >= 1 ms: {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [3] Feature vector construction latency           : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Threshold: < {THRESHOLD_MS} ms per prediction (local model)")
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
