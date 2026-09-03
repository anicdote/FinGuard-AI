"""Structured JSON logging with prediction audit trail."""

import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class PredictionLogger:
    """Dedicated logger for ML prediction audit trail."""

    def __init__(self):
        self.logger = logging.getLogger("finguard.predictions")

    def log_prediction(
        self,
        transaction_id: str,
        fraud_probability: float,
        is_fraud: bool,
        features: Dict[str, Any],
        model_version: str = "v1.0",
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "prediction",
            "transaction_id": transaction_id,
            "fraud_probability": round(fraud_probability, 4),
            "is_fraud": is_fraud,
            "model_version": model_version,
            "features": features,
        }
        self.logger.info(json.dumps(entry))

    def log_batch_analysis(self, batch_size: int, fraud_count: int, duration_ms: float):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "batch_analysis",
            "batch_size": batch_size,
            "fraud_detected": fraud_count,
            "duration_ms": round(duration_ms, 2),
        }
        self.logger.info(json.dumps(entry))

    def log_case_created(self, case_id: str, account_id: str, risk_score: float):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "case_created",
            "case_id": case_id,
            "account_id": account_id,
            "risk_score": round(risk_score, 2),
        }
        self.logger.info(json.dumps(entry))


prediction_logger = PredictionLogger()
