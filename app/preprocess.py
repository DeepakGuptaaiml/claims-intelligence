import json

import numpy as np
import pandas as pd

from app.config import PREPROCESS_CONFIG_PATH

MODEL_FEATURES = [
    "patient_age",
    "diagnosis_code",
    "procedure_code",
    "admission_type",
    "days_in_hospital",
    "provider_type",
    "injury_severity",
    "num_previous_claims",
    "avg_previous_reserve",
    "initial_estimate",
    "reported_delay_days",
    "state",
]

CAT_IMPUTE_COLS = ["diagnosis_code", "procedure_code", "injury_severity"]
NUM_IMPUTE_COLS = ["days_in_hospital", "reported_delay_days", "patient_age"]


def load_preprocess_config() -> dict:
    with open(PREPROCESS_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def prepare_features(payload: dict, feature_columns: list[str]) -> pd.DataFrame:
    """Transform raw API input into model-ready encoded features."""
    config = load_preprocess_config()
    row = {feature: payload.get(feature) for feature in MODEL_FEATURES}
    df = pd.DataFrame([row])

    for col in CAT_IMPUTE_COLS:
        df[col] = df[col].astype(str).replace({"nan": None, "None": None})
        df[col] = df[col].fillna(config["cat_impute"][col])

    for col in NUM_IMPUTE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(config["num_impute"][col])

    df["provider_type"] = df["provider_type"].astype(str)
    df["admission_type"] = df["admission_type"].astype(str)
    df["state"] = df["state"].astype(str).str.upper()
    df["num_previous_claims"] = df["num_previous_claims"].fillna(0).astype(float)
    df["avg_previous_reserve"] = df["avg_previous_reserve"].fillna(0).astype(float)
    df["initial_estimate"] = df["initial_estimate"].astype(float)

    encoded = pd.get_dummies(df[MODEL_FEATURES], drop_first=True)
    encoded = encoded.reindex(columns=feature_columns, fill_value=0)
    return encoded.astype(float)


def predict_reserve(model, payload: dict, feature_columns: list[str]) -> float:
    features = prepare_features(payload, feature_columns)
    prediction = float(model.predict(features)[0])
    return max(prediction, 0.0)
