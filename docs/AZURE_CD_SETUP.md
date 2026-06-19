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

> **Critical — Value vs Secret ID (causes `AADSTS7000215`):**
>
> After you click Add, the table shows two columns:
>
> | Column | Example | Use in JSON? |
> |--------|---------|--------------|
> | **Secret ID** | `a1b2c3d4-e5f6-7890-...` (GUID) | **No** |
> | **Value** | `abc~8Q~longRandomString...` | **Yes** → `clientSecret` |
>
> Copy from the **Value** column only. If you only see Secret ID, the Value is gone — create a **new** secret.

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

> **Portal shows Scope as “This resource”?**  
> That is **normal** if you added the role while on **rg-claims-intelligence** → **Access control (IAM)**.  
> “This resource” means *this resource group* — not the whole subscription.  
> Click the assignment row → **Scope** should show a path ending in `/resourceGroups/rg-claims-intelligence`.  
> **Wrong scope:** if you opened a **Container App** (e.g. `claims-reserve-api`) and assigned IAM there, scope is only that app — remove and re-assign on the **resource group** instead.

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

Both packages must be **Public** so Azure can pull without registry credentials (simplest path):

| Package | GitHub path |
|---------|-------------|
| API | **Packages** → `claims-intelligence` → **Package settings** → **Public** |
| Streamlit | **Packages** → `claims-intelligence-streamlit` → **Package settings** → **Public** |

**Or** keep packages private and add GitHub secrets for CD to configure Azure pull:

| Secret | Value |
|--------|--------|
| `GHCR_TOKEN` | GitHub PAT with `read:packages` |
| `GHCR_USER` | `DeepakGuptaaiml` (optional; defaults in workflow) |

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

### `AADSTS7000215: Invalid client secret provided`

**Cause:** `clientSecret` in GitHub is wrong — usually the **Secret ID** (GUID) was pasted instead of the **Value** (long string starting with letters/numbers, often contains `~`).

**Fix:**

1. Portal → **Microsoft Entra ID** → **App registrations** → `github-claims-intelligence-cd`
2. **Certificates & secrets** → **+ New client secret** → **Add**
3. Copy the **Value** column immediately (not Secret ID)
4. GitHub repo → **Settings** → **Secrets** → **Actions** → edit **`AZURE_CREDENTIALS`**
5. Update only `clientSecret` in the JSON (or replace the whole JSON)
6. Re-run **Deploy to Azure** (Actions → workflow → **Re-run all jobs**)

**Correct JSON shape** (no extra quotes around the whole blob, valid JSON):

```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "abc~8Q~pasteValueColumnHere",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

> **`subscriptionId` must be a GUID** from Portal → **Subscriptions** → **Subscription ID**.  
> Do **not** paste a client secret or any `~` string here — that causes *No subscriptions found*.

### `No subscriptions found for ***`

**Cause:** Login succeeded (secret is valid) but the service principal has **no access** to the subscription in your JSON — usually **wrong `subscriptionId`** or **missing Contributor role** on `rg-claims-intelligence`.

**Fix:**

1. **Get the real subscription ID**
   - Portal → **Subscriptions** → open your subscription
   - Copy **Subscription ID** — must look like `11111111-2222-3333-4444-555555555555` (GUID with dashes)

2. **Confirm IAM on the resource group**
   - Portal → **Resource groups** → **rg-claims-intelligence**
   - **Access control (IAM)** → **Role assignments**
   - You should see **Contributor** for `github-claims-intelligence-cd`
   - If missing: **Add role assignment** → Contributor → select the app → **Review + assign**

3. **Update GitHub secret** — fix `subscriptionId` in `AZURE_CREDENTIALS` JSON (rotate `clientSecret` if it was exposed)

4. Wait **2–5 minutes** for IAM to propagate, then **Re-run** Deploy to Azure

**Optional local test** (Mac Terminal — use new secret, don’t paste in chat):

```bash
az login --service-principal \
  -u "<clientId>" \
  -p "<clientSecret>" \
  --tenant "<tenantId>"
az account list -o table
```

If the table is **empty**, the role assignment is still missing or on the wrong subscription/resource group.

### `Cannot find user or service principal in graph database for '<clientId>'`

**Cause:** Wrong **client ID** (typo), wrong **tenant**, or the **service principal** was never created for the app registration.

**Fix (Portal — no local CLI):**

1. **Copy the exact client ID**
   - **Microsoft Entra ID** → **App registrations** → `github-claims-intelligence-cd` → **Overview**
   - Copy **Application (client) ID** — use every character exactly (easy to mistype one digit)

2. **Confirm the service principal exists**
   - On the same **Overview** page, click **Managed application in local directory** (under the client ID)
   - **Pass:** Opens **Enterprise application** with the same name
   - **Fail / link missing:** Service principal not provisioned — go to step 3

3. **Create the service principal (Azure Cloud Shell in browser)**
   - Portal top bar → **Cloud Shell** (`>_`) → **Bash**
   - Run (paste **your** client ID from step 1):

   ```bash
   az ad sp create --id "<Application-client-ID-from-Overview>"
   ```

4. **Re-assign Contributor on the resource group**
   - **Resource groups** → **rg-claims-intelligence** → **Access control (IAM)**
   - **Add role assignment** → **Contributor** → **Members** → search `github-claims-intelligence-cd`
   - Pick the entry whose **Type** is **Service principal** (not App registration)
   - **Review + assign**

5. Update GitHub **`AZURE_CREDENTIALS`** so `clientId` matches step 1 exactly.

| Issue | Fix |
|-------|-----|
| Deploy workflow skipped | CI must finish **success** on `main` |
| `AADSTS7000215` invalid client secret | Use **Value**, not Secret ID — see above |
| `No subscriptions found` | Fix `subscriptionId` (must be GUID); add **Contributor** on `rg-claims-intelligence` |
| `Cannot find service principal in graph` | Fix client ID typo; run `az ad sp create --id <clientId>` in Cloud Shell; re-assign Contributor |
| `MANIFEST_UNKNOWN` on deploy | Make GHCR packages **Public**, or add `GHCR_TOKEN` secret; confirm SHA tag exists under **Packages** |
| Image pull failed | Make GHCR package public or add `GHCR_TOKEN` + `GHCR_USER` secrets |
| `ResourceNotFound` | Check resource group / app names in `deploy-azure.yml` |
| Deploy runs but old code shows | Confirm deploy workflow ran for the same commit SHA as CI |

### `MANIFEST_UNKNOWN: manifest unknown` on deploy

**Cause:** Azure cannot pull the image tag from GHCR. Even with **public** packages, this happens when:

1. **SHA tag missing** — Deploy used `:550f7ad...` but CI never pushed that tag (common if you **Re-run Deploy** without a fresh CI build)
2. **Package not linked / wrong name** — image must be `ghcr.io/deepakguptaaiml/claims-intelligence`
3. **Still private** — package page says public but pull fails until visibility propagates (~few minutes)

**Fix:**

**A — Verify tag exists (Portal/GitHub UI)**

1. GitHub → **Packages** → **claims-intelligence**
2. Open latest version → check **Tags** include `latest` (and optionally your commit SHA)
3. If SHA tag is missing → trigger a **new** pipeline: push any commit to `main` (don’t only re-run old Deploy)

**B — Deploy uses `:latest` (current workflow)**

CD deploys `ghcr.io/.../claims-intelligence:latest` — same tag that worked in manual Portal deploy. The commit SHA is recorded in the workflow summary for traceability.

**C — Fresh end-to-end run**

```bash
git commit --allow-empty -m "Trigger CI/CD deploy"
git push origin main
```

Wait for **CI** green → **Deploy to Azure** green.

**D — Private packages**

Add `GHCR_TOKEN` (PAT with `read:packages`) — see GHCR section above.

---

## Interview talking point

> *“CI publishes immutable SHA-tagged images to GHCR. CD is a separate GitHub Actions workflow triggered on CI success — it runs `az containerapp update` so Azure pulls the new digest and rolls out a revision without Portal clicks. That’s the missing link between build and production.”*
