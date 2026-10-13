"""
UT2 - Unit Test: Preprocessing (Feature Engineering)
Test ID : UT2
Module  : Preprocessing — ETL / Feature Vector Construction
Test    : Check data cleaning and formatting
Expected: Clean dataset with 9-element feature vector per record
Run     : python UT2_preprocessing.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import numpy as np
from ml_engine import build_feature_vector

print("=" * 60)
print("UT2 - Unit Test: Preprocessing (Feature Engineering)")
print("=" * 60)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

results = []

# Test 1: Feature vector has correct shape (1, 9)
try:
    fv = build_feature_vector(2, 6, 0.05, "auth", True, True)
    assert fv.shape == (1, 9), f"Expected shape (1,9), got {fv.shape}"
    print(f"  [1] Feature vector shape is (1, 9)                 : {PASS}")
    print(f"      Vector: {fv[0].tolist()}")
    results.append(True)
except Exception as e:
    print(f"  [1] Feature vector shape                           : {FAIL} — {e}")
    results.append(False)

# Test 2: Endpoint one-hot encoding is correct
try:
    for ep, expected_idx in [("auth", 3), ("profile", 4), ("search", 5)]:
        fv = build_feature_vector(12, 2, 1.0, ep, False, False)
        # Index 3=auth, 4=profile, 5=search should be 1.0
        assert fv[0][expected_idx] == 1.0
        others = [i for i in [3,4,5] if i != expected_idx]
        assert fv[0][others[0]] == 0.0 and fv[0][others[1]] == 0.0
    print(f"  [2] One-hot endpoint encoding is correct           : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [2] One-hot encoding                               : {FAIL} — {e}")
    results.append(False)

# Test 3: is_business_hours flag computed correctly
try:
    # Weekday 09:00 → business hours = 1
    fv_biz  = build_feature_vector(12, 2, 1.0, "auth", False, False)
    # Weekend 02:00 → business hours = 0
    fv_off  = build_feature_vector(2,  6, 0.05, "auth", True,  True)
    assert fv_biz[0][8] == 1.0, f"Expected 1.0, got {fv_biz[0][8]}"
    assert fv_off[0][8] == 0.0, f"Expected 0.0, got {fv_off[0][8]}"
    print(f"  [3] is_business_hours flag computed correctly      : {PASS}")
    print(f"      Weekday 12:00 → biz={fv_biz[0][8]:.0f}, Weekend 02:00 → biz={fv_off[0][8]:.0f}")
    results.append(True)
except Exception as e:
    print(f"  [3] is_business_hours flag                         : {FAIL} — {e}")
    results.append(False)

# Test 4: All values are floats (no None, no NaN)
try:
    fv = build_feature_vector(3, 6, 0.07, "search", True, True)
    assert not any(v is None for v in fv[0]), "None found in feature vector"
    assert not any(np.isnan(v) for v in fv[0]), "NaN found in feature vector"
    print(f"  [4] No None or NaN in feature vector               : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [4] Feature vector data quality                    : {FAIL} — {e}")
    results.append(False)

# Test 5: Feature vector values are in expected ranges
try:
    fv = build_feature_vector(14, 3, 0.5, "profile", False, False)
    assert 0 <= fv[0][0] <= 23,   f"hour_of_day out of range: {fv[0][0]}"
    assert 0 <= fv[0][1] <= 6,    f"day_of_week out of range: {fv[0][1]}"
    assert 0 <= fv[0][2] <= 10,   f"traffic_intensity out of range: {fv[0][2]}"
    assert fv[0][8] in [0.0, 1.0], f"is_business_hours not binary: {fv[0][8]}"
    print(f"  [5] Feature values within expected ranges          : {PASS}")
    results.append(True)
except Exception as e:
    print(f"  [5] Feature value ranges                           : {FAIL} — {e}")
    results.append(False)

# Summary
total  = len(results)
passed = sum(results)
print()
print(f"  Result: {passed}/{total} tests passed", end="  ")
print(f"  Overall: {PASS}" if passed == total else f"  Overall: {FAIL}")
print("=" * 60)
