# 🧠 Crypto Backtester – Modular Strategies with Logarithmic Zones

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square\&logo=python)
![VectorBT](https://img.shields.io/badge/VectorBT-Powered-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

Backtesting system for cryptocurrencies focused on strategies using **logarithmic price zones**. Supports multiple exchanges via CCXT, multiple timeframes, and automatic export of results to Excel spreadsheets.

---

## ⚙️ Technologies Used

* **[Python 3.10+](https://www.python.org/)**
* **[CCXT](https://github.com/ccxt/ccxt)** – For historical data from exchanges
* **[VectorBT](https://vectorbt.dev/)** – Backtesting, performance metrics, and portfolio simulation
* **[Pandas](https://pandas.pydata.org/)** + **[NumPy](https://numpy.org/)**
* **[OpenPyXL](https://openpyxl.readthedocs.io/)** – Excel spreadsheet generation
* **[TQDM](https://tqdm.github.io/)** – Terminal progress bar

---

## 📁 Project Structure

```
.
├── config.yaml                  # Configuration file with backtest parameters
├── exchange.py                 # Selects exchange via CCXT
├── executor.py                 # Main script to run the backtest
├── strategy/
│   ├── strategy.py             # Abstract base strategy and trade structure
│   └── log_zones_activity.py   # Logarithmic zone strategy
├── requirements.txt            # Project dependencies
├── venv.sh                     # Script to activate virtual environment and run the project
└── backtest/                   # (generated) Folder with Excel result files
```

### File Descriptions

* **`config.yaml`**: Defines cryptos, timeframes, lookback window, exchange, and other settings.
* **`exchange.py`**: Loads the chosen exchange and instantiates a `ccxt` client.
* **`executor.py`**: Controls the entire execution flow. Iterates dates, applies strategy, exports results.
* **`strategy/log_zones_activity.py`**: Main strategy using logarithmic zones.
* **`venv.sh`**: Automates environment activation, dependency installation, and execution.

---

## ▶️ How to Run the Project

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/crypto-backtester.git
cd crypto-backtester
```

### 2. Configure `config.yaml`

Example content:

```yaml
exchange:
  name: binance
  market: futures
  quote_asset: USDT

symbols:
  - ETH/USDT

timeframes:
  - 15m
  - 1h

date_range:
  start_year: 2020
  start_month: 1
  end_year: 2020
  end_month: 12

execution:
  initial_balance: 1000.0
  max_loss_percent: 1.0

strategy:
  name: log_zones_activity
  lookback_candles: 200

  zones:
    total: 8
    top_active: 3
    bottom_active: 2

  activity:
    min_percent_from_extreme: 40.0

  targets:
    take_profit_zones_ahead: 2
    stop_loss_zones_behind: 2

output:
  folder: backtest_results
  export_excel: true
```

### 3. Run the `venv.sh` Script

Use the command below to activate the virtual environment and automatically execute the project:

```bash
source venv.sh
```

> 💡 **Important:** The script must be executed with `source` to work correctly.

---

## 📄 Output Example

After execution, `.xlsx` files will be saved in `backtest_results/`, containing:

* One row per analyzed month
* Metrics calculated by `VectorBT`

> Note: The project no longer generates `_signals.xlsx` or `_trades.xlsx`. Only **monthly statistics** are exported.

---

## 💡 Strategy: Logarithmic Zones Activity

The `log_zones_activity` strategy uses price zones calculated via logarithmic transformations of the **rolling min and max** over a window (`lookback`). It includes rules such as:

* Identifies **top3 zones most active in sequence**
* Avoids trades if **activity is below threshold**
* LONG entry occurs after **price crosses above central zone**
* SHORT entry occurs after **price crosses below central zone**
* Stop loss and take profit defined by zones behind/ahead
* Logic resets each month

---

## 📈 Adding New Strategies

1. Create a new file in `strategy/`, e.g. `my_strategy.py`
2. Define a function with the signature:

```python
def my_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    ...
```

3. In `executor.py`, import and replace the strategy function:

```python
from strategy.my_strategy import my_strategy

# Replace:
# strategy_func=backtest_strategy
# With:
strategy_func=my_strategy
```

---

## 🧪 Understanding LOOKBACK and Candle Limit

Each month, the script fetches up to **1000 candles** for the given timeframe:

| Timeframe | Coverage with 1000 candles |
| --------- | -------------------------- |
| `15m`     | ~10 days                   |
| `1h`      | ~41 days                   |
| `4h`      | ~166 days (~5.5 months)    |
| `1d`      | ~2.7 years                 |

* The first `LOOKBACK` candles are used to compute zones.
* The rest is used to simulate trades and evaluate performance.
* If there aren’t enough candles, the month is skipped.

---

## 📌 Future Improvements

* [ ] Add more exchanges (KuCoin, OKX, etc.)
* [ ] Parallel execution using `ThreadPoolExecutor`
* [ ] Export charts with `vectorbt.plot()`
* [ ] Cache OHLCV data locally to reduce API calls
* [ ] Web interface for uploading and running strategies

---

## 📄 License

Distributed under the [MIT License](LICENSE).

---

Made with 💙 by [Your Name or GitHub](https://github.com/yourusername)
