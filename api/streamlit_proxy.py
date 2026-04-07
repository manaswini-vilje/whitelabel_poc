"""
When STREAMLIT_INTERNAL_URL is set (e.g. http://127.0.0.1:8501), attach HTTP + WebSocket
proxying so Streamlit serves the UI at / while FastAPI keeps /api/* and /health.

Run Streamlit bound to 127.0.0.1 only; the public port serves uvicorn (FastAPI + proxy).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import websockets
from fastapi import WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocketState
from websockets.exceptions import ConnectionClosed

from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

POC_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

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
        "content-length",
    }
)


def _read_brand_page_title() -> str | None:
    path = POC_ROOT / ".streamlit_page_title"
    try:
        text = path.read_text(encoding="utf-8").strip()
        return text or None
    except OSError:
        return None


def _rewrite_streamlit_shell_title(content: bytes, media_type: str) -> bytes:
    """Replace default <title>Streamlit</title> so the tab matches brand ui.page_title."""
    if "text/html" not in media_type.lower():
        return content
    title = _read_brand_page_title()
    if not title:
        return content
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    if "<title" not in text.lower():
        return content
    replaced = re.sub(
        r"<title>[\s\S]*?</title>",
        f"<title>{escape(title)}</title>",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return replaced.encode("utf-8")


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

    body = _rewrite_streamlit_shell_title(
        r.content,
        r.headers.get("content-type", ""),
    )

    out_headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in _SKIP_RESPONSE_HEADERS
    }

    return Response(content=body, status_code=r.status_code, headers=out_headers)


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


def _parse_streamlit_sec_websocket_protocol(
    websocket: WebSocket,
) -> tuple[str | None, str]:
    """Mirror Streamlit's _parse_subprotocols: comma-separated entries keep positions (xsrf, session).

    See streamlit/web/server/starlette/starlette_websocket.py — the header carries more than
    one token; only the first value is the subprotocol passed to websocket.accept().
    """
    raw = websocket.headers.get("sec-websocket-protocol", "")
    if not raw:
        return None, ""
    entries = [value.strip() for value in raw.split(",")]
    selected = entries[0] if entries and entries[0] else None
    return selected, raw


def _host_header_value(streamlit_http_base: str) -> str:
    from urllib.parse import urlparse

    u = urlparse(streamlit_http_base)
    host = u.hostname or "127.0.0.1"
    if u.port:
        return f"{host}:{u.port}"
    return host


def _cookie_header_for_upstream(websocket: WebSocket) -> str | None:
    """Ensure Streamlit sees XSRF/session cookies on the internal WS handshake."""
    raw = websocket.headers.get("cookie")
    if raw:
        return raw
    if not websocket.cookies:
        return None
    return "; ".join(f"{k}={v}" for k, v in websocket.cookies.items())


async def _proxy_websocket_to_streamlit(websocket: WebSocket, path: str) -> None:
    base = _streamlit_base()
    if not base:
        await websocket.close(code=1011)
        return

    # First comma-separated entry is the subprotocol; rest are xsrf + session (must be preserved).
    selected_subprotocol, full_protocol_header = _parse_streamlit_sec_websocket_protocol(
        websocket
    )
    await websocket.accept(subprotocol=selected_subprotocol or "streamlit")

    target_base = _http_to_ws_base(base)
    target = f"{target_base}/{path}" if path else target_base
    if websocket.url.query:
        target = f"{target}?{websocket.url.query}"

    # Streamlit validates Origin against Host; internal Host 127.0.0.1 + public Origin fails.
    # Use the browser's Host / Origin so _is_origin_allowed matches the real site.
    public_host = websocket.headers.get("host") or _host_header_value(base)
    extra: list[tuple[str, str]] = [
        ("Host", public_host),
    ]
    origin = websocket.headers.get("origin")
    if origin:
        extra.append(("Origin", origin))

    for k, v in websocket.headers.items():
        lk = k.lower()
        if lk in {
            "host",
            "origin",
            "connection",
            "upgrade",
            "sec-websocket-key",
            "sec-websocket-version",
            "sec-websocket-protocol",
            "sec-websocket-extensions",
            "cookie",
        }:
            continue
        extra.append((k, v))

    if full_protocol_header:
        extra.append(("Sec-WebSocket-Protocol", full_protocol_header))

    cookie_hdr = _cookie_header_for_upstream(websocket)
    if cookie_hdr:
        extra.append(("Cookie", cookie_hdr))

    # websockets>=14: if the server responds with Sec-WebSocket-Protocol (Streamlit sends
    # "streamlit"), the client MUST declare subprotocols or handshake raises
    # NegotiationError("no subprotocols supported") and the browser reconnects forever.
    negotiated = selected_subprotocol or "streamlit"
    try:
        # Disable client-side keepalive pings: behind Azure they can time out (ping_timeout)
        # and tear down the link to Streamlit, which makes the browser reconnect in a loop.
        async with websockets.connect(
            target,
            max_size=50 * 1024 * 1024,
            max_queue=512,
            subprotocols=[negotiated],
            additional_headers=extra,
            compression=None,
            open_timeout=60,
            ping_interval=None,
            ping_timeout=None,
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
                except asyncio.CancelledError:
                    raise
                except ConnectionClosed:
                    pass
                except Exception as exc:
                    logger.warning("streamlit ws client→upstream: %s", exc)

            async def upstream_to_client() -> None:
                try:
                    while True:
                        raw = await upstream.recv()
                        if isinstance(raw, str):
                            await websocket.send_text(raw)
                        else:
                            await websocket.send_bytes(raw)
                except asyncio.CancelledError:
                    raise
                except ConnectionClosed as exc:
                    rcvd = exc.rcvd
                    code = int(rcvd.code) if rcvd is not None else 1000
                    reason = (rcvd.reason or "")[:123] if rcvd is not None else ""
                    logger.debug(
                        "streamlit upstream closed: code=%s reason=%s",
                        code,
                        reason,
                    )
                    if websocket.application_state == WebSocketState.CONNECTED:
                        try:
                            await websocket.close(code=code, reason=reason)
                        except Exception:
                            pass
                except Exception as exc:
                    logger.warning("streamlit ws upstream→client: %s", exc)

            # If one side stops, cancel the other — otherwise receive() can block forever
            # and Streamlit's frontend reconnects in a tight loop (WebSocket onclose).
            t_client = asyncio.create_task(client_to_upstream())
            t_upstream = asyncio.create_task(upstream_to_client())
            done, pending = await asyncio.wait(
                (t_client, t_upstream),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            await asyncio.gather(t_client, t_upstream, return_exceptions=True)
            # If the browser leg is still open (e.g. client disconnected first), finish it.
            if websocket.application_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close(code=1000)
                except Exception:
                    pass
    except Exception:
        logger.exception("streamlit websocket proxy failed")
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
