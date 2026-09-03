"""
ML Fraud Prediction Service
────────────────────────────
XGBoost + Isolation Forest ensemble with SHAP explainability.
Models loaded from models/ folder (trained via train_model.py).
"""

import logging
import math
import time
import os
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Load models ───────────────────────────────────────────────────────────────
try:
    import joblib
    _MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models")
    _MODEL_DIR = os.path.abspath(_MODEL_DIR)
    _xgb_model   = joblib.load(os.path.join(_MODEL_DIR, "xgboost_model.joblib"))
    _iso_model   = joblib.load(os.path.join(_MODEL_DIR, "isolation_forest.joblib"))
    _feat_names  = joblib.load(os.path.join(_MODEL_DIR, "feature_names.joblib"))
    MODEL_VERSION = "xgboost-isoforest-v1.0"
    logger.info(f"✓ Models loaded from {_MODEL_DIR}")
except Exception as e:
    _xgb_model  = None
    _iso_model  = None
    _feat_names = None
    MODEL_VERSION = "rule-based-v1.0-fallback"
    logger.warning(f"Models not found, using rule-based fallback: {e}")

# ── SHAP explainer (lazy init) ────────────────────────────────────────────────
_shap_explainer = None

def _get_shap_explainer():
    global _shap_explainer
    if _shap_explainer is None and _xgb_model is not None:
        try:
            import shap
            _shap_explainer = shap.TreeExplainer(_xgb_model)
        except Exception as e:
            logger.warning(f"SHAP explainer init failed: {e}")
    return _shap_explainer


class FraudPredictionService:

    def __init__(self):
        logger.info(f"FraudPredictionService initialised — model: {MODEL_VERSION}")

    # ── Feature extraction ────────────────────────────────────────────────────

    def extract_features(self, txn: dict) -> Dict[str, float]:
        """Convert a transaction dict into a numeric feature vector."""
        high_risk_locations = {"Dubai", "Hong Kong", "Singapore", "Panama", "Cayman Islands"}
        night_hours         = set(range(0, 6)) | {23}

        amount      = float(txn.get("amount", 0))
        old_bal     = float(txn.get("oldbalanceOrg", 0))
        new_bal     = float(txn.get("newbalanceOrig", old_bal))
        hour        = int(txn.get("hour", 12))
        location    = txn.get("location", "")
        channel     = txn.get("channel", "")
        paysim_type = txn.get("paySimType", txn.get("type", "PAYMENT"))

        balance_drain = 1.0 if (old_bal > 0 and new_bal == 0) else 0.0
        near_ctr      = 1.0 if 850_000 <= amount < 1_000_000 else 0.0
        is_night      = 1.0 if hour in night_hours else 0.0
        is_intl       = 1.0 if location in high_risk_locations else 0.0
        is_risky_ch   = 1.0 if channel in {"Wire Transfer", "Crypto"} or \
                                paysim_type in {"TRANSFER", "CASH_OUT"} else 0.0
        is_cash_out   = 1.0 if paysim_type == "CASH_OUT" else 0.0
        is_transfer   = 1.0 if paysim_type == "TRANSFER" else 0.0
        log_amount    = math.log1p(amount)
        large_amount  = 1.0 if amount > 1_000_000 else 0.0
        balance_ratio = min(amount / old_bal, 1.0) if old_bal > 0 else 1.0

        return {
            "log_amount":    log_amount,
            "balance_drain": balance_drain,
            "near_ctr":      near_ctr,
            "is_night":      is_night,
            "is_intl":       is_intl,
            "is_risky_ch":   is_risky_ch,
            "is_cash_out":   is_cash_out,
            "is_transfer":   is_transfer,
            "large_amount":  large_amount,
            "balance_ratio": balance_ratio,
            # Keep original fields for backward compat
            "amount":        amount,
        }

    # ── Main scoring ──────────────────────────────────────────────────────────

    def score_transaction(self, txn: dict) -> Dict[str, Any]:
        """
        Returns fraud probability, ensemble signal, SHAP values,
        and disagreement flag for a single transaction.
        """
        features = self.extract_features(txn)

        if _xgb_model is not None:
            xgb_score, iso_score, disagreement = self._ensemble_score(features)
            probability = (xgb_score * 0.7) + (iso_score * 0.3)
            shap_values = self._get_shap_values(features)
        else:
            probability  = self._rule_based_score(features)
            xgb_score    = probability
            iso_score    = probability
            disagreement = False
            shap_values  = []

        is_fraud = probability >= 0.35  # lower threshold — let agents decide

        return {
            "transaction_id":    txn.get("id", txn.get("_id", "unknown")),
            "fraud_probability": round(probability, 4),
            "xgb_score":         round(xgb_score, 4),
            "iso_score":         round(iso_score, 4),
            "disagreement_flag": disagreement,
            "is_fraud":          is_fraud,
            "risk_level":        self._risk_level(probability),
            "features":          features,
            "shap_values":       shap_values,
            "model_version":     MODEL_VERSION,
            "confidence":        round(probability * 100, 1),
        }

    def score_batch(self, transactions: List[dict]) -> List[Dict[str, Any]]:
        start   = time.monotonic()
        results = [self.score_transaction(t) for t in transactions]
        logger.info(
            f"[Batch] {len(transactions)} txns scored in "
            f"{(time.monotonic()-start)*1000:.1f}ms — "
            f"{sum(1 for r in results if r['is_fraud'])} fraud"
        )
        return results

    # ── Ensemble scoring ──────────────────────────────────────────────────────

    def _ensemble_score(self, features: Dict[str, float]):
        """Run both models, return scores and disagreement flag."""
        feat_names = _feat_names or [
            "log_amount", "balance_drain", "near_ctr", "is_night",
            "is_intl", "is_risky_ch", "is_cash_out", "is_transfer",
            "large_amount", "balance_ratio"
        ]
        vector = np.array([[features.get(f, 0.0) for f in feat_names]])

        # XGBoost — fraud probability
        xgb_score = float(_xgb_model.predict_proba(vector)[0][1])

        # Isolation Forest — anomaly score (normalised to 0-1)
        iso_raw   = _iso_model.decision_function(vector)[0]
        # decision_function: negative = anomaly. Normalise to 0-1 fraud prob.
        iso_score = float(np.clip(1 - (iso_raw + 0.5), 0, 1))

        # Disagreement: XGB says fraud but IF says normal (or vice versa)
        xgb_fraud = xgb_score >= 0.5
        iso_fraud  = iso_score >= 0.5
        disagreement = xgb_fraud != iso_fraud

        return xgb_score, iso_score, disagreement

    # ── SHAP values ───────────────────────────────────────────────────────────

    def _get_shap_values(self, features: Dict[str, float]) -> List[Dict]:
        """Return top 5 SHAP feature contributions for this prediction."""
        try:
            explainer = _get_shap_explainer()
            if explainer is None:
                return []

            feat_names = _feat_names or []
            vector     = np.array([[features.get(f, 0.0) for f in feat_names]])
            shap_vals  = explainer.shap_values(vector)

            # For binary XGBoost, shap_values returns array of shape (1, n_features)
            if hasattr(shap_vals, '__len__') and len(shap_vals) == 2:
                vals = shap_vals[1][0]  # fraud class
            else:
                vals = shap_vals[0] if len(shap_vals.shape) > 1 else shap_vals

            contributions = [
                {"feature": feat_names[i], "value": round(float(vals[i]), 4)}
                for i in range(len(feat_names))
            ]
            # Sort by absolute value, return top 5
            contributions.sort(key=lambda x: abs(x["value"]), reverse=True)
            return contributions[:5]

        except Exception as e:
            logger.warning(f"SHAP calculation failed: {e}")
            return []

    # ── Fallback rule-based scorer ────────────────────────────────────────────

    def _rule_based_score(self, features: Dict[str, float]) -> float:
        score  = 0.0
        score += features.get("balance_drain", 0) * 0.30
        score += features.get("near_ctr",      0) * 0.20
        score += features.get("is_night",      0) * 0.10
        score += features.get("is_intl",       0) * 0.20
        score += features.get("is_risky_ch",   0) * 0.10
        score += features.get("is_cash_out",   0) * 0.15
        if features.get("amount", 0) > 5_000_000:
            score += 0.10
        elif features.get("amount", 0) > 1_000_000:
            score += 0.05
        return min(score, 1.0)

    @staticmethod
    def _risk_level(prob: float) -> str:
        if prob >= 0.85: return "critical"
        if prob >= 0.65: return "high"
        if prob >= 0.40: return "medium"
        return "low"


# Singleton
fraud_service = FraudPredictionService()
