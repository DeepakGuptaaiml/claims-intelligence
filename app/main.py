import joblib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from app.config import MODEL_PATH
from app.preprocess import load_preprocess_config, predict_reserve
from app.schemas import (
    ClaimFeatures,
    HealthResponse,
    ModelInfoResponse,
    PredictionResponse,
)

artifact: dict = {}


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


@app.post("/predict", response_model=PredictionResponse)
def predict(claim: ClaimFeatures):
    data = _get_artifact()
    try:
        total_reserve = predict_reserve(
            data["model"],
            claim.model_dump(),
            data["feature_columns"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {exc}") from exc

    return PredictionResponse(
        total_reserve=round(total_reserve, 2),
        model_name=data["model_name"],
        target=data["target"],
    )
