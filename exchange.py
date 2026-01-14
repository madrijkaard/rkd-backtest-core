# exchange.py

import ccxt
import yaml
import os

# =========================================================
# Load config.yaml
# =========================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

EXCHANGE_NAME = config["exchange"]["name"].lower()
MARKET_TYPE = config["exchange"].get("market", "spot").lower()

# =========================================================
# Função para instanciar a exchange correta
# =========================================================
def get_exchange():
    """
    Retorna uma instância CCXT de acordo com nome e tipo de mercado.
    """

    if EXCHANGE_NAME == "binance":
        # Spot
        if MARKET_TYPE == "spot":
            return ccxt.binance({
                "enableRateLimit": True
            })
        # USDT-margined Futures
        elif MARKET_TYPE == "futures":
            return ccxt.binanceusdm({
                "enableRateLimit": True
            })
        # Coin-margined Futures
        elif MARKET_TYPE == "coinm":
            return ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "delivery"}
            })
        else:
            raise ValueError(f"Tipo de mercado '{MARKET_TYPE}' não suportado para Binance.")

    # Outras exchanges
    exchange_map = {
        "bybit": ccxt.bybit,
        "huobi": ccxt.huobi,
        "coinbase": ccxt.coinbase,
    }

    if EXCHANGE_NAME not in exchange_map:
        raise ValueError(
            f"Exchange '{EXCHANGE_NAME}' não suportada. "
            f"Escolha uma das: {list(exchange_map.keys())}"
        )

    return exchange_map[EXCHANGE_NAME]({"enableRateLimit": True})
