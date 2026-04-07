#!/usr/bin/env python3
"""Prepare brand-specific runtime directories and Streamlit config."""

import sys
from pathlib import Path


def build_streamlit_config(brand_config) -> str:
    """Render a Streamlit config.toml string from the active brand config."""
    theme = brand_config.theme
    return "\n".join(
        [
            "[server]",
            "port = 8000",
            'address = "0.0.0.0"',
            "headless = true",
            "enableCORS = false",
            "enableXsrfProtection = false",
            'baseUrlPath = ""',
            'fileWatcherType = "none"',
            "runOnSave = false",
            "allowRunOnSave = false",
            "",
            "[browser]",
            "gatherUsageStats = false",
            'serverAddress = ""',
            "serverPort = 8000",
            "",
            "[runner]",
            "fastReruns = false",
            "magicEnabled = true",
            "installTracer = false",
            "fixMatplotlib = true",
            "",
            "[theme]",
            f'primaryColor = "{theme.primary_color}"',
            f'backgroundColor = "{theme.background_color}"',
            f'secondaryBackgroundColor = "{theme.secondary_background_color}"',
            f'textColor = "{theme.text_color}"',
            f'font = "{theme.font}"',
            "",
        ]
    )


def bootstrap_brand_runtime(project_root: Path) -> int:
    """Create brand-specific runtime folders and a matching Streamlit config."""
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from white_label import load_brand_config

    brand_config = load_brand_config(project_root=project_root)
    runtime_root = brand_config.runtime_root(project_root)

    for directory in (
        runtime_root,
        brand_config.uploads_dir(project_root),
        brand_config.data_dir(project_root),
        brand_config.outputs_dir(project_root),
        project_root / ".streamlit",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    config_path = project_root / ".streamlit" / "config.toml"
    config_path.write_text(build_streamlit_config(brand_config), encoding="utf-8")

    # Used by api/streamlit_proxy.py to rewrite the shell HTML <title> (defaults to "Streamlit"
    # before the app connects) so the browser tab shows the same name as st.set_page_config.
    (project_root / ".streamlit_page_title").write_text(
        brand_config.ui.page_title, encoding="utf-8"
    )

    print(f"Bootstrapped brand: {brand_config.brand_id}")
    print(f"Runtime root: {runtime_root}")
    print(f"Streamlit config: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(bootstrap_brand_runtime(Path(__file__).resolve().parent))
