#macro connector.py
from yahooquery import Ticker


def fetch_macro_data(tickers_dict, period="1y", interval="1d"):
    symbols = list(tickers_dict.values())
    ticker_obj = Ticker(symbols)
    df = ticker_obj.history(period=period, interval=interval).reset_index()
    reverse_map = {v: k for k, v in tickers_dict.items()}
    df["asset"] = df["symbol"].map(reverse_map)
    return df

