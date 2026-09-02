# 正式環境部署（Prod Deployment）

本專案根目錄已有 `docker-compose.yml`（`core` ＋ `frontend` ＋ 共用 `results` volume，用法見 `README.md`〈方式 3〉）；正式部署仍建議以「分角色容器化」方式進行：

- `core/Dockerfile`：回測/策略執行
- `frontend/Dockerfile`：前端（Streamlit）

## 1) 建立映像

在專案根目錄執行：

```bash
docker build -f core/Dockerfile -t alphaedge-core .
docker build -f frontend/Dockerfile -t alphaedge-frontend .
```

## 2) 準備資料與環境檔

建議至少準備：

- `.env`（可由 `.env.example` 複製）
- `data/db/`（`tw_stock.db`、`tw_futures.db`——容器映像**不含**資料庫，必須由本機掛入）
- `data/downloads/`（只有要在容器內跑 `tasks.update_db` 時才需要）
- `results/`

## 3) 執行 core 容器（回測）

```bash
docker run --rm \
  --name alphaedge-core-run \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/results:/app/results" \
  -v "$(pwd)/logs:/app/logs" \
  --env-file .env \
  alphaedge-core --strategy MomentumStrategy1
```

## 4) 執行前端容器（選用）

> 注意：`frontend/Dockerfile` 在沒有 `frontend/requirements.txt` 時只會安裝 `streamlit pandas`，而 `frontend/app.py` 需要 `plotly`——請先補上該檔或改用 `pip install -e ".[frontend]"`（見健檢 F-093）。

```bash
docker run --rm -d \
  --name alphaedge-frontend \
  -p 8501:8501 \
  -v "$(pwd)/results:/results:ro" \
  -e ALPHAEDGE_BACKTEST_RESULTS=/results \
  alphaedge-frontend
```

## 5) 建議的正式環境切分

- **資料更新節點**：定時執行 `python -m tasks.update_db ...`
- **回測節點**：執行 `run.py --strategy ...`
- **展示節點**：掛載唯讀的 `results` 給前端

## 6) 健康檢查與維運

```bash
# 查看容器
docker ps

# 查看 core 日誌
docker logs -f alphaedge-core-run

# 停止前端
docker stop alphaedge-frontend
```

compose 版的啟動方式見 `README.md`〈方式 3：Docker Compose〉；注意 `docker-compose.yml` 目前沒有為 `core` 掛 `data/`，回測會因找不到資料庫而中止（見健檢 F-094）。
