"""
ST2 - System Test: Cold Start Prediction Accuracy
Test ID : ST2
Test    : Cold start prediction — accurate prediction verified
Expected: Model correctly identifies high/low risk scenarios
Run     : python ST2_cold_start_prediction.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import numpy as np
import joblib
from ml_engine import build_feature_vector, ensemble_predict

print("=" * 60)
print("ST2 - System Test: Cold Start Prediction Accuracy")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Define test scenarios with expected outcomes
test_scenarios = [
    # (hour, day, traffic, endpoint, user_new, mobile, expected_label, description)
    (2,  6, 0.04, "auth",    True,  True,  "cold_start", "Midnight Sunday low traffic new mobile"),
    (3,  5, 0.06, "profile", True,  True,  "cold_start", "3AM Saturday new mobile user"),
    (23, 6, 0.07, "search",  True,  True,  "cold_start", "11PM Sunday off-hours"),
    (14, 2, 1.80, "search",  False, False, "warm",       "2PM Wednesday high traffic returning"),
    (11, 1, 1.60, "auth",    False, False, "warm",       "11AM Monday business hours desktop"),
    (15, 3, 1.50, "profile", False, False, "warm",       "3PM Wednesday returning user"),
]

correct = 0
for i, (h, d, t, ep, un, mob, expected, desc) in enumerate(test_scenarios, 1):
    try:
        fv   = build_feature_vector(h, d, t, ep, un, mob)
        pred = ensemble_predict(fv)
        label  = pred['label']
        p      = pred['p_final']
        status = PASS if label == expected else FAIL
        if label == expected:
            correct += 1
        print(f"  [{i}] {desc[:45]:<45}: {status}")
        print(f"      P_final={p:.3f}  Expected={expected}  Got={label}")
    except Exception as e:
        print(f"  [{i}] {desc:<45}: {FAIL} — {e}")

results.append(correct)

# Test 7: Ensemble uses correct weights (0.7 XGB + 0.3 RF)
try:
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg', 'models')
    xgb = joblib.load(os.path.join(model_dir, 'xgboost_model.pkl'))
    rf  = joblib.load(os.path.join(model_dir, 'random_forest_model.pkl'))
    fv  = build_feature_vector(2, 6, 0.05, "auth", True, True)
    xp  = float(xgb.predict_proba(fv)[0][1])
    rp  = float(rf.predict_proba(fv)[0][1])
    expected_p = round(0.7 * xp + 0.3 * rp, 4)
    pred = ensemble_predict(fv)
    assert abs(pred['p_final'] - expected_p) < 0.001
    print(f"\n  [7] Ensemble weight: 0.7×XGB({xp:.3f}) + 0.3×RF({rp:.3f}) = {expected_p:.3f}: {PASS}")
    results.append(True)
except Exception as e:
    print(f"\n  [7] Ensemble weight verification                  : {FAIL} — {e}")
    results.append(False)

# Summary
print()
acc = (correct / len(test_scenarios)) * 100
print(f"  Scenario accuracy: {correct}/{len(test_scenarios)} = {acc:.1f}%")
print(f"  Accuracy {'>=' if acc >= 80 else '<'} 80% threshold: {PASS if acc >= 80 else FAIL}")
print("=" * 60)
