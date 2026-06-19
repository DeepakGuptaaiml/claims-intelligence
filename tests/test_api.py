import joblib
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.preprocess import predict_reserve


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_payload():
    return {
        "patient_age": 55.0,
        "diagnosis_code": "SPRAIN",
        "procedure_code": "KNEE",
        "admission_type": "MO",
        "days_in_hospital": 120.0,
        "provider_type": "29",
        "injury_severity": "STRAIN",
        "num_previous_claims": 1,
        "avg_previous_reserve": 5000.0,
        "initial_estimate": 3500.0,
        "reported_delay_days": 45.0,
        "state": "PA",
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_model_info(client):
    response = client.get("/model/info")
    assert response.status_code == 200
    body = response.json()
    assert body["target"] == "total_reserve"
    assert body["feature_count"] > 0


def test_predict(client, sample_payload):
    response = client.post("/predict", json=sample_payload)
    assert response.status_code == 200
    body = response.json()
    assert "total_reserve" in body
    assert body["total_reserve"] >= 0


def test_model_sample(client):
    response = client.get("/model/sample")
    assert response.status_code == 200
    body = response.json()
    assert body["state"]
    assert body["initial_estimate"] > 0
    predict_response = client.post("/predict", json=body)
    assert predict_response.status_code == 200


def test_predict_preprocess_unit(sample_payload):
    artifact = joblib.load("models/best_reserve_model.pkl")
    reserve = predict_reserve(
        artifact["model"], sample_payload, artifact["feature_columns"]
    )
    assert reserve >= 0
