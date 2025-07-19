import ccxt
from resources import EXCHANGE_NAME

def get_exchange():
    exchange_map = {
        "binance": ccxt.binance,
        "coinbase": ccxt.coinbase,
        "bybit": ccxt.bybit,
        "huobi": ccxt.huobi
    }

    exchange_name = EXCHANGE_NAME.lower()

    if exchange_name not in exchange_map:
        raise ValueError(f"Exchange '{EXCHANGE_NAME}' não é suportada. Escolha uma das: {list(exchange_map.keys())}")

    return exchange_map[exchange_name]()
