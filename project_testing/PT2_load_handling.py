"""
PT2 - Performance Test: Load Handling
Test ID : PT2
Test    : Load handling — system stable under simulated concurrent load
Expected: 500 predictions in < 5 seconds, no errors, stable output
Run     : python PT2_load_handling.py
"""
import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import numpy as np
from ml_engine import build_feature_vector, ensemble_predict

print("=" * 60)
print("PT2 - Performance Test: Load Handling")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: 500 sequential predictions without error
try:
    scenarios = [
        (2,  6, 0.05, "auth",    True,  True),
        (14, 2, 1.80, "profile", False, False),
        (23, 5, 0.07, "search",  True,  True),
        (9,  1, 1.20, "auth",    False, True),
        (0,  6, 0.02, "search",  True,  True),
    ]
    errors  = 0
    times   = []
    start_t = time.perf_counter()

    for i in range(500):
        h, d, t, ep, un, mob = scenarios[i % 5]
        fv   = build_feature_vector(h, d, t, ep, un, mob)
        s    = time.perf_counter()
        pred = ensemble_predict(fv)
        times.append((time.perf_counter() - s) * 1000)
        if pred is None or not (0 <= pred['p_final'] <= 1):
            errors += 1

    total_s = time.perf_counter() - start_t
    avg_ms  = sum(times) / len(times)

    if errors == 0 and total_s < 5.0:
        print(f"  [1] 500 predictions: {total_s:.2f}s  avg={avg_ms:.2f}ms  errors=0 : {PASS}")
        results.append(True)
    elif errors == 0:
        print(f"  [1] 500 predictions completed in {total_s:.2f}s (>5s target) : {FAIL}")
        results.append(False)
    else:
        print(f"  [1] 500 predictions: {errors} errors occurred         : {FAIL}")
        results.append(False)
    print(f"      P95 latency: {sorted(times)[474]:.2f} ms")
except Exception as e:
    print(f"  [1] Sequential load test                          : {FAIL} — {e}")
    results.append(False)

# Test 2: Concurrent predictions (10 threads, 50 each)
try:
    errors    = []
    latencies = []
    lock      = threading.Lock()

    def run_predictions(thread_id):
        for j in range(50):
            fv   = build_feature_vector(2 + j % 20, j % 7, 0.05 + j * 0.02, "auth", True, True)
            s    = time.perf_counter()
            pred = ensemble_predict(fv)
            ms   = (time.perf_counter() - s) * 1000
            with lock:
                latencies.append(ms)
                if pred is None or not (0 <= pred['p_final'] <= 1):
                    errors.append(f"Thread {thread_id}, iter {j}")

    threads   = [threading.Thread(target=run_predictions, args=(i,)) for i in range(10)]
    start_t   = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    total_s   = time.perf_counter() - start_t

    n_err     = len(errors)
    avg_ms    = sum(latencies) / len(latencies)

    if n_err == 0:
        print(f"  [2] 10 threads × 50 predictions: {total_s:.2f}s  errors=0  avg={avg_ms:.2f}ms: {PASS}")
        results.append(True)
    else:
        print(f"  [2] Concurrent test: {n_err} errors occurred          : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [2] Concurrent load test                          : {FAIL} — {e}")
    results.append(False)

# Test 3: Output consistency — same input always same output
try:
    fv = build_feature_vector(2, 6, 0.05, "auth", True, True)
    outputs = [ensemble_predict(fv)['p_final'] for _ in range(20)]
    assert len(set(outputs)) == 1, f"Non-deterministic: {set(outputs)}"
    print(f"  [3] Deterministic output: same input → same P_final={outputs[0]}: {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [3] Output consistency                            : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
