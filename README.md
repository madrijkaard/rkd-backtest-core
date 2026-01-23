# 🧠 Crypto Backtester – Modular Strategies with Logarithmic Zones

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square\&logo=python)
![VectorBT](https://img.shields.io/badge/VectorBT-Powered-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

A cryptocurrency backtesting system focused on **logarithmic price zone strategies**. Supports multiple exchanges via CCXT, multiple timeframes, automatic export of results to Excel, and parameter grid search.

---

## ⚙️ Technologies Used

* **[Python 3.10+](https://www.python.org/)**
* **[CCXT](https://github.com/ccxt/ccxt)** – Historical market data from exchanges
* **[VectorBT](https://vectorbt.dev/)** – Portfolio simulation and performance metrics
* **[Pandas](https://pandas.pydata.org/)** + **[NumPy](https://numpy.org/)**
* **[OpenPyXL](https://openpyxl.readthedocs.io/)** – Excel export
* **[TQDM](https://tqdm.github.io/)** – Terminal progress bars
* **[PyYAML](https://pyyaml.org/)** – YAML configuration files

---

## 📁 Project Structure

```
.
├── config.yaml                        # Global backtest configuration (exchange, symbols, timeframes, dates, output)
├── exchange.py                         # Select exchange via CCXT
├── executor.py                         # Main script to run monthly backtests
├── strategy/
│   ├── accumulation_zone/
│   │   ├── accumulation_zone.py       # Log_zones_activity strategy
│   │   ├── config.yaml                # Strategy-specific parameters
│   │   └── scanning.py                # Grid search for positive parameter combinations
├── requirements.txt                    # Project dependencies
├── README.md                           # This file
└── backtest/                           # (generated) Excel files with backtest results
```

---

## 📄 File Descriptions

* **`config.yaml`** – Global backtest configuration:

  * Exchange and market type (`spot`/`futures`/`coinm`)
  * Symbols to backtest
  * Timeframes
  * Start and end dates
  * Initial balance and output folder

* **`exchange.py`** – Loads the configured exchange and returns a `ccxt` client.

* **`executor.py`** – Executes backtests:

  * Downloads OHLCV for each symbol and timeframe
  * Splits data into monthly intervals
  * Applies `log_zones_activity_strategy`
  * Simulates portfolios with VectorBT
  * Exports monthly statistics to Excel

* **`strategy/accumulation_zone/accumulation_zone.py`** – Strategy implementation:

  * Computes **logarithmic zones**
  * Measures zone activity
  * Defines LONG/SHORT entries, stop loss, and take profit based on zones
  * Prevents position conflicts

* **`strategy/accumulation_zone/config.yaml`** – Strategy parameters:

  * `lookback_candles`, `max_loss_percent`
  * Zones configuration and activity filters
  * Targets based on zones

* **`strategy/accumulation_zone/scanning.py`** – Parameter grid search:

  * Tests `max_loss_percent` × `min_percent_from_extreme` combinations
  * Identifies parameter sets that yield positive returns in all months for each year
  * Prints results in the console

---

## ▶️ How to Run

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/crypto-backtester.git
cd crypto-backtester
```

### 2. Configure `config.yaml`

```yaml
exchange:
  name: binance
  market: futures

symbols:
  - ETH/USDT

timeframes:
  - 30m

date_range:
  start_year: 2019
  start_month: 1
  end_year: 2025
  end_month: 12

execution:
  initial_balance: 1000.0

output:
  folder: output
```

### 3. Configure strategy (`strategy/accumulation_zone/config.yaml`)

```yaml
strategy:
  name: log_zones_activity
  lookback_candles: 200
  max_loss_percent: 1.5

  zones:
    total: 8
    top_active: 3
    bottom_active: 2

  activity:
    min_percent_from_extreme: 55.0

  targets:
    take_profit_zones_ahead: 2
    stop_loss_zones_behind: 2
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the backtest

```bash
python executor.py
```

> 💡 Excel files will be generated per symbol and timeframe in the configured output folder.

### 6. Run Grid Search for Positive Parameters

```bash
python strategy/accumulation_zone/scanning.py
```

> 💡 Prints all parameter combinations that produced positive returns for all months in each year.

---

## 📄 Output

* Excel files in `output/`:

  * One file per symbol
  * One sheet per timeframe
  * Rows represent months
  * Metrics computed by VectorBT (return, drawdown, Sharpe ratio, etc.)

* Grid search prints **combinations with all years positive** to the console.

---

## 💡 Strategy: Logarithmic Zones Activity

* Calculates **logarithmic price zones** using the last `lookback_candles`
* Identifies **most active** and **least active zones**
* LONG/SHORT entries only occur if:

  * Price crosses central zone
  * Adjacent zones are not blocked
  * Minimum distance from last extreme is respected
  * Maximum stop loss is not exceeded
* Stop loss and take profit are zone-based
* Conflicting positions are prevented

---

## 📌 Future Improvements

* [ ] Add more exchanges (KuCoin, OKX, etc.)
* [ ] Parallel execution using `ThreadPoolExecutor`
* [ ] Export trade charts with `vectorbt.plot()`
* [ ] Cache OHLCV data locally
* [ ] Web interface for uploading and running strategies

---

## 📄 License

Distributed under the [MIT License](LICENSE).

---

Made with 💙 by [Rijkaard Balduíno or GitHub](https://github.com/madrijkaard)
