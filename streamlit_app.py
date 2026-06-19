"""Streamlit UI for Claims Reserve Forecasting — calls FastAPI backend."""

import os

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


def check_health() -> tuple[bool, str]:
    """Return (ok, detail) for sidebar status."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code} from {API_URL}/health"
        body = response.json()
        if not body.get("model_loaded"):
            return False, f"API up but model not loaded: {body}"
        return True, ""
    except requests.RequestException as exc:
        return False, str(exc)


def apply_sample_to_form(sample: dict) -> None:
    """Push API sample claim values into Streamlit widget session state."""
    for key, value in sample.items():
        if key == "num_previous_claims":
            st.session_state[key] = int(value)
        elif key in ("days_in_hospital", "reported_delay_days") and value is None:
            st.session_state[key] = 0.0
        else:
            st.session_state[key] = value


with st.sidebar:
    st.header("API Status")
    st.caption(f"**API_URL:** `{API_URL}`")
    healthy, health_detail = check_health()
    if healthy:
        st.success("Connected to API")
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
        st.markdown(f"**Error:** {health_detail}")
        if API_URL in ("http://127.0.0.1:8000", "http://api:8000"):
            st.warning(
                "Set **API_URL** to your deployed FastAPI URL (HTTPS, no trailing slash). "
                "Azure: Container App → **claims-reserve-ui** → **Containers** → "
                "**Environment variables** → add `API_URL=https://<your-api-fqdn>` → **Create new revision**."
            )
        else:
            st.info(
                "Verify the API is running: open `{url}/health` in a browser or run "
                "`curl {url}/health`.".format(url=API_URL.rstrip("/"))
            )
        st.stop()

try:
    options = fetch_options()
except requests.RequestException as exc:
    st.error(f"Failed to load form options: {exc}")
    st.stop()

with st.expander("Load sample claim from training data"):
    if st.button("Fill form from random claim", key="load_sample_btn"):
        try:
            response = requests.get(f"{API_URL}/model/sample", timeout=10)
            response.raise_for_status()
            sample = response.json()
        except requests.RequestException as exc:
            st.error(f"Could not load sample claim: {exc}")
        else:
            apply_sample_to_form(sample)
            st.session_state["loaded_sample"] = sample
            st.rerun()

    if sample := st.session_state.get("loaded_sample"):
        st.info("Form filled with a random claim from training data.")
        st.json(sample)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Claimant & Clinical")
    patient_age = st.number_input(
        "Patient age", min_value=18.0, max_value=100.0, value=65.0, key="patient_age"
    )
    diagnosis_code = st.selectbox(
        "Diagnosis code", options["diagnosis_code"], key="diagnosis_code"
    )
    procedure_code = st.selectbox(
        "Procedure code", options["procedure_code"], key="procedure_code"
    )
    injury_severity = st.selectbox(
        "Injury severity", options["injury_severity"], key="injury_severity"
    )
    admission_type = st.selectbox(
        "Admission type", options["admission_type"], key="admission_type"
    )
    days_in_hospital = st.number_input(
        "Days in hospital (leave 0 to impute median)",
        min_value=0.0,
        value=0.0,
        key="days_in_hospital",
    )

with col2:
    st.subheader("Financial & History")
    initial_estimate = st.number_input(
        "Initial estimate ($)", min_value=0.0, value=5000.0, key="initial_estimate"
    )
    num_previous_claims = st.number_input(
        "Previous claims", min_value=0, value=0, step=1, key="num_previous_claims"
    )
    avg_previous_reserve = st.number_input(
        "Avg previous reserve ($)", min_value=0.0, value=0.0, key="avg_previous_reserve"
    )
    reported_delay_days = st.number_input(
        "Reported delay days (0 = impute median)",
        min_value=0.0,
        value=0.0,
        key="reported_delay_days",
    )
    provider_type = st.text_input(
        "Provider type (proc unit)", value="29", key="provider_type"
    )
    state = st.selectbox("State", options["state"], key="state")

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

st.markdown("---")
st.caption(
    "Architecture: Streamlit UI → FastAPI `/predict` → `best_reserve_model.pkl` | "
    "Swagger docs at `/docs` on the API server"
)
