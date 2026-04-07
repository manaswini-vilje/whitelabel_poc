#!/usr/bin/env python3
"""
Streamlit UI for document processing workflow.
Allows users to upload PDF files and process them through the backend pipeline.
"""

import sys
import os
import shutil
from html import escape
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Add src to path for package imports
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import backend modules
from pdf_to_json_converter import DocumentToJSONConverter, AllocationGenerator
from white_label import load_brand_config

# Load environment variables
load_dotenv()

brand_config = load_brand_config(project_root=project_root)

# Page configuration - must be first Streamlit command
st.set_page_config(
    page_title=brand_config.ui.page_title,
    page_icon=brand_config.ui.page_icon,
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": None,
    },
)

# Native Streamlit options (no late CSS): avoids top bar flashing on reload. Also in .streamlit/config.toml (bootstrap).
st.set_option("client.toolbarMode", "minimal")

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'output_url' not in st.session_state:
    st.session_state.output_url = None
if 'output_path' not in st.session_state:
    st.session_state.output_path = None
if 'output_blob_name' not in st.session_state:
    st.session_state.output_blob_name = None


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert a hex color like #RRGGBB to an RGB tuple."""
    normalized = color.lstrip("#")
    if len(normalized) != 6:
        return (31, 119, 180)
    return tuple(int(normalized[index:index + 2], 16) for index in (0, 2, 4))


def rgba(color: str, alpha: float) -> str:
    """Convert a hex color into an rgba() CSS string."""
    red, green, blue = hex_to_rgb(color)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def ui_value(field_name: str, fallback: str) -> str:
    """Safely read optional UI config fields with a fallback for older in-memory configs."""
    value = getattr(brand_config.ui, field_name, fallback)
    return value if isinstance(value, str) and value.strip() else fallback


def apply_brand_theme():
    """Apply runtime CSS theme values from the active brand config."""
    theme = brand_config.theme
    background = escape(theme.background_color)
    secondary_background = escape(theme.secondary_background_color)
    primary_color = escape(theme.primary_color)
    text_color = escape(theme.text_color)
    font = "sans-serif" if theme.font == "sans serif" else escape(theme.font)
    primary_soft = rgba(theme.primary_color, 0.12)
    primary_mid = rgba(theme.primary_color, 0.22)
    primary_strong = rgba(theme.primary_color, 0.82)
    white_glass = "rgba(255, 255, 255, 0.76)"
    white_panel = "rgba(255, 255, 255, 0.92)"

    st.markdown(
        f"""
        <style>
            html, body, [class*="css"] {{
                scroll-behavior: smooth;
            }}

            .stApp {{
                background:
                    radial-gradient(circle at top left, {primary_soft} 0%, transparent 34%),
                    radial-gradient(circle at 85% 8%, {primary_soft} 0%, transparent 22%),
                    linear-gradient(135deg, {background} 0%, {secondary_background} 54%, {background} 100%);
                color: {text_color};
                font-family: {font};
            }}

            .block-container {{
                max-width: 1260px;
                padding-top: 2rem;
                padding-bottom: 2rem;
            }}

            .brand-hero {{
                position: relative;
                overflow: hidden;
                background:
                    linear-gradient(140deg, {white_glass} 0%, {white_panel} 48%, {rgba(theme.primary_color, 0.10)} 100%);
                border: 1px solid {primary_mid};
                border-radius: 30px;
                padding: 2rem;
                margin-bottom: 1.35rem;
                box-shadow: 0 24px 60px {rgba(theme.primary_color, 0.12)};
            }}

            .brand-hero::before {{
                content: "";
                position: absolute;
                inset: auto -3rem -5rem auto;
                width: 15rem;
                height: 15rem;
                border-radius: 999px;
                background: {primary_soft};
                filter: blur(8px);
            }}

            .brand-hero__grid {{
                display: grid;
                gap: 1.25rem;
                grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.95fr);
                align-items: start;
            }}

            .brand-hero__eyebrow {{
                color: {primary_color};
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                margin-bottom: 0.75rem;
                text-transform: uppercase;
            }}

            .brand-hero__headline {{
                color: {text_color};
                font-size: 2.85rem;
                line-height: 0.98;
                margin: 0 0 0.65rem 0;
                letter-spacing: -0.04em;
            }}

            .brand-hero__description {{
                color: {text_color};
                font-size: 1.02rem;
                line-height: 1.7;
                margin: 0;
                max-width: 42rem;
                opacity: 0.9;
            }}

            .brand-hero__chips {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.65rem;
                margin-top: 1rem;
            }}

            .brand-chip {{
                background: rgba(255, 255, 255, 0.76);
                border: 1px solid {primary_mid};
                border-radius: 999px;
                color: {text_color};
                font-size: 0.84rem;
                font-weight: 600;
                padding: 0.55rem 0.9rem;
            }}

            .hero-panel {{
                background: rgba(255, 255, 255, 0.78);
                border: 1px solid {primary_mid};
                border-radius: 24px;
                padding: 1.1rem;
                backdrop-filter: blur(8px);
            }}

            .hero-panel__title {{
                color: {primary_color};
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                margin-bottom: 1rem;
                text-transform: uppercase;
            }}

            .hero-stat-grid {{
                display: grid;
                gap: 0.8rem;
            }}

            .hero-stat {{
                background: rgba(255, 255, 255, 0.84);
                border: 1px solid {rgba(theme.primary_color, 0.16)};
                border-radius: 18px;
                padding: 0.9rem 1rem;
            }}

            .hero-stat__label {{
                color: {primary_color};
                display: block;
                font-size: 0.74rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                margin-bottom: 0.35rem;
                text-transform: uppercase;
            }}

            .hero-stat__value {{
                color: {text_color};
                display: block;
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.35;
                word-break: break-word;
            }}

            .section-shell {{
                background: rgba(255, 255, 255, 0.66);
                border: 1px solid {rgba(theme.primary_color, 0.14)};
                border-radius: 26px;
                box-shadow: 0 18px 40px {rgba(theme.primary_color, 0.08)};
                padding: 1.15rem;
                height: 100%;
            }}

            .section-shell--dark {{
                background:
                    linear-gradient(165deg, {rgba(theme.primary_color, 0.92)} 0%, {primary_strong} 100%);
                color: white;
            }}

            .section-shell--dark * {{
                color: white !important;
            }}

            .section-title {{
                color: {text_color};
                font-size: 1.12rem;
                font-weight: 800;
                letter-spacing: -0.02em;
                margin-bottom: 0.35rem;
            }}

            .section-copy {{
                color: {rgba(theme.text_color, 0.84)};
                font-size: 0.93rem;
                line-height: 1.6;
                margin-bottom: 1rem;
            }}

            div[data-testid="stFileUploader"] {{
                background: rgba(255, 255, 255, 0.82);
                border: 1.5px dashed {primary_mid};
                border-radius: 22px;
                padding: 0.55rem;
                transition: transform 160ms ease, box-shadow 160ms ease;
            }}

            div[data-testid="stFileUploader"] section {{
                border-radius: 18px;
            }}

            div[data-testid="stFileUploader"]:hover {{
                transform: translateY(-1px);
                box-shadow: 0 14px 34px {rgba(theme.primary_color, 0.10)};
            }}

            .stButton > button {{
                background:
                    linear-gradient(135deg, {primary_color} 0%, {primary_strong} 100%);
                border: 1px solid {primary_color};
                border-radius: 999px;
                color: white;
                font-weight: 700;
                min-height: 3rem;
                padding: 0.75rem 1.5rem;
                width: 100%;
            }}

            .stButton > button:hover {{
                background: linear-gradient(135deg, {primary_strong} 0%, {primary_color} 100%);
                border-color: {primary_color};
                color: white;
            }}

            .stButton > button:focus {{
                box-shadow: 0 0 0 0.2rem {rgba(theme.primary_color, 0.20)};
            }}

            div[data-testid="stStatusWidget"],
            div[data-testid="stAlert"] {{
                border-radius: 18px;
            }}

            .mini-card-grid {{
                display: grid;
                gap: 0.85rem;
            }}

            .mini-card {{
                background: rgba(255, 255, 255, 0.76);
                border: 1px solid {rgba(theme.primary_color, 0.14)};
                border-radius: 20px;
                padding: 0.95rem 1rem;
            }}

            .mini-card__label {{
                color: {primary_color};
                display: block;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                margin-bottom: 0.35rem;
                text-transform: uppercase;
            }}

            .mini-card__value {{
                color: {text_color};
                display: block;
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.4;
                word-break: break-word;
            }}

            .workflow-list {{
                display: grid;
                gap: 0.8rem;
            }}

            .workflow-step {{
                align-items: flex-start;
                background: rgba(255, 255, 255, 0.76);
                border: 1px solid {rgba(theme.primary_color, 0.14)};
                border-radius: 18px;
                display: grid;
                gap: 0.8rem;
                grid-template-columns: 2.3rem minmax(0, 1fr);
                padding: 0.9rem 1rem;
            }}

            .workflow-step__index {{
                align-items: center;
                background: {rgba(theme.primary_color, 0.14)};
                border-radius: 14px;
                color: {primary_color};
                display: flex;
                font-size: 0.95rem;
                font-weight: 800;
                height: 2.3rem;
                justify-content: center;
                width: 2.3rem;
            }}

            .workflow-step__title {{
                color: {text_color};
                display: block;
                font-size: 0.96rem;
                font-weight: 700;
                margin-bottom: 0.18rem;
            }}

            .workflow-step__copy {{
                color: {rgba(theme.text_color, 0.80)};
                display: block;
                font-size: 0.88rem;
                line-height: 1.5;
            }}

            .result-shell {{
                background:
                    linear-gradient(160deg, rgba(255, 255, 255, 0.94) 0%, {rgba(theme.primary_color, 0.08)} 100%);
                border: 1px solid {primary_mid};
                border-radius: 28px;
                margin-top: 1rem;
                padding: 1.3rem;
                box-shadow: 0 18px 40px {rgba(theme.primary_color, 0.10)};
            }}

            .result-shell__title {{
                color: {text_color};
                font-size: 1.28rem;
                font-weight: 800;
                margin-bottom: 0.35rem;
            }}

            .result-shell__copy {{
                color: {rgba(theme.text_color, 0.82)};
                font-size: 0.92rem;
                line-height: 1.6;
                margin-bottom: 0.95rem;
            }}

            .result-meta {{
                display: grid;
                gap: 0.85rem;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                margin-top: 0.75rem;
            }}

            .result-meta .mini-card {{
                background: rgba(255, 255, 255, 0.86);
            }}

            @media (max-width: 980px) {{
                .brand-hero__grid,
                .result-meta {{
                    grid-template-columns: 1fr;
                }}

                .brand-hero__headline {{
                    font-size: 2.3rem;
                }}
            }}
        </style>
        """,
        unsafe_allow_html=True
    )


def render_brand_header():
    """Render a branded app header."""
    logo_path = brand_config.resolve_logo_path(project_root)
    if logo_path and logo_path.exists():
        st.image(str(logo_path), width=180)
    elif brand_config.assets.logo_url:
        st.image(brand_config.assets.logo_url, width=180)

    display_brand_name = ui_value("display_brand_name", brand_config.app_name)
    display_warehouse_label = ui_value(
        "display_warehouse_label", brand_config.allocation.warehouse_id
    )
    display_blob_target_label = ui_value(
        "display_blob_target_label",
        f"{brand_config.storage.container_name}/{brand_config.storage.blob_prefix}",
    )
    display_runtime_label = ui_value(
        "display_runtime_label",
        str(brand_config.outputs_dir(project_root).relative_to(project_root)),
    )

    st.markdown(
        f"""
        <section class="brand-hero">
            <div class="brand-hero__grid">
                <div>
                    <div class="brand-hero__eyebrow">{escape(display_brand_name)}</div>
                    <div class="brand-hero__headline">{escape(brand_config.ui.title)}</div>
                    <p class="brand-hero__description">{escape(brand_config.ui.description)}</p>
                    <div class="brand-hero__chips">
                        <span class="brand-chip">White-label ready</span>
                        <span class="brand-chip">Brand aware storage</span>
                        <span class="brand-chip">PO allocation pipeline</span>
                    </div>
                </div>
                <div class="hero-panel">
                    <div class="hero-panel__title">Live Configuration</div>
                    <div class="hero-stat-grid">
                        <div class="hero-stat">
                            <span class="hero-stat__label">Warehouse</span>
                            <span class="hero-stat__value">{escape(display_warehouse_label)}</span>
                        </div>
                        <div class="hero-stat">
                            <span class="hero-stat__label">Blob Target</span>
                            <span class="hero-stat__value">{escape(display_blob_target_label)}</span>
                        </div>
                        <div class="hero-stat">
                            <span class="hero-stat__label">Runtime Output</span>
                            <span class="hero-stat__value">{escape(display_runtime_label)}</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True
    )


def render_workflow_step(index: int, title: str, copy: str):
    """Render a single workflow step card."""
    st.markdown(
        f"""
        <div class="workflow-step">
            <div class="workflow-step__index">{index}</div>
            <div>
                <span class="workflow-step__title">{escape(title)}</span>
                <span class="workflow-step__copy">{escape(copy)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_workspace_overview():
    """Render the main dashboard around the uploader."""
    left_col, right_col = st.columns([1.3, 0.9], gap="large")

    with left_col:
        st.markdown(
            """
            <div class="section-shell">
                <div class="section-title">Upload Workspace</div>
                <div class="section-copy">
                    Drop a supplier PDF into the pipeline and the app will extract structured
                    PL data, generate the PO allocation JSON, and place the output in the active brand runtime.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        uploaded_file = st.file_uploader(
            brand_config.ui.upload_label,
            type=["pdf"],
            help=brand_config.ui.upload_help
        )
        display_brand_name = ui_value("display_brand_name", brand_config.app_name)
        display_blob_target_label = ui_value(
            "display_blob_target_label",
            f"{brand_config.storage.container_name}/{brand_config.storage.blob_prefix}",
        )
        st.caption(
            f"Experience profile: `{display_brand_name}` | "
            f"Output lane: `{display_blob_target_label}`"
        )

        if uploaded_file is not None:
            st.markdown(
                f"""
                <div class="mini-card-grid" style="margin-top: 0.85rem;">
                    <div class="mini-card">
                        <span class="mini-card__label">Queued File</span>
                        <span class="mini-card__value">{escape(uploaded_file.name)}</span>
                    </div>
                    <div class="mini-card">
                        <span class="mini-card__label">File Size</span>
                        <span class="mini-card__value">{escape(format_file_size(uploaded_file.size))}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with right_col:
        st.markdown(
            """
            <div class="section-shell section-shell--dark">
                <div class="section-title">Pipeline Storyboard</div>
                <div class="section-copy">
                    The interface is intentionally structured like an operations cockpit:
                    clear upload entry, visible brand routing, and a high-signal result panel when the file is complete.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('<div class="workflow-list">', unsafe_allow_html=True)
        render_workflow_step(1, "Extract", "Read supplier text, tables, SKUs, and metadata from the uploaded PDF.")
        render_workflow_step(2, "Transform", "Convert document content into normalized PL data aligned to your schema.")
        render_workflow_step(3, "Allocate", "Build the final purchase order JSON using the active brand defaults.")
        render_workflow_step(4, "Deliver", "Save locally in the brand runtime and upload to the brand blob target.")
        st.markdown("</div>", unsafe_allow_html=True)

    return uploaded_file


def render_result_panel():
    """Render a richer result area after processing completes."""
    if not st.session_state.output_url or not st.session_state.output_path:
        return

    output_path = Path(st.session_state.output_path)
    blob_name = st.session_state.output_blob_name or output_path.name

    st.markdown(
        f"""
        <section class="result-shell">
            <div class="result-shell__title">{escape(brand_config.ui.success_message)}</div>
            <div class="result-shell__copy">
                The file was processed successfully and routed through the active white-label pipeline.
                You can download the generated JSON locally or open the uploaded blob output.
            </div>
        </section>
        """,
        unsafe_allow_html=True
    )

    action_col, link_col = st.columns([1, 1], gap="large")
    with action_col:
        if output_path.exists():
            with open(output_path, "rb") as generated_file:
                st.download_button(
                    label="Download Generated JSON",
                    data=generated_file.read(),
                    file_name=output_path.name,
                    mime="application/json",
                    use_container_width=True
                )

    with link_col:
        st.link_button(
            label=f"{brand_config.ui.output_link_label}",
            url=st.session_state.output_url,
            use_container_width=True
        )

    st.markdown(
        f"""
        <div class="result-meta">
            <div class="mini-card">
                <span class="mini-card__label">Local Output</span>
                <span class="mini-card__value">{escape(str(output_path.relative_to(project_root)))}</span>
            </div>
            <div class="mini-card">
                <span class="mini-card__label">Blob Object</span>
                <span class="mini-card__value">{escape(blob_name)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def upload_to_azure_blob(local_file_path: str, blob_name: str) -> str:
    """
    Upload a file to Azure Blob Storage and return the public URL.

    Args:
        local_file_path: Path to local file to upload
        blob_name: Name for the blob in storage

    Returns:
        Public URL of the uploaded blob
    """
    connection_string_env = brand_config.storage.connection_string_env
    connection_string = os.getenv(connection_string_env)
    if not connection_string:
        raise ValueError(
            f"{connection_string_env} environment variable is required. "
            "Please set it in your .env file."
        )

    container_name = brand_config.storage.container_name
    blob_name = brand_config.build_blob_name(blob_name)

    try:
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
            raise ValueError("Could not extract account name from connection string")

        return (
            f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        )

    except Exception as e:
        raise Exception(f"Failed to upload to Azure Blob Storage: {str(e)}")


def process_document(uploaded_file):
    """
    Process uploaded document through the backend pipeline.

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        Path to output JSON file
    """
    uploads_dir = brand_config.uploads_dir(project_root)
    data_dir = brand_config.data_dir(project_root)
    outputs_dir = brand_config.outputs_dir(project_root)

    uploads_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    input_filename = uploaded_file.name
    temp_file_path = uploads_dir / input_filename

    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

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

        input_stem = Path(input_filename).stem
        output_filename = f"{input_stem}_output.json"
        output_path = outputs_dir / output_filename

        shutil.copy2(final_allocation_path, output_path)

        return str(output_path)

    finally:
        try:
            if temp_file_path.exists():
                os.remove(temp_file_path)
        except Exception:
            pass


def main():
    """Main Streamlit app."""
    apply_brand_theme()
    render_brand_header()
    uploaded_file = render_workspace_overview()
    
    # Process button
    if uploaded_file is not None:
        st.success(brand_config.ui.file_uploaded_message.format(filename=uploaded_file.name))
        
        if st.button(
            brand_config.ui.process_button_label,
            type="primary",
            disabled=st.session_state.processing
        ):
            st.session_state.processing = True
            st.session_state.output_url = None
            st.session_state.output_path = None
            st.session_state.output_blob_name = None
            
            try:
                # Show processing status
                with st.status(brand_config.ui.processing_status_label, expanded=True) as status:
                    st.write(brand_config.ui.upload_step_label)

                    st.write(brand_config.ui.convert_step_label)
                    output_path = process_document(uploaded_file)

                    st.write(brand_config.ui.save_step_label)

                    st.write(brand_config.ui.blob_upload_step_label)
                    output_filename = Path(output_path).name
                    blob_url = upload_to_azure_blob(output_path, output_filename)

                    status.update(label=brand_config.ui.success_message, state="complete")
                    st.write(brand_config.ui.all_steps_completed_message)

                st.session_state.output_url = blob_url
                st.session_state.output_path = output_path
                st.session_state.output_blob_name = brand_config.build_blob_name(output_filename)
                st.session_state.processing = False
                
            except Exception as e:
                st.session_state.processing = False
                st.error(f"{brand_config.ui.error_message_prefix}: {str(e)}")
                st.exception(e)
    
    # Display output URL if available
    if st.session_state.output_url:
        st.success(brand_config.ui.success_message)
        st.markdown(f"### {brand_config.ui.output_heading}")
        st.info(brand_config.ui.output_info)
        render_result_panel()


if __name__ == "__main__":
    main()
