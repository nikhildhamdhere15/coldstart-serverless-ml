"""
Save Models for Streamlit Deployment
Trains XGBoost and Random Forest (XGBoost with RF hyperparameters)
using the EXACT same data generation logic and hyperparameters
as cold_start_ensemble_deployment/deploy_xgboost.py and deploy_random_forest.py

Run this once locally (where AWS credentials are configured):
    cd streamlit_ml_tg
    python save_models.py

This creates:
    models/xgboost_model.pkl
    models/random_forest_model.pkl
"""

import os
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, roc_auc_score
import xgboost as xgb

os.makedirs("models", exist_ok=True)

# ── Data generation — exact same logic as deploy_xgboost.py ──────────────────

def generate_data(n_samples: int, seed: int) -> pd.DataFrame:
    np.random.seed(seed)
    rows = []

    for _ in range(n_samples):
        hour_of_day  = np.random.randint(0, 24)
        day_of_week  = np.random.randint(0, 7)
        is_biz       = 1 if (9 <= hour_of_day <= 17 and day_of_week < 5) else 0

        if is_biz:
            traffic = np.random.beta(2, 1)
        elif 18 <= hour_of_day <= 23:
            traffic = np.random.beta(1.5, 1.5)
        else:
            traffic = np.random.beta(1, 3)

        ep_type      = np.random.choice([0, 1, 2], p=[0.5, 0.3, 0.2])
        ep_auth      = 1 if ep_type == 0 else 0
        ep_profile   = 1 if ep_type == 1 else 0
        ep_search    = 1 if ep_type == 2 else 0
        user_new     = np.random.choice([0, 1], p=[0.75, 0.25])
        device_mob   = np.random.choice([0, 1], p=[0.35, 0.65])

        # Cold start probability — same logic as deploy scripts
        p = 0.05
        if not is_biz:                              p += 0.4
        if traffic < 0.15:                          p += 0.5
        if user_new and traffic < 0.3:              p += 0.3
        if ep_auth and hour_of_day < 7:             p += 0.4
        if device_mob and not is_biz:               p += 0.2
        if day_of_week >= 5:                        p += 0.25
        p = min(p, 0.95)

        label = 1 if np.random.random() < p else 0

        rows.append([
            label, hour_of_day, day_of_week, traffic,
            ep_auth, ep_profile, ep_search,
            user_new, device_mob, is_biz
        ])

    cols = [
        "label", "hour_of_day", "day_of_week", "traffic_intensity",
        "endpoint_auth", "endpoint_profile", "endpoint_search",
        "user_type_new", "device_mobile", "is_business_hours"
    ]
    return pd.DataFrame(rows, columns=cols)


# ── Train XGBoost — exact hyperparameters from deploy_xgboost.py ─────────────

def train_xgboost(df: pd.DataFrame):
    X = df.drop("label", axis=1).values
    y = df["label"].values
    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        objective       = "binary:logistic",
        n_estimators    = 100,
        max_depth       = 6,
        learning_rate   = 0.1,       # eta = 0.1
        subsample       = 0.8,
        colsample_bytree= 0.8,
        min_child_weight= 1,
        eval_metric     = "auc",
        use_label_encoder=False,
        random_state    = 42,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1]
    print(f"  XGBoost  — F1: {f1_score(y_val, preds):.3f}  AUC: {roc_auc_score(y_val, probs):.3f}")
    return model


# ── Train Random Forest — exact hyperparameters from deploy_random_forest.py ─

def train_random_forest(df: pd.DataFrame):
    X = df.drop("label", axis=1).values
    y = df["label"].values
    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=123)

    # Random Forest uses XGBoost container with RF-like hyperparameters
    model = xgb.XGBClassifier(
        objective        = "binary:logistic",
        n_estimators     = 200,      # num_round = 200 (more trees)
        max_depth        = 8,        # deeper trees
        learning_rate    = 0.05,     # eta = 0.05 (lower)
        subsample        = 0.7,      # more aggressive subsampling
        colsample_bytree = 0.7,      # feature subsampling
        min_child_weight = 3,
        eval_metric      = "auc",
        use_label_encoder=False,
        random_state     = 123,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1]
    print(f"  RandomForest — F1: {f1_score(y_val, preds):.3f}  AUC: {roc_auc_score(y_val, probs):.3f}")
    return model


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating training data (seed=42, n=2000)...")
    df_xgb = generate_data(n_samples=1000, seed=42)   # XGBoost uses 1000 samples
    df_rf  = generate_data(n_samples=2000, seed=123)  # RF uses 2000 samples

    print(f"  XGBoost data  — cold start ratio: {df_xgb['label'].mean():.2%}")
    print(f"  RF data       — cold start ratio: {df_rf['label'].mean():.2%}")

    print("\nTraining models...")
    xgb_model = train_xgboost(df_xgb)
    rf_model  = train_random_forest(df_rf)

    print("\nSaving models...")
    joblib.dump(xgb_model, "models/xgboost_model.pkl")
    joblib.dump(rf_model,  "models/random_forest_model.pkl")
    print("  Saved: models/xgboost_model.pkl")
    print("  Saved: models/random_forest_model.pkl")

    # Quick ensemble test — same test case as deploy_complete_ensemble.py
    test_features = np.array([[2, 6, 0.1, 1, 0, 0, 1, 1, 0]])  # high risk scenario
    xgb_prob = float(xgb_model.predict_proba(test_features)[0][1])
    rf_prob  = float(rf_model.predict_proba(test_features)[0][1])
    p_final  = 0.7 * xgb_prob + 0.3 * rf_prob
    conf     = 1.0 - abs(xgb_prob - rf_prob)

    print(f"\nEnsemble test (early morning, weekend, low traffic, new mobile user):")
    print(f"  XGBoost (70%):      {xgb_prob:.3f}")
    print(f"  Random Forest (30%): {rf_prob:.3f}")
    print(f"  P_final:            {p_final:.3f}")
    print(f"  Confidence C:       {conf:.3f}")
    print(f"  CBW decision:       {'WARM' if p_final >= 0.7 and conf >= 0.6 else 'SKIP'}")
    print("\nDone. Models ready for Streamlit deployment.")
