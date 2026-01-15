# executor.py

import os
import sys
import yaml
import pandas as pd
import numpy as np
import vectorbt as vbt
from datetime import datetime, timezone
from pandas.api.types import is_datetime64tz_dtype
from exchange import get_exchange
from strategy.log_zones_activity import backtest_strategy

# =========================================================
# LOAD CONFIG
# =========================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

EXCHANGE_NAME = config["exchange"]["name"].lower()
MARKET_TYPE = config["exchange"].get("market", "spot").lower()
SYMBOLS = config["symbols"]
TIMEFRAMES = config["timeframes"]
LOOKBACK = config["strategy"]["lookback_candles"]
INITIAL_BALANCE = config["execution"].get("initial_balance", 1000)
FEE_PERCENTAGE = config["execution"].get("fee_percentage", 0.0)
SLIPPAGE = config["execution"].get("slippage", 0.0)

date_cfg = config["date_range"]
START_DATE = f"{date_cfg['start_year']}-{date_cfg['start_month']:02d}-01"
END_DATE = f"{date_cfg['end_year']}-{date_cfg['end_month']:02d}-28"

OUTPUT_FOLDER = config["output"]["folder"]
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "results_log_zones.xlsx")
OUTPUT_SIGNALS = os.path.join(OUTPUT_FOLDER, "signals_log_zones.xlsx")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =========================================================
# EXCHANGE
# =========================================================
exchange = get_exchange()

# =========================================================
# PROGRESS BAR
# =========================================================
def print_progress_bar(current, total, prefix="", length=30):
    """
    Prints a progress bar in the terminal.
    """
    if total <= 0:
        return
    percent = int((current / total) * 100)
    filled = int(length * current // total)
    bar = "█" * filled + "░" * (length - filled)
    sys.stdout.write(f"\r{prefix} [{bar}] {percent}%")
    sys.stdout.flush()
    if current == total:
        print()

# =========================================================
# FETCH OHLCV
# =========================================================
def fetch_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Fetch OHLCV data from the exchange using CCXT.
    Handles limits and date ranges.
    """
    symbol_ccxt = symbol.replace("/", "")

    since = int(
        datetime.fromisoformat(START_DATE)
        .replace(tzinfo=timezone.utc)
        .timestamp() * 1000
    )
    end_ts = int(
        datetime.fromisoformat(END_DATE)
        .replace(tzinfo=timezone.utc)
        .timestamp() * 1000
    )

    ohlcv = []
    while since < end_ts:
        try:
            batch = exchange.fetch_ohlcv(
                symbol=symbol_ccxt,
                timeframe=timeframe,
                since=since,
                limit=1000
            )
        except Exception as e:
            print(f"\nError fetching OHLCV: {exchange.name} {e}")
            break

        if not batch:
            break

        ohlcv.extend(batch)
        since = batch[-1][0] + 1

        # ✅ Remove print duplicado para não conflitar com progress bar
        # print(f"    Downloaded {len(ohlcv)} candles for {symbol_ccxt} {timeframe}", end="\r")

    if not ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df.loc[START_DATE:END_DATE]

# =========================================================
# REMOVE TIMEZONE
# =========================================================
def remove_timezone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove timezone from all datetime columns and index.
    """
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype):
            df[col] = df[col].dt.tz_convert(None)
    if isinstance(df.index.dtype, pd.DatetimeTZDtype):
        df.index = df.index.tz_convert(None)
    return df

# =========================================================
# RUN BACKTEST
# =========================================================
def run():
    all_stats = []
    all_signals = []

    for symbol in SYMBOLS:
        print(f"\n⚙️ Generating backtest for pair {symbol}")

        for timeframe in TIMEFRAMES:
            df = fetch_ohlcv(symbol, timeframe)
            if df.empty or len(df) < LOOKBACK + 50:
                print("    Insufficient data, skipping...")
                continue

            total_steps = len(df) - LOOKBACK
            for i in range(total_steps):
                print_progress_bar(i + 1, total_steps, prefix=f"{timeframe}")

            # =============================
            # EXECUTE STRATEGY
            # =============================
            entries_long, entries_short = backtest_strategy(df, lookback=LOOKBACK)

            # =============================
            # CREATE VECTORBT PORTFOLIO
            # =============================
            portfolio = vbt.Portfolio.from_signals(
                close=df["close"],
                entries=entries_long,
                exits=entries_short,
                init_cash=INITIAL_BALANCE,
                fees=FEE_PERCENTAGE,
                slippage=SLIPPAGE
            )

            # =============================
            # COLLECT COMPLETE STATISTICS
            # =============================
            stats = portfolio.stats()
            stats["symbol"] = symbol
            stats["timeframe"] = timeframe
            all_stats.append(stats)

            # =============================
            # SAVE SIGNALS PER CANDLE
            # =============================
            signals_df = pd.DataFrame({
                "timestamp": df.index,
                "open": df["open"],
                "close": df["close"],
                "high": df["high"],
                "low": df["low"],
                "volume": df["volume"],
                "entry_long": entries_long,
                "entry_short": entries_short
            })
            signals_df["symbol"] = symbol
            signals_df["timeframe"] = timeframe
            all_signals.append(signals_df)

            print(
                f"    Result | Total Return: {stats['Total Return [%]']:.2f}% | "
                f"Trades executed: {stats['Total Trades']}"
            )

    # =============================
    # EXPORT RESULTS
    # =============================
    if all_stats:
        stats_df = pd.DataFrame(all_stats)
        stats_df = remove_timezone(stats_df)
        stats_df.to_excel(OUTPUT_FILE, index=False)
        print(f"\nComplete statistics saved to: {OUTPUT_FILE}")

    if all_signals:
        signals_df = pd.concat(all_signals, ignore_index=True)
        signals_df = remove_timezone(signals_df)
        signals_df.to_excel(OUTPUT_SIGNALS, index=False)
        print(f"Candle-by-candle signals saved to: {OUTPUT_SIGNALS}")

# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("\nError during execution:")
        print(e)
        input("\nPress ENTER to exit...")
