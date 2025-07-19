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
├── strategies/              # Directory for all strategies
│   └── strategy_max_min.py  # Logarithmic high/low zone strategy
└── backtest/                # (generated) Excel files with results
```

---

## ⚙️ Technologies Used

- [Python 3.10+](https://www.python.org/)
- [CCXT](https://github.com/ccxt/ccxt) – for historical data from Binance
- [VectorBT](https://vectorbt.dev/) – for backtesting and financial analysis
- [Pandas + NumPy](https://pandas.pydata.org/)
- [OpenPyXL](https://openpyxl.readthedocs.io/en/stable/) – for Excel output
- [TQDM](https://tqdm.github.io/) – progress bars

---

## 🧪 Execution

### ▶️ Requirements

Install all dependencies with:

```bash
pip install ccxt pandas numpy vectorbt openpyxl tqdm
```

### ▶️ Run the backtest

```bash
python executor.py
```

> Excel files will be saved to the `backtest/` folder, as defined in `resources.py`.

---

## 🧰 Configuration (`resources.py`)

You can customize the following parameters:

```python
TIMEFRAMES = ['15m', '1h', '4h']
START_YEAR = 2020
END_YEAR = 2024
LOOKBACK = 200
CRYPTOS = ["ETHUSDT", "AVAXUSDT", "ADAUSDT"]
OUTPUT_FOLDER = "backtest"
```

---

## 📈 Adding New Strategies

1. Create a new file in `strategies/`, e.g. `strategy_crossover.py`
2. Define a function matching the following format:

```python
def my_strategy(close: pd.Series, lookback: int) -> vbt.Portfolio:
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

---

## 📌 To-do

- [ ] Add support for more exchanges (Coinbase, Kucoin...)
- [ ] Auto-plot results using `vectorbt.plot()`
- [ ] Parallelize execution using `ThreadPoolExecutor`
- [ ] Web interface for uploading strategies

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

Made with 💙 by [Your Name or GitHub](https://github.com/yourusername)
