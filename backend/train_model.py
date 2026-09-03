"""
FinGuard AI — Model Training Script
Trains XGBoost + Isolation Forest on PaySim dataset.
Run from backend folder: python train_model.py

Output:
  models/xgboost_model.joblib
  models/isolation_forest.joblib
  models/feature_names.joblib
"""

import os
import math
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score,
    precision_score, recall_score, f1_score
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

CSV_PATH    = "paysim.csv"
MODEL_DIR   = "models"
SAMPLE_SIZE = 200_000
RANDOM_SEED = 42

os.makedirs(MODEL_DIR, exist_ok=True)

print("Loading PaySim dataset...")
df = pd.read_csv(CSV_PATH, nrows=SAMPLE_SIZE)
print(f"  Loaded {len(df):,} rows")
print(f"  Fraud rate: {df['isFraud'].mean():.2%}")

NIGHT_HOURS = set(range(0, 6)) | {23}

def engineer_features(df):
    df = df.copy()
    df["log_amount"]    = np.log1p(df["amount"])
    df["balance_drain"] = ((df["oldbalanceOrg"] > 0) & (df["newbalanceOrig"] == 0)).astype(float)
    df["near_ctr"]      = ((df["amount"] >= 850_000) & (df["amount"] < 1_000_000)).astype(float)
    df["is_night"]      = df["step"].apply(lambda h: 1.0 if (h % 24) in NIGHT_HOURS else 0.0)
    df["is_cash_out"]   = (df["type"] == "CASH_OUT").astype(float)
    df["is_transfer"]   = (df["type"] == "TRANSFER").astype(float)
    df["is_intl"]       = 0.0
    df["is_risky_ch"]   = ((df["type"] == "TRANSFER") | (df["type"] == "CASH_OUT")).astype(float)
    df["large_amount"]  = (df["amount"] > 1_000_000).astype(float)
    df["balance_ratio"] = df.apply(
        lambda r: r["amount"] / r["oldbalanceOrg"] if r["oldbalanceOrg"] > 0 else 1.0,
        axis=1
    ).clip(0, 1)
    return df

print("Engineering features...")
df = engineer_features(df)

FEATURE_COLS = [
    "log_amount", "balance_drain", "near_ctr",
    "is_night", "is_intl", "is_risky_ch", "is_cash_out",
    "is_transfer", "large_amount", "balance_ratio"
]

X = df[FEATURE_COLS].values
y = df["isFraud"].values

print(f"  Class distribution — Fraud: {y.sum():,} | Normal: {(y==0).sum():,}")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
)
print(f"Train: {len(X_train):,} | Test: {len(X_test):,}")

print("\nTraining XGBoost...")
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
xgb = XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    scale_pos_weight=scale_pos_weight,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric="auc", random_state=RANDOM_SEED, n_jobs=-1,
)
xgb.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

y_pred  = xgb.predict(X_test)
y_proba = xgb.predict_proba(X_test)[:, 1]
print("\n=== XGBoost Results ===")
print(classification_report(y_test, y_pred, target_names=["Normal", "Fraud"]))
print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}")

print("\nTraining Isolation Forest...")
X_normal = X_train[y_train == 0]
iso = IsolationForest(n_estimators=200, contamination=0.01,
                      random_state=RANDOM_SEED, n_jobs=-1)
iso.fit(X_normal)

iso_pred = (iso.predict(X_test) == -1).astype(int)
print("\n=== Isolation Forest Results ===")
print(classification_report(y_test, iso_pred, target_names=["Normal", "Fraud"]))

joblib.dump(xgb, os.path.join(MODEL_DIR, "xgboost_model.joblib"))
joblib.dump(iso, os.path.join(MODEL_DIR, "isolation_forest.joblib"))
joblib.dump(FEATURE_COLS, os.path.join(MODEL_DIR, "feature_names.joblib"))

print("\n✓ Models saved to models/ folder")
print("Training complete.")