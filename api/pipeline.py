"""
Document processing + blob upload — same steps as `whitelabel_poc/app.py`, without Streamlit.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from azure.storage.blob import BlobServiceClient

# Ensure `src/` is importable for pdf_to_json_converter / white_label (same as Streamlit entry).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def process_uploaded_pdf(
    *,
    project_root: Path,
    brand_config,
    file_bytes: bytes,
    filename: str,
) -> tuple[str, str, str]:
    """
    Run PDF → PL JSON → allocation JSON, copy to outputs, upload blob.

    Returns:
        output_url: HTTPS blob URL
        blob_name: prefixed blob path (e.g. default/processed/foo_output.json)
        local_path_relative: path relative to project root (POSIX)
    """
    from pdf_to_json_converter import AllocationGenerator, DocumentToJSONConverter

    uploads_dir = brand_config.uploads_dir(project_root)
    data_dir = brand_config.data_dir(project_root)
    outputs_dir = brand_config.outputs_dir(project_root)

    uploads_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    temp_file_path = uploads_dir / filename
    with open(temp_file_path, "wb") as handle:
        handle.write(file_bytes)

    try:
        pl_data_path = data_dir / "pl_data.json"
        final_allocation_path = data_dir / "final_allocation.json"
        custom_prompt = brand_config.prompt_overrides.get("document_extraction_prompt")

        converter = DocumentToJSONConverter()
        converter.convert_to_json(
            str(temp_file_path),
            str(pl_data_path),
            custom_prompt=custom_prompt,
        )

        AllocationGenerator.generate_po_allocation_from_pl(
            str(pl_data_path),
            str(final_allocation_path),
            priority=brand_config.allocation.priority,
            warehouse_id=brand_config.allocation.warehouse_id,
            supplier_country=brand_config.allocation.supplier_country,
        )

        input_stem = Path(filename).stem
        output_filename = f"{input_stem}_output.json"
        output_path = outputs_dir / output_filename
        shutil.copy2(final_allocation_path, output_path)

        blob_url = upload_to_azure_blob(
            brand_config=brand_config,
            local_file_path=str(output_path),
            blob_filename=output_filename,
        )
        blob_name = brand_config.build_blob_name(output_filename)
        try:
            local_rel = output_path.relative_to(project_root)
        except ValueError:
            local_rel = output_path
        local_path_relative = local_rel.as_posix()

        return blob_url, blob_name, local_path_relative

    finally:
        try:
            if temp_file_path.exists():
                temp_file_path.unlink()
        except OSError:
            pass


def upload_to_azure_blob(
    *,
    brand_config,
    local_file_path: str,
    blob_filename: str,
) -> str:
    connection_string_env = brand_config.storage.connection_string_env
    connection_string = os.getenv(connection_string_env)
    if not connection_string:
        raise ValueError(
            f"{connection_string_env} is not set. Add it to whitelabel_poc/.env or the environment."
        )

    container_name = brand_config.storage.container_name
    blob_name = brand_config.build_blob_name(blob_filename)

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except Exception:
        pass

    blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob=blob_name,
    )

    with open(local_file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    account_name = None
    for part in connection_string.split(";"):
        if part.startswith("AccountName="):
            account_name = part.split("=", 1)[1]
            break

    if not account_name:
        raise ValueError("Could not extract AccountName from Azure connection string")

    return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
