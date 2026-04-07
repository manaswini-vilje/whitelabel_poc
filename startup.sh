#!/bin/bash
# Azure App Service: one public process (uvicorn) on $PORT. Streamlit listens on loopback only;
# FastAPI serves /api/* and /health and proxies everything else to Streamlit.
# Azure Portal → Configuration → General settings → Web sockets = On (required for /_stcore/stream).
#
# Startup Command: bash startup.sh

set -e

pip install --upgrade pip
pip install -r requirements.txt

python bootstrap_brand_runtime.py

export PORT="${PORT:-8000}"
export STREAMLIT_INTERNAL_URL="${STREAMLIT_INTERNAL_URL:-http://127.0.0.1:8501}"

python -m streamlit run app.py \
  --server.address=127.0.0.1 \
  --server.port=8501 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false \
  --server.fileWatcherType=none \
  &

# Wait until Streamlit accepts HTTP (App Service may not have curl; Python is always available)
python - <<'PY'
import os
import time
import urllib.request

url = os.environ.get("STREAMLIT_INTERNAL_URL", "http://127.0.0.1:8501").rstrip("/") + "/"
for _ in range(60):
    try:
        urllib.request.urlopen(url, timeout=2)
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Streamlit did not become ready in time")
PY

# Long-lived /stream WebSockets: default uvicorn ping timeout (20s) can drop the browser leg
# behind Azure/proxies before pong returns, causing Streamlit to reconnect forever (skeleton UI).
exec python -m uvicorn api.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --ws-ping-interval 60 \
  --ws-ping-timeout 300
