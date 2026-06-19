# Claims Reserve Forecasting

ML pipeline and production API for predicting workers' compensation **total case reserve** from claim intake features.

## Architecture

```
Claims Data → Notebook (train/tune) → best_reserve_model.pkl
                                              ↓
Streamlit UI ──HTTP──→ FastAPI /predict ──→ XGBoost inference
```

## Quick start (local)

```bash
cd claims-intelligence
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — UI
streamlit run streamlit_app.py
```

| Service | URL |
|---------|-----|
| API docs | http://127.0.0.1:8000/docs |
| Streamlit | http://localhost:8501 |

## Docker (build on GitHub — no local Docker required)

Push to `main` and **GitHub Actions** will:
1. Run tests
2. Build the Docker image on GitHub's servers
3. Push to **GitHub Container Registry (GHCR)**:

```
ghcr.io/deepakguptaaiml/claims-intelligence:latest
ghcr.io/deepakguptaaiml/claims-intelligence:<commit-sha>
```

After the first push, make the package **public** (if needed):
GitHub → your repo → **Packages** → package settings → **Change visibility** → Public

### Local Docker (optional)

```bash
docker build -t claims-reserve-api .
docker run -p 8000:8000 claims-reserve-api
docker compose up --build
```

## Tests

```bash
pytest tests/ -v
```

## Deploy to Azure — API only

**Full guide:** [docs/AZURE_API_DEPLOY.md](docs/AZURE_API_DEPLOY.md)

Quick summary:
1. Make GHCR package **Public** (GitHub → Packages → claims-intelligence)
2. `az login`
3. `./scripts/deploy-azure-api.sh`
4. Open `https://<your-app>.azurecontainerapps.io/docs`

| Setting | Value |
|---------|--------|
| Image | `ghcr.io/deepakguptaaiml/claims-intelligence:latest` |
| Port | `8000` |
| Health probe | `GET /health` |

Streamlit stays **local** for v1; **Azure Streamlit guide:** [docs/AZURE_STREAMLIT_DEPLOY.md](docs/AZURE_STREAMLIT_DEPLOY.md)

| Image | Purpose |
|-------|---------|
| `ghcr.io/deepakguptaaiml/claims-intelligence:latest` | API |
| `ghcr.io/deepakguptaaiml/claims-intelligence-streamlit:latest` | Streamlit UI |

## Model metrics (test set)

| Metric | Value |
|--------|-------|
| RMSE | ~1837 |
| MAE | ~785 |
| R² | ~0.29 |
| Within 10% of actual | ~10% |

## Project layout

```
app/           FastAPI service + preprocessing
models/        best_reserve_model.pkl, preprocess_config.json
streamlit_app.py   Demo UI
tests/         API integration tests
Dockerfile     Production API container
```

## Interview highlights

- End-to-end: EDA → feature engineering → 6-model comparison → hyperparameter tuning → `.pkl` artifact
- Production: FastAPI, Pydantic validation, Docker, health checks, CI, Azure-ready
- Business metric: % predictions within 10% of actual reserve
