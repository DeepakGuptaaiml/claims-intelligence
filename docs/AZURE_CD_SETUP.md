# Azure CD Setup — Auto-deploy after CI

GitHub Actions **CI** builds and pushes Docker images to GHCR. **CD** (`.github/workflows/deploy-azure.yml`) runs after a green CI on `main` and updates both Azure Container Apps with the **commit SHA** image tag.

```
git push main → CI (test, build, push GHCR) → Deploy to Azure (az containerapp update)
```

No manual “create new revision” in the Portal after this is configured.

---

## One-time setup

### Option A — Azure Portal (click-through)

#### Step 1 — Register the app (service principal)

1. Open [portal.azure.com](https://portal.azure.com)
2. Search **Microsoft Entra ID** (formerly Azure Active Directory)
3. Left menu → **App registrations** → **+ New registration**
4. Fill in:
   - **Name:** `github-claims-intelligence-cd`
   - **Supported account types:** *Accounts in this organizational directory only*
   - **Redirect URI:** leave blank
5. Click **Register**

#### Step 2 — Copy IDs

On the app **Overview** page, copy and save:

| Field | Used as |
|-------|---------|
| **Application (client) ID** | `clientId` |
| **Directory (tenant) ID** | `tenantId` |

#### Step 3 — Create a client secret

1. Left menu → **Certificates & secrets**
2. **Client secrets** → **+ New client secret**
3. Description: `github-actions-cd`
4. Expires: 24 months (or per your org policy)
5. Click **Add**
6. **Copy the secret Value immediately** (you won’t see it again) → this is `clientSecret`

#### Step 4 — Get subscription ID

1. Portal search → **Subscriptions**
2. Open your subscription → copy **Subscription ID** → this is `subscriptionId`

#### Step 5 — Grant Contributor on your resource group

Scope the service principal to **only** `rg-claims-intelligence` (least privilege):

1. Portal search → **Resource groups** → **rg-claims-intelligence**
2. Left menu → **Access control (IAM)**
3. **+ Add** → **Add role assignment**
4. **Role** tab → select **Contributor** → **Next**
5. **Members** tab → **+ Select members**
6. Search `github-claims-intelligence-cd` → select it → **Select** → **Next** → **Review + assign**

Wait ~1 minute for IAM to propagate.

#### Step 6 — Build the GitHub secret JSON

Paste into a text editor and fill in your values:

```json
{
  "clientId": "<Application (client) ID from Step 2>",
  "clientSecret": "<Secret Value from Step 3>",
  "subscriptionId": "<Subscription ID from Step 4>",
  "tenantId": "<Directory (tenant) ID from Step 2>"
}
```

Example (fake values):

```json
{
  "clientId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "clientSecret": "abc~SECRET_VALUE_FROM_PORTAL",
  "subscriptionId": "11111111-2222-3333-4444-555555555555",
  "tenantId": "99999999-8888-7777-6666-555555555555"
}
```

---

### Option B — Azure CLI (faster if you have `az` installed)

Replace `{subscription-id}` with your subscription ID (`az account show --query id -o tsv`):

```bash
az login
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "github-claims-intelligence-cd" \
  --role contributor \
  --scopes "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/rg-claims-intelligence" \
  --sdk-auth
```

Copy the **entire JSON output** (starts with `{ "clientId": ...`).

---

### Add GitHub secret (both options)

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|------|--------|
| `AZURE_CREDENTIALS` | Full JSON from Portal Step 6 or CLI output |

### Confirm Container Apps exist

CD **updates** existing apps; it does not create them. Bootstrap once via [AZURE_API_DEPLOY.md](AZURE_API_DEPLOY.md) and [AZURE_STREAMLIT_DEPLOY.md](AZURE_STREAMLIT_DEPLOY.md) if needed.

Default names (edit in `deploy-azure.yml` if yours differ):

| App | Name |
|-----|------|
| API | `claims-reserve-api` |
| Streamlit | `claims-reserve-ui` |
| Resource group | `rg-claims-intelligence` |

### GHCR packages public

Both `claims-intelligence` and `claims-intelligence-streamlit` packages must be **Public** so Azure can pull without registry credentials.

---

## What happens on each push to `main`

1. **CI** runs tests, builds API + Streamlit images, pushes to GHCR with tags `latest` and `{git-sha}`.
2. **Deploy to Azure** triggers when CI succeeds.
3. `az containerapp update` sets each app to `ghcr.io/deepakguptaaiml/claims-intelligence:{sha}` (immutable tag).
4. Azure creates a **new revision automatically** and routes traffic to it.
5. Workflow curls `/health` and `/model/sample` on the live API URL.

Streamlit env vars (e.g. `API_URL`) are **unchanged** across image updates.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Deploy workflow skipped | CI must finish **success** on `main` |
| `AZURE_CREDENTIALS` auth failed | Re-create service principal; paste full JSON secret |
| Image pull failed | Make GHCR package public |
| `ResourceNotFound` | Check resource group / app names in `deploy-azure.yml` |
| Deploy runs but old code shows | Confirm deploy workflow ran for the same commit SHA as CI |

---

## Interview talking point

> *“CI publishes immutable SHA-tagged images to GHCR. CD is a separate GitHub Actions workflow triggered on CI success — it runs `az containerapp update` so Azure pulls the new digest and rolls out a revision without Portal clicks. That’s the missing link between build and production.”*
