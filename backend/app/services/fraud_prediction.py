"""Production V2.2 behavioural fraud inference with strict-prior history."""
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)
MODEL_VERSION = "xgboost-isoforest-v2.2-behavioral"
V2_2_FEATURES = ["log_amount", "is_night", "is_cash_out", "is_transfer", "large_amount", "origin_txn_count", "destination_txn_count", "origin_prev_avg_amount", "destination_prev_avg_amount", "origin_amount_ratio", "destination_amount_ratio", "time_since_prev_origin", "time_since_prev_destination", "origin_type_frequency", "destination_type_frequency"]

try:
    _MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
    _xgb_model = joblib.load(os.path.join(_MODEL_DIR, "xgboost_model.joblib"))
    _iso_model = joblib.load(os.path.join(_MODEL_DIR, "isolation_forest.joblib"))
    _feat_names = list(joblib.load(os.path.join(_MODEL_DIR, "feature_names.joblib")))
    if _feat_names != V2_2_FEATURES:
        raise RuntimeError(f"Expected V2.2 feature order, got {_feat_names!r}")
    logger.info("Loaded %s from %s", MODEL_VERSION, _MODEL_DIR)
except Exception as exc:
    _xgb_model = _iso_model = None
    _feat_names = V2_2_FEATURES
    logger.exception("V2.2 model artifacts unavailable: %s", exc)


def _transaction_type(txn: dict) -> str:
    return str(txn.get("paySimType", txn.get("type", "PAYMENT"))).upper()


def _time_marker(txn: dict) -> float:
    if txn.get("step") is not None:
        return float(txn["step"])
    value = txn.get("timestamp")
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp() / 3600.0


class FraudPredictionService:
    """Scores V2.2 from repository-provided prior origin/destination summaries."""
    def extract_features(self, txn: dict, history: Optional[dict] = None) -> Dict[str, float]:
        amount = max(float(txn.get("amount", 0.0)), 0.0)
        transaction_type = _transaction_type(txn)
        hour = int(txn.get("hour", int(_time_marker(txn)) % 24)) % 24
        history = history or txn.get("_behavioral_history", {}) or {}
        marker = _time_marker(txn)

        def role_values(role: dict):
            count = max(int(role.get("count", 0)), 0)
            average = max(float(role.get("average_amount", 0.0)), 0.0)
            previous = role.get("last_marker")
            elapsed = 0.0 if previous is None else max(marker - float(previous), 0.0)
            ratio = 1.0 if count == 0 else min(amount / max(average, 1.0), 100.0)
            frequency = max(float(role.get("type_count", 0)), 0.0) / count if count else 0.0
            return math.log1p(count), math.log1p(average), ratio, math.log1p(min(elapsed, 10_000.0)), frequency

        oc, oa, oratio, ot, of = role_values(history.get("origin", {}))
        dc, da, dratio, dt, dfreq = role_values(history.get("destination", {}))
        features = {"log_amount": math.log1p(amount), "is_night": float(hour in {0, 1, 2, 3, 4, 5, 23}), "is_cash_out": float(transaction_type == "CASH_OUT"), "is_transfer": float(transaction_type == "TRANSFER"), "large_amount": float(amount > 1_000_000), "origin_txn_count": oc, "destination_txn_count": dc, "origin_prev_avg_amount": oa, "destination_prev_avg_amount": da, "origin_amount_ratio": oratio, "destination_amount_ratio": dratio, "time_since_prev_origin": ot, "time_since_prev_destination": dt, "origin_type_frequency": of, "destination_type_frequency": dfreq}
        if not all(math.isfinite(value) for value in features.values()):
            raise ValueError("V2.2 feature construction produced a non-finite value")
        return {name: float(features[name]) for name in _feat_names}

    async def score_transaction_with_history(self, txn: dict, transaction_repo) -> Dict[str, Any]:
        return self.score_transaction(txn, await transaction_repo.get_v2_2_history(txn))

    def score_transaction(self, txn: dict, history: Optional[dict] = None) -> Dict[str, Any]:
        features = self.extract_features(txn, history)
        if _xgb_model is None or _iso_model is None:
            raise RuntimeError("V2.2 production model artifacts are not loaded")
        xgb_score, iso_score, disagreement = self._ensemble_score(features)
        probability = 0.7 * xgb_score + 0.3 * iso_score
        return {"transaction_id": txn.get("id", txn.get("_id", "unknown")), "fraud_probability": round(probability, 4), "xgb_score": round(xgb_score, 4), "iso_score": round(iso_score, 4), "disagreement_flag": disagreement, "is_fraud": probability >= settings.FRAUD_THRESHOLD, "risk_level": self._risk_level(probability), "features": features, "shap_values": [], "model_version": MODEL_VERSION, "confidence": round(probability * 100, 1)}

    async def score_batch_with_history(self, transactions: List[dict], transaction_repo) -> List[Dict[str, Any]]:
        start = time.monotonic()
        results = [await self.score_transaction_with_history(txn, transaction_repo) for txn in transactions]
        logger.info("[Batch] %d V2.2 transactions scored in %.1fms", len(transactions), (time.monotonic() - start) * 1000)
        return results

    def score_batch(self, transactions: List[dict]) -> List[Dict[str, Any]]:
        return [self.score_transaction(txn) for txn in transactions]

    def _ensemble_score(self, features: Dict[str, float]):
        vector = np.asarray([[features[name] for name in _feat_names]], dtype=np.float32)
        xgb_score = float(_xgb_model.predict_proba(vector)[0, 1])
        iso_score = float(np.clip(0.5 - _iso_model.decision_function(vector)[0], 0, 1))
        return xgb_score, iso_score, (xgb_score >= 0.5) != (iso_score >= 0.5)

    @staticmethod
    def _risk_level(probability: float) -> str:
        if probability >= 0.85: return "critical"
        if probability >= settings.FRAUD_THRESHOLD: return "high"
        if probability >= 0.40: return "medium"
        return "low"


fraud_service = FraudPredictionService()
