# executor.py

import os
import yaml
import shutil
import pandas as pd
import vectorbt as vbt
from tqdm import tqdm

from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from exchange import get_exchange
from strategy.accumulation_zone.accumulation_zone import (
    log_zones_activity_strategy
)

# =========================================================
# LOAD GLOBAL CONFIG
# =========================================================

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

SYMBOLS = config["symbols"]
TIMEFRAMES = config["timeframes"]
INITIAL_BALANCE = config["execution"].get("initial_balance", 1000.0)

date_cfg = config["date_range"]
OUTPUT_FOLDER = config["output"]["folder"]

# =========================================================
# LOAD STRATEGY CONFIG
# =========================================================

STRATEGY_CONFIG_PATH = os.path.join(
    BASE_DIR,
    "strategy",
    "accumulation_zone",
    "config.yaml"
)

with open(STRATEGY_CONFIG_PATH, "r", encoding="utf-8") as f:
    strategy_cfg = yaml.safe_load(f)["strategy"]

MAX_LOSS_PERCENT = strategy_cfg.get("max_loss_percent", None)
MIN_PERCENT_FROM_EXTREME = strategy_cfg["activity"]["min_percent_from_extreme"]

# =========================================================
# EXCHANGE
# =========================================================

exchange = get_exchange()

# =========================================================
# HELPERS
# =========================================================

def build_base_filename(symbol: str) -> str:
    symbol_clean = symbol.replace("/", "")
    return (
        f"{symbol_clean}_"
        f"{date_cfg['start_month']}_{date_cfg['start_year']}_"
        f"{date_cfg['end_month']}_{date_cfg['end_year']}"
    )


def generate_month_ranges(start_year, start_month, end_year, end_month):
    ranges = []
    current = date(start_year, start_month, 1)
    end = date(end_year, end_month, 1)

    while current <= end:
        month_start = pd.Timestamp(current)
        month_end = month_start + pd.offsets.MonthEnd(1)
        ranges.append((month_start, month_end))
        current += relativedelta(months=1)

    return ranges


def clean_output_folder(path: str):
    if path in ("", ".", "/", ".."):
        raise ValueError(f"Unsafe OUTPUT_FOLDER path: '{path}'")

    if os.path.exists(path):
        for name in os.listdir(path):
            file_path = os.path.join(path, name)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
    else:
        os.makedirs(path, exist_ok=True)

# =========================================================
# FETCH OHLCV
# =========================================================

def fetch_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    start_date = datetime(
        date_cfg["start_year"],
        date_cfg["start_month"],
        1,
        tzinfo=timezone.utc
    )
    end_date = datetime(
        date_cfg["end_year"],
        date_cfg["end_month"],
        28,
        tzinfo=timezone.utc
    )

    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    ohlcv = []

    with tqdm(
        desc=f"Downloading candlesticks {symbol} {timeframe}",
        unit="batch"
    ) as pbar:
        while since < end_ts:
            batch = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=1000
            )
            if not batch:
                break
            ohlcv.extend(batch)
            since = batch[-1][0] + 1
            pbar.update(1)

    if not ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.index = df.index.tz_convert(None)

    return df

# =========================================================
# RUN BACKTEST
# =========================================================

def run():
    print(f"\n🧹 Cleaning output folder: {OUTPUT_FOLDER}")
    clean_output_folder(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    generated_files: list[str] = []

    for symbol in SYMBOLS:
        print(f"\n⚙️  Running backtest for {symbol}")

        base_name = build_base_filename(symbol)

        for timeframe in TIMEFRAMES:
            print(f"\n⏱  Timeframe: {timeframe}")

            stats_file = os.path.join(
                OUTPUT_FOLDER,
                f"{base_name}_{timeframe}_strategy.xlsx"
            )

            trades_file = os.path.join(
                OUTPUT_FOLDER,
                f"{base_name}_{timeframe}_trades.xlsx"
            )

            all_monthly_stats = []
            all_trades = []

            df_full = fetch_ohlcv(symbol, timeframe)
            if df_full.empty:
                continue

            month_ranges = generate_month_ranges(
                date_cfg["start_year"],
                date_cfg["start_month"],
                date_cfg["end_year"],
                date_cfg["end_month"]
            )

            for month_start, month_end in tqdm(month_ranges, unit="month"):
                df = df_full.loc[month_start:month_end]
                if df.empty:
                    continue

                entries_l, exits_l, entries_s, exits_s = (
                    log_zones_activity_strategy(
                        open_=df["open"].values,
                        high=df["high"].values,
                        low=df["low"].values,
                        close=df["close"].values,
                        max_loss_percent=MAX_LOSS_PERCENT,
                        min_percent_from_extreme=MIN_PERCENT_FROM_EXTREME
                    )
                )

                portfolio = vbt.Portfolio.from_signals(
                    close=df["close"],
                    entries=entries_l,
                    exits=exits_l,
                    short_entries=entries_s,
                    short_exits=exits_s,
                    init_cash=INITIAL_BALANCE,
                    freq=timeframe
                )

                stats = portfolio.stats()
                stats["symbol"] = symbol
                stats["timeframe"] = timeframe
                stats["year"] = month_start.year
                stats["month"] = month_start.month
                all_monthly_stats.append(stats)

                records = portfolio.trades.records
                if records is not None and not records.empty:
                    trades = records.copy()
                    trades["symbol"] = symbol
                    trades["timeframe"] = timeframe
                    trades["year"] = month_start.year
                    trades["month"] = month_start.month
                    all_trades.append(trades)

            if all_monthly_stats:
                pd.DataFrame(all_monthly_stats).to_excel(
                    stats_file,
                    index=False
                )
                generated_files.append(stats_file)

            if all_trades:
                pd.concat(all_trades).to_excel(
                    trades_file,
                    index=False
                )
                generated_files.append(trades_file)

    # =====================================================
    # FINAL REPORT
    # =====================================================

    if generated_files:
        print("\n✅ Backtest finished successfully!")
        print("📁 Files generated:")
        for path in generated_files:
            print(f"  - {os.path.normpath(path)}")
    else:
        print("\n⚠️  Backtest finished, but no files were generated.")

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    run()
