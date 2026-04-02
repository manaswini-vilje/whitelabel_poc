"""Centralized white-label configuration loading and validation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_BRAND_ID = "default"


class BrandConfigError(ValueError):
    """Raised when a brand configuration file is missing or invalid."""


@dataclass(frozen=True)
class UIConfig:
    page_title: str
    page_icon: str
    title: str
    description: str
    display_brand_name: str
    display_warehouse_label: str
    display_blob_target_label: str
    display_runtime_label: str
    upload_label: str
    upload_help: str
    file_uploaded_message: str
    process_button_label: str
    processing_status_label: str
    upload_step_label: str
    convert_step_label: str
    save_step_label: str
    blob_upload_step_label: str
    all_steps_completed_message: str
    error_message_prefix: str
    output_heading: str
    output_url_label: str
    output_link_label: str
    success_message: str
    output_info: str


@dataclass(frozen=True)
class ThemeConfig:
    primary_color: str
    background_color: str
    secondary_background_color: str
    text_color: str
    font: str


@dataclass(frozen=True)
class AssetsConfig:
    logo_path: Optional[str] = None
    logo_url: Optional[str] = None


@dataclass(frozen=True)
class StorageConfig:
    container_name: str
    blob_prefix: str
    local_root: str
    connection_string_env: str


@dataclass(frozen=True)
class AllocationConfig:
    priority: int
    warehouse_id: str
    supplier_country: str


@dataclass(frozen=True)
class BrandConfig:
    brand_id: str
    app_name: str
    ui: UIConfig
    theme: ThemeConfig
    assets: AssetsConfig
    storage: StorageConfig
    allocation: AllocationConfig
    prompt_overrides: Dict[str, str]
    source_path: Path

    def runtime_root(self, project_root: Path) -> Path:
        return project_root / self.storage.local_root

    def uploads_dir(self, project_root: Path) -> Path:
        return self.runtime_root(project_root) / "uploads"

    def data_dir(self, project_root: Path) -> Path:
        return self.runtime_root(project_root) / "data"

    def outputs_dir(self, project_root: Path) -> Path:
        return self.runtime_root(project_root) / "outputs"

    def build_blob_name(self, filename: str) -> str:
        clean_filename = filename.lstrip("/\\")
        prefix = self.storage.blob_prefix.strip("/\\")
        return f"{prefix}/{clean_filename}" if prefix else clean_filename

    def resolve_logo_path(self, project_root: Path) -> Optional[Path]:
        if not self.assets.logo_path:
            return None
        candidate = Path(self.assets.logo_path)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        return candidate


def load_brand_config(
    brand_name: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> BrandConfig:
    """Load the active brand configuration from the brands directory or an explicit path."""
    root = Path(project_root) if project_root else _default_project_root()
    brands_dir = _brands_dir(root)
    default_path = brands_dir / f"{DEFAULT_BRAND_ID}.json"
    default_data = _load_json_file(default_path)

    explicit_path = os.getenv("BRAND_CONFIG_PATH")
    if explicit_path:
        config_path = _resolve_path(Path(explicit_path), root)
        config_data = _load_json_file(config_path)
        merged_data = _deep_merge(default_data, config_data)
        if not merged_data.get("brand_id"):
            merged_data["brand_id"] = config_path.stem
        return _build_brand_config(merged_data, config_path)

    selected_brand = (brand_name or os.getenv("ACTIVE_BRAND") or DEFAULT_BRAND_ID).strip()
    if not selected_brand:
        selected_brand = DEFAULT_BRAND_ID

    if selected_brand == DEFAULT_BRAND_ID:
        return _build_brand_config(default_data, default_path)

    config_path = brands_dir / f"{selected_brand}.json"
    config_data = _load_json_file(config_path)
    merged_data = _deep_merge(default_data, config_data)
    if merged_data.get("brand_id") == DEFAULT_BRAND_ID:
        merged_data["brand_id"] = selected_brand
    return _build_brand_config(merged_data, config_path)


def list_brand_config_paths(project_root: Optional[Path] = None) -> list[Path]:
    """Return all brand config JSON files in the brands directory."""
    root = Path(project_root) if project_root else _default_project_root()
    brands_dir = _brands_dir(root)
    return sorted(path for path in brands_dir.glob("*.json") if path.is_file())


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _brands_dir(project_root: Path) -> Path:
    configured_dir = os.getenv("BRANDS_DIR")
    if configured_dir:
        return _resolve_path(Path(configured_dir), project_root)
    return project_root / "brands"


def _resolve_path(path: Path, base_dir: Path) -> Path:
    if path.is_absolute():
        return path
    return base_dir / path


def _load_json_file(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        raise BrandConfigError(f"Brand config file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise BrandConfigError(f"Invalid JSON in brand config {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise BrandConfigError(f"Brand config must be a JSON object: {file_path}")

    return data


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build_brand_config(data: Dict[str, Any], source_path: Path) -> BrandConfig:
    brand_id = _required_string(data, "brand_id", source_path)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", brand_id):
        raise BrandConfigError(
            f"brand_id must contain only lowercase letters, numbers, and hyphens: {source_path}"
        )

    ui_data = _required_dict(data, "ui", source_path)
    theme_data = _required_dict(data, "theme", source_path)
    assets_data = _optional_dict(data, "assets")
    storage_data = _required_dict(data, "storage", source_path)
    allocation_data = _required_dict(data, "allocation", source_path)
    prompt_overrides = data.get("prompt_overrides", {})
    if not isinstance(prompt_overrides, dict):
        raise BrandConfigError(f"prompt_overrides must be an object: {source_path}")

    return BrandConfig(
        brand_id=brand_id,
        app_name=_required_string(data, "app_name", source_path),
        ui=UIConfig(
            page_title=_required_string(ui_data, "page_title", source_path),
            page_icon=_required_string(ui_data, "page_icon", source_path),
            title=_required_string(ui_data, "title", source_path),
            description=_required_string(ui_data, "description", source_path),
            display_brand_name=_required_string(ui_data, "display_brand_name", source_path),
            display_warehouse_label=_required_string(
                ui_data, "display_warehouse_label", source_path
            ),
            display_blob_target_label=_required_string(
                ui_data, "display_blob_target_label", source_path
            ),
            display_runtime_label=_required_string(ui_data, "display_runtime_label", source_path),
            upload_label=_required_string(ui_data, "upload_label", source_path),
            upload_help=_required_string(ui_data, "upload_help", source_path),
            file_uploaded_message=_required_string(ui_data, "file_uploaded_message", source_path),
            process_button_label=_required_string(ui_data, "process_button_label", source_path),
            processing_status_label=_required_string(
                ui_data, "processing_status_label", source_path
            ),
            upload_step_label=_required_string(ui_data, "upload_step_label", source_path),
            convert_step_label=_required_string(ui_data, "convert_step_label", source_path),
            save_step_label=_required_string(ui_data, "save_step_label", source_path),
            blob_upload_step_label=_required_string(
                ui_data, "blob_upload_step_label", source_path
            ),
            all_steps_completed_message=_required_string(
                ui_data, "all_steps_completed_message", source_path
            ),
            error_message_prefix=_required_string(ui_data, "error_message_prefix", source_path),
            output_heading=_required_string(ui_data, "output_heading", source_path),
            output_url_label=_required_string(ui_data, "output_url_label", source_path),
            output_link_label=_required_string(ui_data, "output_link_label", source_path),
            success_message=_required_string(ui_data, "success_message", source_path),
            output_info=_required_string(ui_data, "output_info", source_path),
        ),
        theme=ThemeConfig(
            primary_color=_required_string(theme_data, "primary_color", source_path),
            background_color=_required_string(theme_data, "background_color", source_path),
            secondary_background_color=_required_string(
                theme_data, "secondary_background_color", source_path
            ),
            text_color=_required_string(theme_data, "text_color", source_path),
            font=_required_string(theme_data, "font", source_path),
        ),
        assets=AssetsConfig(
            logo_path=_optional_string(assets_data, "logo_path"),
            logo_url=_optional_string(assets_data, "logo_url"),
        ),
        storage=StorageConfig(
            container_name=_required_string(storage_data, "container_name", source_path),
            blob_prefix=_required_string(storage_data, "blob_prefix", source_path),
            local_root=_required_string(storage_data, "local_root", source_path),
            connection_string_env=_required_string(
                storage_data, "connection_string_env", source_path
            ),
        ),
        allocation=AllocationConfig(
            priority=_required_int(allocation_data, "priority", source_path),
            warehouse_id=_required_string(allocation_data, "warehouse_id", source_path),
            supplier_country=_required_string(allocation_data, "supplier_country", source_path),
        ),
        prompt_overrides={str(key): str(value) for key, value in prompt_overrides.items()},
        source_path=source_path,
    )


def _required_dict(data: Dict[str, Any], key: str, source_path: Path) -> Dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise BrandConfigError(f"Missing or invalid '{key}' object in {source_path}")
    return value


def _optional_dict(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise BrandConfigError(f"Invalid '{key}' object")
    return value


def _required_string(data: Dict[str, Any], key: str, source_path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BrandConfigError(f"Missing or invalid '{key}' value in {source_path}")
    return value.strip()


def _required_int(data: Dict[str, Any], key: str, source_path: Path) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise BrandConfigError(f"Missing or invalid '{key}' integer value in {source_path}")
    return value


def _optional_string(data: Dict[str, Any], key: str) -> Optional[str]:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BrandConfigError(f"Invalid '{key}' value")
    stripped = value.strip()
    return stripped or None
