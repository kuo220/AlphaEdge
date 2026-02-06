[English](#) | [Chinese (中文版)](README_zh.md)

# AlphaEdge

**AlphaEdge** is a *trading framework* designed for backtesting trading strategies, generating backtest reports, and enabling *live trading* through the [Shioaji API](https://sinotrade.github.io/zh_TW/). It supports backtesting and trading for **stocks, futures, and options** (though currently, only stock trading has been implemented).

## 📚 Documentation

- **[Complete API Documentation](docs/README.md)** - Complete API reference documentation built with MkDocs (includes usage instructions, documentation structure, and features)
- **[Architecture Analysis](ARCHITECTURE_REVIEW.md)** - Detailed system architecture analysis
- **[Strategy Development Guide](trader/strategies/README.md)** - Complete guide for strategy development

### View Documentation Website with MkDocs

To preview the API documentation website locally (with search, navigation, and code examples), follow these steps:

1. **Install MkDocs and documentation dependencies** (run in project root directory):
   ```bash
   pip install -r docs/requirements.txt
   ```

2. **Start the documentation server**:
   ```bash
   mkdocs serve
   ```

3. **Open documentation in browser**:
   - Default URL: **http://127.0.0.1:8000**
   - If port 8000 is occupied, the terminal will display the actual port used (e.g., `http://127.0.0.1:8001`), please use the URL shown in the terminal.

4. **(Optional) Build static website**: To build only without starting the server:
   ```bash
   mkdocs build
   ```
   Output will be in the `site/` folder in the project root, which can be deployed to any static website host.

To get started, users should follow the instructions in [Strategy Instruction](trader/strategies/README.md) and complete the following steps:

1. Familiarize themselves with the backtest Data API.
2. Develop a trading strategy.
3. Configure the strategy parameters.

## Table of Contents

- [AlphaEdge](#alphaedge)
- [Documentation](#-documentation)
  - [View Documentation Website with MkDocs](#view-documentation-website-with-mkdocs)
- [Backtesting Methods](#backtesting-methods)
  - [Running Backtests](#running-backtests)
  - [Backtest Levels](#backtest-levels)
  - [Backtest Results](#backtest-results)
- [Strategy Format](#strategy-format)
  - [Basic Structure](#basic-structure)
  - [Required Methods](#required-methods)
  - [Strategy Configuration Parameters](#strategy-configuration-parameters)
  - [Data API Usage](#data-api-usage)
  - [FinMind Data](#finmind-data)
  - [Example Strategies](#example-strategies)
- [Database Updates](#database-updates)
  - [Update Commands](#update-commands)
  - [Supported Data Types](#supported-data-types)
  - [Update Process](#update-process)

## Backtesting Methods

### Running Backtests

Use `run.py` to execute backtests. Basic syntax:

```bash
python run.py --strategy <StrategyName>
```

**Parameter Description:**
- `--mode`: Execution mode, options are `backtest` or `live`, default is `backtest`
- `--strategy`: Specify the strategy class name to use (required)

**Usage Examples:**

```bash
# Run backtest mode using a strategy named "Momentum"
python run.py --strategy Momentum

# Run live trading mode (not yet implemented)
python run.py --mode live --strategy Momentum
```

**Notes:**
- Strategy Name is the Class name
- Strategies are automatically loaded from the `trader/strategies/stock/` directory
- Backtest results are stored in the `trader/backtest/results/<StrategyName>/` directory

### Backtest Levels

AlphaEdge supports four backtest levels (KBar levels):

1. **TICK**: Tick-by-tick trade data backtesting
   - Uses `StockTickAPI` to get tick-by-tick trade data
   - Suitable for strategies requiring precise prices and timing
   - See `trader/strategies/stock/momentum_tick_strategy.py` for reference

2. **DAY**: Daily bar data backtesting
   - Uses `StockPriceAPI` to get daily closing price data
   - Suitable for strategies based on daily technical indicators
   - See `trader/strategies/stock/momentum_strategy.py` or `trader/strategies/stock/simple_long_strategy.py` for reference

3. **MIX**: Mixed level backtesting
   - Uses both TICK and DAY data simultaneously
   - Not yet fully implemented

4. **ALL**: Use all available data
   - Loads both TICK and DAY data APIs simultaneously
   - Suitable for strategies requiring multiple data sources

Set the backtest level in your strategy:

```python
self.scale: str = Scale.DAY  # or Scale.TICK, Scale.MIX, Scale.ALL
```

### Backtest Results

After backtesting completes, the system automatically generates:

1. **Trading Report** (`trading_report.csv`)
   - Contains all trading records, profit/loss statistics, etc.

2. **Chart Analysis**
   - Balance curve chart (`balance_curve.png`)
   - Balance and benchmark comparison chart (`balance_and_benchmark_curve.png`)
   - Maximum drawdown chart (`balance_mdd.png`)
   - Daily profit/loss chart (`everyday_profit.png`)

3. **Log Files** (`<StrategyName>.log`)
   - Records all information and warnings during the backtest process

Backtest results are stored at: `trader/backtest/results/<StrategyName>/`

## Strategy Format

### Basic Structure

All strategies must inherit from the `BaseStockStrategy` class and implement all abstract methods.

```python
from trader.strategies.stock import BaseStockStrategy
from trader.models import StockAccount, StockOrder, StockQuote
from trader.utils import Action, Scale, PositionType

class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        # Strategy configuration...
```

### Required Methods

#### 1. `setup_account(account: StockAccount)`
Load virtual account information for managing funds and positions during backtesting.

```python
def setup_account(self, account: StockAccount):
    self.account = account
```

#### 2. `setup_apis()`
Load required data APIs, selectively loaded based on backtest level.

```python
def setup_apis(self):
    self.chip = StockChipAPI()  # Chip data
    self.mrr = MonthlyRevenueReportAPI()  # Monthly revenue data
    self.fs = FinancialStatementAPI()  # Financial statement data
    
    if self.scale in (Scale.TICK, Scale.MIX, Scale.ALL):
        self.tick = StockTickAPI()  # Tick data
    
    if self.scale in (Scale.DAY, Scale.MIX, Scale.ALL):
        self.price = StockPriceAPI()  # Daily bar data
```

#### 3. `check_open_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
Opening position strategy logic to determine which stocks should open positions.

```python
def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    open_positions = []
    
    for stock_quote in stock_quotes:
        # Your opening condition logic
        if your_condition:
            open_positions.append(stock_quote)
    
    return self.calculate_position_size(open_positions, Action.BUY)
```

#### 4. `check_close_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
Closing position strategy logic to determine which positions should be closed.

```python
def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    close_positions = []
    
    for stock_quote in stock_quotes:
        if self.account.check_has_position(stock_quote.stock_id):
            # Your closing condition logic
            if your_condition:
                close_positions.append(stock_quote)
    
    return self.calculate_position_size(close_positions, Action.SELL)
```

#### 5. `check_stop_loss_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
Stop loss strategy logic to determine which positions should trigger stop loss.

```python
def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    stop_loss_orders = []
    
    for stock_quote in stock_quotes:
        if self.account.check_has_position(stock_quote.stock_id):
            position = self.account.get_first_open_position(stock_quote.stock_id)
            # Your stop loss condition logic (e.g., loss exceeds 5%)
            if (stock_quote.close / position.price - 1) < -0.05:
                stop_loss_orders.append(stock_quote)
    
    return self.calculate_position_size(stop_loss_orders, Action.SELL)
```

#### 6. `calculate_position_size(stock_quotes: List[StockQuote], action: Action) -> List[StockOrder]`
Calculate order size based on current funds, price, and risk control rules.

```python
def calculate_position_size(
    self, stock_quotes: List[StockQuote], action: Action
) -> List[StockOrder]:
    orders = []
    
    if action == Action.BUY:
        # Calculate available position count
        available_position_cnt = max(
            0, self.max_holdings - self.account.get_position_count()
        )
        
        if available_position_cnt > 0:
            per_position_size = self.account.balance / available_position_cnt
            
            for stock_quote in stock_quotes:
                open_volume = int(
                    per_position_size / (stock_quote.close * Units.LOT)
                )
                
                if open_volume >= 1:
                    orders.append(
                        StockOrder(
                            stock_id=stock_quote.stock_id,
                            date=stock_quote.date,
                            action=action,
                            position_type=PositionType.LONG,
                            price=stock_quote.cur_price,
                            volume=open_volume,
                        )
                    )
                    available_position_cnt -= 1
                    
                    if available_position_cnt == 0:
                        break
    elif action == Action.SELL:
        # Use full position volume when closing
        for stock_quote in stock_quotes:
            position = self.account.get_first_open_position(stock_quote.stock_id)
            if position is None:
                continue
            
            orders.append(
                StockOrder(
                    stock_id=stock_quote.stock_id,
                    date=stock_quote.date,
                    action=action,
                    position_type=position.position_type,
                    price=stock_quote.cur_price,
                    volume=position.volume,
                )
            )
    
    return orders
```

### Strategy Configuration Parameters

Set strategy parameters in the `__init__` method:

```python
def __init__(self):
    super().__init__()
    
    # === Strategy Basic Information ===
    self.strategy_name: str = "MyStrategy"  # Strategy name
    self.market: str = Market.STOCK  # Market type
    self.position_type: str = PositionType.LONG  # Position direction (long/short)
    self.enable_intraday: bool = True  # Whether to allow intraday trading
    
    # === Account Settings ===
    self.init_capital: float = 1000000.0  # Initial capital
    self.max_holdings: Optional[int] = 10  # Maximum number of positions
    
    # === Backtest Settings ===
    self.is_backtest: bool = True  # Whether in backtest mode
    self.scale: str = Scale.DAY  # Backtest level
    self.start_date: datetime.date = datetime.date(2020, 1, 1)  # Backtest start date
    self.end_date: datetime.date = datetime.date(2025, 5, 31)  # Backtest end date
    
    # Load data APIs
    self.setup_apis()
```

### Data API Usage

Strategies can access data through the following APIs:

#### StockPriceAPI - Daily Price Data

```python
# Get all stock prices for a specified date
prices = self.price.get(date=datetime.date(2024, 1, 1))

# Get all stock prices for a date range
prices = self.price.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)

# Get price for a specific stock
stock_prices = self.price.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
```

#### StockTickAPI - Tick-by-Tick Trade Data

```python
# Get tick data for a specified date
ticks = self.tick.get(date=datetime.date(2024, 1, 1))

# Get tick data for a specific stock
stock_ticks = self.tick.get_stock_tick(
    stock_id="2330",
    date=datetime.date(2024, 1, 1)
)
```

#### StockChipAPI - Chip Data

```python
# Get chip data for a specified date
chips = self.chip.get(date=datetime.date(2024, 1, 1))
```

#### MonthlyRevenueReportAPI - Monthly Revenue Data

```python
# Get monthly revenue data for a specified year and month
mrr = self.mrr.get(year=2024, month=1)
```

#### FinancialStatementAPI - Financial Statement Data

```python
# Get financial statement data for a specified year and quarter
fs = self.fs.get(year=2024, season=1)
```

### FinMind Data

AlphaEdge supports accessing the following data through the FinMind API:

1. **Taiwan Stock Overview (including warrants)** (`stock_info`): Contains basic information for all listed, OTC, and emerging stocks and warrants
2. **Securities Firm Information** (`broker_info`): Contains codes, names, addresses, phone numbers, etc. for all securities firms
3. **Broker Branch Statistics** (`broker_trading`): Daily buy/sell statistics for each broker branch for each stock

This data is stored in a SQLite database and can be accessed through SQL queries. Currently, no dedicated API class is provided; it is recommended to use SQL queries or pandas to read the database directly in strategies.

**Table Names:**
- `taiwan_stock_info_with_warrant`: Taiwan Stock Overview (including warrants)
- `taiwan_securities_trader_info`: Securities Firm Information
- `taiwan_stock_trading_daily_report_secid_agg`: Broker Branch Statistics

### Example Strategies

AlphaEdge provides several strategy examples for reference:

- **MomentumStrategy** (`trader/strategies/stock/momentum_strategy.py`): Momentum strategy at daily bar level
- **MomentumTickStrategy** (`trader/strategies/stock/momentum_tick_strategy.py`): Momentum strategy at TICK level
- **SimpleLongStrategy** (`trader/strategies/stock/simple_long_strategy.py`): Simple long position strategy example

For detailed strategy writing guidelines, please refer to [Strategy Instruction](trader/strategies/README.md).

## Database Updates

### Update Commands

Use `tasks/update_db.py` to update the database. Basic syntax:

```bash
python -m tasks.update_db --target <data_type>
```

### Supported Data Types

- `tick`: Tick-by-tick trade data
- `chip`: Three major institutional investor chip data
- `price`: Closing price data
- `fs`: Financial statement data
- `mrr`: Monthly revenue report
- `finmind`: Update all FinMind data (Taiwan Stock Overview, Securities Firm Information, Broker Branch Statistics)
- `stock_info`: Update only FinMind Taiwan Stock Overview (excluding warrants)
- `stock_info_with_warrant`: Update only FinMind Taiwan Stock Overview (including warrants)
- `broker_info`: Update only FinMind Securities Firm Information
- `broker_trading`: Update only FinMind Broker Branch Statistics
- `all`: Update all data (including tick and finmind)
- `no_tick`: Update all data (excluding tick, default)

### Update Process

Data updates follow an ETL (Extract, Transform, Load) process:

1. **Crawl**: Crawl raw data from data sources
2. **Clean**: Clean and standardize data format
3. **Load**: Load cleaned data into the database

Each data type has a corresponding Updater class responsible for coordinating the entire process.

**Usage Examples:**

```bash
# Update only tick data
python -m tasks.update_db --target tick

# Update three major institutional investors and closing prices
python -m tasks.update_db --target chip price

# Update all FinMind data
python -m tasks.update_db --target finmind

# Update only FinMind Taiwan Stock Overview
python -m tasks.update_db --target stock_info

# Update only FinMind Broker Branch Statistics
python -m tasks.update_db --target broker_trading

# Update multiple data types simultaneously
python -m tasks.update_db --target chip price finmind

# Update all data (excluding tick, default)
python -m tasks.update_db --target no_tick
# or
python -m tasks.update_db

# Update all data (including tick and finmind)
python -m tasks.update_db --target all
```

**Data Update Time Range:**

- **General Data** (price, chip, mrr, fs): Starting from 2013/1/1
- **Tick Data**: Starting from 2020/3/2 (provided by Shioaji API)
- **FinMind Data**:
  - Taiwan Stock Overview (including warrants) (`stock_info`): One-time update of all data
  - Securities Firm Information (`broker_info`): One-time update of all data
  - Broker Branch Statistics (`broker_trading`): Starting from 2021/6/30

**Update Status Description:**

Data updates return the following statuses:
- `UpdateStatus.SUCCESS`: Successfully updated
- `UpdateStatus.NO_DATA`: No data (API returned empty results)
- `UpdateStatus.ALREADY_UP_TO_DATE`: Database is already up to date
- `UpdateStatus.ERROR`: Error occurred

**Notes:**

- Update programs automatically start updating from the latest date in the database; no need to manually specify start date
- Update process automatically handles delays and error retries
- Update logs are stored in the `trader/logs/` directory
- FinMind Broker Branch Statistics updates support automatic API Quota management and Metadata tracking. For detailed process, please refer to [Broker Branch Statistics Update Process](docs/broker_trading_update_flow.md)

**Financial Report Filing Deadline Reminder:**

General industry financial report filing deadlines:
- Q1: May 15
- Q2: August 14
- Q3: November 14
- Annual Report: March 31
