"""Streamlit UI for Claims Reserve Forecasting — calls FastAPI backend."""

import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Claims Reserve Forecaster",
    page_icon="🏥",
    layout="wide",
)

st.title("Claims Reserve Forecaster")
st.caption("Predict total case reserve using the trained XGBoost model via FastAPI")


@st.cache_data(ttl=300)
def fetch_options() -> dict:
    response = requests.get(f"{API_URL}/model/options", timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300)
def fetch_model_info() -> dict:
    response = requests.get(f"{API_URL}/model/info", timeout=10)
    response.raise_for_status()
    return response.json()


def check_health() -> bool:
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200 and response.json().get("model_loaded")
    except requests.RequestException:
        return False


with st.sidebar:
    st.header("API Status")
    if check_health():
        st.success(f"Connected to {API_URL}")
        try:
            info = fetch_model_info()
            st.markdown(f"**Model:** {info['model_name']}")
            st.markdown(f"**Target:** `{info['target']}`")
            metrics = info.get("metrics_test", {})
            if metrics:
                st.markdown("**Test metrics**")
                st.json(metrics)
        except requests.RequestException as exc:
            st.warning(f"Could not load model info: {exc}")
    else:
        st.error("API unavailable")
        st.code(
            "uvicorn app.main:app --reload --host 127.0.0.1 --port 8000",
            language="bash",
        )
        st.stop()

try:
    options = fetch_options()
except requests.RequestException as exc:
    st.error(f"Failed to load form options: {exc}")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Claimant & Clinical")
    patient_age = st.number_input("Patient age", min_value=18.0, max_value=100.0, value=65.0)
    diagnosis_code = st.selectbox("Diagnosis code", options["diagnosis_code"])
    procedure_code = st.selectbox("Procedure code", options["procedure_code"])
    injury_severity = st.selectbox("Injury severity", options["injury_severity"])
    admission_type = st.selectbox("Admission type", options["admission_type"])
    days_in_hospital = st.number_input(
        "Days in hospital (leave 0 to impute median)", min_value=0.0, value=0.0
    )

with col2:
    st.subheader("Financial & History")
    initial_estimate = st.number_input("Initial estimate ($)", min_value=0.0, value=5000.0)
    num_previous_claims = st.number_input("Previous claims", min_value=0, value=0, step=1)
    avg_previous_reserve = st.number_input("Avg previous reserve ($)", min_value=0.0, value=0.0)
    reported_delay_days = st.number_input(
        "Reported delay days (0 = impute median)", min_value=0.0, value=0.0
    )
    provider_type = st.text_input("Provider type (proc unit)", value="29")
    state = st.selectbox("State", options["state"])

payload = {
    "patient_age": patient_age,
    "diagnosis_code": diagnosis_code,
    "procedure_code": procedure_code,
    "admission_type": admission_type,
    "days_in_hospital": None if days_in_hospital == 0 else days_in_hospital,
    "provider_type": provider_type,
    "injury_severity": injury_severity,
    "num_previous_claims": int(num_previous_claims),
    "avg_previous_reserve": avg_previous_reserve,
    "initial_estimate": initial_estimate,
    "reported_delay_days": None if reported_delay_days == 0 else reported_delay_days,
    "state": state,
}

st.divider()

if st.button("Predict Total Reserve", type="primary", use_container_width=True):
    with st.spinner("Calling prediction API..."):
        try:
            response = requests.post(f"{API_URL}/predict", json=payload, timeout=15)
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            st.error(f"Prediction failed: {exc}")
            if hasattr(exc, "response") and exc.response is not None:
                st.code(exc.response.text)
            st.stop()

    st.success(f"Predicted total reserve: **${result['total_reserve']:,.2f}**")

    m1, m2, m3 = st.columns(3)
    m1.metric("Predicted Reserve", f"${result['total_reserve']:,.2f}")
    m2.metric("Model", result.get("model_name", "—"))
    m3.metric("Initial Estimate", f"${initial_estimate:,.2f}")

    st.subheader("Request payload")
    st.json(payload)

with st.expander("Load sample claim from training data"):
    sample_file = "data/claims_data.csv"
    if st.button("Fill form from random claim"):
        df = pd.read_csv(sample_file)
        row = df.sample(1, random_state=42).iloc[0]
        st.session_state["sample"] = row
        st.info("Re-run the app sections above or use values below:")
        st.dataframe(row)

st.markdown("---")
st.caption(
    "Architecture: Streamlit UI → FastAPI `/predict` → `best_reserve_model.pkl` | "
    "Swagger docs at `/docs` on the API server"
)
