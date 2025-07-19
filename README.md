# 🧠 Crypto Backtester with Modular Strategies

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![VectorBT](https://img.shields.io/badge/VectorBT-Powered-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

> Backtesting system for cryptocurrencies using **logarithmic highs and lows**, with pluggable modular strategy support. Results are automatically exported to Excel spreadsheets. 🚀

---

## 📁 Project Structure

```
.
├── executor.py              # Main script to run the backtests
├── resources.py             # Global configuration file
├── exchanges.py             # Exchange selector using ccxt
├── strategies/              # Directory for all strategies
│   └── strategy_max_min.py  # Logarithmic high/low zone strategy
└── backtest/                # (generated) Excel files with results
```

---

## ⚙️ Technologies Used

- [Python 3.10+](https://www.python.org/)
- [CCXT](https://github.com/ccxt/ccxt) – for historical market data
- [VectorBT](https://vectorbt.dev/) – backtesting and performance metrics
- [Pandas + NumPy](https://pandas.pydata.org/)
- [OpenPyXL](https://openpyxl.readthedocs.io/) – Excel export
- [TQDM](https://tqdm.github.io/) – visual progress bar

---

## 🔁 Supported Exchanges

You can choose from the following exchanges, defined in `resources.py`:

```python
EXCHANGE_NAME = "binance"  # Options: binance, coinbase, bybit, huobi
```

This is handled internally via the `get_exchange()` function in [`exchanges.py`](./exchanges.py), which returns a `ccxt` client instance accordingly.

---

## 🧪 Execution

### ▶️ Install dependencies

```bash
pip install ccxt pandas numpy vectorbt openpyxl tqdm
```

### ▶️ Run the backtest

```bash
python executor.py
```

> Excel files will be saved to the `backtest/` folder (or as configured in `resources.py`).

---

## ⚙️ Configuration (`resources.py`)

You can customize the behavior of the backtest here:

```python
TIMEFRAMES = ['15m', '1h', '4h']          # Timeframes to test
START_YEAR = 2020                         # Start of backtest period
END_YEAR = 2024                           # End of backtest period
LOOKBACK = 200                            # Window for rolling min/max zones
CANDLE_LIMIT = 1000                       # Number of candles fetched per test
CRYPTOS = ["ETHUSDT", "AVAXUSDT", "ADAUSDT"]
OUTPUT_FOLDER = "backtest"
EXCHANGE_NAME = "binance"
```

---

## 🕰️ How Timeframes & Candle Count Work

Each backtest pulls `CANDLE_LIMIT` candles for a given month/start date and timeframe.

Here’s what `CANDLE_LIMIT = 1000` means in terms of historical data:

| Timeframe | Duration Covered       |
|-----------|------------------------|
| `15m`     | ~10.4 days of data     |
| `30m`     | ~20.8 days of data     |
| `1h`      | ~41.6 days of data     |
| `4h`      | ~166.6 days (~5.5 mo)  |
| `1d`      | ~1000 days (~2.7 years)|

From these 1000 candles:
- The first `LOOKBACK` candles (e.g. 200) are used to calculate dynamic price zones.
- The remaining candles are used to simulate entries/exits and compute portfolio stats.
- If the timeframe doesn’t provide enough candles, that test is skipped.

You can adjust `CANDLE_LIMIT` to increase or reduce the analysis window as needed.

---

## 📈 Adding New Strategies

1. Create a new file in `strategies/`, e.g. `strategy_crossover.py`
2. Define a function matching this format:

```python
def my_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    ...
```

3. Import and use it in `executor.py`:

```python
from strategies.strategy_crossover import my_strategy

# Replace estrategia_func=estrategia_max_min with:
estrategia_func=my_strategy
```

---

## 📸 Output Example

<p align="center">
  <img src="https://user-images.githubusercontent.com/placeholder/backtest_example.png" width="600" alt="Excel output preview">
</p>

Each Excel file will have one tab per timeframe tested (e.g., 15m, 1h, 4h) for a specific symbol.

---

## 📌 To-do

- [ ] Add more exchanges (KuCoin, OKX, etc.)
- [ ] Generate charts automatically with `vectorbt.plot()`
- [ ] Use `ThreadPoolExecutor` to parallelize execution
- [ ] Add web interface for uploading/running strategies
- [ ] Persist OHLCV cache locally to reduce API calls

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

Made with 💙 by [Your Name or GitHub](https://github.com/yourusername)