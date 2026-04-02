#!/usr/bin/env python3
"""Validate all white-label brand configs and report conflicts."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from white_label import BrandConfigError, list_brand_config_paths, load_brand_config


def main() -> int:
    brand_paths = list_brand_config_paths(PROJECT_ROOT)
    if not brand_paths:
        print("No brand configs found.")
        return 1

    errors: list[str] = []
    seen_brand_ids: dict[str, Path] = {}
    seen_runtime_roots: dict[str, Path] = {}
    seen_storage_targets: dict[tuple[str, str], Path] = {}

    print("White-label validation summary")
    print("=" * 60)

    for brand_path in brand_paths:
        try:
            brand = load_brand_config(brand_name=brand_path.stem, project_root=PROJECT_ROOT)
        except BrandConfigError as exc:
            errors.append(f"{brand_path.name}: {exc}")
            continue

        runtime_root = str(brand.runtime_root(PROJECT_ROOT))
        storage_target = (brand.storage.container_name, brand.storage.blob_prefix)

        print(f"{brand.brand_id}: {brand.app_name}")
        print(f"  config: {brand_path.name}")
        print(f"  runtime: {runtime_root}")
        print(f"  storage env: {brand.storage.connection_string_env}")
        print(f"  blob target: {brand.storage.container_name}/{brand.storage.blob_prefix}")

        existing_brand = seen_brand_ids.get(brand.brand_id)
        if existing_brand:
            errors.append(
                f"Duplicate brand_id '{brand.brand_id}' in {brand_path.name} and {existing_brand.name}"
            )
        else:
            seen_brand_ids[brand.brand_id] = brand_path

        existing_runtime = seen_runtime_roots.get(runtime_root)
        if existing_runtime:
            errors.append(
                f"Duplicate runtime root '{runtime_root}' in {brand_path.name} and {existing_runtime.name}"
            )
        else:
            seen_runtime_roots[runtime_root] = brand_path

        existing_storage = seen_storage_targets.get(storage_target)
        if existing_storage:
            errors.append(
                "Duplicate storage target "
                f"'{brand.storage.container_name}/{brand.storage.blob_prefix}' "
                f"in {brand_path.name} and {existing_storage.name}"
            )
        else:
            seen_storage_targets[storage_target] = brand_path

        logo_path = brand.resolve_logo_path(PROJECT_ROOT)
        if brand.assets.logo_path and (not logo_path or not logo_path.exists()):
            errors.append(
                f"{brand_path.name}: logo_path '{brand.assets.logo_path}' does not exist"
            )

    if errors:
        print("\nValidation errors")
        print("-" * 60)
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nAll brand configs validated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
