# White-Label Runbook

This repo is now white-label ready.

## What is configurable

- brand name and UI copy
- theme colors and font
- optional logo asset
- blob container and blob prefix
- runtime storage folder
- storage connection string env var name
- allocation defaults such as warehouse, country, and priority
- document extraction prompt overrides

## Add a New Client

1. Copy `brands/client-template.json` to `brands/<client-id>.json`
2. Update the brand fields
3. Set `ACTIVE_BRAND=<client-id>` locally or in Azure App Service
4. Add the storage secret required by `storage.connection_string_env`
5. Run `venv\Scripts\python.exe validate_white_label.py`
6. Run `venv\Scripts\python.exe bootstrap_brand_runtime.py`
7. Start the app and test one document end to end

## Useful Commands

Validate all brands:

```powershell
venv\Scripts\python.exe validate_white_label.py
```

Bootstrap the active brand locally:

```powershell
$env:ACTIVE_BRAND="default"
venv\Scripts\python.exe bootstrap_brand_runtime.py
```

Run the Streamlit app:

```powershell
$env:ACTIVE_BRAND="default"
venv\Scripts\python.exe -m streamlit run app.py
```

## Production Checklist

- rotate any secrets previously stored in `.env`
- keep production secrets in App Service settings or Key Vault
- use one App Service per brand unless you have a clear multi-tenant routing plan
- verify blob container, blob prefix, and runtime folder are unique per brand
- validate every new brand config before deployment
