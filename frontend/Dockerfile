FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# NOTE:
# Build this Dockerfile with project root as context:
# docker build -f frontend/Dockerfile -t alphaedge-frontend .
COPY frontend /app/frontend

# 前端唯一用到的後端程式碼：風險指標的共用公式（見 frontend/services/metrics.py）。
# 只 COPY 這條最小鏈，映像不必帶整個 core/ 與 shioaji——`risk_metrics.py`
# 只相依 math 與 typing，而 `analysis/__init__.py` 刻意不 eager import analyzer。
# 哪天前端多用了 core 的別的東西，這裡會在啟動時 ImportError 而不是安靜地算錯。
COPY core/__init__.py /app/core/__init__.py
COPY core/backtest/__init__.py /app/core/backtest/__init__.py
COPY core/backtest/analysis/__init__.py /app/core/backtest/analysis/__init__.py
COPY core/backtest/analysis/risk_metrics.py /app/core/backtest/analysis/risk_metrics.py

RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f /app/frontend/requirements.txt ]; then \
      pip install --no-cache-dir -r /app/frontend/requirements.txt; \
    else \
      pip install --no-cache-dir streamlit pandas; \
    fi

EXPOSE 8501

ENV ALPHAEDGE_RESULTS_DIR=/results

CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
