# executor.py

import os
import glob
import datetime
import yaml
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from tqdm import tqdm

from strategy.peaks_and_valleys import backtest_strategy
from exchange import get_exchange

# 📥 Load YAML configuration with UTF-8 encoding
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TIMEFRAMES = config["timeframes"]
START_YEAR = config["start_year"]
END_YEAR = config["end_year"]
LOOKBACK = config["lookback"]
CANDLE_LIMIT = config["candle_limit"]
CRYPTOS = config["cryptos"]
OUTPUT_FOLDER = config["output_folder"]

# 🕒 Map ccxt timeframes to Pandas frequency strings
TIMEFRAME_TO_FREQ = {
    '15m': '15min',
    '30m': '30min',
    '1h': '1h'
}

# 📊 Ideal number of candles per month for each timeframe
TIMEFRAME_CANDLES_PER_MONTH = {
    '15m': 1000,   # ~2880 candles/month, limited to 1000
    '30m': 1000,   # ~1440 candles/month, limited to 1000
    '1h': 720,     # 24h x 30 days
}

# 🔁 Generic backtest execution function
def run_backtest(exchange, symbol, timeframe_str, start_date, strategy_func, lookback: int, limit=1000):
    since = int(start_date.timestamp() * 1000)
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe_str, since=since, limit=limit)
    except Exception as e:
        print(f"❌ Error fetching data for {symbol} {timeframe_str} {start_date.date()}: {e}")
        return None

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    close = df['close']

    if len(close) < lookback:
        return None

    freq = TIMEFRAME_TO_FREQ.get(timeframe_str, None)
    try:
        pf = strategy_func(close, lookback, freq=freq)
        stats = pf.stats()
        stats["Date"] = start_date.strftime("%Y-%m-%d")
        return stats
    except Exception as e:
        print(f"❌ Error running backtest for {symbol} {timeframe_str} {start_date.date()}: {e}")
        return None

# ▶️ Run backtests for all cryptos and timeframes
def run_for_all():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Clean output folder
    for f in glob.glob(os.path.join(OUTPUT_FOLDER, "*")):
        os.remove(f)
    print(f"\n🧹 Folder '{OUTPUT_FOLDER}' cleaned successfully.")

    exchange = get_exchange()
    dates = [datetime.datetime(year, month, 1)
             for year in range(START_YEAR, END_YEAR + 1)
             for month in range(1, 13)]

    for symbol in CRYPTOS:
        print(f"\n🔍 Processing {symbol}...")
        wb = Workbook()
        wb.remove(wb.active)

        for tf in TIMEFRAMES:
            results = []
            limit_for_tf = TIMEFRAME_CANDLES_PER_MONTH.get(tf, CANDLE_LIMIT)

            for start_date in tqdm(dates, desc=f"{symbol} {tf}", unit="month"):
                stats = run_backtest(
                    exchange,
                    symbol.replace("USDT", "/USDT"),
                    tf,
                    start_date,
                    strategy_func=backtest_strategy,
                    lookback=LOOKBACK,
                    limit=limit_for_tf
                )
                if stats is not None:
                    results.append(stats)

            if not results:
                print(f"\n⚠ Not enough data for {symbol} {tf}")
                continue

            df = pd.DataFrame(results)
            df.reset_index(inplace=True)
            ws = wb.create_sheet(title=tf)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

        file_path = os.path.join(OUTPUT_FOLDER, f"{symbol}.xlsx")
        wb.save(file_path)
        print(f"\n✅ File saved: {file_path}")


# 🚀 Main execution
if __name__ == "__main__":
    try:
        run_for_all()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    input("\n✅ Execution finished. Press Enter to exit...")
