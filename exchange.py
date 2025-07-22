import ccxt
import yaml
import os

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

EXCHANGE_NAME = config["exchange_name"].lower()

def get_exchange():
    exchange_map = {
        "binance": ccxt.binance,
        "coinbase": ccxt.coinbase,
        "bybit": ccxt.bybit,
        "huobi": ccxt.huobi
    }

    if EXCHANGE_NAME not in exchange_map:
        raise ValueError(f"Exchange '{EXCHANGE_NAME}' não é suportada. Escolha uma das: {list(exchange_map.keys())}")

    return exchange_map[EXCHANGE_NAME]()
