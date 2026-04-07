"""
FastAPI app for the React frontend. Run from the `whitelabel_poc` directory:

    uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

REST routes: `/health`, `/api/*`. With `STREAMLIT_INTERNAL_URL` set, unmatched HTTP 404s and
WebSockets are proxied to Streamlit so `/` serves the Streamlit UI (see `startup.sh`).
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

POC_ROOT = Path(__file__).resolve().parent.parent

# Load Azure / OpenAI keys from this project
load_dotenv(POC_ROOT / ".env")

_SRC = POC_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from white_label import BrandConfig, load_brand_config

from api.pipeline import process_uploaded_pdf
from api.streamlit_proxy import attach_streamlit_proxy

_brand: BrandConfig | None = None


def get_brand() -> BrandConfig:
    global _brand
    if _brand is None:
        raise RuntimeError("Brand config not loaded")
    return _brand


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _brand
    _brand = load_brand_config(project_root=POC_ROOT)
    yield
    _brand = None


app = FastAPI(
    title="White-label document API",
    description="REST API for the Vite frontend; pipeline lives alongside Streamlit in this repo.",
    lifespan=lifespan,
)


def brand_to_json(bc: BrandConfig) -> dict:
    """Shape matches `whitelabel-poc-frontend/src/config/brand.ts` BrandConfig."""
    return {
        "brand_id": bc.brand_id,
        "app_name": bc.app_name,
        "ui": asdict(bc.ui),
        "theme": asdict(bc.theme),
        "storage": asdict(bc.storage),
        "allocation": asdict(bc.allocation),
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.get("/api/brand")
def api_brand():
    return brand_to_json(get_brand())


@app.post("/api/process")
async def api_process(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Expected a PDF file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    bc = get_brand()
    try:
        output_url, blob_name, local_path_relative = process_uploaded_pdf(
            project_root=POC_ROOT,
            brand_config=bc,
            file_bytes=data,
            filename=file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    out_path = POC_ROOT / local_path_relative
    try:
        with open(out_path, encoding="utf-8") as handle:
            output_json = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline wrote a file but it could not be read as JSON: {exc}",
        ) from exc

    return {
        "success": True,
        "output_url": output_url,
        "blob_name": blob_name,
        "local_path_relative": local_path_relative,
        "message": bc.ui.success_message,
        "output_json": output_json,
    }


# Streamlit UI at / when STREAMLIT_INTERNAL_URL is set (see startup.sh). CORS added after so it runs first.
attach_streamlit_proxy(app)

_cors = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
