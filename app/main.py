import json
import random
import time

import joblib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from app.config import MODEL_PATH, SAMPLE_CLAIMS_PATH
from app.monitor import check_drift, get_prediction_stats, log_prediction
from app.preprocess import load_preprocess_config, predict_reserve
from app.schemas import (
    ClaimFeatures,
    DriftResponse,
    HealthResponse,
    ModelInfoResponse,
    MonitoringResponse,
    PredictionResponse,
)

artifact: dict = {}


def _load_sample_claims() -> list[dict]:
    if not SAMPLE_CLAIMS_PATH.exists():
        return []
    with open(SAMPLE_CLAIMS_PATH, encoding="utf-8") as f:
        return json.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model artifact not found: {MODEL_PATH}")
    artifact["data"] = joblib.load(MODEL_PATH)
    artifact["config"] = load_preprocess_config()
    yield
    artifact.clear()


app = FastAPI(
    title="Claims Reserve Forecasting API",
    description="Predict total case reserve for workers' compensation claims.",
    version="1.0.0",
    lifespan=lifespan,
)


def _get_artifact() -> dict:
    data = artifact.get("data")
    if data is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return data


@app.get("/health", response_model=HealthResponse)
def health():
    data = artifact.get("data")
    return HealthResponse(
        status="ok" if data else "starting",
        model_loaded=data is not None,
        model_name=data.get("model_name") if data else None,
    )


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info():
    data = _get_artifact()
    return ModelInfoResponse(
        model_name=data["model_name"],
        sampling_strategy=data["sampling_strategy"],
        target=data["target"],
        feature_count=len(data["feature_columns"]),
        metrics_test=data.get("metrics_test", {}),
    )


@app.get("/model/options")
def model_options():
    config = artifact.get("config") or load_preprocess_config()
    return config.get("categorical_options", {})


@app.get("/model/sample", response_model=ClaimFeatures)
def model_sample():
    samples = _load_sample_claims()
    if not samples:
        raise HTTPException(status_code=503, detail="No sample claims available")
    return random.choice(samples)


@app.post("/predict", response_model=PredictionResponse)
def predict(claim: ClaimFeatures):
    start_time = time.time()
    data = _get_artifact()
    try:
        total_reserve = predict_reserve(
            data["model"],
            claim.model_dump(),
            data["feature_columns"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {exc}") from exc

    latency_ms = (time.time() - start_time) * 1000

    log_prediction(
        input_features=claim.model_dump(),
        prediction=total_reserve,
        probability=None,
        latency_ms=latency_ms,
        model_name=data["model_name"],
        model_version="1.0",
    )

    return PredictionResponse(
        total_reserve=round(total_reserve, 2),
        model_name=data["model_name"],
        target=data["target"],
    )


@app.get("/monitor/health", response_model=MonitoringResponse, tags=["Monitoring"])
def monitor_health():
    """
    Real-time prediction statistics and SLO status.
    In production: data would persist in Azure Table Storage.
    """
    return get_prediction_stats()


@app.get("/monitor/drift", response_model=DriftResponse, tags=["Monitoring"])
def monitor_drift():
    """
    Check for prediction and latency drift.
    In production: use Evidently AI + Azure Monitor alerts.
    """
    return check_drift()


@app.get("/monitor/slo", tags=["Monitoring"])
def monitor_slo():
    """Service Level Objectives status."""
    stats = get_prediction_stats()
    latency = stats.get("latency") or {}
    slo = stats.get("slo_status") or {}
    return {
        "slo_definitions": {
            "p95_latency_ms": {
                "target": "< 500ms",
                "current": latency.get("p95_ms", "N/A"),
                "status": "ok" if slo.get("p95_latency_ok", True) else "breached",
            },
            "availability": {
                "target": "99.9%",
                "status": "ok",
            },
            "prediction_drift": {
                "target": "< 20% mean shift",
                "status": "ok",
            },
        },
        "total_predictions_tracked": stats.get("total_predictions", 0),
    }
