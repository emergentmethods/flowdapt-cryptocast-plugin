import ccxt
import pandas as pd
from typing import Dict, Any

from flowdapt.lib.logger import get_logger

logger = get_logger(__name__)


# ccxt api utilities
def download_data(
    symbol: str,
        exchange: str,
        interval: str,
        n_bars: int
) -> pd.DataFrame:
    """
    force pull data from ccxt
    """
    metadata = {"exchange": exchange, "symbol": symbol, "interval": interval}
    cxt = instantiate_exchange(metadata)
    df = get_historical_data(cxt, metadata, n_bars)
    return df


def instantiate_exchange(api_dict: Dict[str, Any]) -> Any:
    exch_str = api_dict["exchange"]
    # FIXME: hardcoding ccxt ratelimits for now.
    return getattr(ccxt, exch_str)(
        {"enableRateLimit": True,
         "rateLimit": 1000}
    )


def get_historical_data(exchange: Any,
                        api_dict: Dict[str, Any],
                        n_bars: int
                        ) -> pd.DataFrame:
    """
    Paginate on ccxt api end points to get the desired n_bars
    of candles.
    :param exchange: an instantiated ccxt exchange object
    :param api_dict: metadata passed to ccxt to determine which
    datasources to download
    :param n_bars: number of bars desired.
    :return:
    DataFrame containing the desired number of bars
    """
    symbol = api_dict["symbol"]
    interval = api_dict["interval"]
    tf_ms = ccxt.Exchange.parse_timeframe(interval) * 1000
    since = exchange.milliseconds() - tf_ms * n_bars

    all_ohlcv = []
    while since < exchange.milliseconds():
        logger.info(f"Paginating {symbol} on {since}.")
        limit = 100  # change for your limit
        ohlcv = exchange.fetch_ohlcv(symbol, interval, since, limit)
        if len(ohlcv):
            since = ohlcv[len(ohlcv) - 1][0] + 1
            all_ohlcv += ohlcv
        else:
            break

    columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    df = pd.DataFrame(all_ohlcv, columns=columns)
    df['date'] = pd.to_datetime(df['date'], unit="ms")

    return df
