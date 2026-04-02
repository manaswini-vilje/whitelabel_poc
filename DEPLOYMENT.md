# Azure App Service Deployment Guide

This project is now white-label aware. Each deployment should be pinned to a single active brand and its own storage/output settings.

## Deployment Model

Recommended approach:

1. Use one shared codebase.
2. Create one App Service per client brand.
3. Set `ACTIVE_BRAND` in that App Service.
4. Give each brand its own blob container, blob prefix, runtime folder, and storage connection string environment variable.

The active brand is selected from:

- `ACTIVE_BRAND=<brand-id>`
- or `BRAND_CONFIG_PATH=<path-to-json>`

On startup, `startup.sh` runs `bootstrap_brand_runtime.py`, which:

- loads the active brand config
- creates brand-specific runtime folders under `runtime/<brand>/`
- rewrites `.streamlit/config.toml` from the selected brand theme

## Prerequisites

1. Azure CLI installed and logged in
2. Azure subscription with appropriate permissions
3. Azure OpenAI and Azure Document Intelligence resources
4. A storage account and container strategy for each brand
5. A brand config file in `brands/<brand-id>.json`

## Step 1: Create a Brand Config

Each brand should define its own storage and allocation defaults. Example:

```json
{
  "brand_id": "acme-demo",
  "app_name": "Acme Logistics",
  "storage": {
    "container_name": "acme-processed-output",
    "blob_prefix": "acme-demo/processed",
    "local_root": "runtime/acme-demo",
    "connection_string_env": "ACME_AZURE_STORAGE_CONNECTION_STRING"
  },
  "allocation": {
    "priority": 3,
    "warehouse_id": "ACME-NORTH",
    "supplier_country": "GB"
  }
}
```

Fastest way to start:

1. Copy `brands/client-template.json`
2. Rename it to `brands/<your-brand-id>.json`
3. Update `brand_id`, client copy, theme colors, storage settings, and allocation defaults

## Step 2: Create Azure App Service

```bash
RESOURCE_GROUP="your-resource-group"
APP_NAME="your-brand-app-name"
LOCATION="eastus"
PLAN_NAME="${APP_NAME}-plan"

az appservice plan create \
  --name $PLAN_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku B1 \
  --is-linux

az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $PLAN_NAME \
  --runtime "PYTHON:3.12"
```

## Step 3: Configure App Settings

Set shared AI settings plus brand-specific deployment settings.

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    ACTIVE_BRAND="acme-demo" \
    AZURE_OPENAI_ENDPOINT="https://your-openai-resource.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="your-openai-key" \
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini" \
    AZURE_OPENAI_API_VERSION="2025-01-01-preview" \
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-doc-intel-resource.cognitiveservices.azure.com/" \
    AZURE_DOCUMENT_INTELLIGENCE_KEY="your-doc-intel-key" \
    ACME_AZURE_STORAGE_CONNECTION_STRING="your-acme-storage-connection-string"
```

Notes:

- The storage env var name must match `storage.connection_string_env` in the active brand config.
- If you prefer one shared env var across brands, keep `connection_string_env` as `AZURE_STORAGE_CONNECTION_STRING`.
- If you deploy with `BRAND_CONFIG_PATH`, make sure the file exists on the deployed filesystem.

## Step 4: Configure Startup Command

```bash
az webapp config set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"
```

Or in Azure Portal:

1. Go to Configuration > General settings
2. Set Startup Command to `startup.sh`

## Step 5: Deploy the Application

### Option 1: Azure CLI local git

```bash
az webapp deployment source config-local-git \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

DEPLOYMENT_URL=$(az webapp deployment source show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query url -o tsv)

git remote add azure $DEPLOYMENT_URL
git push azure main
```

### Option 2: GitHub Actions

```yaml
name: Deploy to Azure App Service

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: azure/webapps-deploy@v3
        with:
          app-name: ${{ secrets.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
```

## Step 6: Verify the Brand Deployment

1. Open `https://<app-name>.azurewebsites.net`
2. Confirm the expected brand title, colors, and copy appear
3. Upload a document
4. Confirm the output lands in the brand-specific blob container/prefix
5. Confirm files are written under `runtime/<brand>/...` on the app instance

## Troubleshooting

### View logs

```bash
az webapp log tail \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### Common issues

1. `Brand config file not found`: verify `ACTIVE_BRAND` matches a file in `brands/`.
2. Storage upload fails: verify the configured `connection_string_env` exists in App Settings.
3. Wrong brand theme appears: confirm `startup.sh` ran and rewrote `.streamlit/config.toml`.
4. Output files overlap across brands: verify each brand has a unique `storage.local_root` and `storage.blob_prefix`.

## Runtime Layout

```text
runtime/
  <brand-id>/
    uploads/
    data/
    outputs/
```

## Security Notes

- Do not commit real secrets to `.env`.
- Use `.env.example` as the safe template for local onboarding.
- Use Azure App Service settings or Azure Key Vault for production secrets.
- Rotate any keys that were previously stored in the repository or shared locally.
