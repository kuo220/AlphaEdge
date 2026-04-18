[English](#) | [Chinese (中文版)](README_zh.md)

# AlphaEdge

AlphaEdge is a strategy research and trading framework focused on Taiwan market workflows (backtest + reporting + data update pipeline + Streamlit result viewer).

## Architecture Overview

```mermaid
graph TB
    subgraph entry ["Entry Layer"]
        RunPy["run.py"]
        Tasks["tasks/update_db.py"]
    end

    subgraph trading_core ["Trading Core"]
        Strategies["trader/strategies"]
        Managers["trader/managers"]
        Models["trader/models"]
        Utils["trader/utils"]
    end

    subgraph data_layer ["Data & Pipeline"]
        API["trader/api"]
        Adapters["trader/adapters"]
        Pipeline["trader/pipeline"]
        DB["trader/database"]
        Data["trader/data"]
    end

    subgraph output_layer ["Backtest Outputs"]
        Backtest["trader/backtest/results"]
    end

    subgraph frontend_layer ["Frontend (Streamlit)"]
        FrontendApp["frontend/app.py"]
        FrontendService["frontend/services/report_loader.py"]
        FrontendConfig["frontend/config.py"]
        FrontendDocker["frontend/Dockerfile"]
    end

    subgraph docs_layer ["Docs"]
        Readme["README.md / README_zh.md"]
        Docs["docs/"]
    end

    RunPy --> Strategies
    Tasks --> Pipeline
    Strategies --> Managers
    Managers --> Models
    Strategies --> API
    API --> Adapters
    Adapters --> DB
    Pipeline --> DB
    DB --> Backtest
    Backtest --> FrontendService
    FrontendConfig --> FrontendService
    FrontendService --> FrontendApp
    FrontendDocker --> FrontendApp
    Readme --> Docs
```

## Module Guide

| Module                   | Description                                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------------------- |
| `trader/`                | Core trading domain code (strategies, managers, models, adapters, API, data, backtest outputs) |
| `frontend/`              | Streamlit Docker image for viewing backtest results                                            |
| `tasks/`                 | Data maintenance and database update scripts                                                   |
| `tests/`                 | Unit/integration tests for crawlers, updaters, and DB workflows                                |
| `docs/`                  | Project docs (setup, deployment, data coverage)                                                |
| `ARCHITECTURE_REVIEW.md` | Additional architecture analysis notes                                                         |

---

## Documentation

| Document                                                  | Description                                                   |
| --------------------------------------------------------- | ------------------------------------------------------------- |
| [Dev Setup](docs/setup/dev-setup.md)                      | Python environment, dependencies, formatting, env vars        |
| [Dev Deployment](docs/deployment/dev-deployment.md)       | Local service startup flow, collector run commands, dashboard |
| [Prod Deployment](docs/deployment/prod-deployment.md)     | Docker Compose deployment, monitoring, multi-node strategy    |
| [Data Coverage](docs/exchanges/data_coverage.md)          | Data source and API coverage in current platform              |
| [Strategy Development Guide](trader/strategies/README.md) | How to implement strategies in this project                   |

---

## Environment Setup

### Option 1: Local venv + requirements.txt

```bash
# create virtualenv
python3 -m venv .venv
# activate virtualenv
source .venv/bin/activate

# install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Run Trader + Frontend Together (Local)

After installing dependencies above, open two terminal tabs at project root:

**Tab 1 (Trader: run backtest)**

```bash
source .venv/bin/activate
python run.py --strategy <StrategyClassName>
```

**Tab 2 (Frontend: view results)**

```bash
source .venv/bin/activate
streamlit run frontend/app.py
```

Then open: `http://localhost:8501`

### Option 2: Docker Container

#### Trader Container

```bash
# build image
docker build -f trader/Dockerfile -t alphaedge-trader .

# run container and show CLI help
docker run --rm alphaedge-trader --help
```

#### Frontend Container

```bash
# build image
docker build -f frontend/Dockerfile -t alphaedge-frontend .

# run container
docker run --rm -p 8501:8501 alphaedge-frontend
```

### Option 3: Docker Compose (Trader + Frontend)

#### Build and Start

```bash
# Build all services
docker compose build

# Start trader and frontend together
docker compose up
```

#### Run in Background / Stop

```bash
# Start in detached mode
docker compose up -d

# Stop and remove containers
docker compose down
```

## Command Usage

```bash
# update database (default: no_tick)
python -m tasks.update_db --target no_tick

# run backtest with your strategy class
python run.py --strategy <StrategyClassName>
```

## Project Structure

```text
AlphaEdge/
├── trader/                    # trading domain modules
│   ├── strategies/            # strategy implementations
│   ├── api/                   # data access APIs
│   ├── adapters/              # data adapters / integrations
│   ├── managers/              # account / order / flow managers
│   ├── models/                # domain models
│   ├── pipeline/              # ETL/update pipeline
│   ├── database/              # sqlite database files
│   ├── backtest/              # backtest engine and outputs
│   └── data/                  # downloaded/raw data
├── frontend/                  # Streamlit docker image
│   ├── app.py                 # Streamlit entrypoint
│   ├── config.py              # frontend configuration
│   ├── services/              # data loading services
│   │   └── report_loader.py   # load backtest report files
│   ├── Dockerfile             # frontend container image
│   ├── README.md              # frontend usage notes
│   └── __init__.py
├── tasks/                     # data update scripts
├── tests/                     # test suites
├── docs/                      # project docs
│   ├── setup/
│   ├── deployment/
│   └── exchanges/
├── run.py
├── ARCHITECTURE_REVIEW.md
├── README.md
└── README_zh.md
```
