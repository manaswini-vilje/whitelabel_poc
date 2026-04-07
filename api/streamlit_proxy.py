"""
When STREAMLIT_INTERNAL_URL is set (e.g. http://127.0.0.1:8501), attach HTTP + WebSocket
proxying so Streamlit serves the UI at / while FastAPI keeps /api/* and /health.

Run Streamlit bound to 127.0.0.1 only; the public port serves uvicorn (FastAPI + proxy).
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import httpx
import websockets
from fastapi import WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

_SKIP_REQUEST_HEADERS = frozenset(
    {
        "host",
        "connection",
        "content-length",
        "transfer-encoding",
        "te",
        "upgrade",
        "keep-alive",
        "proxy-connection",
    }
)

_SKIP_RESPONSE_HEADERS = frozenset(
    {
        "connection",
        "transfer-encoding",
        "content-encoding",
    }
)


def _streamlit_base() -> str:
    return os.environ.get("STREAMLIT_INTERNAL_URL", "").rstrip("/")


def _is_reserved_api_path(path: str) -> bool:
    if path.startswith("/api"):
        return True
    if path == "/health":
        return True
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    if path == "/openapi.json":
        return True
    return False


async def _proxy_http_to_streamlit(request: Request) -> Response:
    base = _streamlit_base()
    if not base:
        return Response("Streamlit proxy not configured", status_code=503)

    url = f"{base}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _SKIP_REQUEST_HEADERS
    }

    body = await request.body()

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        r = await client.request(
            request.method,
            url,
            headers=headers,
            content=body if body else None,
        )

    out_headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in _SKIP_RESPONSE_HEADERS
    }

    return Response(content=r.content, status_code=r.status_code, headers=out_headers)


class Streamlit404FallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _streamlit_base():
            return await call_next(request)

        response = await call_next(request)
        if response.status_code != 404:
            return response

        path = request.url.path
        if _is_reserved_api_path(path):
            return response

        return await _proxy_http_to_streamlit(request)


def _http_to_ws_base(base: str) -> str:
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :]
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :]
    return base


async def _proxy_websocket_to_streamlit(websocket: WebSocket, path: str) -> None:
    base = _streamlit_base()
    if not base:
        await websocket.close(code=1011)
        return

    await websocket.accept()

    target_base = _http_to_ws_base(base)
    target = f"{target_base}/{path}" if path else target_base
    if websocket.url.query:
        target = f"{target}?{websocket.url.query}"

    extra: list[tuple[str, str]] = []
    for k, v in websocket.headers.items():
        lk = k.lower()
        if lk in {"host", "connection", "upgrade"}:
            continue
        extra.append((k, v))

    try:
        async with websockets.connect(
            target,
            max_size=50 * 1024 * 1024,
            additional_headers=extra,
        ) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if "text" in msg:
                            await upstream.send(msg["text"])
                        elif "bytes" in msg:
                            await upstream.send(msg["bytes"])
                except Exception:
                    pass

            async def upstream_to_client() -> None:
                try:
                    while True:
                        raw = await upstream.recv()
                        if isinstance(raw, str):
                            await websocket.send_text(raw)
                        else:
                            await websocket.send_bytes(raw)
                except Exception:
                    pass

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


def attach_streamlit_proxy(app: FastAPI) -> None:
    """No-op unless STREAMLIT_INTERNAL_URL is set."""
    if not _streamlit_base():
        return

    app.add_middleware(Streamlit404FallbackMiddleware)

    @app.websocket("/{path:path}")
    async def _streamlit_ws(path: str, websocket: WebSocket) -> None:
        path_slash = f"/{path}" if path else "/"
        if _is_reserved_api_path(path_slash) or path.startswith("api/"):
            await websocket.close(code=4404)
            return
        await _proxy_websocket_to_streamlit(websocket, path)
