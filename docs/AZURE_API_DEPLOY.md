# Azure Deploy — API Only (Container Apps)

Deploy the **FastAPI** reserve forecasting API to Azure Container Apps using the Docker image built by GitHub Actions.

**Image:** `ghcr.io/deepakguptaaiml/claims-intelligence:latest`  
**Port:** `8000`  
**Health:** `GET /health`  
**Streamlit UI:** deploy separately — see [AZURE_STREAMLIT_DEPLOY.md](AZURE_STREAMLIT_DEPLOY.md)

---

## Prerequisites

- [Azure subscription](https://azure.microsoft.com/free/) (free tier works for demo)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli): `brew install azure-cli`
- GitHub Actions **green** (image published to GHCR)
- GHCR package **Public** (recommended for simplest pull):
  - GitHub → repo → **Packages** → `claims-intelligence` → **Package settings** → **Change visibility** → **Public**

---

## Option A — Azure Portal (click-through)

1. Go to [portal.azure.com](https://portal.azure.com) → **Create a resource** → **Container Apps**
2. **Basics**
   - Resource group: `rg-claims-intelligence` (new)
   - Container app name: `claims-reserve-api`
   - Region: e.g. **East US**
3. **Container Apps environment** → Create new (e.g. `claims-env`)
4. **Container**
   - Image source: **Docker Hub or other registries**
   - Image type: **Public** (if GHCR package is public)
   - Registry: `ghcr.io`
   - Image: `deepakguptaaiml/claims-intelligence`
   - Tag: `latest`
   - CPU / Memory: 0.5 CPU, 1 Gi (enough for demo)
5. **Ingress**
   - Enabled: **Yes**
   - Ingress traffic: **Accepting traffic from anywhere**
   - Target port: **8000**
6. **Health probes** (under Containers → Health probes)
   - Type: **HTTP GET**
   - Path: `/health`
   - Port: **8000**
7. **Create** → wait ~2–3 minutes

### Verify

```bash
curl https://<your-app-fqdn>/health
```

Browser: `https://<your-app-fqdn>/docs`

---

## Option B — Azure CLI (script)

From the project root:

```bash
# 1. Login
az login

# 2. Set variables (edit location if needed)
export RESOURCE_GROUP=rg-claims-intelligence
export LOCATION=eastus
export ENV_NAME=claims-env
export APP_NAME=claims-reserve-api
export IMAGE=ghcr.io/deepakguptaaiml/claims-intelligence:latest

# 3. Run deploy script
chmod +x scripts/deploy-azure-api.sh
./scripts/deploy-azure-api.sh
```

The script prints your **public API URL** when done.

---

## Private GHCR package (optional)

If the package stays **private**, create a GitHub PAT with **`read:packages`** and pass registry credentials when creating the container app:

```bash
export GHCR_USER=DeepakGuptaaiml
export GHCR_TOKEN=<your-github-pat-with-read-packages>

az containerapp create \
  ... \
  --registry-server ghcr.io \
  --registry-username "$GHCR_USER" \
  --registry-password "$GHCR_TOKEN"
```

Or add credentials in Portal under **Containers** → **Registry**.

---

## Test the live API

Replace `<FQDN>` with your Container App URL (e.g. `claims-reserve-api.xxxx.eastus.azurecontainerapps.io`):

```bash
# Health
curl https://<FQDN>/health

# Predict
curl -X POST https://<FQDN>/predict \
  -H "Content-Type: application/json" \
  -d '{
    "patient_age": 55,
    "diagnosis_code": "SPRAIN",
    "procedure_code": "KNEE",
    "admission_type": "MO",
    "days_in_hospital": 120,
    "provider_type": "29",
    "injury_severity": "STRAIN",
    "num_previous_claims": 1,
    "avg_previous_reserve": 5000,
    "initial_estimate": 3500,
    "reported_delay_days": 45,
    "state": "PA"
  }'
```

---

## SLO / monitoring (interview talking points)

| SLO | Target (demo) |
|-----|----------------|
| Availability | 99.5% (health probe on `/health`) |
| p95 latency | < 500 ms for `/predict` |
| Error rate | < 1% 5xx |

Optional next steps:
- Enable **Application Insights** on the Container App
- Alert on failed health probes
- Log prediction latency (custom metrics)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Image pull failed | Make GHCR package **Public** or add registry credentials |
| 502 / app not ready | Check logs: Portal → Container App → **Log stream**; model load takes ~10s on cold start |
| Wrong port | Target port must be **8000** (uvicorn in Dockerfile) |
| Health probe failing | Path must be `/health`, not `/` |

---

## What we are NOT deploying (v1)

- **Streamlit UI** — run locally with `API_URL=https://<FQDN>` or deploy as a second Container App later
- **React UI** — future phase

---

## Architecture on Azure

```
Internet → Azure Container Apps (FastAPI :8000) → best_reserve_model.pkl
                ↓
         GET /health  (probe)
         POST /predict
         GET /docs    (Swagger)
```
