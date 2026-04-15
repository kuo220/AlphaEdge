FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# NOTE:
# Build this Dockerfile with project root as context:
# docker build -f frontend/Dockerfile -t alphaedge-frontend .
COPY frontend /app/frontend

RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f /app/frontend/requirements.txt ]; then \
      pip install --no-cache-dir -r /app/frontend/requirements.txt; \
    else \
      pip install --no-cache-dir streamlit pandas; \
    fi

EXPOSE 8501

ENV ALPHAEDGE_BACKTEST_RESULTS=/results

CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
