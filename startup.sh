#!/bin/bash

set -e

pip install --upgrade pip
pip install -r requirements.txt

python bootstrap_brand_runtime.py

# Set environment variable for Streamlit
export STREAMLIT_SERVER_PORT=8000
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_ENABLE_CORS=false
export STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

# Start Streamlit with proper configuration
python -m streamlit run app.py \
    --server.port=8000 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false \
    --server.fileWatcherType=none
