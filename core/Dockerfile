FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BROWSER_PATH=/usr/bin/chromium

WORKDIR /app

# chromium：回測報表存 PNG 走 plotly `write_image()` → kaleido 1.x，而 kaleido 1.x
# 不再內建瀏覽器，找不到 Chrome 就在報表最後一步拋 RuntimeError（CSV 已寫出、圖全沒有）。
# 用 Debian 的 chromium 而不是 `plotly_get_chrome`：後者下載的 Chrome for Testing
# 沒有 linux arm64 版本。`BROWSER_PATH` 讓 kaleido 不必猜瀏覽器的名稱與位置
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# 相依分兩層裝：先照 requirements.txt 的鎖定版本裝第三方套件，只改原始碼時這層仍吃快取。
# 略過最後一行 `-e .`：此時原始碼還沒進來，editable 安裝會失敗，改由下方裝本專案
COPY requirements.txt /tmp/requirements.txt
RUN grep -v '^-e ' /tmp/requirements.txt > /tmp/requirements.lock.txt \
    && pip install --no-cache-dir -r /tmp/requirements.lock.txt

# NOTE:
# Build this Dockerfile with project root as context:
# docker build -f core/Dockerfile -t alphaedge-core .
COPY pyproject.toml /app/pyproject.toml
COPY run.py /app/run.py
COPY core /app/core
# `tasks/` 是 ETL 的入口（`python -m tasks.update_db`）。少了它，映像只跑得了
# 回測，compose 描述的資料更新流程在容器裡完全不存在
COPY tasks /app/tasks

# 以 pyproject 安裝本專案，取代原本的 `PYTHONPATH=/app`：與本機、CI 同一種安裝方式，
# pyproject 宣告了而鎖定檔漏列的相依也會在這裡補上，而不是等執行到那條路徑才 ImportError。
# **必須是 editable**：`core/config/paths.py` 以 `__file__` 推算專案根目錄，
# 一般安裝會把程式複製進 site-packages，`results/`、`logs/` 就不會落在掛載的 /app 底下
RUN pip install --no-cache-dir -e . && pip check

ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
