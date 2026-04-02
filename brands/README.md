# Brand Configuration

This directory contains white-label brand definitions for the app.

## How it works

- `default.json` is the shared baseline config.
- Any other brand file only needs to override the values that differ.
- Set `ACTIVE_BRAND=<brand-id>` to load `brands/<brand-id>.json`.
- Set `BRAND_CONFIG_PATH=<absolute-or-relative-path>` to load a specific file instead.

## Current files

- `default.json`: Base configuration used by all brands
- `acme-demo.json`: Example override showing how a client-specific brand can customize the app
- `client-template.json`: Copy-ready scaffold for a new real client brand

## Recommended workflow

1. Copy `client-template.json` to `your-client-id.json`
2. Change `brand_id`, UI text, colors, storage settings, and allocation defaults
3. Set `ACTIVE_BRAND=your-client-id`
4. Add the storage secret using the env var named in `storage.connection_string_env`

## UI fields

The `ui` section controls Streamlit copy such as:

- page title and icon
- hero title and description
- uploader label/help
- upload, processing, success, error, and output text

The `theme` section controls runtime colors and fonts applied by the app.

## Optional assets

You can also include:

- `assets.logo_path`: relative path to a local logo file in the repo
- `assets.logo_url`: remote logo URL if you prefer a hosted asset

If provided, the app header will render the logo above the brand hero section.
