import os
import glob
import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from tqdm import tqdm

from resources import TIMEFRAMES, START_YEAR, END_YEAR, LOOKBACK, CRYPTOS, OUTPUT_FOLDER
from strategy.peaks_and_valleys import backtest_strategy
from strategy.duplo_reteste import estrategia_duplo_reteste
from exchange import get_exchange

TIMEFRAME_TO_FREQ = {
    '15m': '15min',
    '30m': '30min',
    '1h': '1h',
    '4h': '4h',
    '1d': '1d'
}

def run_backtest(exchange, symbol, timeframe_str, start_date, strategy_func, lookback: int, limit=1000):
    since = int(start_date.timestamp() * 1000)
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe_str, since=since, limit=limit)
    except Exception as e:
        print(f"❌ Error in {symbol} {timeframe_str} {start_date.date()}: {e}")
        return None

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    close = df['close']

    if len(close) < lookback:
        return None

    freq = TIMEFRAME_TO_FREQ.get(timeframe_str, None)
    pf = strategy_func(close, lookback, freq=freq)
    stats = pf.stats()
    stats["Date"] = start_date.strftime("%Y-%m-%d")
    return stats

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
            for start_date in tqdm(dates, desc=f"{symbol} {tf}", unit="month"):
                stats = run_backtest(
                    exchange,
                    symbol.replace("USDT", "/USDT"),
                    tf,
                    start_date,
                    strategy_func=backtest_strategy,
                    lookback=LOOKBACK
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

if __name__ == "__main__":
    run_for_all()
