"""
UT3 - Unit Test: Prediction Module
Test ID : UT3
Module  : ML Prediction (XGBoost + Random Forest ensemble)
Test    : Verify model output — probability generated, CBW gate correct
Expected: P_final in [0,1], Confidence in [0,1], label in [cold_start, warm]
Run     : python UT3_prediction.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import numpy as np
import joblib
from ml_engine import build_feature_vector, ensemble_predict

print("=" * 60)
print("UT3 - Unit Test: ML Prediction Module")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: Models load successfully
try:
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg', 'models')
    xgb = joblib.load(os.path.join(model_dir, 'xgboost_model.pkl'))
    rf  = joblib.load(os.path.join(model_dir, 'random_forest_model.pkl'))
    print(f"  [1] XGBoost and RF models load successfully        : {PASS}")
    print(f"      XGBoost type: {type(xgb).__name__}, RF type: {type(rf).__name__}")
    results.append(True)
except Exception as e:
    print(f"  [1] Model loading                                  : {FAIL} — {e}")
    results.append(False)

# Test 2: High-risk scenario produces high P_final
try:
    # 2AM, Sunday, very low traffic, new mobile user → should be HIGH risk
    fv   = build_feature_vector(2, 6, 0.05, "auth", True, True)
    pred = ensemble_predict(fv)
    assert pred is not None, "ensemble_predict returned None"
    p    = pred['p_final']
    assert p >= 0.7, f"High-risk scenario P_final={p:.3f} < 0.7"
    print(f"  [2] High-risk scenario: P_final={p:.3f} >= 0.7    : {PASS}")
    print(f"      XGBoost={pred['xgboost']:.3f}  RF={pred['random_forest']:.3f}  "
          f"Confidence={pred['confidence']:.3f}  Label={pred['label']}")
    results.append(True)
except Exception as e:
    print(f"  [2] High-risk prediction                           : {FAIL} — {e}")
    results.append(False)

# Test 3: Low-risk scenario produces low P_final
try:
    # 14:00, Wednesday, high traffic, returning desktop user → should be LOW risk
    fv   = build_feature_vector(14, 2, 1.8, "search", False, False)
    pred = ensemble_predict(fv)
    p    = pred['p_final']
    assert p < 0.5, f"Low-risk scenario P_final={p:.3f} >= 0.5"
    print(f"  [3] Low-risk scenario: P_final={p:.3f} < 0.5      : {PASS}")
    print(f"      XGBoost={pred['xgboost']:.3f}  RF={pred['random_forest']:.3f}  "
          f"Label={pred['label']}")
    results.append(True)
except Exception as e:
    print(f"  [3] Low-risk prediction                            : {FAIL} — {e}")
    results.append(False)

# Test 4: P_final is always in [0, 1]
try:
    test_cases = [
        (0,  6, 0.01, "auth",    True,  True),
        (12, 2, 1.5,  "profile", False, False),
        (23, 5, 0.08, "search",  True,  True),
        (9,  1, 1.0,  "auth",    False, True),
    ]
    for case in test_cases:
        fv   = build_feature_vector(*case)
        pred = ensemble_predict(fv)
        assert 0.0 <= pred['p_final'] <= 1.0, f"P_final={pred['p_final']} out of [0,1]"
    print(f"  [4] P_final always in range [0.0, 1.0]            : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [4] P_final range check                            : {FAIL} — {e}")
    results.append(False)

# Test 5: CBW gate logic is correct
try:
    fv_hi  = build_feature_vector(2, 6, 0.05, "auth",   True,  True)
    fv_lo  = build_feature_vector(14, 2, 1.8,  "search", False, False)
    pred_hi = ensemble_predict(fv_hi)
    pred_lo = ensemble_predict(fv_lo)
    # High risk → should_warm=True, Low risk → should_warm=False
    cbw_hi = pred_hi['should_warm']
    cbw_lo = pred_lo['should_warm']
    if cbw_hi and not cbw_lo:
        print(f"  [5] CBW gate: HIGH→WARM={cbw_hi}, LOW→SKIP={not cbw_lo} : {PASS}")
        results.append(True)
    else:
        print(f"  [5] CBW gate: HIGH→{cbw_hi}, LOW→{cbw_lo}            : {FAIL}")
        results.append(False)
except Exception as e:
    print(f"  [5] CBW gate logic                                 : {FAIL} — {e}")
    results.append(False)

# Test 6: Priority assignment
try:
    fv = build_feature_vector(2, 6, 0.05, "auth", True, True)
    pred = ensemble_predict(fv)
    p    = pred['p_final']
    prio = pred['priority']
    if p >= 0.8:
        assert prio == "HIGH",   f"P={p:.3f} >= 0.8 but priority={prio}"
    elif p >= 0.7:
        assert prio == "MEDIUM", f"P={p:.3f} >= 0.7 but priority={prio}"
    else:
        assert prio == "NONE",   f"P={p:.3f} < 0.7 but priority={prio}"
    print(f"  [6] Priority assigned correctly: P={p:.3f} → {prio}: {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [6] Priority assignment                            : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
