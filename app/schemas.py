from typing import Any, Optional

from pydantic import BaseModel, Field


class ClaimFeatures(BaseModel):
    patient_age: float = Field(..., ge=0, le=120, description="Claimant age at date of event")
    diagnosis_code: str = Field(..., description="Injury/diagnosis category")
    procedure_code: str = Field(..., description="Body part / procedure category")
    admission_type: str = Field(..., description="Claim admission type (MO, OT, IO)")
    days_in_hospital: float | None = Field(None, ge=0, description="Days from claim open to close")
    provider_type: str = Field(..., description="Processing unit ID")
    injury_severity: str = Field(..., description="Injury mechanism")
    num_previous_claims: int = Field(0, ge=0, description="Prior claims for same claimant")
    avg_previous_reserve: float = Field(0.0, ge=0, description="Average reserve on prior claims")
    initial_estimate: float = Field(..., ge=0, description="Initial payment estimate")
    reported_delay_days: float | None = Field(None, ge=0, description="Days to CMS reporting")
    state: str = Field(..., min_length=2, max_length=2, description="US state code")


class PredictionResponse(BaseModel):
    total_reserve: float
    model_name: str
    target: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str | None = None


class ModelInfoResponse(BaseModel):
    model_name: str
    sampling_strategy: str
    target: str
    feature_count: int
    metrics_test: dict


class PredictionLogEntry(BaseModel):
    timestamp: str
    model_name: str
    model_version: str
    prediction: Any
    probability: Optional[float]
    latency_ms: float


class LatencyStats(BaseModel):
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float


class SLOStatus(BaseModel):
    p95_latency_ok: bool
    p95_latency_ms: float
    slo_threshold_ms: float


class MonitoringResponse(BaseModel):
    total_predictions: int
    first_prediction: Optional[str] = None
    last_prediction: Optional[str] = None
    latency: Optional[LatencyStats] = None
    prediction_distribution: Optional[dict] = None
    slo_status: Optional[SLOStatus] = None
    message: Optional[str] = None


class DriftAlert(BaseModel):
    type: str
    severity: str
    message: str


class DriftResponse(BaseModel):
    drift_detected: bool
    status: str
    alerts: list[DriftAlert] = []
    predictions_analyzed: int
    recommendation: str
    message: Optional[str] = None
