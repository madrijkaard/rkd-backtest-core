import os
import yaml
import pandas as pd
import vectorbt as vbt

from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from exchange import get_exchange
from strategy.log_zones_activity import backtest_strategy


# =========================================================
# LOAD CONFIG
# =========================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

SYMBOLS = config["symbols"]
TIMEFRAMES = config["timeframes"]
LOOKBACK = config["strategy"]["lookback_candles"]

INITIAL_BALANCE = config["execution"].get("initial_balance", 1000.0)
FEE_PERCENTAGE = config["execution"].get("fee_percentage", 0.0)
SLIPPAGE = config["execution"].get("slippage", 0.0)

date_cfg = config["date_range"]

OUTPUT_FOLDER = config["output"]["folder"]
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# =========================================================
# EXCHANGE
# =========================================================
exchange = get_exchange()


# =========================================================
# HELPERS
# =========================================================
def timeframe_to_label(tf: str) -> str:
    if tf.endswith("m"):
        return tf.replace("m", "min")
    return tf


def build_output_filename(symbol: str, timeframe: str) -> str:
    symbol_clean = symbol.replace("/", "")
    tf_label = timeframe_to_label(timeframe)

    return (
        f"{symbol_clean}_"
        f"{date_cfg['start_month']}_{date_cfg['start_year']}_"
        f"{date_cfg['end_month']}_{date_cfg['end_year']}_"
        f"{tf_label}.xlsx"
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


# =========================================================
# FETCH OHLCV (TZ-NAIVE)
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
# RUN BACKTEST (MONTHLY)
# =========================================================
def run():
    for symbol in SYMBOLS:
        print(f"\n⚙️ Running monthly backtest for {symbol}")

        for timeframe in TIMEFRAMES:
            print(f"\n⏱ Timeframe: {timeframe}")

            output_file = os.path.join(
                OUTPUT_FOLDER,
                build_output_filename(symbol, timeframe)
            )

            all_monthly_stats = []
            all_monthly_signals = []
            all_monthly_trades = []

            df_full = fetch_ohlcv(symbol, timeframe)

            if df_full.empty or len(df_full) < LOOKBACK + 20:
                print(" ❌ Insufficient data, skipping timeframe.")
                continue

            month_ranges = generate_month_ranges(
                date_cfg["start_year"],
                date_cfg["start_month"],
                date_cfg["end_year"],
                date_cfg["end_month"]
            )

            for month_start, month_end in month_ranges:
                df_month = df_full.loc[month_start:month_end]

                if len(df_month) < LOOKBACK + 10:
                    continue

                # =============================
                # STRATEGY (LONG + SHORT)
                # =============================
                entries_long, exits_long, entries_short, exits_short = backtest_strategy(
                    df_month,
                    lookback=LOOKBACK
                )

                # =============================
                # PORTFOLIO (VECTORBT)
                # =============================
                portfolio = vbt.Portfolio.from_signals(
                    close=df_month["close"],
                    entries=entries_long,
                    exits=exits_long,
                    short_entries=entries_short,
                    short_exits=exits_short,
                    init_cash=INITIAL_BALANCE,
                    fees=FEE_PERCENTAGE,
                    slippage=SLIPPAGE,
                    freq=timeframe
                )

                # =============================
                # STATS (MONTHLY)
                # =============================
                stats = portfolio.stats()
                stats["symbol"] = symbol
                stats["timeframe"] = timeframe
                stats["month"] = month_start.month
                stats["year"] = month_start.year

                all_monthly_stats.append(stats)

                # =============================
                # SIGNALS (CANDLE LEVEL)
                # =============================
                signals_df = pd.DataFrame({
                    "timestamp": df_month.index,
                    "open": df_month["open"],
                    "high": df_month["high"],
                    "low": df_month["low"],
                    "close": df_month["close"],
                    "volume": df_month["volume"],
                    "entry_long": entries_long,
                    "exit_long": exits_long,
                    "entry_short": entries_short,
                    "exit_short": exits_short,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "month": month_start.month,
                    "year": month_start.year
                })

                all_monthly_signals.append(signals_df)

                # =============================
                # TRADES (PER-TRADE)
                # =============================
                trades_df = portfolio.trades.records_readable.copy()

                if not trades_df.empty:
                    trades_df["symbol"] = symbol
                    trades_df["timeframe"] = timeframe
                    trades_df["month"] = month_start.month
                    trades_df["year"] = month_start.year

                    all_monthly_trades.append(trades_df)

                print(
                    f" {month_start.strftime('%Y-%m')} | "
                    f"Return: {stats['Total Return [%]']:.2f}% | "
                    f"Trades: {stats['Total Trades']}"
                )

            # =============================
            # EXPORT RESULTS
            # =============================
            if all_monthly_stats:
                stats_df = pd.DataFrame(all_monthly_stats)
                stats_df.to_excel(output_file, index=False)
                print(f"\n📁 Monthly stats saved to: {output_file}")

            if all_monthly_signals:
                signals_df = pd.concat(all_monthly_signals, ignore_index=True)
                signals_file = output_file.replace(".xlsx", "_signals.xlsx")
                signals_df.to_excel(signals_file, index=False)
                print(f"📁 Monthly signals saved to: {signals_file}")

            if all_monthly_trades:
                trades_df = pd.concat(all_monthly_trades, ignore_index=True)
                trades_file = output_file.replace(".xlsx", "_trades.xlsx")
                trades_df.to_excel(trades_file, index=False)
                print(f"📁 Monthly trades saved to: {trades_file}")


# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("\n❌ Error during execution:")
        print(e)
        input("\nPress ENTER to exit...")
