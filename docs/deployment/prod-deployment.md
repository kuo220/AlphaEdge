# 正式環境部署（Prod Deployment）

本專案目前沒有 `docker-compose.yml`，正式部署建議以「分角色容器化」方式進行：

- `trader/Dockerfile`：回測/策略執行
- `frontend/Dockerfile`：前端（Streamlit）

## 1) 建立映像

在專案根目錄執行：

```bash
docker build -f trader/Dockerfile -t alphaedge-trader .
docker build -f frontend/Dockerfile -t alphaedge-frontend .
```

## 2) 準備資料與環境檔

建議至少準備：

- `.env`（可由 `.env.example` 複製）
- `trader/database/`
- `trader/data/`
- `trader/backtest/results/`

## 3) 執行 trader 容器（回測）

```bash
docker run --rm \
  --name alphaedge-trader-run \
  -v "$(pwd)/trader/database:/app/trader/database" \
  -v "$(pwd)/trader/data:/app/trader/data" \
  -v "$(pwd)/trader/backtest/results:/app/trader/backtest/results" \
  --env-file .env \
  alphaedge-trader --strategy MomentumStrategy
```

## 4) 執行前端容器（選用）

> 注意：目前倉庫內僅有 `frontend/Dockerfile`，請先確認前端程式檔（例如 `frontend/app.py`）已存在，再啟動容器。

```bash
docker run --rm -d \
  --name alphaedge-frontend \
  -p 8501:8501 \
  -v "$(pwd)/trader/backtest/results:/results:ro" \
  -e ALPHAEDGE_BACKTEST_RESULTS=/results \
  alphaedge-frontend
```

## 5) 建議的正式環境切分

- **資料更新節點**：定時執行 `python -m tasks.update_db ...`
- **回測節點**：執行 `run.py --strategy ...`
- **展示節點**：掛載唯讀的 `trader/backtest/results` 給前端

## 6) 健康檢查與維運

```bash
# 查看容器
docker ps

# 查看 trader 日誌
docker logs -f alphaedge-trader-run

# 停止前端
docker stop alphaedge-frontend
```

若你後續加入 `docker-compose.yml`，建議再補一份 compose 版部署文件。
