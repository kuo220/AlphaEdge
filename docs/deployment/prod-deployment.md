# 正式環境部署（Prod Deployment）

本專案以「分角色容器化」部署：

- `core/Dockerfile`：回測／策略執行
- `frontend/Dockerfile`：前端（Streamlit，相依列在 `frontend/requirements.txt`）

容器映像**不含資料庫**，資料一律由主機掛入。

## 1) 建立映像

在專案根目錄執行：

```bash
docker build -f core/Dockerfile -t alphaedge-core .
docker build -f frontend/Dockerfile -t alphaedge-frontend .
```

## 2) 準備資料與環境檔

建議至少準備：

- `.env`（可由 `.env.example` 複製）
- `data/db/`（`tw_stock.db`、`tw_futures.db`）
- `data/downloads/`（只有要在容器內跑 `tasks.update_db` 時才需要）
- `results/`

## 3) 執行 core 容器（回測）

```bash
docker run --rm \
  --name alphaedge-core-run \
  -v "$(pwd)/data:/app/data:ro" \
  -v "$(pwd)/results:/app/results" \
  -v "$(pwd)/logs:/app/logs" \
  --env-file .env \
  alphaedge-core --strategy MomentumStrategy1
```

只跑回測時 `data/` 以唯讀掛載：主機上的 ETL 可能正在寫同一個資料庫檔。
要在容器內更新資料時才改為可寫掛載。

## 4) 執行前端容器（選用）

```bash
docker run --rm -d \
  --name alphaedge-frontend \
  -p 8501:8501 \
  -v "$(pwd)/results:/results:ro" \
  -e ALPHAEDGE_RESULTS_DIR=/results \
  alphaedge-frontend
```

`ALPHAEDGE_RESULTS_DIR` 與後端同名：後端寫哪、前端就讀哪。

## 5) Docker Compose

根目錄的 `docker-compose.yml` 一次起 `core` 與 `frontend`：

```bash
docker compose up --build
STRATEGY=MomentumFuturesStrategy docker compose up core   # 換策略
```

| 服務 | 掛載 | 說明 |
|------|------|------|
| `core` | `./data` → `/app/data`（唯讀）、`./logs` → `/app/logs`、具名 volume `alphaedge_results` → `/app/results` | 以 `MODE`／`STRATEGY` 環境變數決定要跑什麼 |
| `frontend` | 具名 volume `alphaedge_results` → `/results` | 開 `http://localhost:8501` |

回測結果放在**具名 volume** 而非主機的 `results/`，要在主機上看 CSV 請改用第 3、4 節的 `docker run`。

## 6) 建議的正式環境切分

- **資料更新節點**：定時執行 `python -m tasks.update_db ...`
- **回測節點**：執行 `run.py --strategy ...`，唯讀掛載資料庫
- **展示節點**：掛載唯讀的 `results` 給前端

## 7) 健康檢查與維運

```bash
# 查看容器
docker ps

# 查看 core 日誌
docker logs -f alphaedge-core-run

# 停止前端
docker stop alphaedge-frontend
```
