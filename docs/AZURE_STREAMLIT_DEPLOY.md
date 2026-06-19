# Azure Deploy — Streamlit UI (Container Apps)

Deploy the **Streamlit** front-end as a **second** Container App. It calls your **already-live API** via the `API_URL` environment variable.

**Prerequisite:** API deployed and healthy (`GET /health` returns OK).

| Component | Image | Port |
|-----------|--------|------|
| API (existing) | `ghcr.io/deepakguptaaiml/claims-intelligence:latest` | 8000 |
| **Streamlit UI (new)** | `ghcr.io/deepakguptaaiml/claims-intelligence-streamlit:latest` | 8501 |

---

## Step 0 — Push code & wait for CI

After merging/pushing Streamlit CI changes, GitHub Actions builds **both** images. Confirm green run, then make the **streamlit** package public:

GitHub → **Packages** → `claims-intelligence-streamlit` → **Public**

---

## Step 1 — Get your API URL

Azure Portal → Container App **`claims-reserve-api`** → **Overview** → **Application Url**

Example: `https://claims-reserve-api.xxxx.eastus.azurecontainerapps.io`

Copy this — you need it for `API_URL` (no trailing slash).

---

## Step 2 — Create Streamlit Container App (Portal)

1. **Create a resource** → **Container Apps**
2. **Basics**
   - Resource group: same as API (e.g. `rg-claims-intelligence`)
   - Container app name: `claims-reserve-ui`
   - Region: same as API
   - Container Apps environment: **Use existing** → `claims-env` (same environment as API)
3. **Container**
   - Image source: Docker Hub or other registries
   - Registry: `ghcr.io`
   - Image: `deepakguptaaiml/claims-intelligence-streamlit`
   - Tag: `latest`
   - CPU / Memory: 0.5 CPU, 1 Gi
4. **Environment variables** (critical)

   | Name | Value |
   |------|--------|
   | `API_URL` | `https://<your-api-fqdn>` |

   Example:
   ```
   API_URL=https://claims-reserve-api.xxxx.eastus.azurecontainerapps.io
   ```

5. **Ingress**
   - Enabled: **Yes**
   - Traffic: **Accepting traffic from anywhere**
   - Target port: **8501**
6. **Health probes** (optional but recommended)
   - Type: HTTP GET
   - Path: `/`
   - Port: **8501**
7. **Create**

---

## Step 3 — Use the UI

Open Streamlit **Application Url** from Overview:

```
https://claims-reserve-ui.xxxx.eastus.azurecontainerapps.io
```

- Sidebar should show **Connected to API** (green)
- Fill form → **Predict Total Reserve**

---

## Architecture on Azure

```
User browser
    ↓
Streamlit Container App (:8501)  —  claims-reserve-ui
    ↓  HTTP (API_URL)
FastAPI Container App (:8000)   —  claims-reserve-api
    ↓
best_reserve_model.pkl
```

Both apps share the same **Container Apps Environment** but run as separate apps with separate URLs.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Sidebar: **API unavailable** | Check `API_URL` env var — must be `https://...` with no trailing `/` |
| Image pull failed | Make `claims-intelligence-streamlit` package **Public** on GitHub |
| CORS / connection errors | API ingress must be **external**; test `curl $API_URL/health` |
| Blank Streamlit page | Check **Log stream** on the UI container app; wait 30s on cold start |

---

## Local Streamlit against Azure API (no UI deploy)

If you only want to demo without deploying Streamlit:

```bash
API_URL=https://<your-api-fqdn> streamlit run streamlit_app.py
```

---

## Interview talking point

> *“I split inference and presentation: FastAPI serves the model with health probes; Streamlit is a separate container that only calls REST endpoints. That keeps the ML service stable while the UI can iterate independently.”*
