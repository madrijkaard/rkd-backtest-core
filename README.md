# 🧠 Crypto Backtester – Modular Strategies with Logarithmic Zones

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![VectorBT](https://img.shields.io/badge/VectorBT-Powered-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

Backtesting system for cryptocurrencies focused on strategies using **logarithmic price zones**. Supports multiple exchanges via CCXT, multiple timeframes, and automatic export of results to Excel spreadsheets.

---

## ⚙️ Technologies Used

- **[Python 3.10+](https://www.python.org/)**  
- **[CCXT](https://github.com/ccxt/ccxt)** – For historical data from exchanges  
- **[VectorBT](https://vectorbt.dev/)** – Backtesting, performance metrics, and portfolio simulation  
- **[Pandas](https://pandas.pydata.org/)** + **[NumPy](https://numpy.org/)**  
- **[OpenPyXL](https://openpyxl.readthedocs.io/)** – Excel spreadsheet generation  
- **[TQDM](https://tqdm.github.io/)** – Terminal progress bar  

---

## 📁 Project Structure

```
.
├── config.yaml                  # Configuration file with backtest parameters
├── exchange.py                 # Selects exchange via CCXT
├── executor.py                 # Main script to run the backtest
├── strategy/
│   ├── strategy.py             # Abstract base strategy and trade structure
│   └── peaks_and_valleys.py    # Logarithmic zone strategy
├── requirements.txt            # Project dependencies
├── venv.sh                     # Script to activate virtual environment and run the project
└── backtest/                   # (generated) Folder with Excel result files
```

### File Descriptions

- **`config.yaml`**: Defines cryptos, timeframes, lookback window, exchange, and other settings.  
- **`exchange.py`**: Loads the chosen exchange and instantiates a `ccxt` client.  
- **`executor.py`**: Controls the entire execution flow. Iterates dates, applies strategy, exports results.  
- **`strategy/peaks_and_valleys.py`**: Main strategy using logarithmic zones.  
- **`venv.sh`**: Automates environment activation, dependency installation, and execution.  

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
exchange_name: binance
output_folder: backtest
start_year: 2021
end_year: 2024
lookback: 200
candle_limit: 1000
timeframes: ["15m", "1h"]
cryptos: ["ETHUSDT", "AVAXUSDT"]
```

### 3. Run the `venv.sh` Script

Use the command below to activate the virtual environment and automatically execute the project:

```bash
source venv.sh
```

> 💡 **Important:** The script must be executed with `source` to work correctly.

---

## 📄 Output Example

After execution, `.xlsx` files will be saved in `backtest/`, containing:

- One tab per timeframe tested (e.g., `15m`, `1h`, etc.)
- One row per analyzed month
- Metrics calculated by `VectorBT`

---

## 💡 Strategy: Peaks and Valleys

The `PeaksAndValleys` strategy uses price zones calculated via logarithmic transformations of the **rolling min and max** over a window (`lookback`). It includes rules such as:

- LONG entry after 3 alternating `line_1 → line_4` cycles  
- SHORT entry after 3 `line_8 → line_6` sequences  
- Stop loss and take profit exits  
- Logic reset each month  
- Ignore month after 2 consecutive wins or losses  

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

## 🧪 Understanding CANDLE_LIMIT

Each month, the script fetches `CANDLE_LIMIT` candles for the given timeframe:

| Timeframe | Coverage with 1000 candles |
|-----------|-----------------------------|
| `15m`     | ~10 days                    |
| `1h`      | ~41 days                    |
| `4h`      | ~166 days (~5.5 months)     |
| `1d`      | ~2.7 years                  |

- The first `LOOKBACK` candles are used to compute zones.
- The rest is used to simulate trades and evaluate performance.
- If there aren’t enough candles, the month is skipped.

---

## 📌 Future Improvements

- [ ] Add more exchanges (KuCoin, OKX, etc.)
- [ ] Parallel execution using `ThreadPoolExecutor`
- [ ] Export charts with `vectorbt.plot()`
- [ ] Cache OHLCV data locally to reduce API calls
- [ ] Web interface for uploading and running strategies

---

## 📄 License

Distributed under the [MIT License](LICENSE).

---

Made with 💙 by [Your Name or GitHub](https://github.com/yourusername)